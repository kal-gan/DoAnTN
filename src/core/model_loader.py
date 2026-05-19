"""
src/core/model_loader.py
Tiện ích tải và khởi tạo mô hình YOLO cho hệ thống phát hiện lửa/khói.
"""
import os
import urllib.request

from ultralytics import YOLO

# Màu sắc bounding box cho từng lớp (BGR)
COLORS = {
    "fire": (0, 0, 255),      # Đỏ
    "smoke": (128, 128, 128), # Xám
}

# Ngưỡng tin cậy mặc định
CONFIDENCE_THRESHOLD = 0.45

# Cooldown tối thiểu giữa các lần lưu ảnh cảnh báo (giây)
ALERT_COOLDOWN = 5

# URL tải mô hình pretrained fire/smoke
MODEL_DOWNLOAD_URL = (
    "https://github.com/spacewalk01/yolov8-fire-and-smoke-detection"
    "/releases/download/v1.0/best.pt"
)

# Đường dẫn mô hình mặc định
DEFAULT_MODEL_PATH = "models/best.pt"


def download_model(save_path: str) -> bool:
    """
    Thử tải mô hình fire/smoke pretrained từ URL.
    Trả về True nếu tải thành công, False nếu thất bại.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    print(f"[INFO] Đang thử tải mô hình fire/smoke từ:\n       {MODEL_DOWNLOAD_URL}")
    try:
        urllib.request.urlretrieve(MODEL_DOWNLOAD_URL, save_path)
        print(f"[INFO] Tải mô hình thành công: {save_path}")
        return True
    except Exception as exc:
        print(f"[WARN] Không thể tải mô hình tự động: {exc}")
        return False


def load_model(model_path: str) -> YOLO:
    """
    Tải mô hình theo thứ tự ưu tiên:
    1. File .pt tại model_path nếu tồn tại.
    2. Thử tải tự động từ URL về model_path.
    3. Fallback sang yolov8n.pt (COCO) và in cảnh báo rõ ràng.
    """
    if os.path.isfile(model_path):
        print(f"[INFO] Tìm thấy mô hình: {model_path}")
        return YOLO(model_path)

    if download_model(model_path):
        return YOLO(model_path)

    print("\n" + "=" * 65)
    print("[WARN] Không tải được mô hình fire/smoke chuyên dụng.")
    print("[WARN] Sẽ dùng yolov8n.pt (COCO, 80 lớp) làm dự phòng.")
    print("[WARN] Mô hình COCO KHÔNG có lớp 'fire' hoặc 'smoke'.")
    print("[WARN] Script sẽ chạy nhưng sẽ KHÔNG phát hiện được lửa/khói.")
    print("[WARN] Để phát hiện đúng, hãy tải thủ công mô hình best.pt")
    print("[WARN] và đặt vào thư mục models/. Nguồn tải:")
    print("[WARN]   https://github.com/spacewalk01/yolov8-fire-and-smoke-detection")
    print("[WARN]   https://github.com/MuhammadMoinFaisal/YOLOv8_Fire_and_Smoke_Detection")
    print("=" * 65 + "\n")
    return YOLO("yolov8n.pt")
