"""Optional Groq commentary; prediction and evidence are computed on the server."""

import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .features import add_features

CHECKS = {
    "repayment": "Đối chiếu trạng thái trả nợ, số tháng trễ và nguyên nhân chậm thanh toán.",
    "balances": "Xác minh hạn mức, dư nợ sao kê và mức sử dụng hạn mức trên chứng từ.",
    "payments": "Đối chiếu số tiền thanh toán với dư nợ của các kỳ tương ứng.",
    "imputed": "Xác minh các giá trị được điền từ thống kê train trước khi sử dụng kết quả.",
}
SYSTEM = """Bạn diễn giải bằng tiếng Việt cho chuyên viên kiểm tra hồ sơ tín dụng.
Chỉ dùng evidence và prediction được cung cấp. SHAP là đóng góp trước hiệu chỉnh,
không phải phần trăm PD, không chứng minh nguyên nhân hay tác dụng của thay đổi đầu vào.
Không suy luận từ tuổi, giới tính, học vấn, hôn nhân. Không bịa số liệu, chính sách,
thu nhập, khả năng trả nợ. Không đề xuất phê duyệt, từ chối, giảm/tăng hạn mức,
lãi suất hay tài sản bảo đảm. Chỉ gợi ý bước xác minh bằng các mã allowed_checks.
Trả JSON: {"insights":[{"text":"nhận xét ngắn, phân biệt tăng/giảm điểm",
"features":["mã đặc trưng trong evidence"]}],"checks":["mã trong allowed_checks"]}.
Tối đa 4 insights và 4 checks; mỗi insight phải dẫn đúng đặc trưng được cung cấp.
"""


def generate_insights(frame, explanation, prediction, model_name, has_imputed):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return {"status": "unavailable", "message": "Chưa cấu hình Groq. Quản trị viên cần thêm GROQ_API_KEY trên máy chủ."}
    model = os.environ.get("GROQ_MODEL", "").strip() or "openai/gpt-oss-20b"
    values = add_features(frame.rename(columns={"PAY_0": "PAY_1"})).iloc[0]
    evidence = []
    for row in explanation.sort_values("contribution", key=lambda s: s.abs(), ascending=False).to_dict("records"):
        feature = row["feature"].split("__")[-1]
        if feature in values and feature not in {"ID", "SEX", "EDUCATION", "MARRIAGE", "AGE"}:
            evidence.append({"feature": feature, "value": float(values[feature]), "contribution": float(row["contribution"])})
        if len(evidence) == 12:
            break
    allowed = {name: text for name, text in CHECKS.items() if name != "imputed" or has_imputed}
    data = {"prediction": prediction, "prediction_model": model_name, "evidence": evidence,
            "has_imputed_data": has_imputed, "allowed_checks": allowed}
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
            "response_format": {"type": "json_object"}, "temperature": .2, "max_completion_tokens": 1800}
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    request = Request("https://api.groq.com/openai/v1/chat/completions", data=json.dumps(body).encode(),
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Oversized response")
        content = json.loads(raw)["choices"][0]["message"]["content"]
        output = json.loads(content)
        insights, checks = output["insights"], output["checks"]
        known = {item["feature"] for item in evidence}
        if not isinstance(insights, list) or not 1 <= len(insights) <= 4:
            raise ValueError("Invalid insights")
        for insight in insights:
            if (not isinstance(insight, dict) or not isinstance(insight.get("text"), str)
                    or not 1 <= len(insight["text"].strip()) <= 600
                    or not isinstance(insight.get("features"), list) or not insight["features"]
                    or any(not isinstance(f, str) or f not in known for f in insight["features"])):
                raise ValueError("Invalid evidence references")
        if not isinstance(checks, list) or len(checks) > 4 or any(not isinstance(c, str) or c not in allowed for c in checks):
            raise ValueError("Invalid checks")
        return {"status": "ok", "provider": "Groq", "model": model, "insights": insights,
                "checks": [{"code": code, "text": allowed[code]} for code in dict.fromkeys(checks)], "evidence": evidence}
    except HTTPError as error:
        provider_code = "unknown"
        try:
            candidate = json.loads(error.read(16384)).get("error", {}).get("code")
            if candidate in {"invalid_api_key", "model_not_found", "model_decommissioned", "model_permission_blocked", "json_validate_failed", "rate_limit_exceeded"}:
                provider_code = candidate
        except (ValueError, TypeError, AttributeError, OSError):
            pass
        logging.warning("Groq request failed: http_status=%s provider_code=%s", error.code, provider_code)
        reasons = {
            400: "Groq từ chối định dạng hoặc tham số yêu cầu; cần kiểm tra cấu hình model.",
            401: "Groq không xác thực được API key. Kiểm tra key trong môi trường Production và triển khai lại.",
            403: "Groq từ chối quyền truy cập. Kiểm tra Model Permissions của tổ chức và project trên Groq.",
            404: "Groq không tìm thấy model. Kiểm tra GROQ_MODEL trong Vercel.",
            429: "Groq đã hết hạn mức tạm thời. Hãy thử lại sau.",
        }
        message = reasons.get(error.code, "Dịch vụ Groq đang lỗi. Hãy thử lại sau.")
        return {"status": "unavailable", "code": f"groq_http_{error.code}",
                "message": f"{message} (HTTP {error.code}; {provider_code})"}
    except (URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError):
        message = "Chưa nhận được insight AI hợp lệ. Kết quả dự báo và SHAP vẫn sử dụng được."
    return {"status": "unavailable", "message": message}
