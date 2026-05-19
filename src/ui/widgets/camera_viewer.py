"""
src/ui/widgets/camera_viewer.py
CameraViewerWindow - cửa sổ xem chi tiết camera với zoom/pan, chụp ảnh huấn luyện.
Mở bằng cách bấm đúp vào tile video.
"""
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from typing import Any, Dict, Optional, Callable

import cv2
from PIL import Image, ImageTk

BG_DARK      = "#11141d"
BG_CARD      = "#1d212e"
BG_HOVER     = "#2a3047"
BG_TILE      = "#12141e"
ACCENT       = "#f04e1a"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED   = "#9ba4b4"
BORDER       = "#2b3047"
WARNING      = "#fbbf24"
DANGER       = "#ef4444"
SUCCESS      = "#22c55e"

_DANGER_COLORS = {
    "LOW":      "#22c55e",
    "MEDIUM":   "#fbbf24",
    "HIGH":     "#ef4444",
    "CRITICAL": "#c026d3",
}
_DANGER_LABELS = {
    "LOW":      "THẤP",
    "MEDIUM":   "TRUNG BÌNH",
    "HIGH":     "CAO",
    "CRITICAL": "NGUY HIỂM",
}


class CameraViewerWindow(tk.Toplevel):
    """
    Cửa sổ xem chi tiết camera với:
    - Zoom / pan bằng chuột (scroll = zoom, drag = pan)
    - Hiển thị cấp độ nguy hiểm
    - Nút chụp ảnh → lưu vào training_data/ (phân loại fire/smoke/normal)
    - Auto-update từ latest_frames của app
    """

    def __init__(self, parent: tk.Misc, tile_key: int, source_name: str,
                 get_frame_fn: Callable[[], Optional[Any]],
                 get_stream_info_fn: Callable[[], Optional[Dict[str, Any]]],
                 on_capture_fn: Optional[Callable[[str, str], None]] = None):
        """
        parent           : cửa sổ cha
        tile_key         : id nguồn
        source_name      : tên hiển thị
        get_frame_fn     : callable → np.ndarray|None (BGR frame hiện tại)
        get_stream_info_fn: callable → dict stream state hoặc None
        on_capture_fn    : callback(image_path, label) sau khi chụp
        """
        super().__init__(parent)
        self.tile_key          = tile_key
        self.source_name       = source_name
        self._get_frame        = get_frame_fn
        self._get_stream_info  = get_stream_info_fn
        self._on_capture       = on_capture_fn

        self.title(f"📷  {source_name}")
        self.geometry("1100x720")
        self.minsize(640, 480)
        self.configure(bg=BG_DARK)
        self.transient(parent)

        # Zoom / pan state
        self._zoom: float = 1.0
        self._zoom_min: float = 0.2
        self._zoom_max: float = 8.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._drag_start: Optional[tuple] = None
        self._pan_start: Optional[tuple] = None

        # UI state
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._last_raw_frame: Optional[Any] = None
        self._after_id: Optional[str] = None
        self._danger_var = tk.StringVar(value="—")
        self._danger_color = tk.StringVar(value=TEXT_MUTED)
        self._conf_var = tk.StringVar(value="")
        self._fps_var = tk.StringVar(value="")
        self._info_var = tk.StringVar(value=source_name)

        self._build_ui()
        self._bind_events()
        self._schedule_update()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ──────────────────────────────────────────────────────────────────
    #  UI
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Top bar ───────────────────────────────────────────────────
        top = tk.Frame(self, bg=BG_CARD, pady=8, padx=14)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(2, weight=1)

        tk.Label(top, textvariable=self._info_var,
                 bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w")

        # Danger level badge
        self._danger_badge = tk.Label(top, textvariable=self._danger_var,
                                      bg=BG_CARD, fg=TEXT_MUTED,
                                      font=("Segoe UI", 9, "bold"),
                                      padx=10, pady=3, relief="flat")
        self._danger_badge.grid(row=0, column=1, padx=(14, 0), sticky="w")

        tk.Label(top, textvariable=self._conf_var, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(12, 0))

        # Zoom controls
        zoom_frame = tk.Frame(top, bg=BG_CARD)
        zoom_frame.grid(row=0, column=3, sticky="e")
        self._zoom_var = tk.StringVar(value="100%")
        tk.Label(zoom_frame, textvariable=self._zoom_var,
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 9), width=6).pack(side="left")
        tk.Button(zoom_frame, text="−", bg=BG_HOVER, fg=TEXT_PRIMARY,
                  relief="flat", bd=0, padx=8, pady=2, font=("Segoe UI", 10),
                  cursor="hand2", command=lambda: self._zoom_by(0.8)).pack(side="left")
        tk.Button(zoom_frame, text="+", bg=BG_HOVER, fg=TEXT_PRIMARY,
                  relief="flat", bd=0, padx=8, pady=2, font=("Segoe UI", 10),
                  cursor="hand2", command=lambda: self._zoom_by(1.25)).pack(side="left", padx=(2, 0))
        tk.Button(zoom_frame, text="⊡ Reset", bg=BG_HOVER, fg=TEXT_MUTED,
                  relief="flat", bd=0, padx=8, pady=2, font=("Segoe UI", 9),
                  cursor="hand2", command=self._reset_view).pack(side="left", padx=(4, 0))

        # FPS label
        tk.Label(top, textvariable=self._fps_var, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Segoe UI", 8)).grid(row=0, column=4, padx=(10, 0), sticky="e")

        # ── Canvas (video) ─────────────────────────────────────────────
        canvas_frame = tk.Frame(self, bg=BG_TILE)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(canvas_frame, bg=BG_TILE, highlightthickness=0, cursor="crosshair")
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # ── Bottom toolbar ─────────────────────────────────────────────
        bot = tk.Frame(self, bg=BG_CARD, pady=8, padx=14)
        bot.grid(row=2, column=0, sticky="ew")

        tk.Label(bot, text="Chụp lưu để huấn luyện:", bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(side="left")

        self._capture_label_var = tk.StringVar(value="fire")
        for lbl, color in [("🔥 Lửa", ACCENT), ("💨 Khói", WARNING), ("✓ Bình thường", SUCCESS)]:
            val = "fire" if "Lửa" in lbl else ("smoke" if "Khói" in lbl else "normal")
            rb = tk.Radiobutton(bot, text=lbl, variable=self._capture_label_var, value=val,
                                bg=BG_CARD, fg=color, selectcolor=BG_HOVER,
                                activebackground=BG_CARD, activeforeground=color,
                                font=("Segoe UI", 9), cursor="hand2")
            rb.pack(side="left", padx=(10, 0))

        tk.Button(bot, text="📸  Chụp ảnh", bg=ACCENT, fg="white",
                  relief="flat", bd=0, padx=14, pady=5, font=("Segoe UI", 9, "bold"),
                  cursor="hand2", activebackground="#c73508", activeforeground="white",
                  command=self._do_capture).pack(side="right")

        tk.Label(bot, text="[Scroll] Zoom  [Drag] Pan  [Esc] Đóng",
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 8)).pack(side="right", padx=(0, 16))

        self._status_var = tk.StringVar(value="")
        tk.Label(bot, textvariable=self._status_var, bg=BG_CARD, fg=SUCCESS,
                 font=("Segoe UI", 8)).pack(side="left", padx=(16, 0))

    # ──────────────────────────────────────────────────────────────────
    #  Events
    # ──────────────────────────────────────────────────────────────────

    def _bind_events(self):
        self._canvas.bind("<MouseWheel>",      self._on_scroll)
        self._canvas.bind("<Button-4>",        self._on_scroll)   # Linux scroll up
        self._canvas.bind("<Button-5>",        self._on_scroll)   # Linux scroll down
        self._canvas.bind("<ButtonPress-1>",   self._on_drag_start)
        self._canvas.bind("<B1-Motion>",       self._on_drag_move)
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.bind("<Escape>", lambda _: self._on_close())

    def _on_scroll(self, event):
        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            self._zoom_by(1.15, pivot=(event.x, event.y))
        else:
            self._zoom_by(1 / 1.15, pivot=(event.x, event.y))

    def _on_drag_start(self, event):
        self._drag_start = (event.x, event.y)
        self._pan_start  = (self._pan_x, self._pan_y)
        self._canvas.config(cursor="fleur")

    def _on_drag_move(self, event):
        if self._drag_start and self._pan_start:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self._pan_x = self._pan_start[0] + dx
            self._pan_y = self._pan_start[1] + dy
            self._render_frame()

    def _on_drag_end(self, event):
        self._drag_start = None
        self._pan_start  = None
        self._canvas.config(cursor="crosshair")

    # ──────────────────────────────────────────────────────────────────
    #  Zoom / pan helpers
    # ──────────────────────────────────────────────────────────────────

    def _zoom_by(self, factor: float, pivot: Optional[tuple] = None):
        old_zoom = self._zoom
        new_zoom = max(self._zoom_min, min(self._zoom_max, self._zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-6:
            return
        if pivot:
            # Zoom around pivot point
            px, py = pivot
            self._pan_x = px - (px - self._pan_x) * (new_zoom / old_zoom)
            self._pan_y = py - (py - self._pan_y) * (new_zoom / old_zoom)
        self._zoom = new_zoom
        self._zoom_var.set(f"{int(self._zoom * 100)}%")
        self._render_frame()

    def _reset_view(self):
        self._zoom  = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._zoom_var.set("100%")
        self._render_frame()

    # ──────────────────────────────────────────────────────────────────
    #  Render
    # ──────────────────────────────────────────────────────────────────

    def _render_frame(self):
        if self._last_raw_frame is None:
            return
        try:
            self._canvas.update_idletasks()
            cw = self._canvas.winfo_width()
            ch = self._canvas.winfo_height()
            if cw < 10 or ch < 10:
                return

            frame = self._last_raw_frame
            fh, fw = frame.shape[:2]

            # Base scale to fit canvas (zoom=1.0 → fit)
            base_scale = min(cw / fw, ch / fh)
            scale = base_scale * self._zoom
            nw = max(1, int(fw * scale))
            nh = max(1, int(fh * scale))

            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (nw, nh), interpolation=interp)

            img = Image.fromarray(resized)
            self._photo = ImageTk.PhotoImage(image=img)

            # Draw
            self._canvas.delete("all")
            cx = cw // 2 + int(self._pan_x)
            cy = ch // 2 + int(self._pan_y)
            self._canvas.create_image(cx, cy, image=self._photo, anchor="center")
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    #  Update loop
    # ──────────────────────────────────────────────────────────────────

    def _schedule_update(self):
        self._after_id = self.after(40, self._update_tick)  # ~25 fps

    def _update_tick(self):
        self._after_id = None
        if not self.winfo_exists():
            return
        frame = self._get_frame()
        if frame is not None:
            self._last_raw_frame = frame.copy()
            self._render_frame()

        stream_info = self._get_stream_info()
        if stream_info:
            labels = stream_info.get("active_labels") or set()
            conf   = float(stream_info.get("active_conf") or 0.0)
            danger = stream_info.get("danger_level") or ("" if not labels else "LOW")
            color  = _DANGER_COLORS.get(str(danger), TEXT_MUTED)
            label_vn = _DANGER_LABELS.get(str(danger), "")
            label_type = "fire" if "fire" in labels else ("smoke" if "smoke" in labels else "")
            prefix = "🔥" if label_type == "fire" else ("💨" if label_type == "smoke" else "")
            self._danger_var.set(f"{prefix}  Cấp độ: {label_vn}" if label_vn else "—")
            self._danger_badge.config(fg=color)
            self._conf_var.set(f"Độ tin cậy: {conf:.0%}" if conf > 0 else "")
            fps = stream_info.get("display_fps") or 0
            self._fps_var.set(f"{fps:.1f} FPS" if fps else "")

        self._schedule_update()

    # ──────────────────────────────────────────────────────────────────
    #  Chụp ảnh
    # ──────────────────────────────────────────────────────────────────

    def _do_capture(self):
        frame = self._last_raw_frame
        if frame is None:
            messagebox.showwarning("Chưa có ảnh", "Không có frame để chụp.", parent=self)
            return
        label = self._capture_label_var.get()
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        out_dir = os.path.abspath(os.path.join("training_data", label))
        os.makedirs(out_dir, exist_ok=True)
        fname = f"{label}_{ts}.jpg"
        fpath = os.path.join(out_dir, fname)
        try:
            cv2.imwrite(fpath, frame)
        except Exception as exc:
            messagebox.showerror("Lỗi lưu ảnh", str(exc), parent=self)
            return
        self._status_var.set(f"✔  Đã lưu: {fname}")
        self.after(3000, lambda: self._status_var.set("") if self.winfo_exists() else None)
        if self._on_capture:
            try:
                self._on_capture(fpath, label)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────
    #  Close
    # ──────────────────────────────────────────────────────────────────

    def _on_close(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self.destroy()
