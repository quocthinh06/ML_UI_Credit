"""Safe MongoDB diagnostics shared by HTTP and the operator check command."""
from pymongo.errors import ConfigurationError, OperationFailure, PyMongoError, ServerSelectionTimeoutError


def connection_error(exc):
    if isinstance(exc, OperationFailure):
        if exc.code in (18, 8000):
            return "MONGO_AUTH_FAILED", (
                "MongoDB Atlas từ chối xác thực database user (không phải tài khoản đăng nhập web). "
                "Kiểm tra Database Access, đúng cluster, mật khẩu và authSource trong MONGODB_URI. "
                "Mật khẩu trong URI cần percent-encode đúng một lần; có thể dùng MONGODB_USERNAME/"
                "MONGODB_PASSWORD riêng để tránh lỗi mã hóa. Cập nhật trong Vercel rồi redeploy.")
        if exc.code == 13:
            return "MONGO_PERMISSION_DENIED", "Database user cần quyền readWrite trên database MONGODB_DATABASE."
        return "MONGO_OPERATION_FAILED", "MongoDB không thực hiện được thao tác. Kiểm tra quyền và cấu hình database."
    if isinstance(exc, ServerSelectionTimeoutError):
        return "MONGO_UNREACHABLE", "Không kết nối được MongoDB Atlas. Kiểm tra cluster, Network Access và DNS."
    if isinstance(exc, (ConfigurationError, PyMongoError)):
        return "MONGO_CONFIGURATION_INVALID", "Cấu hình connection string MONGODB_URI hoặc xác thực không hợp lệ. Kiểm tra biến môi trường rồi redeploy."
    return None
