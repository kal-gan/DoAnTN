"""
src/core/detector.py
Lớp FireSmokeDetector - phát hiện lửa và khói theo thời gian thực bằng YOLOv8.

FIX: 
- Giảm max_inference_size mặc định từ 960 → 640 để tăng tốc inference.
- Thêm CAP_PROP_BUFFERSIZE=1 để tránh đọc frame cũ từ buffer.
- Thêm frame skip để giữ video/camera đồng bộ thời gian thực.
- Đưa save_alert_frame ra thread riêng để không block main loop.
- Loại bỏ _prepare_inference_frame gọi 2 lần trong process_frame.
"""
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

import cv2

from .model_loader import (
    ALERT_COOLDOWN,
    COLORS,
    CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL_PATH,
    load_model,
)


class FireSmokeDetector:
    """Lớp phát hiện lửa và khói theo thời gian thực."""

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        conf: float = CONFIDENCE_THRESHOLD,
        smoke_conf: float = 0.55,
        smoke_min_area_ratio: float = 0.005,
        alert_cooldown: float = ALERT_COOLDOWN,
        auto_save_alert: bool = True,
        # FIX ❶: Giảm từ 960 → 640 để inference nhanh hơn ~2.25x
        max_inference_size: int = 640,
    ):
        self.conf = conf
        self.smoke_conf = max(0.0, min(1.0, smoke_conf))
        self.smoke_min_area_ratio = max(0.0, min(0.5, smoke_min_area_ratio))
        self.model = load_model(model_path)
        self.class_names = self.model.names  # dict {id: name}
        self.alert_cooldown = alert_cooldown
        self.auto_save_alert = auto_save_alert
        self.last_alert_time = 0.0
        self.max_inference_size = max(320, int(max_inference_size))

        os.makedirs("alerts", exist_ok=True)

    @staticmethod
    def _clip_bbox(x1: int, y1: int, x2: int, y2: int, width: int, height: int) -> Tuple[int, int, int, int]:
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(0, min(x2, width - 1))
        y2 = max(0, min(y2, height - 1))
        if x2 <= x1:
            x2 = min(width - 1, x1 + 1)
        if y2 <= y1:
            y2 = min(height - 1, y1 + 1)
        return x1, y1, x2, y2

    def _prepare_inference_frame(self, frame) -> Tuple[Any, float]:
        inference_frame = frame
        scale = 1.0
        h, w = frame.shape[:2]
        longest_side = max(h, w)
        if longest_side > self.max_inference_size:
            scale = self.max_inference_size / float(longest_side)
            inference_size = (max(2, int(w * scale)), max(2, int(h * scale)))
            inference_frame = cv2.resize(frame, inference_size, interpolation=cv2.INTER_AREA)
        return inference_frame, scale

    # ── Màu sắc theo class (BGR) ─────────────────────────────────────
    _CLASS_COLORS: Dict[str, Tuple[int, int, int]] = {
        "fire":  (0, 100, 255),    # cam-đỏ (BGR: R=255, G=100, B=0)
        "smoke": (180, 160, 100),  # xanh-xám nhạt
    }
    _CLASS_FILL: Dict[str, Tuple[int, int, int]] = {
        "fire":  (0, 60, 200),
        "smoke": (120, 110, 70),
    }

    @staticmethod
    def _draw_corner_box(
        frame,
        x1: int, y1: int, x2: int, y2: int,
        color: Tuple[int, int, int],
        fill_color: Tuple[int, int, int],
        label: str,
        conf: float,
    ):
        """Vẽ bbox kiểu góc cạnh surveillance + fill mờ + label sắc nét."""
        import numpy as np
        h_frame, w_frame = frame.shape[:2]
        bw = x2 - x1
        bh = y2 - y1
        corner_len = max(12, min(28, int(min(bw, bh) * 0.20)))
        thickness   = 2

        # Semi-transparent fill
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), fill_color, -1)
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)

        # 4 góc (L-shape corners)
        corners = [
            # top-left
            [(x1, y1 + corner_len), (x1, y1), (x1 + corner_len, y1)],
            # top-right
            [(x2 - corner_len, y1), (x2, y1), (x2, y1 + corner_len)],
            # bottom-left
            [(x1, y2 - corner_len), (x1, y2), (x1 + corner_len, y2)],
            # bottom-right
            [(x2 - corner_len, y2), (x2, y2), (x2, y2 - corner_len)],
        ]
        for pts in corners:
            for i in range(len(pts) - 1):
                cv2.line(frame, pts[i], pts[i + 1], color, thickness + 1, cv2.LINE_AA)

        # Viền mỏng toàn box (độ mờ)
        border_overlay = frame.copy()
        cv2.rectangle(border_overlay, (x1, y1), (x2, y2), color, 1)
        cv2.addWeighted(border_overlay, 0.35, frame, 0.65, 0, frame)

        # Label tag
        icon = "🔥" if label == "fire" else "💨"
        tag_text = f"{label.upper()} {conf:.0%}"
        font       = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.52
        font_thick = 1
        (tw, th), baseline = cv2.getTextSize(tag_text, font, font_scale, font_thick)
        pad = 5
        tag_x1 = x1
        tag_y2 = y1
        tag_y1 = max(0, y1 - th - pad * 2)
        tag_x2 = min(w_frame, x1 + tw + pad * 2)

        # Tag background
        cv2.rectangle(frame, (tag_x1, tag_y1), (tag_x2, tag_y2), color, -1)
        # Tag text
        cv2.putText(
            frame, tag_text,
            (tag_x1 + pad, tag_y2 - pad + 1),
            font, font_scale, (255, 255, 255), font_thick, cv2.LINE_AA,
        )

    def _draw_detections(self, frame, detections: List[Dict[str, Any]]):
        """Vẽ từng bbox riêng biệt theo class, kiểu góc cạnh surveillance."""
        for det in detections:
            label = det["label"]
            conf  = float(det["confidence"])
            x1, y1, x2, y2 = det["bbox"]
            color      = self._CLASS_COLORS.get(label, (0, 200, 255))
            fill_color = self._CLASS_FILL.get(label, (0, 150, 200))
            self._draw_corner_box(frame, x1, y1, x2, y2, color, fill_color, label, conf)


        """Chạy inference và trả về danh sách object fire/smoke gồm label, conf, bbox."""
        inference_frame, scale = self._prepare_inference_frame(frame)
        results = self.model(inference_frame, conf=self.conf, verbose=False)

        h, w = frame.shape[:2]
        detections: List[Dict[str, Any]] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                label = str(self.class_names.get(cls_id, "unknown")).lower()
                if label not in ("fire", "smoke"):
                    continue

                conf_score = float(box.conf[0])
                x1, y1, x2, y2 = map(float, box.xyxy[0])
                if scale != 1.0:
                    x1 /= scale
                    y1 /= scale
                    x2 /= scale
                    y2 /= scale
                bx1, by1, bx2, by2 = self._clip_bbox(int(x1), int(y1), int(x2), int(y2), w, h)
                detections.append({
                    "label": label,
                    "confidence": conf_score,
                    "bbox": (bx1, by1, bx2, by2),
                })
        return detections

    def save_alert_frame(self, frame, label: str) -> str:
        """Lưu khung hình cảnh báo vào thư mục alerts/ với timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join("alerts", f"{label}_{timestamp}.jpg")
        cv2.imwrite(filename, frame)
        print(f"[ALERT] Đã lưu ảnh cảnh báo: {filename}")
        return filename

    def detect_labels(self, frame):
        """Chạy inference và trả về danh sách detection dicts {label, confidence, bbox}."""
        inference_frame, scale = self._prepare_inference_frame(frame)
        h, w = frame.shape[:2]

        model_conf = min(self.conf, self.smoke_conf)
        results = self.model(inference_frame, conf=model_conf, verbose=False)
        detections: List[Dict[str, Any]] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                label = str(self.class_names.get(cls_id, "unknown")).lower()
                if label not in ("fire", "smoke"):
                    continue

                conf_score = float(box.conf[0])
                threshold = self.conf if label == "fire" else self.smoke_conf
                if conf_score < threshold:
                    continue

                x1, y1, x2, y2 = map(float, box.xyxy[0])
                if scale != 1.0:
                    x1 /= scale
                    y1 /= scale
                    x2 /= scale
                    y2 /= scale
                bx1, by1, bx2, by2 = self._clip_bbox(int(x1), int(y1), int(x2), int(y2), w, h)
                # Lọc smoke có bbox quá nhỏ (thường do sương/mờ cam)
                if label == "smoke" and self.smoke_min_area_ratio > 0:
                    area_ratio = max(0, bx2 - bx1) * max(0, by2 - by1) / float(w * h)
                    if area_ratio < self.smoke_min_area_ratio:
                        continue
                detections.append({
                    "label": label,
                    "confidence": conf_score,
                    "bbox": (bx1, by1, bx2, by2),
                })

        return detections

    def process_frame(self, frame):
        """
        Chạy YOLO inference trên một khung hình.
        - Chỉ xử lý các lớp 'fire' hoặc 'smoke'.
        - Vẽ bounding box và banner cảnh báo khi phát hiện.
        - Lưu ảnh cảnh báo trong thread riêng (không block main loop).
        Trả về: (frame đã vẽ, danh sách nhãn phát hiện được)
        """
        # FIX ❷: Gọi _prepare_inference_frame 1 lần duy nhất
        inference_frame, scale = self._prepare_inference_frame(frame)
        h, w = frame.shape[:2]

        model_conf = min(self.conf, self.smoke_conf)
        results = self.model(inference_frame, conf=model_conf, verbose=False)
        detected_labels: List[str] = []
        detections: List[Dict[str, Any]] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                label = str(self.class_names.get(cls_id, "unknown")).lower()
                if label not in ("fire", "smoke"):
                    continue

                conf_score = float(box.conf[0])
                threshold = self.conf if label == "fire" else self.smoke_conf
                if conf_score < threshold:
                    continue

                x1, y1, x2, y2 = map(float, box.xyxy[0])
                if scale != 1.0:
                    x1 /= scale
                    y1 /= scale
                    x2 /= scale
                    y2 /= scale
                bx1, by1, bx2, by2 = self._clip_bbox(int(x1), int(y1), int(x2), int(y2), w, h)
                if label == "smoke" and self.smoke_min_area_ratio > 0:
                    area_ratio = max(0, bx2 - bx1) * max(0, by2 - by1) / float(w * h)
                    if area_ratio < self.smoke_min_area_ratio:
                        continue
                detections.append({
                    "label": label,
                    "confidence": conf_score,
                    "bbox": (bx1, by1, bx2, by2),
                })
                detected_labels.append(label)

        if detections:
            self._draw_detections(frame, detections)

        if detected_labels:
            current_time = time.time()
            if self.auto_save_alert and current_time - self.last_alert_time > self.alert_cooldown:
                alert_label = "fire" if "fire" in detected_labels else "smoke"
                # FIX ❸: Lưu ảnh trong thread riêng để không block main loop
                save_thread = threading.Thread(
                    target=self.save_alert_frame,
                    args=(frame.copy(), alert_label),
                    daemon=True,
                )
                save_thread.start()
                self.last_alert_time = current_time

            # Tính nhanh mức độ rủi ro từ detections hiện tại
            fire_dets = [d for d in detections if d["label"] == "fire"]
            max_conf_all = max(float(d["confidence"]) for d in detections) if detections else 0.0
            if fire_dets:
                max_fire_conf = max(float(d["confidence"]) for d in fire_dets)
                if max_fire_conf >= 0.75:
                    risk_text = "CUC NGUY HIEM"
                elif max_fire_conf >= 0.55:
                    risk_text = "NGUY HIEM"
                else:
                    risk_text = "CANH BAO"
            else:
                risk_text = "THEO DOI"

            # Banner cảnh báo 2 dòng: dòng 1 = loại, dòng 2 = hai chỉ số
            unique_labels = "+".join(sorted(set(l.upper() for l in detected_labels)))
            banner_color = (0, 60, 200) if "fire" in detected_labels else (90, 80, 20)
            cv2.rectangle(frame, (0, 0), (w, 46), banner_color, -1)
            cv2.putText(
                frame, f"  CANH BAO: {unique_labels}",
                (8, 18), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
            )
            cv2.putText(
                frame, f"  Do rui ro: {risk_text}   Do tin cay: {max_conf_all:.0%}",
                (8, 39), cv2.FONT_HERSHEY_DUPLEX, 0.46, (255, 230, 80), 1, cv2.LINE_AA,
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

        # FIX ❹: Giới hạn buffer OpenCV xuống 1 frame để luôn lấy frame mới nhất
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        fps_src = cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[INFO] Nguồn: {source} | Độ phân giải: {width}x{height} | FPS nguồn: {fps_src:.1f}")
        print(f"[INFO] Inference size tối đa: {self.max_inference_size}px")
        print("[INFO] Nhấn 'Q' để thoát.")

        # Xác định có phải live source (camera/stream) hay video file
        is_live = isinstance(source, int) or str(source).startswith(("rtsp://", "rtmp://", "http://"))

        prev_time = time.time()
        while True:
            # FIX ❺: Frame skip — với live source, flush buffer để lấy frame mới nhất
            if is_live:
                cap.grab()  # đọc nhanh không decode để bỏ frame cũ
                cap.grab()

            ret, frame = cap.read()
            if not ret:
                print("[INFO] Hết video hoặc không đọc được khung hình.")
                break

            frame, _ = self.process_frame(frame)

            curr_time = time.time()
            elapsed = curr_time - prev_time
            fps = 1.0 / elapsed if elapsed > 0 else 0.0
            prev_time = curr_time

            h = frame.shape[0]
            cv2.putText(
                frame, f"FPS: {fps:.1f}", (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
            )

            cv2.imshow("Fire & Smoke Detection - Nhan Q de thoat", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[INFO] Người dùng nhấn Q, đang thoát...")
                break

        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Đã kết thúc phiên phát hiện.")
