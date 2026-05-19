"""
src/ui/admin/training_gallery.py
Gallery ảnh huấn luyện (dạng thumbnail + checkbox) cho admin.

- Đọc ảnh từ `training_data/collected/images/` và label tương ứng trong
  `training_data/collected/labels/`.
- Phân loại 2 nhóm:
    * Tự động gán: chỉ có `<stem>.txt` (do data_collector tạo lúc giám sát).
    * Chủ động gán: có thêm sentinel `<stem>.manual` (admin đã dán nhãn tay).
- Admin tick chọn ảnh nào sẽ tham gia huấn luyện.
- Cung cấp callback `get_selected_paths()` cho training_tab.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageTk  # type: ignore
    _PIL = True
except Exception:
    _PIL = False


BG_DARK = "#11141d"
BG_CARD = "#1d212e"
BG_HOVER = "#2a3047"
ACCENT = "#f04e1a"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED = "#9ba4b4"
BORDER = "#2b3047"
SUCCESS = "#22c55e"
WARNING = "#fbbf24"

THUMB_W, THUMB_H = 220, 150
COLS = 4

IMAGES_DIR = Path("training_data/collected/images")
LABELS_DIR = Path("training_data/collected/labels")


class _ThumbGrid(tk.Frame):
    """Lưới thumbnail có checkbox, có thể cuộn."""

    def __init__(self, parent: tk.Misc, on_open_annotation: Callable[[str], None], on_deleted: Optional[Callable[[], None]] = None):
        super().__init__(parent, bg=BG_CARD)
        self._on_open_annotation = on_open_annotation
        self._on_deleted = on_deleted
        self._photo_refs: List[Any] = []
        self._check_vars: Dict[str, tk.BooleanVar] = {}

        self.canvas = tk.Canvas(self, bg=BG_CARD, highlightthickness=0)
        self.scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG_CARD)

        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(self._win, width=e.width)
        )
        self.canvas.bind(
            "<Enter>",
            lambda _e: self.canvas.bind_all(
                "<MouseWheel>",
                lambda ev: self.canvas.yview_scroll(int(-ev.delta / 120), "units"),
            ),
        )
        self.canvas.bind(
            "<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>")
        )

    def populate(self, items: List[Tuple[Path, Path, str]]) -> None:
        """items: list of (img_path, label_path, summary_text)."""
        for w in self.inner.winfo_children():
            w.destroy()
        self._photo_refs = []
        # Giữ trạng thái checkbox cũ nếu cùng đường dẫn
        old_states = {k: v.get() for k, v in self._check_vars.items()}
        self._check_vars = {}

        if not items:
            tk.Label(
                self.inner,
                text="(không có ảnh trong nhóm này)",
                bg=BG_CARD,
                fg=TEXT_MUTED,
                font=("Segoe UI", 10),
            ).pack(padx=20, pady=30)
            return

        for c in range(COLS):
            self.inner.columnconfigure(c, weight=1)

        for idx, (img_path, _label_path, summary) in enumerate(items):
            row_i, col_i = divmod(idx, COLS)
            cell = tk.Frame(
                self.inner,
                bg=BG_DARK,
                padx=4,
                pady=4,
                highlightthickness=1,
                highlightbackground=BORDER,
            )
            cell.grid(row=row_i, column=col_i, padx=6, pady=6, sticky="nsew")

            photo = None
            if _PIL:
                try:
                    img = Image.open(str(img_path))
                    img.thumbnail((THUMB_W, THUMB_H))
                    photo = ImageTk.PhotoImage(img)
                    self._photo_refs.append(photo)
                except Exception:
                    photo = None

            if photo:
                img_lbl = tk.Label(cell, image=photo, bg=BG_DARK, cursor="hand2")
                img_lbl.image = photo  # type: ignore[attr-defined]
                img_lbl.pack()
                img_lbl.bind(
                    "<Button-1>", lambda _e, p=str(img_path): self._on_open_annotation(p)
                )
            else:
                tk.Label(
                    cell,
                    text="📷",
                    bg=BG_DARK,
                    fg=TEXT_MUTED,
                    font=("Segoe UI", 24),
                    width=12,
                    height=4,
                ).pack()

            row = tk.Frame(cell, bg=BG_DARK)
            row.pack(fill="x", pady=(3, 0))

            key = str(img_path)
            var = tk.BooleanVar(value=old_states.get(key, False))
            self._check_vars[key] = var

            chk = tk.Checkbutton(
                row,
                variable=var,
                bg=BG_DARK,
                fg=ACCENT,
                activebackground=BG_DARK,
                selectcolor=BG_CARD,
                highlightthickness=0,
                bd=0,
            )
            chk.pack(side="left")

            tk.Label(
                row,
                text=summary,
                bg=BG_DARK,
                fg=TEXT_MUTED,
                font=("Segoe UI", 7),
                anchor="w",
                wraplength=THUMB_W - 48,
                justify="left",
            ).pack(side="left", fill="x", expand=True)

            tk.Button(
                row,
                text="🗑",
                command=lambda p=str(img_path): self._delete_one(p),
                font=("Segoe UI", 8),
                bg="#5a3d3d",
                fg=TEXT_PRIMARY,
                activebackground="#7a4d4d",
                activeforeground=TEXT_PRIMARY,
                relief="flat",
                bd=0,
                padx=4,
                pady=0,
                cursor="hand2",
            ).pack(side="right")

    def _delete_one(self, img_path_str: str) -> None:
        p = Path(img_path_str)
        if not messagebox.askyesno(
            "Xác nhận",
            f"Xoá ảnh '{p.name}' và file nhãn của nó?",
            parent=self,
        ):
            return
        self._remove_paths([img_path_str])
        if self._on_deleted:
            try:
                self._on_deleted()
            except Exception:
                pass

    def _remove_paths(self, paths: List[str]) -> int:
        n_ok = 0
        for sp in paths:
            try:
                p = Path(sp)
                stem = p.stem
                if p.exists():
                    p.unlink()
                txt = LABELS_DIR / f"{stem}.txt"
                if txt.exists():
                    txt.unlink()
                manual = LABELS_DIR / f"{stem}.manual"
                if manual.exists():
                    manual.unlink()
                n_ok += 1
            except Exception:
                pass
        return n_ok

    def set_all(self, value: bool) -> None:
        for v in self._check_vars.values():
            v.set(value)

    def selected_paths(self) -> List[str]:
        return [p for p, v in self._check_vars.items() if v.get()]

    def count_selected(self) -> int:
        return sum(1 for v in self._check_vars.values() if v.get())

    def count_total(self) -> int:
        return len(self._check_vars)


class TrainingGallery(tk.Frame):
    """Gallery ảnh huấn luyện với 2 tab: Tự động gán / Chủ động gán."""

    def __init__(self, parent: tk.Misc, on_open_annotation: Callable[[Optional[str]], None]):
        super().__init__(parent, bg=BG_DARK)
        self._on_open_annotation = on_open_annotation

        # ── Header
        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill="x", pady=(0, 6))

        tk.Label(
            hdr,
            text="🖼  Ảnh huấn luyện",
            font=("Segoe UI", 12, "bold"),
            bg=BG_DARK,
            fg=TEXT_PRIMARY,
        ).pack(side="left")

        right_btns = tk.Frame(hdr, bg=BG_DARK)
        right_btns.pack(side="right")

        tk.Button(
            right_btns,
            text="🔄 Làm mới",
            command=self.refresh,
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            width=12,
            pady=5,
            cursor="hand2",
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            right_btns,
            text="✓ Chọn tất cả",
            command=self._select_current_all,
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            width=12,
            pady=5,
            cursor="hand2",
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            right_btns,
            text="☐ Bỏ chọn",
            command=self._select_current_none,
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            width=12,
            pady=5,
            cursor="hand2",
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            right_btns,
            text="🗑 Xoá đã chọn",
            command=self._delete_selected,
            font=("Segoe UI", 9, "bold"),
            bg="#5a3d3d",
            fg=TEXT_PRIMARY,
            activebackground="#7a4d4d",
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            width=12,
            pady=5,
            cursor="hand2",
        ).pack(side="left")

        # ── Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._auto_grid = _ThumbGrid(self.notebook, self._handle_open_annotation_path, on_deleted=self.refresh)
        self._manual_grid = _ThumbGrid(self.notebook, self._handle_open_annotation_path, on_deleted=self.refresh)
        self.notebook.add(self._auto_grid, text="🤖 Tự động gán (0)")
        self.notebook.add(self._manual_grid, text="✅ Ảnh đã gán nhãn để huấn luyện (0)")

        # ── Counter
        self.counter_var = tk.StringVar(value="0 ảnh đã chọn / 0 tổng")
        tk.Label(
            self,
            textvariable=self.counter_var,
            bg=BG_DARK,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(6, 0))

        self.refresh()

    # ────────────────────────────────────────────────────────────────
    def _handle_open_annotation_path(self, img_path: str) -> None:
        self._on_open_annotation(img_path)

    def _scan(self) -> Tuple[List[Tuple[Path, Path, str]], List[Tuple[Path, Path, str]]]:
        auto: List[Tuple[Path, Path, str]] = []
        manual: List[Tuple[Path, Path, str]] = []

        if not IMAGES_DIR.is_dir():
            return auto, manual

        LABELS_DIR.mkdir(parents=True, exist_ok=True)

        img_exts = (".jpg", ".jpeg", ".png", ".bmp")
        files = sorted(
            [p for p in IMAGES_DIR.iterdir() if p.is_file() and p.suffix.lower() in img_exts],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for p in files:
            stem = p.stem
            txt = LABELS_DIR / f"{stem}.txt"
            manual_marker = LABELS_DIR / f"{stem}.manual"

            n_boxes = 0
            if txt.exists():
                try:
                    n_boxes = sum(1 for line in txt.read_text(encoding="utf-8").splitlines() if line.strip())
                except Exception:
                    n_boxes = 0

            if not txt.exists():
                # Chưa có nhãn — bỏ qua (không train được)
                continue

            label_kind = "normal" if n_boxes == 0 else f"{n_boxes} box"
            summary = f"{p.name[:18]}\n{label_kind}"

            if manual_marker.exists():
                manual.append((p, txt, summary))
            else:
                auto.append((p, txt, summary))

        return auto, manual

    def refresh(self) -> None:
        auto, manual = self._scan()
        self._auto_grid.populate(auto)
        self._manual_grid.populate(manual)
        try:
            self.notebook.tab(0, text=f"🤖 Tự động gán ({len(auto)})")
            self.notebook.tab(1, text=f"✅ Ảnh đã gán nhãn để huấn luyện ({len(manual)})")
        except Exception:
            pass
        self._update_counter()

    def _update_counter(self) -> None:
        sel = self._auto_grid.count_selected() + self._manual_grid.count_selected()
        tot = self._auto_grid.count_total() + self._manual_grid.count_total()
        self.counter_var.set(f"{sel} ảnh đã chọn  /  {tot} tổng")

    def _current_grid(self) -> _ThumbGrid:
        idx = self.notebook.index(self.notebook.select()) if self.notebook.tabs() else 0
        return self._auto_grid if idx == 0 else self._manual_grid

    def _select_current_all(self) -> None:
        self._current_grid().set_all(True)
        self._update_counter()

    def _select_current_none(self) -> None:
        self._current_grid().set_all(False)
        self._update_counter()

    def _delete_selected(self) -> None:
        paths = self.selected_paths()
        if not paths:
            messagebox.showinfo(
                "Chưa chọn ảnh",
                "Hãy tick chọn ít nhất 1 ảnh để xoá.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Xác nhận",
            f"Xoá {len(paths)} ảnh đã chọn cùng file nhãn? (Không thể hoàn tác)",
            parent=self,
        ):
            return
        n = self._auto_grid._remove_paths(paths) + self._manual_grid._remove_paths(paths)
        self.refresh()
        messagebox.showinfo("Đã xoá", f"Đã xoá {n} ảnh.", parent=self)

    def selected_paths(self) -> List[str]:
        """Tổng hợp ảnh đã tick từ cả 2 tab."""
        return self._auto_grid.selected_paths() + self._manual_grid.selected_paths()
