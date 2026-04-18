from ultralytics import YOLO
import torch
import os


def train_model():
    """
    Script train YOLOv8 phát hiện lửa và khói.
    Yêu cầu: dataset đã chuẩn bị tại data/images/ và data/labels/.
    Xem data/data.yaml để biết cấu hình chi tiết.
    """
    # Kiểm tra và thông báo thiết bị tính toán
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Đang sử dụng thiết bị: {device}")
    if device == "cpu":
        print("[WARN] Không tìm thấy GPU. Train bằng CPU sẽ rất chậm.")

    # Kiểm tra file cấu hình dataset
    data_yaml = os.path.join("data", "data.yaml")
    if not os.path.isfile(data_yaml):
        print(f"[ERROR] Không tìm thấy file cấu hình: {data_yaml}")
        print("[ERROR] Vui lòng chuẩn bị dataset trước khi train.")
        return

    # Load mô hình YOLOv8 nano pretrained (nhẹ, nhanh, phù hợp fine-tune)
    print("[INFO] Đang tải mô hình YOLOv8n pretrained...")
    model = YOLO("yolov8n.pt")

    # Bắt đầu train
    print("[INFO] Bắt đầu quá trình huấn luyện...")
    results = model.train(
        data=data_yaml,
        epochs=100,
        imgsz=640,
        batch=16,
        name="fire_smoke_detector",
        patience=20,           # Early stopping nếu không cải thiện sau 20 epoch
        device=device,
        workers=4,
        optimizer="AdamW",
        lr0=0.001,
        augment=True,          # Tăng cường dữ liệu (data augmentation)
        mosaic=1.0,
        mixup=0.1,
        project="runs/train",
    )

    # Đánh giá mô hình trên tập validation
    print("[INFO] Đang đánh giá mô hình trên tập validation...")
    metrics = model.val()
    print(f"[INFO] mAP50:    {metrics.box.map50:.4f}")
    print(f"[INFO] mAP50-95: {metrics.box.map:.4f}")

    best_weights = os.path.join("runs", "train", "fire_smoke_detector", "weights", "best.pt")
    print(f"[INFO] Huấn luyện hoàn tất! Mô hình tốt nhất lưu tại: {best_weights}")
    print(f"[INFO] Sao chép vào models/ để dùng:\n       cp {best_weights} models/best.pt")


if __name__ == "__main__":
    train_model()
