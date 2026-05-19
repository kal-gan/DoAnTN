"""
src/ui/utils/danger_level.py
Đánh giá cấp độ nguy hiểm từ confidence + tỉ lệ diện tích bbox.

Levels (str): LOW | MEDIUM | HIGH | CRITICAL
"""
from typing import Any, Dict, List, Optional


# (min_conf, min_area_ratio) -> level
# area_ratio = bbox_area / frame_area
_THRESHOLDS = [
    # (min_conf, min_area_ratio, level)
    (0.85, 0.15, "CRITICAL"),
    (0.70, 0.08, "HIGH"),
    (0.50, 0.02, "MEDIUM"),
    (0.00, 0.00, "LOW"),
]

LEVEL_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def compute_danger_level(
    detections: List[Dict[str, Any]],
    frame_h: int,
    frame_w: int,
) -> str:
    """
    detections: list của dict có keys 'confidence', 'bbox' (x1,y1,x2,y2)
    Trả về: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    """
    if not detections or frame_h <= 0 or frame_w <= 0:
        return "LOW"

    frame_area = frame_h * frame_w
    best_level = "LOW"

    for det in detections:
        conf = float(det.get("confidence") or 0.0)
        bbox = det.get("bbox")
        if bbox and len(bbox) >= 4:
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            area = max(0, (x2 - x1) * (y2 - y1))
            ratio = area / frame_area
        elif det.get("x2") is not None:
            x1 = int(det.get("x1") or 0)
            y1 = int(det.get("y1") or 0)
            x2 = int(det.get("x2") or 0)
            y2 = int(det.get("y2") or 0)
            area = max(0, (x2 - x1) * (y2 - y1))
            ratio = area / frame_area
        else:
            ratio = 0.0

        for min_conf, min_ratio, level in _THRESHOLDS:
            if conf >= min_conf and ratio >= min_ratio:
                if LEVEL_ORDER.get(level, 0) > LEVEL_ORDER.get(best_level, 0):
                    best_level = level
                break

    return best_level


def level_requires_sound(level: str) -> bool:
    return LEVEL_ORDER.get(level, 0) >= LEVEL_ORDER["MEDIUM"]


def level_requires_email(level: str) -> bool:
    return LEVEL_ORDER.get(level, 0) >= LEVEL_ORDER["HIGH"]
