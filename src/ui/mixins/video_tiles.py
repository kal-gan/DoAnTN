"""
src/ui/mixins/video_tiles.py
VideoTileMixin - quản lý lưới tile video và vẽ frame lên giao diện.
UI thiết kế lại: dark tile cards với border accent khi có cảnh báo.
"""
import math
from typing import Any, Dict, List, Optional

import cv2
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk

BG_DARK    = "#11141d"
BG_CARD    = "#1d212e"
BG_TILE    = "#12141e"
ACCENT     = "#f04e1a"
WARNING    = "#fbbf24"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED   = "#9ba4b4"
BORDER       = "#2b3047"
SUCCESS      = "#22c55e"

_DANGER_BG = {
    "LOW":      BG_TILE,
    "MEDIUM":   "#1a1505",
    "HIGH":     "#1a0808",
    "CRITICAL": "#1a0520",
}
_DANGER_BORDER = {
    "LOW":      BORDER,
    "MEDIUM":   WARNING,
    "HIGH":     "#ef4444",
    "CRITICAL": "#c026d3",
}


class VideoTileMixin:
    """Mixin xử lý tạo/cập nhật lưới tile hiển thị video."""

    # ──────────────────────────────────────────────────────────────────
    #  Quản lý tile
    # ──────────────────────────────────────────────────────────────────

    def _ensure_video_tiles(self, force: bool = False):
        expected_order = [int(source["id"]) for source in self.sources if source.get("id") is not None]  # type: ignore[attr-defined]
        layout_signature = tuple(expected_order)
        if not force and self.tile_layout_signature == layout_signature and self.video_tiles:  # type: ignore[attr-defined]
            return

        for child in self.video_grid_container.winfo_children():  # type: ignore[attr-defined]
            child.destroy()

        self.video_tiles = {}  # type: ignore[attr-defined]
        self.tile_order = expected_order  # type: ignore[attr-defined]
        self.tile_layout_signature = layout_signature  # type: ignore[attr-defined]

        reset_span = max(12, len(expected_order) + 3)
        for index in range(reset_span):
            self.video_grid_container.rowconfigure(index, weight=0, uniform="")  # type: ignore[attr-defined]
            self.video_grid_container.columnconfigure(index, weight=0, uniform="")  # type: ignore[attr-defined]

        if not expected_order:
            empty_frame = tk.Frame(self.video_grid_container, bg=BG_CARD)  # type: ignore[attr-defined]
            empty_frame.grid(row=0, column=0, sticky="nsew")
            self.video_grid_container.rowconfigure(0, weight=1)  # type: ignore[attr-defined]
            self.video_grid_container.columnconfigure(0, weight=1)  # type: ignore[attr-defined]
            inner = tk.Frame(empty_frame, bg=BG_CARD)
            inner.place(relx=0.5, rely=0.5, anchor="center")
            tk.Label(inner, text="📷", bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 32)).pack()
            tk.Label(inner, text="Chưa có nguồn camera",
                     bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 11)).pack(pady=(4, 0))
            tk.Label(inner, text="Thêm nguồn trong menu Admin → Nguồn",
                     bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 9)).pack(pady=(2, 0))
            return

        tile_count = len(expected_order)
        cols = max(1, math.ceil(math.sqrt(tile_count)))
        rows = math.ceil(tile_count / cols)
        for row in range(rows):
            self.video_grid_container.rowconfigure(row, weight=1, uniform="video-row")  # type: ignore[attr-defined]
        for col in range(cols):
            self.video_grid_container.columnconfigure(col, weight=1, uniform="video-col")  # type: ignore[attr-defined]

        for idx, tile_key in enumerate(expected_order):
            row, col = divmod(idx, cols)
            source = next(
                (item for item in self.sources if item.get("id") is not None and int(item["id"]) == tile_key),  # type: ignore[attr-defined]
                None,
            )
            title = self._source_to_text(source) if source is not None else f"Nguồn {idx + 1}"  # type: ignore[attr-defined]

            # Outer tile container (provides colored border)
            outer = tk.Frame(
                self.video_grid_container,  # type: ignore[attr-defined]
                bg=BORDER, padx=1, pady=1,
            )
            outer.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            outer.rowconfigure(0, weight=0)
            outer.rowconfigure(1, weight=1)
            outer.columnconfigure(0, weight=1)

            # Title bar
            title_bar = tk.Frame(outer, bg=BG_TILE, pady=6, padx=10)
            title_bar.grid(row=0, column=0, sticky="ew")
            title_bar.columnconfigure(0, weight=1)
            title_label = tk.Label(
                title_bar, text=title,
                bg=BG_TILE, fg=TEXT_MUTED,
                font=("Segoe UI", 8, "bold"), anchor="w",
            )
            title_label.grid(row=0, column=0, sticky="w")
            status_dot = tk.Label(
                title_bar, text="●",
                bg=BG_TILE, fg=TEXT_MUTED,
                font=("Segoe UI", 8),
            )
            status_dot.grid(row=0, column=1, sticky="e")

            # Video label
            label = tk.Label(outer, bg=BG_TILE, text="", anchor="center")
            label.grid(row=1, column=0, sticky="nsew")

            # Placeholder text
            placeholder = tk.Label(outer, bg=BG_TILE, fg=TEXT_MUTED,
                                   text="Đang chờ tín hiệu...",
                                   font=("Segoe UI", 9))
            placeholder.grid(row=1, column=0, sticky="nsew")

            self.video_tiles[tile_key] = {  # type: ignore[attr-defined]
                "frame": outer,
                "label": label,
                "placeholder": placeholder,
                "title_bar": title_bar,
                "title_label": title_label,
                "status_dot": status_dot,
                "photo": None,
                "active_labels": set(),
            }

            # Frame viewer disabled - kept UI simple for supervisors

    # ──────────────────────────────────────────────────────────────────
    #  Vẽ frame lên tile
    # ──────────────────────────────────────────────────────────────────

    def _draw_frame_to_tile(self, tile_key: int):
        if tile_key not in self.video_tiles or tile_key not in self.latest_frames:  # type: ignore[attr-defined]
            return

        tile = self.video_tiles[tile_key]  # type: ignore[attr-defined]
        label = tile["label"]
        frame = self.latest_frames[tile_key]  # type: ignore[attr-defined]

        target_w = max(120, label.winfo_width() - 4)
        target_h = max(90, label.winfo_height() - 4)
        if target_w <= 120 or target_h <= 90:
            self.update_idletasks()  # type: ignore[attr-defined]
            target_w = max(120, label.winfo_width() - 4)
            target_h = max(90, label.winfo_height() - 4)

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_h, frame_w = frame_rgb.shape[:2]
        scale = min(target_w / frame_w, target_h / frame_h)
        new_w, new_h = max(2, int(frame_w * scale)), max(2, int(frame_h * scale))

        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        resized = cv2.resize(frame_rgb, (new_w, new_h), interpolation=interpolation)

        image = Image.fromarray(resized)
        photo = ImageTk.PhotoImage(image=image)
        label.configure(image=photo, text="")
        tile["photo"] = photo

        # Ẩn placeholder khi đã có frame
        if tile.get("placeholder"):
            tile["placeholder"].grid_remove()

    def _redraw_all_tiles(self, _event=None):
        for tile_key in list(self.latest_frames.keys()):  # type: ignore[attr-defined]
            self._draw_frame_to_tile(tile_key)

    def _update_video(self, tile_key: int, stream_name: str, frame: Any, active_labels: Optional[set] = None):
        if frame is None:
            return
        if tile_key not in self.video_tiles:  # type: ignore[attr-defined]
            return

        tile = self.video_tiles[tile_key]  # type: ignore[attr-defined]
        alert_labels = set(active_labels or set())
        tile["active_labels"] = alert_labels

        # Obtain current danger level for this stream
        danger_level = "LOW"
        for stream in getattr(self, "stream_states", []):
            if int(stream.get("tile_key", -1)) == tile_key:
                danger_level = str(stream.get("danger_level") or "LOW")
                break

        tile_bg     = _DANGER_BG.get(danger_level, BG_TILE)
        border_col  = _DANGER_BORDER.get(danger_level, BORDER)

        # Cập nhật title + màu sắc border/dot theo trạng thái
        if "fire" in alert_labels:
            tile["frame"].config(bg=border_col)
            tile["title_bar"].config(bg=tile_bg)
            tile["title_label"].config(bg=tile_bg, fg=border_col, text=f"🔥 {stream_name}")
            tile["status_dot"].config(bg=tile_bg, fg=border_col)
            tile["label"].config(bg=tile_bg)
        elif "smoke" in alert_labels:
            tile["frame"].config(bg=WARNING)
            tile["title_bar"].config(bg=tile_bg)
            tile["title_label"].config(bg=tile_bg, fg=WARNING, text=f"💨 {stream_name}")
            tile["status_dot"].config(bg=tile_bg, fg=WARNING)
            tile["label"].config(bg=tile_bg)
        else:
            tile["frame"].config(bg=BORDER)
            tile["title_bar"].config(bg=BG_TILE)
            tile["title_label"].config(bg=BG_TILE, fg=TEXT_MUTED, text=stream_name)
            tile["status_dot"].config(bg=BG_TILE, fg=SUCCESS)
            tile["label"].config(bg=BG_TILE)

        self.latest_frames[tile_key] = frame  # type: ignore[attr-defined]
        self._draw_frame_to_tile(tile_key)

    def _set_tile_message(self, tile_key: int, message: str):
        tile = self.video_tiles.get(tile_key)  # type: ignore[attr-defined]
        if tile is None:
            return
        tile["label"].configure(image="", text="")
        tile["photo"] = None
        if tile.get("placeholder"):
            tile["placeholder"].config(text=message)
            tile["placeholder"].grid()

    def _clear_video_tiles(self, message: str):
        self.latest_frames.clear()  # type: ignore[attr-defined]
        # Flush pending frame buffer so stale frames don't render onto new tiles
        try:
            with self._latest_ui_frames_lock:  # type: ignore[attr-defined]
                self._latest_ui_frames.clear()  # type: ignore[attr-defined]
        except Exception:
            pass
        for tile in self.video_tiles.values():  # type: ignore[attr-defined]
            tile["label"].configure(image="", text="")
            tile["photo"] = None
            tile["frame"].config(bg=BORDER)
            tile["title_bar"].config(bg=BG_TILE)
            tile["title_label"].config(bg=BG_TILE, fg=TEXT_MUTED)
            tile["status_dot"].config(bg=BG_TILE, fg=TEXT_MUTED)
            tile["label"].config(bg=BG_TILE)
            if tile.get("placeholder"):
                tile["placeholder"].config(text=message, bg=BG_TILE)
                tile["placeholder"].grid()

    # ──────────────────────────────────────────────────────────────────
    #  Camera viewer (bấm đúp)
    # ──────────────────────────────────────────────────────────────────

    # Tracks open viewer windows: tile_key → CameraViewerWindow
    _viewer_windows: Dict[int, Any] = {}

    def _open_camera_viewer(self, tile_key: int):
        """Mở CameraViewerWindow cho tile_key; nếu đang mở thì focus lên."""
        existing = self.__class__._viewer_windows.get(tile_key)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass
            del self.__class__._viewer_windows[tile_key]

        # Find source name
        source = next(
            (s for s in getattr(self, "sources", [])
             if s.get("id") is not None and int(s["id"]) == tile_key),
            None,
        )
        name = self._source_to_text(source) if source else f"Nguồn {tile_key}"  # type: ignore[attr-defined]

        def _get_frame():
            return self.latest_frames.get(tile_key)  # type: ignore[attr-defined]

        def _get_stream_info():
            for s in getattr(self, "stream_states", []):
                if int(s.get("tile_key", -1)) == tile_key:
                    return s
            return None

        def _on_capture(image_path: str, label: str):
            try:
                user_id = int(self.admin_user["id"]) if self.admin_user else None  # type: ignore[attr-defined]
                self.db.add_training_capture(  # type: ignore[attr-defined]
                    image_path=image_path, label=label,
                    source_name=name, captured_by=user_id,
                )
                self._log(f"Đã lưu ảnh huấn luyện [{label}]: {image_path}")  # type: ignore[attr-defined]
            except Exception:
                pass

        try:
            from src.ui.widgets.camera_viewer import CameraViewerWindow
        except ImportError:
            from ui.widgets.camera_viewer import CameraViewerWindow  # type: ignore[no-redef]

        win = CameraViewerWindow(
            parent=self,  # type: ignore[arg-type]
            tile_key=tile_key,
            source_name=name,
            get_frame_fn=_get_frame,
            get_stream_info_fn=_get_stream_info,
            on_capture_fn=_on_capture,
        )
        self.__class__._viewer_windows[tile_key] = win

    def _focus_fire_tile(self, tile_key: int, source_name: str):
        """Auto-zoom: mở viewer khi phát hiện cháy ở cấp HIGH/CRITICAL."""
        return

    def _draw_detection_icons(self, frame: Any, labels_set: set):
        return
