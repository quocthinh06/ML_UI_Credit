from dataclasses import asdict
from pathlib import Path
import os
import tempfile
import getpass

import pandas as pd
from sqlalchemy import func, insert, select

from .database import datasets, versions, records, runs, predictions
from .validation import FEATURES, TARGET, ValidationError, customer_ids, validate_frame, prepare_input


def run_parameters(thresholds):
    return {**asdict(thresholds), "performed_by": getpass.getuser()}


def read_file(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        # Inspect the raw header: pandas otherwise silently renames duplicate columns.
        import csv

        with path.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        stripped = [c.strip() for c in header]
        if len(stripped) != len(set(stripped)):
            raise ValidationError("Tệp chứa tên cột bị trùng.")
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype={"ID": str})
    elif path.suffix.lower() == ".xlsx":
        header = pd.read_excel(path, header=None, nrows=1).iloc[0].map(str).str.strip()
        if header.duplicated().any():
            raise ValidationError("Tệp chứa tên cột bị trùng.")
        frame = pd.read_excel(path, dtype={"ID": str})
    elif path.suffix.lower() == ".json":
        frame = pd.read_json(path, orient="records", dtype={"ID": str})
    else:
        raise ValidationError("Chỉ hỗ trợ CSV UTF-8, Excel .xlsx hoặc JSON (danh sách hồ sơ).")
    frame.columns = [str(c).strip() for c in frame.columns]
    return prepare_input(frame)


def export_filename(model_name):
    suffix = {"Random Forest": "RF", "Logistic Regression": "LR", "XGBoost": "XGb"}.get(model_name)
    return f"ket_qua_{suffix}.xlsx" if suffix else "ket_qua.xlsx"


