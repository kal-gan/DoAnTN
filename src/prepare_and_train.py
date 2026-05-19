
import os
import sys
import shutil
import zipfile
import argparse
import glob
from pathlib import Path


def _find_yaml(root: Path) -> Path | None:
    """Tìm file data.yaml trong thư mục dataset."""
    for p in sorted(root.rglob("*.yaml")):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if "train" in txt and ("nc:" in txt or "names" in txt):
            return p
    return None


def _find_split_dir(root: Path, split: str) -> Path | None:
    """Tìm thư mục images/train hoặc images/valid trong dataset."""
    # Thử các tên phổ biến
    candidates = [
        root / "images" / split,
        root / split / "images",
        root / split,
    ]
    for p in candidates:
        if p.is_dir() and any(f.suffix.lower() in (".jpg",".jpeg",".png")
                               for f in p.iterdir()):
            return p
    # Tìm đệ quy
    for p in root.rglob("*"):
        if p.is_dir() and p.name == split:
            imgs = [f for f in p.iterdir()
                    if f.suffix.lower() in (".jpg",".jpeg",".png")]
            if imgs:
                return p
    return None


def _count_imgs(folder: Path) -> int:
    if not folder or not folder.is_dir():
        return 0
    return sum(1 for f in folder.rglob("*")
               if f.suffix.lower() in (".jpg",".jpeg",".png"))


