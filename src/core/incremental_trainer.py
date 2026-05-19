"""
src/core/incremental_trainer.py
Module huấn luyện gia tăng - kết hợp dữ liệu mới với dữ liệu cũ để cải thiện mô hình.
"""
import os
import yaml
import shutil
from pathlib import Path
from typing import Dict, Optional, Callable
from ultralytics import YOLO
import torch


class IncrementalTrainer:
    """Huấn luyện gia tăng mô hình YOLO với dữ liệu mới."""

    def __init__(
        self,
        base_model_path: str = "models/best.pt",
        data_yaml: str = "data/data.yaml",
        output_dir: str = "models/incremental",
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Khởi tạo IncrementalTrainer.
        
        Args:
            base_model_path: Đường dẫn mô hình cơ sở để tiếp tục huấn luyện
            data_yaml: Đường dẫn file data.yaml
            output_dir: Thư mục lưu mô hình sau huấn luyện
            progress_callback: Hàm callback để báo cáo tiến độ
        """
        self.base_model_path = base_model_path
        self.data_yaml = data_yaml
        self.output_dir = Path(output_dir)
        self.progress_callback = progress_callback
        self.is_training = False
        self.current_model: Optional[YOLO] = None

    def _log(self, message: str):
        """Log message với callback."""
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)

    def prepare_combined_dataset(
        self,
        original_data_dir: str = "data",
        new_data_dir: str = "training_data/collected",
        output_data_dir: str = "data/combined",
    ) -> bool:
        """
        Kết hợp dữ liệu gốc với dữ liệu mới thu thập.
        
        Args:
            original_data_dir: Thư mục dữ liệu gốc
            new_data_dir: Thư mục dữ liệu mới
            output_data_dir: Thư mục output
        
        Returns:
            True nếu thành công
        """
        self._log("[INFO] Chuẩn bị dữ liệu kết hợp...")
        
        try:
            original_path = Path(original_data_dir)
            new_path = Path(new_data_dir)
            output_path = Path(output_data_dir)
            
            # Kiểm tra dữ liệu gốc
            if not (original_path / "images").exists():
                self._log(f"[ERROR] Không tìm thấy {original_path}/images")
                return False
            
            if not (new_path / "images").exists():
                self._log(f"[WARN] Không có dữ liệu mới để kết hợp")
                return True
            
            # Tạo thư mục output
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Copy cấu trúc từ dữ liệu gốc
            for split in ["train", "val", "test"]:
                src_images = original_path / "images" / split
                src_labels = original_path / "labels" / split
                
                if src_images.exists():
                    (output_path / "images" / split).mkdir(parents=True, exist_ok=True)
                    for img_file in src_images.glob("*"):
                        shutil.copy2(str(img_file), str(output_path / "images" / split / img_file.name))
                
                if src_labels.exists():
                    (output_path / "labels" / split).mkdir(parents=True, exist_ok=True)
                    for label_file in src_labels.glob("*"):
                        shutil.copy2(str(label_file), str(output_path / "labels" / split / label_file.name))
            
            # Thêm dữ liệu mới vào training set
            new_images = new_path / "images"
            new_labels = new_path / "labels"
            
            if new_images.exists():
                train_images = output_path / "images" / "train"
                train_images.mkdir(parents=True, exist_ok=True)
                
                for img_file in new_images.glob("*"):
                    if img_file.is_file():
                        shutil.copy2(str(img_file), str(train_images / img_file.name))
                
                # Copy labels
                if new_labels.exists():
                    train_labels = output_path / "labels" / "train"
                    train_labels.mkdir(parents=True, exist_ok=True)
                    
                    for label_file in new_labels.glob("*"):
                        if label_file.is_file():
                            shutil.copy2(str(label_file), str(train_labels / label_file.name))
            
            # Cập nhật data.yaml
            if (original_path / "data.yaml").exists():
                with open(original_path / "data.yaml", "r") as f:
                    data_config = yaml.safe_load(f)
                
                # Cập nhật đường dẫn
                data_config["path"] = str(output_path.absolute())
                
                with open(output_path / "data.yaml", "w") as f:
                    yaml.dump(data_config, f)
            
            self._log(f"[INFO] ✓ Dữ liệu kết hợp lưu tại: {output_path}")
            return True
            
        except Exception as e:
            self._log(f"[ERROR] Lỗi chuẩn bị dữ liệu: {e}")
            return False

    def train_incremental(
        self,
        epochs: int = 10,
        batch: int = 16,
        data_yaml: Optional[str] = None,
        **train_kwargs,
    ) -> bool:
        """
        Huấn luyện gia tăng mô hình.
        
        Args:
            epochs: Số epoch
            batch: Batch size
            data_yaml: Đường dẫn data.yaml (nếu None dùng mặc định)
            **train_kwargs: Các tham số khác cho YOLO.train()
        
        Returns:
            True nếu thành công
        """
        if self.is_training:
            self._log("[WARN] Đang huấn luyện, vui lòng chờ...")
            return False
        
        self.is_training = True
        
        try:
            # Kiểm tra GPU
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._log(f"[INFO] Sử dụng thiết bị: {device}")
            
            # Load model
            if not os.path.isfile(self.base_model_path):
                self._log(f"[ERROR] Không tìm thấy model: {self.base_model_path}")
                return False
            
            self._log(f"[INFO] Load model: {self.base_model_path}")
            self.current_model = YOLO(self.base_model_path)
            
            # Xác định data.yaml
            yaml_path = data_yaml or self.data_yaml
            if not os.path.isfile(yaml_path):
                self._log(f"[WARN] Không tìm thấy {yaml_path}, dùng mặc định: {self.data_yaml}")
                yaml_path = self.data_yaml
            
            # Thư mục output
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            self._log(f"[INFO] Bắt đầu huấn luyện gia tăng...")
            self._log(f"       - Epochs: {epochs}")
            self._log(f"       - Batch: {batch}")
            self._log(f"       - Data: {yaml_path}")
            
            # Default training kwargs
            default_kwargs = {
                "data": yaml_path,
                "epochs": epochs,
                "imgsz": 640,
                "batch": batch,
                "device": device,
                "workers": 2,
                "optimizer": "AdamW",
                "lr0": 0.0001,  # Học tốc độ nhỏ hơn để không quên dữ liệu cũ
                "augment": True,
                "mosaic": 0.8,
                "mixup": 0.05,
                "patience": max(5, epochs // 3),
                "name": "incremental",
                "project": str(self.output_dir.parent),
                "exist_ok": True,
            }
            
            # Merge với kwargs được truyền
            default_kwargs.update(train_kwargs)
            
            # Huấn luyện
            results = self.current_model.train(**default_kwargs)
            
            # Đánh giá
            self._log("[INFO] Đánh giá mô hình...")
            try:
                metrics = self.current_model.val()
                self._log(f"[INFO] mAP50:    {metrics.box.map50:.4f}")
                self._log(f"[INFO] mAP50-95: {metrics.box.map:.4f}")
            except Exception as e:
                self._log(f"[WARN] Lỗi đánh giá: {e}")
            
            # Tìm best.pt
            runs_dir = Path(default_kwargs["project"]) / "incremental"
            best_weights = runs_dir / "weights" / "best.pt"
            
            if best_weights.exists():
                # Copy best.pt vào models/
                output_model = Path("models") / "best_incremental.pt"
                output_model.parent.mkdir(exist_ok=True)
                shutil.copy2(str(best_weights), str(output_model))
                self._log(f"[INFO] ✓ Huấn luyện thành công!")
                self._log(f"       Model lưu tại: {output_model}")
                return True
            else:
                self._log(f"[ERROR] Không tìm thấy best.pt")
                return False
        
        except Exception as e:
            self._log(f"[ERROR] Lỗi huấn luyện: {e}")
            return False
        
        finally:
            self.is_training = False

    def get_training_status(self) -> Dict:
        """Lấy trạng thái huấn luyện."""
        return {
            "is_training": self.is_training,
            "base_model": self.base_model_path,
            "output_dir": str(self.output_dir),
        }
