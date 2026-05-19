"""
src/core/data_collector.py
Module thu thập dữ liệu phát hiện từ thời gian thực.
Lưu ảnh + annotation YOLO (.txt) để huấn luyện gia tăng.
"""
import os
import cv2
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class DataCollector:
    """Thu thập ảnh và annotation từ các lần phát hiện."""

    def __init__(
        self,
        collection_dir: str = "training_data/collected",
        auto_create_dirs: bool = True,
    ):
        """
        Khởi tạo DataCollector.
        
        Args:
            collection_dir: Thư mục lưu dữ liệu thu thập
            auto_create_dirs: Tự động tạo thư mục con cho mỗi class
        """
        self.collection_dir = Path(collection_dir)
        self._lock = threading.Lock()
        self.collection_count = 0
        self.class_map = {}  # Ánh xạ class name → ID
        
        if auto_create_dirs:
            self._ensure_structure()

    def _ensure_structure(self):
        """Tạo cấu trúc thư mục cho dữ liệu thu thập."""
        self.collection_dir.mkdir(parents=True, exist_ok=True)
        # Tạo thư mục con cho images và labels
        (self.collection_dir / "images").mkdir(exist_ok=True)
        (self.collection_dir / "labels").mkdir(exist_ok=True)

    def set_class_map(self, class_names: Dict[int, str]):
        """
        Đặt ánh xạ class ID → name từ model.
        
        Args:
            class_names: Dict {class_id: class_name} từ YOLO model.names
        """
        self.class_map = class_names

    def save_detection(
        self,
        frame: "cv2.Mat",
        detections: List[Dict],
        source_name: str = "unknown",
        timestamp: Optional[str] = None,
    ) -> Optional[str]:
        """
        Lưu frame và annotation từ một lần phát hiện.
        
        Args:
            frame: Frame ảnh (numpy array)
            detections: Danh sách detection {
                'class_id': int,
                'class_name': str,
                'conf': float,
                'x1': int, 'y1': int, 'x2': int, 'y2': int
            }
            source_name: Tên nguồn (camera/video)
            timestamp: Timestamp của ảnh
        
        Returns:
            Tên file ảnh nếu thành công, None nếu thất bại
        """
        with self._lock:
            if timestamp is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            
            # Tạo tên file
            safe_source = "".join(c if c.isalnum() else "_" for c in source_name)
            image_name = f"{safe_source}_{timestamp}.jpg"
            image_path = self.collection_dir / "images" / image_name
            label_path = self.collection_dir / "labels" / image_name.replace(".jpg", ".txt")
            
            try:
                # Lưu ảnh
                cv2.imwrite(str(image_path), frame)
                
                # Lưu annotation YOLO format
                if detections:
                    h, w = frame.shape[:2]
                    annotation_lines = []
                    
                    for det in detections:
                        x1, y1 = det.get("x1", 0), det.get("y1", 0)
                        x2, y2 = det.get("x2", w), det.get("y2", h)
                        class_id = det.get("class_id", 0)
                        
                        # Chuyển sang YOLO format (center_x, center_y, width, height) normalized
                        center_x = ((x1 + x2) / 2.0) / w
                        center_y = ((y1 + y2) / 2.0) / h
                        box_w = (x2 - x1) / w
                        box_h = (y2 - y1) / h
                        
                        # Clamp về [0, 1]
                        center_x = max(0.0, min(1.0, center_x))
                        center_y = max(0.0, min(1.0, center_y))
                        box_w = max(0.0, min(1.0, box_w))
                        box_h = max(0.0, min(1.0, box_h))
                        
                        annotation_lines.append(
                            f"{class_id} {center_x:.6f} {center_y:.6f} {box_w:.6f} {box_h:.6f}"
                        )
                    
                    # Ghi file annotation
                    with open(label_path, "w") as f:
                        f.write("\n".join(annotation_lines))
                else:
                    # Ảnh không có detection - tạo file annotation trống
                    label_path.touch()
                
                self.collection_count += 1
                return image_name
                
            except Exception as e:
                print(f"[ERROR] Lỗi lưu detection: {e}")
                return None

    def get_collection_stats(self) -> Dict:
        """Lấy thống kê về dữ liệu đã thu thập."""
        image_dir = self.collection_dir / "images"
        label_dir = self.collection_dir / "labels"
        
        images = list(image_dir.glob("*.jpg")) if image_dir.exists() else []
        labels = list(label_dir.glob("*.txt")) if label_dir.exists() else []
        
        # Đếm detections
        total_detections = 0
        if labels:
            for label_file in labels:
                with open(label_file, "r") as f:
                    lines = f.readlines()
                    total_detections += len([l for l in lines if l.strip()])
        
        return {
            "total_images": len(images),
            "total_detections": total_detections,
            "collection_dir": str(self.collection_dir),
        }

    def clear_collected_data(self) -> bool:
        """Xoá tất cả dữ liệu đã thu thập."""
        with self._lock:
            try:
                import shutil
                if self.collection_dir.exists():
                    shutil.rmtree(self.collection_dir)
                self._ensure_structure()
                self.collection_count = 0
                return True
            except Exception as e:
                print(f"[ERROR] Lỗi xoá dữ liệu: {e}")
                return False

    def export_to_dataset(
        self,
        output_dir: str = "data/training_additions",
        split_ratio: Tuple[float, float, float] = (0.7, 0.15, 0.15),
    ) -> bool:
        """
        Export dữ liệu thu thập sang định dạng YOLO dataset.
        
        Args:
            output_dir: Thư mục output
            split_ratio: Tỉ lệ (train, val, test)
        
        Returns:
            True nếu thành công
        """
        import shutil
        import random
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        try:
            image_dir = self.collection_dir / "images"
            label_dir = self.collection_dir / "labels"
            
            images = sorted(image_dir.glob("*.jpg"))
            if not images:
                print("[WARN] Không có ảnh để export")
                return False
            
            # Shuffle
            random.shuffle(images)
            
            # Tính số lượng cho mỗi split
            n = len(images)
            n_train = int(n * split_ratio[0])
            n_val = int(n * split_ratio[1])
            
            splits = {
                "train": images[:n_train],
                "val": images[n_train:n_train + n_val],
                "test": images[n_train + n_val:],
            }
            
            # Copy files
            for split_name, split_images in splits.items():
                split_dir = output_path / split_name
                split_dir.mkdir(exist_ok=True)
                
                images_dir = split_dir / "images"
                labels_dir = split_dir / "labels"
                images_dir.mkdir(exist_ok=True)
                labels_dir.mkdir(exist_ok=True)
                
                for img_path in split_images:
                    # Copy image
                    shutil.copy(str(img_path), str(images_dir / img_path.name))
                    
                    # Copy label
                    label_path = label_dir / img_path.name.replace(".jpg", ".txt")
                    if label_path.exists():
                        shutil.copy(str(label_path), str(labels_dir / label_path.name))
                    else:
                        (labels_dir / label_path.name).touch()
            
            print(f"[INFO] Export thành công: {output_path}")
            print(f"       - Train: {len(splits['train'])}")
            print(f"       - Val: {len(splits['val'])}")
            print(f"       - Test: {len(splits['test'])}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Lỗi export: {e}")
            return False