def prepare_dataset(src: str, dest_data: str = "data") -> dict:
    """
    Giải nén / sao chép dataset vào data/.
    Trả về dict thống kê.
    """
    src_path = Path(src)
    dest = Path(dest_data)

    # ── Giải nén nếu là zip ───────────────────────────────────────────────
    if src_path.suffix.lower() == ".zip":
        print(f"[INFO] Giải nén {src_path.name} ...")
        extract_dir = src_path.parent / src_path.stem
        with zipfile.ZipFile(src_path, "r") as zf:
            zf.extractall(extract_dir)
        dataset_root = extract_dir
    else:
        dataset_root = src_path

    if not dataset_root.is_dir():
        print(f"[ERROR] Không tìm thấy thư mục: {dataset_root}")
        return {}

    # ── Tìm splits ────────────────────────────────────────────────────────
    # valid → val (Roboflow dùng "valid", YOLO dùng "val")
    split_map = {
        "train": _find_split_dir(dataset_root, "train"),
        "val":   _find_split_dir(dataset_root, "valid")
                 or _find_split_dir(dataset_root, "val"),
        "test":  _find_split_dir(dataset_root, "test"),
    }

    if split_map["train"] is None:
        print(f"[ERROR] Không tìm thấy thư mục train trong: {dataset_root}")
        print("        Kiểm tra cấu trúc: phải có images/train/ hoặc train/images/")
        return {}

    print("[INFO] Tìm thấy dataset:")
    for sn, sp in split_map.items():
        if sp:
            print(f"  {sn:6s}: {sp}  ({_count_imgs(sp)} ảnh)")

    # ── Tìm thư mục label tương ứng ───────────────────────────────────────
    def _label_dir(img_dir: Path) -> Path | None:
        # Thay "images" → "labels" trong path
        lbl = Path(str(img_dir).replace("images", "labels"))
        if lbl.is_dir():
            return lbl
        # Cùng cấp, tên "labels"
        lbl2 = img_dir.parent.parent / "labels" / img_dir.name
        if lbl2.is_dir():
            return lbl2
        return None

    # ── Sao chép vào data/ ────────────────────────────────────────────────
    stats: dict = {"train": 0, "val": 0, "test": 0,
                   "corrupted": 0, "too_small": 0, "no_label": 0}

    try:
        from PIL import Image as _PILImage
        pil_ok = True
    except ImportError:
        pil_ok = False

    for split_name, img_dir in split_map.items():
        if img_dir is None:
            continue
        lbl_dir = _label_dir(img_dir)

        dst_img = dest / "images" / split_name
        dst_lbl = dest / "labels" / split_name
        dst_img.mkdir(parents=True, exist_ok=True)
        dst_lbl.mkdir(parents=True, exist_ok=True)

        img_files = sorted(img_dir.rglob("*.jpg")) + \
                    sorted(img_dir.rglob("*.jpeg")) + \
                    sorted(img_dir.rglob("*.png"))

        copied = 0
        for img_f in img_files:
            # ── Kiểm tra ảnh ──────────────────────────────────────────
            if pil_ok:
                try:
                    with _PILImage.open(img_f) as im:
                        w, h = im.size
                    if w < 32 or h < 32:
                        stats["too_small"] += 1
                        continue
                except Exception:
                    stats["corrupted"] += 1
                    continue

            # ── Kiểm tra label ────────────────────────────────────────
            stem    = img_f.stem
            lbl_f   = (lbl_dir / (stem + ".txt")) if lbl_dir else None
            has_lbl = lbl_f is not None and lbl_f.is_file()

            if not has_lbl:
                stats["no_label"] += 1
                # Vẫn copy ảnh, tạo label trống (negative sample)

            shutil.copy2(img_f, dst_img / img_f.name)
            if has_lbl:
                shutil.copy2(lbl_f, dst_lbl / (stem + ".txt"))
            else:
                (dst_lbl / (stem + ".txt")).write_text("")

            copied += 1

        stats[split_name] = copied
        print(f"[INFO] {split_name:5s}: {copied} ảnh đã copy → {dst_img}")

    # ── Tìm và cập nhật data.yaml ─────────────────────────────────────────
    orig_yaml = _find_yaml(dataset_root)
    dst_yaml  = dest / "data.yaml"

    if orig_yaml:
        # Đọc yaml gốc, thay path
        txt = orig_yaml.read_text(encoding="utf-8")
        # Thay path tuyệt đối thành path tương đối
        abs_dest = str(dest.resolve()).replace("\\", "/")
        new_yaml = (
            f"path: {abs_dest}\n"
            "train: images/train\n"
            "val:   images/val\n"
        )
        if stats["test"] > 0:
            new_yaml += "test:  images/test\n"
        # Trích nc và names từ yaml gốc
        for line in txt.splitlines():
            stripped = line.strip()
            if stripped.startswith("nc:") or stripped.startswith("names"):
                new_yaml += line + "\n"
            elif stripped.startswith("-") and "names" not in new_yaml.split("\n")[-2:]:
                new_yaml += line + "\n"
        dst_yaml.write_text(new_yaml, encoding="utf-8")
        print(f"[INFO] Đã cập nhật {dst_yaml}")
    else:
        print("[WARN] Không tìm thấy data.yaml gốc. Dùng data.yaml hiện tại.")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Chuẩn bị dataset YOLOv8 và train model")
    parser.add_argument("--src",    required=True,
                        help="Đường dẫn tới file .zip hoặc thư mục dataset gốc")
    parser.add_argument("--epochs", type=int,  default=50,
                        help="Số epoch (mặc định 50)")
    parser.add_argument("--batch",  type=int,  default=8,
                        help="Batch size (mặc định 8)")
    parser.add_argument("--imgsz",  type=int,  default=640,
                        help="Kích thước ảnh (mặc định 640)")
    parser.add_argument("--base",   default="models/best.pt",
                        help="Model gốc để fine-tune (mặc định models/best.pt)")
    parser.add_argument("--no-train", action="store_true",
                        help="Chỉ chuẩn bị dataset, không train")
    args = parser.parse_args()

    print("=" * 60)
    print("  Chuẩn bị dataset")
    print("=" * 60)

    stats = prepare_dataset(args.src)
    if not stats:
        sys.exit(1)

    total = stats["train"] + stats["val"] + stats["test"]
    print(f"\n[INFO] Tổng kết:")
    print(f"  Train  : {stats['train']} ảnh")
    print(f"  Val    : {stats['val']} ảnh")
    print(f"  Test   : {stats['test']} ảnh")
    print(f"  Tổng   : {total} ảnh")
    if stats["corrupted"]:
        print(f"  Bỏ qua : {stats['corrupted']} ảnh lỗi")
    if stats["too_small"]:
        print(f"  Bỏ qua : {stats['too_small']} ảnh quá nhỏ (<32px)")
    if stats["no_label"]:
        print(f"  Thiếu label: {stats['no_label']} ảnh (dùng label trống)")

    if args.no_train:
        print("\n[INFO] --no-train được bật. Dừng tại đây.")
        return

    if total < 10:
        print(f"\n[WARN] Chỉ có {total} ảnh. Nên có ít nhất 50 ảnh để train hiệu quả.")
        ans = input("Tiếp tục train? (y/n): ").strip().lower()
        if ans != "y":
            return

    print("\n" + "=" * 60)
    print("  Bắt đầu huấn luyện")
    print("=" * 60)

    from train import train_model
    train_model(
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        model_path=args.base,
        data_yaml=str(Path("data") / "data.yaml"),
    )

    # Tìm và deploy best.pt
    candidates = sorted(
        glob.glob("runs/train/**/best.pt", recursive=True),
        key=os.path.getmtime, reverse=True)
    if candidates:
        best = candidates[0]
        print(f"\n[INFO] Best weights: {best}")
        ans = input("Copy vào models/best.pt? (y/n): ").strip().lower()
        if ans == "y":
            shutil.copy2(best, "models/best.pt")
            print("[INFO] ✓ Đã deploy → models/best.pt")


if __name__ == "__main__":
    main()
