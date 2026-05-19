"""
src/ui/admin/annotation_tool.py
Cửa sổ dán nhãn thủ công (manual bounding-box annotation) cho admin.

- Liệt kê ảnh trong thư mục được chọn (mặc định training_data/collected/images).
- Cho admin kéo chuột để vẽ bounding box.
- Chọn class (fire / smoke) cho mỗi box.
- Lưu file .txt theo định dạng YOLO trong thư mục labels song song.
- Hỗ trợ ảnh "normal" (lưu file .txt rỗng).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageTk = None  # type: ignore


# ── Palette (đồng bộ với phần còn lại của app) ───────────────────────
BG_DARK = "#11141d"
BG_CARD = "#1d212e"
BG_HOVER = "#2a3047"
ACCENT = "#f04e1a"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED = "#9ba4b4"
BORDER = "#2b3047"
SUCCESS = "#22c55e"
WARNING = "#fbbf24"

CLASSES = [(0, "fire", "#ef4444"), (1, "smoke", "#fbbf24")]
CLASS_COLOR = {cid: color for cid, _, color in CLASSES}
CLASS_NAME = {cid: name for cid, name, _ in CLASSES}

IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp")

# Kích thước canvas hiển thị tối đa (ảnh sẽ scale vừa khít, giữ tỉ lệ)
MAX_CANVAS_W = 900
MAX_CANVAS_H = 600


class AnnotationWindow(tk.Toplevel):
    """Cửa sổ dán nhãn thủ công."""

    def __init__(self, parent: tk.Misc, initial_dir: Optional[str] = None, initial_image: Optional[str] = None, on_saved: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.title("Dán nhãn thủ công (YOLO)")
        self.configure(bg=BG_DARK)
        self.geometry("1200x760")
        self.minsize(1000, 640)
        self._on_saved = on_saved

        if Image is None or ImageTk is None:
            messagebox.showerror(
                "Thiếu thư viện",
                "Cần cài Pillow:\n\n    pip install pillow",
                parent=self,
            )
            self.after(10, self.destroy)
            return

        # Trạng thái
        self.image_dir: Optional[Path] = None
        self.label_dir: Optional[Path] = None
        self.image_files: List[Path] = []
        self.current_index: int = -1

        self.current_pil: Optional["Image.Image"] = None
        self.current_tk: Optional["ImageTk.PhotoImage"] = None
        self.scale: float = 1.0  # tỉ lệ canvas / ảnh gốc
        self.canvas_img_id: Optional[int] = None

        # Boxes: List[Tuple[class_id, x1, y1, x2, y2]] tọa độ trên ẢNH GỐC
        self.boxes: List[Tuple[int, float, float, float, float]] = []
        # Mapping canvas item id -> index trong self.boxes (cho rect)
        self._rect_items: dict = {}
        # Offset của ảnh khi vẽ trên canvas (để căn giữa)
        self._img_offset: Tuple[int, int] = (0, 0)

        # Vẽ tạm
        self._drag_start: Optional[Tuple[int, int]] = None
        self._temp_rect: Optional[int] = None

        # Class hiện hành để gán cho box mới
        self.active_class = tk.IntVar(value=0)

        self._build_ui()

        # Khởi tạo thư mục
        if initial_image and os.path.isfile(initial_image):
            self._load_directory(Path(initial_image).parent)
            try:
                target = Path(initial_image).resolve()
                for i, f in enumerate(self.image_files):
                    if f.resolve() == target:
                        self.current_index = i
                        self._show_current()
                        break
            except Exception:
                pass
        elif initial_dir and os.path.isdir(initial_dir):
            self._load_directory(Path(initial_dir))

        # Phím tắt
        self.bind("<Left>", lambda _e: self._prev_image())
        self.bind("<Right>", lambda _e: self._next_image())
        self.bind("<Control-s>", lambda _e: self._save_current())
        self.bind("<Delete>", lambda _e: self._delete_last_box())
        self.bind("1", lambda _e: self.active_class.set(0))
        self.bind("2", lambda _e: self.active_class.set(1))

    # ────────────────────────────────────────────────────────────────
    # Build UI
    # ────────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=BG_DARK)
        header.pack(fill="x", padx=16, pady=(14, 6))

        tk.Label(
            header,
            text="✏️  Dán nhãn thủ công (YOLO)",
            font=("Segoe UI", 16, "bold"),
            bg=BG_DARK,
            fg=TEXT_PRIMARY,
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Kéo chuột trái để vẽ box. Phím 1=fire, 2=smoke, ←/→ chuyển ảnh, Ctrl+S lưu, Delete xoá box cuối.",
            font=("Segoe UI", 9),
            bg=BG_DARK,
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        # Thanh chọn thư mục
        dir_bar = tk.Frame(self, bg=BG_DARK)
        dir_bar.pack(fill="x", padx=16, pady=(6, 6))

        tk.Button(
            dir_bar,
            text="📁 Chọn thư mục ảnh",
            command=self._choose_directory,
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
        ).pack(side="left")

        self.dir_var = tk.StringVar(value="(chưa chọn)")
        tk.Label(
            dir_bar,
            textvariable=self.dir_var,
            font=("Segoe UI", 9),
            bg=BG_DARK,
            fg=TEXT_MUTED,
        ).pack(side="left", padx=(10, 0))

        # Body: trái = canvas, phải = danh sách + điều khiển
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        # ── Canvas ──
        left = tk.Frame(body, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER)
        left.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(
            left,
            bg="#0b0d15",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)

        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Configure>", lambda _e: self._show_current() if self.current_pil is not None else None)

        # ── Sidebar phải ──
        right = tk.Frame(body, bg=BG_DARK, width=320)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        # Chọn class
        cls_frame = tk.LabelFrame(
            right,
            text=" Class cho box mới ",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold"),
            bd=1,
            relief="solid",
        )
        cls_frame.pack(fill="x", pady=(0, 10))
        for cid, name, color in CLASSES:
            rb = tk.Radiobutton(
                cls_frame,
                text=f"  ■  {name}  (phím {cid + 1})",
                value=cid,
                variable=self.active_class,
                bg=BG_CARD,
                fg=color,
                selectcolor=BG_HOVER,
                activebackground=BG_CARD,
                activeforeground=color,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            )
            rb.pack(fill="x", padx=10, pady=4)

        # Danh sách box hiện tại
        boxes_frame = tk.LabelFrame(
            right,
            text=" Boxes trên ảnh ",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold"),
            bd=1,
            relief="solid",
        )
        boxes_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.boxes_listbox = tk.Listbox(
            boxes_frame,
            bg="#0b0d15",
            fg=TEXT_PRIMARY,
            selectbackground=ACCENT,
            relief="flat",
            font=("Consolas", 9),
            activestyle="none",
        )
        self.boxes_listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self.boxes_listbox.bind("<<ListboxSelect>>", lambda _e: self._highlight_selected_box())
        self.boxes_listbox.bind("<Double-Button-1>", lambda _e: self._relabel_selected_box())

        # Hướng dẫn relabel
        tk.Label(
            boxes_frame,
            text="💡 Chọn box rồi bấm \"Đổi class\" (hoặc double-click)\nđể đổi giữa fire ↔ smoke. Box sẽ đổi màu ngay.",
            bg=BG_CARD,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            justify="left",
        ).pack(fill="x", padx=6, pady=(0, 4))

        btns_box = tk.Frame(boxes_frame, bg=BG_CARD)
        btns_box.pack(fill="x", padx=6, pady=(0, 6))

        tk.Button(
            btns_box,
            text="🔁 Đổi class",
            command=self._relabel_selected_box,
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            relief="flat",
            padx=8,
            pady=4,
            cursor="hand2",
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            btns_box,
            text="🗑 Xoá box chọn",
            command=self._delete_selected_box,
            font=("Segoe UI", 9),
            bg="#5a3d3d",
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=8,
            pady=4,
            cursor="hand2",
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            btns_box,
            text="Xoá tất cả",
            command=self._delete_all_boxes,
            font=("Segoe UI", 9),
            bg=BG_HOVER,
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=8,
            pady=4,
            cursor="hand2",
        ).pack(side="left")

        # Điều hướng ảnh
        nav_frame = tk.Frame(right, bg=BG_DARK)
        nav_frame.pack(fill="x", pady=(0, 10))

        tk.Button(
            nav_frame,
            text="◀ Trước",
            command=self._prev_image,
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        tk.Button(
            nav_frame,
            text="Sau ▶",
            command=self._next_image,
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        # Lưu / Đánh dấu normal
        tk.Button(
            right,
            text="💾  Lưu nhãn (Ctrl+S)",
            command=self._save_current,
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT,
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(fill="x", pady=(0, 6))

        tk.Button(
            right,
            text="✓  Lưu là ảnh BÌNH THƯỜNG (không có lửa/khói)",
            command=self._save_as_normal,
            font=("Segoe UI", 9, "bold"),
            bg=SUCCESS,
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
            wraplength=280,
        ).pack(fill="x", pady=(0, 10))

        # Trạng thái
        self.status_var = tk.StringVar(value="Chọn thư mục để bắt đầu.")
        tk.Label(
            right,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            bg=BG_DARK,
            fg=TEXT_MUTED,
            wraplength=300,
            justify="left",
        ).pack(fill="x", pady=(4, 0))

    # ────────────────────────────────────────────────────────────────
    # Directory & navigation
    # ────────────────────────────────────────────────────────────────
    def _choose_directory(self) -> None:
        initial = str(self.image_dir) if self.image_dir else "training_data/collected/images"
        d = filedialog.askdirectory(parent=self, initialdir=initial, title="Chọn thư mục chứa ảnh")
        if d:
            self._load_directory(Path(d))

    def _load_directory(self, path: Path) -> None:
        if not path.is_dir():
            messagebox.showerror("Lỗi", f"Không phải thư mục: {path}", parent=self)
            return

        # Tự suy ra thư mục labels song song (..../images → ..../labels)
        # Nếu path tên là "images", labels = sibling "labels"
        # Ngược lại, dùng <path>/labels
        if path.name.lower() == "images" and (path.parent / "labels").exists():
            self.label_dir = path.parent / "labels"
        else:
            self.label_dir = path.parent / "labels" if path.name.lower() == "images" else path / "labels"

        self.label_dir.mkdir(parents=True, exist_ok=True)

        self.image_dir = path
        self.image_files = sorted(
            [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS]
        )
        self.dir_var.set(f"{path}  →  labels: {self.label_dir.name}/  ({len(self.image_files)} ảnh)")

        if not self.image_files:
            self.canvas.delete("all")
            self.boxes = []
            self._refresh_boxes_list()
            self.status_var.set("Thư mục không có ảnh.")
            return

        self.current_index = 0
        self._show_current()

    def _show_current(self) -> None:
        if not (0 <= self.current_index < len(self.image_files)):
            return

        img_path = self.image_files[self.current_index]
        try:
            pil = Image.open(str(img_path)).convert("RGB")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được ảnh: {e}", parent=self)
            return
        self.current_pil = pil

        iw, ih = pil.size
        # Scale vừa canvas
        s = min(MAX_CANVAS_W / iw, MAX_CANVAS_H / ih, 1.0)
        # Cũng dựa vào kích thước canvas thực tế (sau khi resize)
        self.update_idletasks()
        cw = max(self.canvas.winfo_width(), 200)
        ch = max(self.canvas.winfo_height(), 200)
        s = min(s, cw / iw, ch / ih)
        if s <= 0:
            s = 1.0
        self.scale = s
        disp_w, disp_h = max(1, int(iw * s)), max(1, int(ih * s))
        disp = pil.resize((disp_w, disp_h), Image.LANCZOS)
        self.current_tk = ImageTk.PhotoImage(disp)

        self.canvas.delete("all")
        self._rect_items.clear()
        ox = max(0, (cw - disp_w) // 2)
        oy = max(0, (ch - disp_h) // 2)
        self._img_offset = (ox, oy)
        self.canvas_img_id = self.canvas.create_image(
            ox, oy, image=self.current_tk, anchor="nw"
        )

        # Nạp label cũ nếu có
        self.boxes = self._read_label_file(img_path)
        self._redraw_boxes()
        self._refresh_boxes_list()

        self.status_var.set(
            f"[{self.current_index + 1}/{len(self.image_files)}]  {img_path.name}  "
            f"({iw}×{ih})  •  {len(self.boxes)} box"
        )

    def _prev_image(self) -> None:
        if not self.image_files:
            return
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current()

    def _next_image(self) -> None:
        if not self.image_files:
            return
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self._show_current()

    # ────────────────────────────────────────────────────────────────
    # Label I/O
    # ────────────────────────────────────────────────────────────────
    def _label_path_for(self, img_path: Path) -> Path:
        assert self.label_dir is not None
        return self.label_dir / (img_path.stem + ".txt")

    def _read_label_file(self, img_path: Path) -> List[Tuple[int, float, float, float, float]]:
        """Đọc file .txt YOLO và trả về list (cls, x1, y1, x2, y2) trong toạ độ ẢNH GỐC."""
        if not self.current_pil:
            return []
        iw, ih = self.current_pil.size
        lp = self._label_path_for(img_path)
        if not lp.exists():
            return []
        out: List[Tuple[int, float, float, float, float]] = []
        try:
            for line in lp.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                cls = int(float(parts[0]))
                cx, cy, bw, bh = (float(x) for x in parts[1:5])
                x1 = (cx - bw / 2.0) * iw
                y1 = (cy - bh / 2.0) * ih
                x2 = (cx + bw / 2.0) * iw
                y2 = (cy + bh / 2.0) * ih
                out.append((cls, x1, y1, x2, y2))
        except Exception:
            pass
        return out

    def _write_label_file(self, img_path: Path, empty: bool = False) -> bool:
        if not self.current_pil:
            return False
        iw, ih = self.current_pil.size
        lp = self._label_path_for(img_path)
        lp.parent.mkdir(parents=True, exist_ok=True)
        manual_marker = lp.with_suffix(".manual")

        if empty or not self.boxes:
            try:
                lp.write_text("", encoding="utf-8")
                manual_marker.write_text("", encoding="utf-8")
                return True
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi ghi file: {e}", parent=self)
                return False

        lines: List[str] = []
        for cls, x1, y1, x2, y2 in self.boxes:
            x1c, x2c = sorted([max(0.0, min(iw, x1)), max(0.0, min(iw, x2))])
            y1c, y2c = sorted([max(0.0, min(ih, y1)), max(0.0, min(ih, y2))])
            bw = (x2c - x1c) / iw
            bh = (y2c - y1c) / ih
            if bw <= 0.001 or bh <= 0.001:
                continue
            cx = ((x1c + x2c) / 2.0) / iw
            cy = ((y1c + y2c) / 2.0) / ih
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        try:
            lp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            manual_marker.write_text("", encoding="utf-8")
            return True
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi ghi file: {e}", parent=self)
            return False

    def _save_current(self) -> None:
        if not (0 <= self.current_index < len(self.image_files)):
            return
        img_path = self.image_files[self.current_index]
        ok = self._write_label_file(img_path, empty=False)
        if ok:
            self.status_var.set(
                f"✓  Đã lưu {len(self.boxes)} box → {self._label_path_for(img_path).name}  (đã chuyển sang 'Ảnh đã gán nhãn để huấn luyện')"
            )
            if self._on_saved:
                try:
                    self._on_saved()
                except Exception:
                    pass

    def _save_as_normal(self) -> None:
        if not (0 <= self.current_index < len(self.image_files)):
            return
        if self.boxes and not messagebox.askyesno(
            "Xác nhận",
            "Ảnh đang có box. Đánh dấu là BÌNH THƯỜNG sẽ ghi đè bằng file rỗng (xoá tất cả box). Tiếp tục?",
            parent=self,
        ):
            return
        img_path = self.image_files[self.current_index]
        if self._write_label_file(img_path, empty=True):
            self.boxes = []
            self.canvas.delete("box")
            self._rect_items.clear()
            self._refresh_boxes_list()
            self.status_var.set(f"✓  Đánh dấu BÌNH THƯỜNG: {img_path.name}")
            if self._on_saved:
                try:
                    self._on_saved()
                except Exception:
                    pass

    # ────────────────────────────────────────────────────────────────
    # Drawing
    # ────────────────────────────────────────────────────────────────
    def _to_image_coords(self, cx: int, cy: int) -> Tuple[float, float]:
        if self.scale <= 0:
            return float(cx), float(cy)
        ox, oy = self._img_offset
        return (cx - ox) / self.scale, (cy - oy) / self.scale

    def _to_canvas_coords(self, ix: float, iy: float) -> Tuple[float, float]:
        ox, oy = self._img_offset
        return ix * self.scale + ox, iy * self.scale + oy

    def _on_canvas_press(self, event: tk.Event) -> None:
        if self.current_pil is None:
            return
        self._drag_start = (event.x, event.y)
        if self._temp_rect is not None:
            self.canvas.delete(self._temp_rect)
        color = CLASS_COLOR[self.active_class.get()]
        self._temp_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline=color, width=2, dash=(4, 2)
        )

    def _on_canvas_drag(self, event: tk.Event) -> None:
        if self._drag_start is None or self._temp_rect is None:
            return
        x0, y0 = self._drag_start
        self.canvas.coords(self._temp_rect, x0, y0, event.x, event.y)

    def _on_canvas_release(self, event: tk.Event) -> None:
        if self._drag_start is None or self.current_pil is None:
            return
        x0, y0 = self._drag_start
        x1, y1 = event.x, event.y
        self._drag_start = None
        if self._temp_rect is not None:
            self.canvas.delete(self._temp_rect)
            self._temp_rect = None

        if abs(x1 - x0) < 5 or abs(y1 - y0) < 5:
            return  # quá nhỏ, bỏ qua

        ix1, iy1 = self._to_image_coords(min(x0, x1), min(y0, y1))
        ix2, iy2 = self._to_image_coords(max(x0, x1), max(y0, y1))
        cls = self.active_class.get()
        self.boxes.append((cls, ix1, iy1, ix2, iy2))
        self._redraw_boxes()
        self._refresh_boxes_list()

    def _redraw_boxes(self) -> None:
        self.canvas.delete("box")
        self._rect_items.clear()
        sel_idx = -1
        try:
            sel = self.boxes_listbox.curselection()
            if sel:
                sel_idx = int(sel[0])
        except Exception:
            sel_idx = -1
        for idx, (cls, x1, y1, x2, y2) in enumerate(self.boxes):
            cx1, cy1 = self._to_canvas_coords(x1, y1)
            cx2, cy2 = self._to_canvas_coords(x2, y2)
            color = CLASS_COLOR.get(cls, "#ffffff")
            width = 4 if idx == sel_idx else 2
            rid = self.canvas.create_rectangle(
                cx1, cy1, cx2, cy2, outline=color, width=width, tags=("box",)
            )
            # Nền nhãn để chữ dễ đọc
            name = CLASS_NAME.get(cls, str(cls))
            tag_w = max(40, 8 * len(name) + 8)
            self.canvas.create_rectangle(
                cx1, cy1, cx1 + tag_w, cy1 + 18,
                fill=color, outline=color, tags=("box",),
            )
            self.canvas.create_text(
                cx1 + 4,
                cy1 + 2,
                anchor="nw",
                text=name,
                fill="#000000",
                font=("Segoe UI", 9, "bold"),
                tags=("box",),
            )
            self._rect_items[rid] = idx

    def _highlight_selected_box(self) -> None:
        """Vẽ lại để khung box đang chọn dày hơn."""
        self._redraw_boxes()

    def _relabel_selected_box(self) -> None:
        """Đổi class của box đang chọn (fire ↔ smoke). Bbox sẽ đổi màu ngay."""
        sel = self.boxes_listbox.curselection()
        if not sel:
            messagebox.showinfo(
                "Chưa chọn box",
                "Hãy bấm chọn 1 box trong danh sách 'Boxes trên ảnh' trước, rồi mới đổi class.",
                parent=self,
            )
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.boxes)):
            return
        cls, x1, y1, x2, y2 = self.boxes[idx]
        new_cls = 1 if cls == 0 else 0
        self.boxes[idx] = (new_cls, x1, y1, x2, y2)
        # Đồng bộ radio để box mới sau sẽ kế thừa class này
        try:
            self.active_class.set(new_cls)
        except Exception:
            pass
        self._redraw_boxes()
        self._refresh_boxes_list()
        try:
            self.boxes_listbox.selection_clear(0, "end")
            self.boxes_listbox.selection_set(idx)
            self.boxes_listbox.activate(idx)
        except Exception:
            pass
        self.status_var.set(
            f"🔁  Box #{idx + 1}: {CLASS_NAME.get(cls)} → {CLASS_NAME.get(new_cls)}  (nhớ bấm Lưu)"
        )

    def _refresh_boxes_list(self) -> None:
        self.boxes_listbox.delete(0, "end")
        for i, (cls, x1, y1, x2, y2) in enumerate(self.boxes):
            self.boxes_listbox.insert(
                "end",
                f"{i + 1:2d}. {CLASS_NAME.get(cls, str(cls)):5s}  "
                f"({int(x1)},{int(y1)})→({int(x2)},{int(y2)})",
            )

    def _delete_selected_box(self) -> None:
        sel = self.boxes_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.boxes):
            del self.boxes[idx]
            self._redraw_boxes()
            self._refresh_boxes_list()

    def _delete_last_box(self) -> None:
        if self.boxes:
            self.boxes.pop()
            self._redraw_boxes()
            self._refresh_boxes_list()

    def _delete_all_boxes(self) -> None:
        if not self.boxes:
            return
        if messagebox.askyesno("Xác nhận", "Xoá tất cả box trên ảnh hiện tại?", parent=self):
            self.boxes = []
            self._redraw_boxes()
            self._refresh_boxes_list()


def open_annotation_window(
    parent: tk.Misc,
    initial_dir: Optional[str] = None,
    initial_image: Optional[str] = None,
    on_saved: Optional[Callable[[], None]] = None,
) -> AnnotationWindow:
    """Helper mở cửa sổ dán nhãn."""
    if initial_dir is None and initial_image is None:
        initial_dir = "training_data/collected/images"
    return AnnotationWindow(parent, initial_dir=initial_dir, initial_image=initial_image, on_saved=on_saved)
