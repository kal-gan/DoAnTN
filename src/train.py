from ultralytics import YOLO
import torch
import os
import argparse


def train_model(
    epochs: int = 100,
    batch: int = 16,
    imgsz: int = 640,
    model_path: str = "yolov8n.pt",
    data_yaml: str | None = None,
):
    """
    Script train YOLOv8 phát hiện lửa và khói.
    Yêu cầu: dataset đã chuẩn bị tại data/images/ và data/labels/.
    Xem data/data.yaml để biết cấu hình chi tiết.
    """
    # Kiểm tra và thông báo thiết bị tính toán
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Đang sử dụng thiết bị: {device}")
    if device == "cpu":
        print("[WARN] Không tìm thấy GPU. Train bằng CPU sẽ chậm hơn GPU.")

    # Kiểm tra file cấu hình dataset
    if data_yaml is None:
        data_yaml = os.path.join("data", "data.yaml")
    if not os.path.isfile(data_yaml):
        print(f"[ERROR] Không tìm thấy file cấu hình: {data_yaml}")
        print("[ERROR] Vui lòng chuẩn bị dataset trước khi train.")
        return

    # Kiểm tra file model gốc
    if not os.path.isfile(model_path):
        print(f"[WARN] Không tìm thấy {model_path}, dùng yolov8n.pt pretrained từ Ultralytics.")
        model_path = "yolov8n.pt"

    print(f"[INFO] Load model: {model_path}")
    model = YOLO(model_path)

    print(f"[INFO] Bắt đầu huấn luyện: epochs={epochs}, batch={batch}, imgsz={imgsz}")
    model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        name="fire_smoke_detector",
        patience=max(10, epochs // 5),
        device=device,
        workers=2,
        optimizer="AdamW",
        lr0=0.001,
        augment=True,
        mosaic=1.0,
        mixup=0.1,
        project="runs/train",
        exist_ok=True,
    )

    # Đánh giá mô hình trên tập validation
    print("[INFO] Đánh giá mô hình trên tập validation...")
    try:
        metrics = model.val()
        print(f"[INFO] mAP50:    {metrics.box.map50:.4f}")
        print(f"[INFO] mAP50-95: {metrics.box.map:.4f}")
    except Exception as e:
        print(f"[WARN] Không thể đánh giá val: {e}")

    best_weights = os.path.join("runs", "train", "fire_smoke_detector", "weights", "best.pt")
    if os.path.isfile(best_weights):
        print(f"[INFO] ✓ Huấn luyện hoàn tất! Model lưu tại: {best_weights}")
    else:
        print("[WARN] Không tìm thấy best.pt, kiểm tra thư mục runs/train/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLOv8 fire/smoke detector")
    parser.add_argument("--epochs", type=int,  default=100,          help="Số epoch")
    parser.add_argument("--batch",  type=int,  default=16,           help="Batch size")
    parser.add_argument("--imgsz",  type=int,  default=640,          help="Kích thước ảnh")
    parser.add_argument("--model",  type=str,  default="yolov8n.pt", help="Model gốc")
    parser.add_argument("--data",   type=str,  default=None,         help="Đường dẫn data.yaml")
    args = parser.parse_args()
    train_model(
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        model_path=args.model,
        data_yaml=args.data,
    )
