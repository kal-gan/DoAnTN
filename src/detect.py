
import argparse

from .core.model_loader import CONFIDENCE_THRESHOLD, DEFAULT_MODEL_PATH
from .core.detector import FireSmokeDetector

__all__ = ["FireSmokeDetector"]


def main():
    parser = argparse.ArgumentParser(
        description="Phát hiện lửa và khói theo thời gian thực bằng YOLOv8 + OpenCV"
    )
    parser.add_argument(
        "--source", type=str, default="0",
        help="0 = camera laptop, hoặc đường dẫn tới video file (vd: videos/test.mp4)",
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL_PATH,
        help=f"Đường dẫn tới file mô hình .pt (mặc định: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--conf", type=float, default=CONFIDENCE_THRESHOLD,
        help=f"Ngưỡng tin cậy (mặc định: {CONFIDENCE_THRESHOLD})",
    )
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    detector = FireSmokeDetector(model_path=args.model, conf=args.conf)
    detector.run(source=source)

