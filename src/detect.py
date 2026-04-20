import cv2
import argparse
import time
import os
import urllib.request
from ultralytics import YOLO
from datetime import datetime

# ========== Cấu hình màu sắc cho từng lớp (BGR) ==========
COLORS = {
    'fire':  (0, 0, 255),      # Đỏ
    'smoke': (128, 128, 128),  # Xám
}

# Ngưỡng tin cậy mặc định
CONFIDENCE_THRESHOLD = 0.45

# Thời gian chờ tối thiểu giữa các lần lưu ảnh cảnh báo (giây)
ALERT_COOLDOWN = 5

# URL thử tải mô hình fire/smoke pretrained
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
    except Exception as e:
        print(f"[WARN] Không thể tải mô hình tự động: {e}")
        return False


def load_model(model_path: str) -> YOLO:
    """
    Tải mô hình theo thứ tự ưu tiên:
    1. Dùng file .pt tại model_path nếu đã tồn tại.
    2. Thử tải tự động từ URL về model_path.
    3. Fallback sang yolov8n.pt (COCO) và in cảnh báo rõ ràng.
    """
    if os.path.isfile(model_path):
        print(f"[INFO] Tìm thấy mô hình: {model_path}")
        return YOLO(model_path)

    # Thử tải tự động
    if download_model(model_path):
        return YOLO(model_path)

    # Fallback sang YOLOv8n COCO
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


class FireSmokeDetector:
    """Lớp phát hiện lửa và khói theo thời gian thực."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, conf: float = CONFIDENCE_THRESHOLD):
        self.conf = conf
        self.model = load_model(model_path)
        self.class_names = self.model.names  # dict {id: name}
        self.last_alert_time = 0.0

        # Tạo thư mục lưu ảnh cảnh báo
        os.makedirs("alerts", exist_ok=True)

    def save_alert_frame(self, frame, label: str):
        """Lưu khung hình cảnh báo vào thư mục alerts/ với timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join("alerts", f"{label}_{timestamp}.jpg")
        cv2.imwrite(filename, frame)
        print(f"[ALERT] Đã lưu ảnh cảnh báo: {filename}")

    def process_frame(self, frame):
        """
        Chạy YOLO inference trên một khung hình.
        - Chỉ xử lý các lớp có tên 'fire' hoặc 'smoke' (không phân biệt hoa/thường).
        - Vẽ bounding box màu đỏ (fire) / xám (smoke).
        - Vẽ banner cảnh báo đỏ ở đầu khung hình khi phát hiện.
        - Lưu ảnh cảnh báo (có cooldown 5 giây).
        Trả về: (frame đã vẽ, danh sách nhãn phát hiện được)
        """
        results = self.model(frame, conf=self.conf, verbose=False)

        detected_labels = []
        h, w = frame.shape[:2]

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0])
                label = self.class_names.get(cls_id, "unknown")

                # Chỉ xử lý fire/smoke
                if label.lower() not in ("fire", "smoke"):
                    continue

                conf_score = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                color = COLORS.get(label.lower(), (0, 255, 0))

                # Vẽ bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # Vẽ nền nhãn
                text = f"{label.upper()} {conf_score:.2f}"
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 4, y1), color, -1)
                cv2.putText(
                    frame, text, (x1 + 2, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                )

                detected_labels.append(label.lower())

        # Xử lý cảnh báo khi có phát hiện
        if detected_labels:
            current_time = time.time()
            if current_time - self.last_alert_time > ALERT_COOLDOWN:
                # Ưu tiên nhãn fire nếu có
                alert_label = "fire" if "fire" in detected_labels else "smoke"
                self.save_alert_frame(frame, alert_label)
                self.last_alert_time = current_time

            # Vẽ banner cảnh báo đỏ ở đầu khung hình
            # Lưu ý: cv2.FONT_HERSHEY không hỗ trợ dấu tiếng Việt,
            # dùng không dấu để tránh hiển thị ký tự lỗi trên canvas.
            cv2.rectangle(frame, (0, 0), (w, 42), (0, 0, 220), -1)
            unique_labels = ", ".join(sorted(set(detected_labels))).upper()
            banner_text = f"!!! CANH BAO: PHAT HIEN {unique_labels} !!!"
            cv2.putText(
                frame, banner_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2
            )

        return frame, detected_labels

    def run(self, source):
        """
        Chạy vòng lặp phát hiện:
        - source = 0 (int)  : camera laptop
        - source = 'path'   : video file
        Nhấn 'Q' để thoát.
        """
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"[ERROR] Không thể mở nguồn: {source}")
            if source == 0:
                print("[ERROR] Hãy kiểm tra webcam đã được kết nối và không bị ứng dụng khác chiếm dụng.")
            else:
                print("[ERROR] Kiểm tra lại đường dẫn file video.")
            return

        # In thông tin nguồn
        fps_src = cap.get(cv2.CAP_PROP_FPS) or 30
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[INFO] Nguồn: {source} | Độ phân giải: {width}x{height} | FPS nguồn: {fps_src:.1f}")
        print("[INFO] Nhấn 'Q' để thoát.")

        prev_time = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] Hết video hoặc không đọc được khung hình.")
                break

            # Phát hiện và vẽ
            frame, _ = self.process_frame(frame)

            # Tính và hiển thị FPS ở góc dưới trái
            curr_time = time.time()
            elapsed = curr_time - prev_time
            fps = 1.0 / elapsed if elapsed > 0 else 0.0
            prev_time = curr_time

            h = frame.shape[0]
            cv2.putText(
                frame, f"FPS: {fps:.1f}", (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )

            cv2.imshow("Fire & Smoke Detection - Nhấn Q để thoát", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[INFO] Người dùng nhấn Q, đang thoát...")
                break

        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Đã kết thúc phiên phát hiện.")


def main():
    parser = argparse.ArgumentParser(
        description="Phát hiện lửa và khói theo thời gian thực bằng YOLOv8 + OpenCV"
    )
    parser.add_argument(
        "--source", type=str, default="0",
        help="0 = camera laptop, hoặc đường dẫn tới video file (vd: videos/test.mp4)"
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL_PATH,
        help=f"Đường dẫn tới file mô hình .pt (mặc định: {DEFAULT_MODEL_PATH})"
    )
    parser.add_argument(
        "--conf", type=float, default=CONFIDENCE_THRESHOLD,
        help=f"Ngưỡng tin cậy (mặc định: {CONFIDENCE_THRESHOLD})"
    )
    args = parser.parse_args()

    # Chuyển source thành int nếu là số (camera index)
    source = int(args.source) if args.source.isdigit() else args.source

    detector = FireSmokeDetector(model_path=args.model, conf=args.conf)
    detector.run(source=source)


if __name__ == "__main__":
    main()