def export_frame(frame, path, *, model=None, thresholds=None):
    """Write beside destination and replace only after the entire export succeeds."""
    path = Path(path)
    if path.suffix.lower() not in (".csv", ".xlsx"):
        raise ValidationError("Tên tệp xuất cần đuôi .csv hoặc .xlsx.")
    if path.suffix.lower() == ".xlsx" and model is not None:
        # Recompute only raw inputs; existing results must match the selected model.
        if "probability" in frame:
            if "model_sha256" not in frame or not frame.model_sha256.eq(model.digest).all():
                raise ValidationError("Kết quả không thuộc model đang chọn. Vui lòng chạy dự báo lại.")
        else:
            from .validation import Thresholds

            thresholds = thresholds or Thresholds()
            frame = frame.reset_index(drop=True).copy()
            output = model.predict(frame, thresholds)
            frame = pd.concat([frame, output.reset_index(drop=True)], axis=1)
            for key, value in {
                "model_name": model.name, "model_version": model.version,
                "model_sha256": model.digest, "decision_threshold": thresholds.decision,
                "decision_basis": thresholds.basis, "risk_low_threshold": thresholds.low,
                "risk_high_threshold": thresholds.high,
            }.items():
                frame[key] = value
    safe = frame.copy()
    # Spreadsheet formula injection: imported identifiers and dataset names are untrusted.
    for col in safe.select_dtypes(include=["object", "string"]).columns:
        safe[col] = safe[col].map(
            lambda x: "'" + x if isinstance(x, str) and x.lstrip().startswith(("=", "+", "-", "@")) else x
        )
    fd, name = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
    os.close(fd)
    try:
        if path.suffix.lower() == ".csv":
            safe.to_csv(name, index=False, encoding="utf-8-sig")
        else:
            from .excel_report import write_report

            write_report(safe, name)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class CreditService:
    def __init__(self, engine):
        self.engine = engine

    def list_datasets(self):
        with self.engine.connect() as conn:
            frame = pd.read_sql(
                select(
                    datasets.c.id,
                    datasets.c.name,
                    datasets.c.created_at,
                    func.max(versions.c.revision).label("revision"),
                    func.max(versions.c.id).label("version_id"),
                )
                .join(versions)
                .group_by(datasets.c.id, datasets.c.name, datasets.c.created_at)
                .order_by(datasets.c.id.desc()),
                conn,
            )
            counts = dict(
                conn.execute(select(records.c.version_id, func.count()).group_by(records.c.version_id)).all()
            )
            processed = set(conn.execute(select(runs.c.version_id).distinct()).scalars())
            updated = dict(conn.execute(select(versions.c.id, versions.c.created_at)).all())
        frame["record_count"] = frame.version_id.map(counts).fillna(0).astype(int)
        frame["processing_status"] = frame.version_id.map(
            lambda vid: "Đã có lượt dự báo" if vid in processed else "Chưa dự báo phiên bản này"
        )
        frame["updated_at_utc"] = frame.version_id.map(updated)
        return frame

    def save_single(
        self, frame, output, model, thresholds, *, dataset_id=None, replace=False, expected_version=None
    ):
        values = validate_frame(frame)
        ids = customer_ids(frame)
        if len(values) != 1 or len(output) != 1:
            raise ValidationError("Lưu đơn lẻ cần đúng một hồ sơ.")
        with self.engine.begin() as conn:
            if dataset_id is None:
                did = conn.execute(
                    insert(datasets).values(name=f"Hồ sơ {ids[0]}"[:255])
                ).inserted_primary_key[0]
                vid = self._write_version(conn, did, 1, values, ids)
            else:
                vid = self._revise(conn, dataset_id, ids[0], values, replace, expected_version)
            rid = conn.execute(
                select(records.c.id).where(records.c.version_id == vid, records.c.customer_id == ids[0])
            ).scalar_one()
            run_id = conn.execute(
                insert(runs).values(
                    version_id=vid,
                    model_name=model.name,
                    model_version=model.version,
                    model_hash=model.digest,
                    thresholds=run_parameters(thresholds),
                )
            ).inserted_primary_key[0]
            result = output[["raw_score", "probability", "default_label", "risk_level"]].iloc[0].to_dict()
            conn.execute(insert(predictions).values(run_id=run_id, record_id=rid, **result))
        return run_id

    def import_dataset(self, name, frame):
        prepared = prepare_input(frame)
        values = prepared.drop(columns=["ID"])
        ids = customer_ids(frame)
        name = name.strip()
        if not name or len(name) > 255:
            raise ValidationError("Tên tệp phải có từ 1 đến 255 ký tự.")
        with self.engine.begin() as conn:
            dataset_id = conn.execute(insert(datasets).values(name=name)).inserted_primary_key[0]
            return self._write_version(conn, dataset_id, 1, values, ids)

    @staticmethod
    def _write_version(conn, dataset_id, revision, values, ids):
        vid = conn.execute(
            insert(versions).values(dataset_id=dataset_id, revision=revision)
        ).inserted_primary_key[0]
        rows = [
            {
                "version_id": vid,
                "customer_id": cid,
                "inputs": {k: None if pd.isna(v) else v for k, v in row.items()},
            }
            for cid, row in zip(ids, values.to_dict("records"))
        ]
        if rows:
            conn.execute(insert(records), rows)
        return vid

    def revise_dataset(self, dataset_id, customer_id, inputs, *, replace=False, expected_version=None):
        """Lock dataset to serialize revisions; explicit duplicate resolution only."""
        new = validate_frame(pd.DataFrame([inputs]))
        customer_id = str(customer_id).strip()
        if not customer_id or len(customer_id) > 128:
            raise ValidationError("ID phải có từ 1 đến 128 ký tự.")
        with self.engine.begin() as conn:
            return self._revise(conn, dataset_id, customer_id, new, replace, expected_version)

    def _revise(self, conn, dataset_id, customer_id, new, replace, expected_version):
        row = conn.execute(select(datasets).where(datasets.c.id == dataset_id).with_for_update()).first()
        if row is None:
            raise ValidationError("Không tìm thấy tệp dữ liệu.")
        latest = (
            conn.execute(
                select(versions)
                .where(versions.c.dataset_id == dataset_id)
                .order_by(versions.c.revision.desc())
                .limit(1)
            )
            .mappings()
            .one()
        )
        if expected_version is not None and latest["id"] != expected_version:
            raise ValidationError("Tệp đã có phiên bản mới. Hãy tải lại trước khi lưu.")
        current = pd.DataFrame(
            conn.execute(select(records).where(records.c.version_id == latest["id"])).mappings().all()
        )
        ids = current["customer_id"].tolist() if not current.empty else []
        values = (
            pd.DataFrame(current["inputs"].tolist()) if not current.empty else pd.DataFrame(columns=FEATURES)
        )
        if customer_id in ids:
            if not replace:
                raise ValidationError("ID đã tồn tại. Chọn cập nhật rõ ràng hoặc nhập ID khác.")
            values.loc[ids.index(customer_id), FEATURES] = new.iloc[0][FEATURES]
            for column in (TARGET,):
                if column in new:
                    values.loc[ids.index(customer_id), column] = new.iloc[0][column]
        else:
            ids.append(customer_id)
            values = new.copy() if values.empty else pd.concat([values, new], ignore_index=True)
        return self._write_version(conn, dataset_id, latest["revision"] + 1, values, ids)

    def data(self, version_id):
        with self.engine.connect() as conn:
            rows = (
                conn.execute(select(records).where(records.c.version_id == version_id).order_by(records.c.id))
                .mappings()
                .all()
            )
        if not rows:
            with self.engine.connect() as conn:
                exists = conn.scalar(select(versions.c.id).where(versions.c.id == version_id))
            if exists is None:
                raise ValidationError("Phiên bản dữ liệu không tồn tại.")
            return pd.DataFrame(columns=["record_id", "ID", *FEATURES])
        return pd.DataFrame([{"record_id": r["id"], "ID": r["customer_id"], **r["inputs"]} for r in rows])

    def remove_record(self, dataset_id, customer_id, expected_version, copy_name=None):
        with self.engine.begin() as conn:
            conn.execute(select(datasets).where(datasets.c.id == dataset_id).with_for_update()).one()
            latest = (
                conn.execute(
                    select(versions)
                    .where(versions.c.dataset_id == dataset_id)
                    .order_by(versions.c.revision.desc())
                    .limit(1)
                )
                .mappings()
                .one()
            )
            if latest["id"] != expected_version:
                raise ValidationError("Tệp đã có phiên bản mới. Hãy tải lại.")
            rows = (
                conn.execute(select(records).where(records.c.version_id == expected_version)).mappings().all()
            )
            kept = [r for r in rows if r["customer_id"] != str(customer_id)]
            if len(kept) == len(rows):
                raise ValidationError("Không tìm thấy ID cần xóa.")
            values = pd.DataFrame([r["inputs"] for r in kept], columns=None if kept else FEATURES)
            if copy_name is not None:
                if not copy_name.strip() or len(copy_name.strip()) > 255:
                    raise ValidationError("Tên bản sao phải có từ 1 đến 255 ký tự.")
                dataset_id = conn.execute(
                    insert(datasets).values(name=copy_name.strip())
                ).inserted_primary_key[0]
                revision = 1
            else:
                revision = latest["revision"] + 1
            return self._write_version(conn, dataset_id, revision, values, [r["customer_id"] for r in kept])

    def transfer_input(
        self, dataset_id, customer_id, inputs, *, expected_version, replace=False, copy_name=None
    ):
        """Transfer inputs only; never reuse a single prediction as batch results."""
        if copy_name is None:
            return self.revise_dataset(
                dataset_id, customer_id, inputs, replace=replace, expected_version=expected_version
            )
        source = self.data(expected_version).drop(columns=["record_id"], errors="ignore")
        if str(customer_id) in source["ID"].tolist():
            if not replace:
                raise ValidationError("ID đã tồn tại. Cần xác nhận cập nhật hoặc nhập ID khác.")
            source = source.loc[source["ID"] != str(customer_id)]
        new = validate_frame(pd.DataFrame([inputs])).assign(ID=str(customer_id))
        return self.import_dataset(copy_name, pd.concat([source, new], ignore_index=True))

    def version_history(self, dataset_id):
        with self.engine.connect() as conn:
            return pd.read_sql(
                select(versions)
                .where(versions.c.dataset_id == dataset_id)
                .order_by(versions.c.revision.desc()),
                conn,
            )

    def predict_version(self, version_id, model, thresholds):
        frame = self.data(version_id)
        result = model.predict(frame, thresholds)
        with self.engine.begin() as conn:
            run_id = conn.execute(
                insert(runs).values(
                    version_id=version_id,
                    model_name=model.name,
                    model_version=model.version,
                    model_hash=model.digest,
                    thresholds=run_parameters(thresholds),
                )
            ).inserted_primary_key[0]
            rows = [
                {"run_id": run_id, "record_id": int(rid), **row}
                for rid, row in zip(frame["record_id"], result.to_dict("records"))
            ]
            conn.execute(insert(predictions), rows)
        return run_id, self.results(run_id)

    def get_or_predict(self, version_id, model, thresholds):
        with self.engine.connect() as conn:
            candidates = (
                conn.execute(
                    select(runs.c.id, runs.c.thresholds)
                    .where(runs.c.version_id == version_id, runs.c.model_hash == model.digest)
                    .order_by(runs.c.id.desc())
                )
                .mappings()
                .all()
            )
        wanted = asdict(thresholds)
        for row in candidates:
            stored = dict(row["thresholds"])
            stored.setdefault("basis", "raw")
            if {key: stored.get(key) for key in wanted} == wanted:
                return row["id"], self.results(row["id"])
        return self.predict_version(version_id, model, thresholds)

    def history(self):
        with self.engine.connect() as conn:
            return pd.read_sql(
                select(
                    runs.c.id.label("run_id"),
                    datasets.c.name,
                    versions.c.revision,
                    runs.c.version_id,
                    runs.c.model_name,
                    runs.c.model_version,
                    runs.c.created_at,
                    runs.c.thresholds,
                    runs.c.model_hash,
                )
                .join(versions, runs.c.version_id == versions.c.id)
                .join(datasets, versions.c.dataset_id == datasets.c.id)
                .order_by(runs.c.id.desc()),
                conn,
            )

    def results(self, run_id):
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(
                        records.c.customer_id.label("ID"),
                        records.c.inputs,
                        predictions.c.raw_score,
                        predictions.c.probability,
                        predictions.c.default_label,
                        predictions.c.risk_level,
                    )
                    .join(predictions, records.c.id == predictions.c.record_id)
                    .where(predictions.c.run_id == run_id)
                    .order_by(records.c.id)
                )
                .mappings()
                .all()
            )
            info = conn.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        result = pd.DataFrame(
            [{**r["inputs"], **{k: v for k, v in r.items() if k != "inputs"}} for r in rows]
        )
        if info and not result.empty:
            config = info["thresholds"]
            for key, value in {
                "run_id": run_id,
                "model_name": info["model_name"],
                "model_version": info["model_version"],
                "model_sha256": info["model_hash"],
                "dataset_version_id": info["version_id"],
                "performed_by": config.get("performed_by", "Không ghi nhận (lịch sử cũ)"),
                "prediction_time_utc": info["created_at"].isoformat(),
                "decision_threshold": config["decision"],
                "decision_basis": config.get("basis", "raw"),
                "risk_low_threshold": config["low"],
                "risk_high_threshold": config["high"],
                "prediction_status": "Đã dự báo",
            }.items():
                result[key] = value
        return result

    def portfolio(self, model_hash=None):
        """Only latest versions and latest run per version; no double counting history."""
        latest_versions = (
            select(versions.c.dataset_id, func.max(versions.c.id).label("vid"))
            .group_by(versions.c.dataset_id)
            .subquery()
        )
        run_query = select(runs.c.version_id, func.max(runs.c.id).label("rid"))
        if model_hash:
            run_query = run_query.where(runs.c.model_hash == model_hash)
        latest_runs = run_query.group_by(runs.c.version_id).subquery()
        current = records.join(latest_versions, records.c.version_id == latest_versions.c.vid)
        current = current.outerjoin(latest_runs, records.c.version_id == latest_runs.c.version_id)
        current = current.outerjoin(
            predictions,
            (predictions.c.record_id == records.c.id) & (predictions.c.run_id == latest_runs.c.rid),
        )
        with self.engine.connect() as conn:
            frame = pd.read_sql(
                select(
                    records.c.customer_id,
                    latest_versions.c.dataset_id,
                    predictions.c.probability,
                    predictions.c.risk_level,
                ).select_from(current),
                conn,
            )
            past = select(versions.c.dataset_id).join(runs)
            if model_hash:
                past = past.where(runs.c.model_hash == model_hash)
            ever = set(conn.execute(past.distinct()).scalars())
        frame["status"] = [
            "Đã dự báo" if pd.notna(p) else "Cần dự báo lại" if did in ever else "Chưa dự báo"
            for p, did in zip(frame["probability"], frame["dataset_id"])
        ]
        return frame
