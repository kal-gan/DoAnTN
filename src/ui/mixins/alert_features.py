"""
src/ui/mixins/alert_features.py
AlertFeaturesMixin - âm thanh cảnh báo, popup cảnh báo, email, gallery ảnh, training, giới hạn dung lượng.
"""
import os
import sys
import smtplib
import threading
import tkinter as tk
from tkinter import ttk
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import Any, Dict, List

try:
    from PIL import Image, ImageTk
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

BG_DARK      = "#11141d"
BG_CARD      = "#1d212e"
BG_HOVER     = "#2a3047"
ACCENT       = "#f04e1a"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED   = "#9ba4b4"
BORDER       = "#2b3047"
WARNING      = "#fbbf24"
DANGER       = "#ef4444"
SUCCESS      = "#22c55e"


class AlertFeaturesMixin:
    """Mixin cung cấp: âm thanh cảnh báo, popup, gallery ảnh, giới hạn dung lượng."""

    # ──────────────────────────────────────────────────────────────────
    #  Âm thanh cảnh báo (phân cấp)
    # ──────────────────────────────────────────────────────────────────

    def _play_alert_sound(self, danger_level: str = "MEDIUM"):
        """Phát âm thanh cảnh báo phân cấp trong daemon thread."""
        if not getattr(self, "sound_alert_enabled", None):
            return
        try:
            if not self.sound_alert_enabled.get():  # type: ignore[attr-defined]
                return
        except Exception:
            return

        volume = 80
        try:
            volume = max(0, min(100, int(self.sound_alert_volume.get())))  # type: ignore[attr-defined]
        except Exception:
            pass
        if volume == 0:
            return

        # Pattern by level: MEDIUM=2 beep, HIGH=3, CRITICAL=4+flash
        _patterns = {
            "LOW":      [(660, 160)],
            "MEDIUM":   [(880, 200), (660, 160)],
            "HIGH":     [(1000, 200), (880, 180), (660, 160)],
            "CRITICAL": [(1200, 180), (1000, 160), (1200, 180), (880, 200)],
        }
        beeps = _patterns.get(str(danger_level).upper(), _patterns["MEDIUM"])

        def _beep():
            try:
                if sys.platform == "win32":
                    import ctypes
                    import winsound
                    winmm = ctypes.WinDLL("winmm", use_last_error=True)
                    prev_vol = ctypes.c_uint32(0)
                    winmm.waveOutGetVolume(None, ctypes.byref(prev_vol))
                    target = int(volume / 100 * 0xFFFF)
                    packed = (target << 16) | target
                    winmm.waveOutSetVolume(None, packed)
                    try:
                        for freq, dur in beeps:
                            winsound.Beep(freq, dur)
                    finally:
                        winmm.waveOutSetVolume(None, prev_vol.value)
                else:
                    sys.stdout.write("\a" * len(beeps))
                    sys.stdout.flush()
            except Exception:
                pass

        threading.Thread(target=_beep, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────
    #  Giới hạn dung lượng alerts/
    # ──────────────────────────────────────────────────────────────────

    def _cleanup_alerts_folder(self):
        """Xóa file cũ trong alerts/ theo giới hạn dung lượng và số ngày lưu."""
        max_mb = 300
        max_days = 7
        try:
            if hasattr(self, "alerts_max_mb"):
                max_mb = max(1, int(self.alerts_max_mb.get()))  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            if hasattr(self, "alerts_max_days"):
                max_days = max(1, min(7, int(self.alerts_max_days.get())))  # type: ignore[attr-defined]
        except Exception:
            pass

        alerts_dir = os.path.abspath("alerts")
        if not os.path.isdir(alerts_dir):
            return
        try:
            cutoff = (datetime.now() - timedelta(days=max_days)).timestamp()
            files: List = []
            for fname in os.listdir(alerts_dir):
                fpath = os.path.join(alerts_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                mtime = os.path.getmtime(fpath)
                # Delete by age first
                if mtime < cutoff:
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
                    continue
                files.append((mtime, fpath))
            # Then enforce size limit on remaining files (oldest first)
            files.sort()
            total = sum(os.path.getsize(p) for _, p in files)
            limit = max_mb * 1024 * 1024
            while total > limit and files:
                _, fpath = files.pop(0)
                try:
                    fsize = os.path.getsize(fpath)
                    os.remove(fpath)
                    total -= fsize
                except Exception:
                    pass
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    #  Popup cảnh báo
    # ──────────────────────────────────────────────────────────────────

    def _show_alert_popup(self, data: Dict[str, Any]):
        """Hiển thị cửa sổ popup cảnh báo trên UI thread."""
        label_type   = str(data.get("label", "fire"))
        source_name  = str(data.get("source_name", "-"))
        image_path   = data.get("image_path")
        danger_level = str(data.get("danger_level") or "LOW")
        tile_key     = data.get("tile_key")

        _level_vi = {"LOW": "THẤP", "MEDIUM": "TRUNG BÌNH",
                     "HIGH": "CAO", "CRITICAL": "NGUY HIỂM"}
        _level_colors = {"LOW": SUCCESS, "MEDIUM": WARNING,
                         "HIGH": DANGER, "CRITICAL": "#c026d3"}

        popup = tk.Toplevel(self)  # type: ignore[arg-type]
        popup.title("⚠ CẢNH BÁO PHÁT HIỆN")
        popup.configure(bg=BG_CARD)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        try:
            self.update_idletasks()  # type: ignore[attr-defined]
            screen_w = self.winfo_screenwidth()  # type: ignore[attr-defined]
        except Exception:
            screen_w = 1920
        popup_w, popup_h = 360, 330
        popup.geometry(f"{popup_w}x{popup_h}+{screen_w - popup_w - 20}+40")

        header_color = _level_colors.get(danger_level, DANGER)
        header = tk.Frame(popup, bg=header_color, pady=10)
        header.pack(fill="x")
        icon_text = "🔥  PHÁT HIỆN LỬA!" if label_type == "fire" else "💨  PHÁT HIỆN KHÓI!"
        tk.Label(header, text=icon_text, bg=header_color, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(padx=14)
        level_vi = _level_vi.get(danger_level, danger_level)
        tk.Label(header, text=f"Cấp độ nguy hiểm: {level_vi}",
                 bg=header_color, fg="white",
                 font=("Segoe UI", 9)).pack(padx=14)

        info_frame = tk.Frame(popup, bg=BG_CARD, pady=8, padx=14)
        info_frame.pack(fill="x")
        tk.Label(info_frame, text=f"📷  {source_name}", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 10)).pack(anchor="w")
        confidence = float(data.get("confidence", 0.0))
        tk.Label(info_frame, text=f"🔎  Độ tin cậy: {confidence*100:.1f}%", bg=BG_CARD,
                 fg=TEXT_PRIMARY, font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
        ts = datetime.now().strftime("%H:%M:%S  %d/%m/%Y")
        tk.Label(info_frame, text=f"🕐  {ts}", bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        img_frame = tk.Frame(popup, bg=BG_CARD)
        img_frame.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        if _PIL_AVAILABLE and image_path and os.path.isfile(str(image_path)):
            try:
                img = Image.open(str(image_path))
                img.thumbnail((330, 120))
                photo = ImageTk.PhotoImage(img)
                img_lbl = tk.Label(img_frame, image=photo, bg=BG_CARD)
                img_lbl.image = photo  # type: ignore[attr-defined]
                img_lbl.pack()
            except Exception:
                tk.Label(img_frame, text="[Không tải được ảnh]", bg=BG_CARD,
                         fg=TEXT_MUTED, font=("Segoe UI", 9)).pack(pady=8)
        else:
            tk.Label(img_frame, text="[Chưa có ảnh]", bg=BG_CARD,
                     fg=TEXT_MUTED, font=("Segoe UI", 9)).pack(pady=8)

        btn_row = tk.Frame(popup, bg=BG_CARD, pady=8)
        btn_row.pack(fill="x", padx=14)
        countdown_var = tk.StringVar(value="Tự đóng: 8s")
        tk.Label(btn_row, textvariable=countdown_var, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left")

        def _go_gallery():
            popup.destroy()
            if hasattr(self, "_show_page"):
                self._show_page("gallery")  # type: ignore[attr-defined]
            if hasattr(self, "_refresh_gallery"):
                self._refresh_gallery()  # type: ignore[attr-defined]

        tk.Button(btn_row, text="Thư viện", bg=BG_DARK, fg=TEXT_MUTED,
                  relief="flat", bd=0, padx=10, pady=4, font=("Segoe UI", 9),
                  cursor="hand2", command=_go_gallery).pack(side="right", padx=(0, 6))
        tk.Button(btn_row, text="Đóng", bg=header_color, fg="white",
                  relief="flat", bd=0, padx=14, pady=4, font=("Segoe UI", 9),
                  cursor="hand2", command=popup.destroy).pack(side="right")

        _remaining = [8]

        def _tick():
            if not popup.winfo_exists():
                return
            _remaining[0] -= 1
            if _remaining[0] <= 0:
                try:
                    popup.destroy()
                except Exception:
                    pass
                return
            try:
                countdown_var.set(f"Tự đóng: {_remaining[0]}s")
                popup.after(1000, _tick)
            except Exception:
                pass

        popup.after(1000, _tick)

    # ──────────────────────────────────────────────────────────────────
    #  Gallery trang (video clips ~20s trước cảnh báo)
    # ──────────────────────────────────────────────────────────────────

    def _create_gallery_page(self) -> tk.Frame:
        page = tk.Frame(self.page_container, bg=BG_DARK)  # type: ignore[attr-defined]

        # Header
        hdr = tk.Frame(page, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(hdr, text="Thư viện video cảnh báo", bg=BG_DARK, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Button(hdr, text="📂  Mở thư mục", bg=BG_CARD, fg=TEXT_MUTED,
                  activebackground=BG_HOVER, activeforeground=TEXT_PRIMARY,
                  relief="flat", bd=0, padx=12, pady=6, font=("Segoe UI", 9),
                  cursor="hand2",
                  command=self._gallery_open_folder).pack(side="right", padx=(8, 0))
        tk.Button(hdr, text="�  Xóa tất cả", bg=BG_CARD, fg=DANGER,
                  activebackground=BG_HOVER, activeforeground=DANGER,
                  relief="flat", bd=0, padx=12, pady=6, font=("Segoe UI", 9),
                  cursor="hand2",
                  command=self._gallery_delete_all).pack(side="right", padx=(8, 0))
        tk.Button(hdr, text="�🔄  Làm mới", bg=BG_CARD, fg=TEXT_MUTED,
                  activebackground=BG_HOVER, activeforeground=TEXT_PRIMARY,
                  relief="flat", bd=0, padx=12, pady=6, font=("Segoe UI", 9),
                  cursor="hand2", command=self._refresh_gallery).pack(side="right")

        tk.Frame(page, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(10, 0))

        self._gallery_info_var = tk.StringVar(value="Chưa tải dữ liệu thư viện")
        tk.Label(page, textvariable=self._gallery_info_var, bg=BG_DARK, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(8, 0))
        tk.Label(page,
                 text="Mỗi video lưu ~20s trước và ~8s sau thời điểm cảnh báo để hỗ trợ điều tra nguyên nhân.",
                 bg=BG_DARK, fg=TEXT_MUTED, font=("Segoe UI", 8, "italic")
                 ).pack(anchor="w", padx=24, pady=(2, 0))

        # Scrollable canvas
        outer = tk.Frame(page, bg=BG_CARD)
        outer.pack(fill="both", expand=True, padx=24, pady=(8, 20))
        canvas = tk.Canvas(outer, bg=BG_CARD, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self._gallery_inner = tk.Frame(canvas, bg=BG_CARD)
        self._gallery_canvas = canvas
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        canvas_win = canvas.create_window((0, 0), window=self._gallery_inner, anchor="nw")

        def _on_inner_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(e):
            canvas.itemconfig(canvas_win, width=e.width)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        self._gallery_inner.bind("<Configure>", _on_inner_resize)
        canvas.bind("<Configure>", _on_canvas_resize)
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self._gallery_photo_refs: List = []
        self._refresh_gallery()
        return page

    def _gallery_open_folder(self):
        alerts_dir = os.path.abspath("alerts")
        try:
            os.makedirs(alerts_dir, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(alerts_dir)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", alerts_dir])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", alerts_dir])
        except Exception:
            pass

    def _gallery_delete_video(self, video_path: str):
        """Xóa 1 video clip sau khi xác nhận."""
        from tkinter import messagebox
        if not os.path.isfile(video_path):
            self._refresh_gallery()
            return
        fname = os.path.basename(video_path)
        if not messagebox.askyesno(
            "Xác nhận xóa",
            f"Xóa video này?\n\n{fname}\n\nThao tác không thể hoàn tác.",
            icon="warning", parent=self,  # type: ignore[arg-type]
        ):
            return
        try:
            os.remove(video_path)
        except Exception as exc:
            messagebox.showerror("Lỗi xóa", f"Không xóa được:\n{exc}", parent=self)  # type: ignore[arg-type]
            return
        # Audit log nếu có user đang đăng nhập
        try:
            user_id = getattr(self, "current_user_id", None)
            if hasattr(self, "db") and user_id:
                self.db.add_audit_log(int(user_id), "delete_alert_video", fname)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._refresh_gallery()

    def _gallery_delete_all(self):
        """Xóa toàn bộ video clip trong alerts/ sau khi xác nhận."""
        from tkinter import messagebox
        alerts_dir = os.path.abspath("alerts")
        if not os.path.isdir(alerts_dir):
            return
        vid_exts = (".avi", ".mp4", ".mov", ".mkv")
        targets = [os.path.join(alerts_dir, f) for f in os.listdir(alerts_dir)
                   if f.lower().endswith(vid_exts) and os.path.isfile(os.path.join(alerts_dir, f))]
        if not targets:
            messagebox.showinfo("Thư viện trống", "Không có video nào để xóa.", parent=self)  # type: ignore[arg-type]
            return
        if not messagebox.askyesno(
            "Xác nhận xóa tất cả",
            f"Xóa toàn bộ {len(targets)} video cảnh báo?\n\nThao tác không thể hoàn tác.",
            icon="warning", parent=self,  # type: ignore[arg-type]
        ):
            return
        removed = 0
        for p in targets:
            try:
                os.remove(p)
                removed += 1
            except Exception:
                pass
        try:
            user_id = getattr(self, "current_user_id", None)
            if hasattr(self, "db") and user_id:
                self.db.add_audit_log(int(user_id), "delete_all_alert_videos", f"{removed}/{len(targets)}")  # type: ignore[attr-defined]
        except Exception:
            pass
        self._refresh_gallery()

    def _video_thumbnail(self, video_path: str, max_w: int = 196, max_h: int = 138):
        """Trích frame đầu (hoặc giữa) của video làm thumbnail PhotoImage."""
        if not _PIL_AVAILABLE:
            return None
        try:
            import cv2  # local import để tránh phụ thuộc cứng khi PIL không có
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            # Lấy frame ở khoảng giữa pre-roll để ảnh không quá tối
            target_idx = max(0, min(total - 1, int(total * 0.4))) if total > 0 else 0
            if total > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
            ok, frame = cap.read()
            cap.release()
            if not ok or frame is None:
                return None
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail((max_w, max_h))
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _refresh_gallery(self):
        if not hasattr(self, "_gallery_inner"):
            return
        for w in self._gallery_inner.winfo_children():
            w.destroy()
        self._gallery_photo_refs = []

        alerts_dir = os.path.abspath("alerts")
        if not os.path.isdir(alerts_dir):
            tk.Label(self._gallery_inner,
                     text="Thư mục alerts/ chưa được tạo. Bắt đầu giám sát để ghi nhận video cảnh báo.",
                     bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 10)).pack(padx=20, pady=30)
            if hasattr(self, "_gallery_info_var"):
                self._gallery_info_var.set("0 video  •  0.0 MB")
            return

        vid_exts = (".avi", ".mp4", ".mov", ".mkv")
        files = sorted(
            [f for f in os.listdir(alerts_dir) if f.lower().endswith(vid_exts)],
            key=lambda f: os.path.getmtime(os.path.join(alerts_dir, f)),
            reverse=True,
        )

        all_files = [f for f in os.listdir(alerts_dir) if os.path.isfile(os.path.join(alerts_dir, f))]
        total_bytes = sum(os.path.getsize(os.path.join(alerts_dir, f)) for f in all_files)
        total_mb = total_bytes / (1024 * 1024)
        max_mb = 300
        try:
            if hasattr(self, "alerts_max_mb"):
                max_mb = int(self.alerts_max_mb.get())  # type: ignore[attr-defined]
        except Exception:
            pass
        if hasattr(self, "_gallery_info_var"):
            self._gallery_info_var.set(
                f"{len(files)} video  •  {total_mb:.1f} MB / {max_mb} MB  •  {alerts_dir}"
            )

        if not files:
            tk.Label(self._gallery_inner, text="Chưa có video cảnh báo nào.",
                     bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 10)).pack(padx=20, pady=30)
            return

        THUMB_W, THUMB_H = 196, 138
        COLS = 4
        for col_i in range(COLS):
            self._gallery_inner.columnconfigure(col_i, weight=1)

        for idx, fname in enumerate(files):
            row_i, col_i = divmod(idx, COLS)
            cell = tk.Frame(self._gallery_inner, bg=BG_DARK, padx=4, pady=4)
            cell.grid(row=row_i, column=col_i, padx=6, pady=6, sticky="nsew")

            vid_path = os.path.join(alerts_dir, fname)
            photo = self._video_thumbnail(vid_path, THUMB_W, THUMB_H)

            thumb_holder = tk.Frame(cell, bg=BG_DARK, width=THUMB_W, height=THUMB_H)
            thumb_holder.pack()
            thumb_holder.pack_propagate(False)
            if photo is not None:
                self._gallery_photo_refs.append(photo)
                lbl = tk.Label(thumb_holder, image=photo, bg=BG_DARK, cursor="hand2")
                lbl.image = photo  # type: ignore[attr-defined]
                lbl.place(relx=0.5, rely=0.5, anchor="center")
                lbl.bind("<Button-1>", lambda e, p=vid_path: self._gallery_view_full(p))
            else:
                placeholder = tk.Label(thumb_holder, text="🎞", bg=BG_DARK, fg=TEXT_MUTED,
                                       font=("Segoe UI", 28), cursor="hand2")
                placeholder.place(relx=0.5, rely=0.5, anchor="center")
                placeholder.bind("<Button-1>", lambda e, p=vid_path: self._gallery_view_full(p))

            # Overlay icon ▶ ở góc dưới phải để gợi ý click phát
            tk.Label(thumb_holder, text="▶", bg=BG_DARK, fg="#ffffff",
                     font=("Segoe UI", 11, "bold")).place(relx=0.94, rely=0.92, anchor="se")

            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(vid_path)).strftime("%d/%m %H:%M")
                size_kb = os.path.getsize(vid_path) // 1024
            except Exception:
                mtime, size_kb = "-", 0

            fn_lower = fname.lower()
            default_lbl = "fire" if "fire" in fn_lower else ("smoke" if "smoke" in fn_lower else "fire")
            ltype = "🔥 Lửa" if default_lbl == "fire" else "💨 Khói"
            info_row = tk.Frame(cell, bg=BG_DARK)
            info_row.pack(fill="x", pady=(3, 0))
            size_txt = f"{size_kb/1024:.1f}MB" if size_kb >= 1024 else f"{size_kb}KB"
            tk.Label(info_row, text=f"{ltype}  {mtime}  {size_txt}",
                     bg=BG_DARK, fg=TEXT_MUTED,
                     font=("Segoe UI", 7), wraplength=THUMB_W - 60, anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(info_row, text="🗑", bg=BG_DARK, fg=DANGER,
                      activebackground=BG_HOVER, activeforeground=DANGER,
                      relief="flat", bd=0, padx=4, pady=0, font=("Segoe UI", 9),
                      cursor="hand2",
                      command=lambda p=vid_path: self._gallery_delete_video(p)
                      ).pack(side="right")

    def _gallery_view_full(self, video_path: str):
        """Mở video bằng trình phát mặc định của hệ điều hành."""
        if not os.path.isfile(video_path):
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(video_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", video_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", video_path])
        except Exception as exc:
            try:
                from tkinter import messagebox
                messagebox.showerror("Lỗi mở video", f"Không mở được video:\n{exc}")
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────
    #  Chuyển ảnh Gallery → Training
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    #  Shared label-picker dialog (card buttons)
    # ──────────────────────────────────────────────────────────────────

    def _open_label_picker(self, title: str, subtitle: str,
                           default_label: str,
                           image_path: Optional[str],
                           on_confirm):
        """
        Mở dialog chọn nhãn dạng card-button lớn.
        on_confirm(chosen_label: str) được gọi khi bấm Xác nhận.
        """
        dialog = tk.Toplevel(self)  # type: ignore[arg-type]
        dialog.title(title)
        dialog.configure(bg=BG_DARK)
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        dw = 360
        try:
            sw = self.winfo_screenwidth()   # type: ignore[attr-defined]
            sh = self.winfo_screenheight()  # type: ignore[attr-defined]
            dialog.geometry(f"{dw}x10+{(sw-dw)//2}+{sh//4}")
        except Exception:
            pass

        # Header
        hdr = tk.Frame(dialog, bg="#4c1d95", pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🎓  " + title, bg="#4c1d95", fg="#ede9fe",
                 font=("Segoe UI", 11, "bold")).pack()
        if subtitle:
            tk.Label(hdr, text=subtitle, bg="#4c1d95", fg="#c4b5fd",
                     font=("Segoe UI", 8)).pack(pady=(2, 0))

        # Thumbnail
        if image_path and _PIL_AVAILABLE and os.path.isfile(str(image_path)):
            try:
                img = Image.open(str(image_path))
                img.thumbnail((330, 140))
                photo = ImageTk.PhotoImage(img)
                lbl_img = tk.Label(dialog, image=photo, bg=BG_DARK)
                lbl_img.image = photo  # type: ignore[attr-defined]
                lbl_img.pack(padx=10, pady=(10, 0))
            except Exception:
                pass

        tk.Label(dialog, text="Chọn nhãn:", bg=BG_DARK, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(12, 4))

        # Card buttons
        _opts = [
            ("fire",   "🔥",  "Lửa",        "fire",    ACCENT,  "#3a0800"),
            ("smoke",  "💨",  "Khói",        "smoke",   WARNING, "#3a2800"),
            ("normal", "✓",   "Bình thường", "normal",  SUCCESS, "#003a1a"),
        ]
        selected_var = tk.StringVar(value=default_label)
        card_refs: Dict[str, tk.Frame] = {}
        cards_frame = tk.Frame(dialog, bg=BG_DARK)
        cards_frame.pack(fill="x", padx=20, pady=(0, 4))
        for c in range(3):
            cards_frame.columnconfigure(c, weight=1, uniform="lcard")

        def _select(val):
            selected_var.set(val)
            for v, card in card_refs.items():
                _, _, _, _, fg, bg = next(o for o in _opts if o[0] == v)
                is_sel = v == val
                card.config(bg=fg if is_sel else bg,
                            relief="solid" if is_sel else "flat",
                            bd=2 if is_sel else 0)
                for ch in card.winfo_children():
                    ch.config(bg=fg if is_sel else bg)

        for col_i, (val, icon, name, _, fg, bg) in enumerate(_opts):
            card = tk.Frame(cards_frame, bg=bg, padx=8, pady=10,
                            relief="flat", bd=0, cursor="hand2")
            card.grid(row=0, column=col_i, sticky="nsew",
                      padx=(0 if col_i == 0 else 4), pady=2)
            tk.Label(card, text=icon, bg=bg, fg=fg,
                     font=("Segoe UI", 20)).pack()
            tk.Label(card, text=name, bg=bg, fg=fg,
                     font=("Segoe UI", 9, "bold")).pack()
            card_refs[val] = card
            card.bind("<Button-1>", lambda e, v=val: _select(v))
            for ch in card.winfo_children():
                ch.bind("<Button-1>", lambda e, v=val: _select(v))

        _select(default_label)  # highlight default

        status_var = tk.StringVar()
        status_lbl = tk.Label(dialog, textvariable=status_var, bg=BG_DARK,
                              fg=SUCCESS, font=("Segoe UI", 8))
        status_lbl.pack(anchor="w", padx=20)

        def _confirm():
            chosen = selected_var.get()
            confirm_btn.config(state="disabled", text="Đang lưu...")
            try:
                on_confirm(chosen, status_var, dialog)
            except Exception as exc:
                from tkinter import messagebox
                messagebox.showerror("Lỗi", str(exc), parent=dialog)
                confirm_btn.config(state="normal", text="✓  Xác nhận")

        btn_row = tk.Frame(dialog, bg=BG_DARK, pady=12)
        btn_row.pack(fill="x", padx=20)
        confirm_btn = tk.Button(btn_row, text="✓  Xác nhận",
                                bg="#7c3aed", fg="white",
                                activebackground="#5b21b6", activeforeground="white",
                                relief="flat", bd=0, padx=18, pady=8,
                                font=("Segoe UI", 10, "bold"),
                                cursor="hand2", command=_confirm)
        confirm_btn.pack(side="right")
        tk.Button(btn_row, text="Hủy", bg=BG_HOVER, fg=TEXT_MUTED,
                  activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
                  relief="flat", bd=0, padx=14, pady=8, font=("Segoe UI", 9),
                  cursor="hand2", command=dialog.destroy).pack(side="right", padx=(0, 8))

        dialog.update_idletasks()
        dialog.geometry(f"{dw}x{dialog.winfo_reqheight()}")

    def _gallery_send_to_training(self, image_path: str, default_label: str = "fire"):
        """Mở label picker rồi copy ảnh gallery vào training_data/."""
        if not os.path.isfile(image_path):
            return

        def _on_confirm(chosen, status_var, dialog):
            import shutil
            dest_dir = os.path.join("training_data", chosen)
            os.makedirs(dest_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            dest_name = f"{chosen}_{ts}.jpg"
            dest_path = os.path.join(dest_dir, dest_name)
            shutil.copy2(image_path, dest_path)
            try:
                who = getattr(getattr(self, "admin_controller", None), "current_user", None)
                who = str(who) if who else "gallery"
                self.db.add_training_capture(  # type: ignore[attr-defined]
                    image_path=dest_path, label=chosen,
                    source_name="gallery", captured_by=who)
            except Exception:
                pass
            status_var.set(f"✓  Đã lưu vào training_data/{chosen}/")
            if hasattr(self, "_refresh_training_page"):
                self._refresh_training_page()  # type: ignore[attr-defined]
            dialog.after(1000, dialog.destroy)

        self._open_label_picker(
            title="Thêm vào tập huấn luyện",
            subtitle=os.path.basename(image_path),
            default_label=default_label,
            image_path=image_path,
            on_confirm=_on_confirm,
        )

    # ──────────────────────────────────────────────────────────────────
    #  Gửi email cảnh báo
    # ──────────────────────────────────────────────────────────────────

    def _smtp_send(self, subject: str, html_body: str, image_path: str | None = None) -> tuple[bool, str]:
        """Gửi 1 email qua SMTP. Trả (success, message).

        - Hỗ trợ Gmail (port 587 STARTTLS hoặc 465 SSL).
        - Hỗ trợ nhiều người nhận (phân tách bằng dấu phẩy hoặc chấm phẩy).
        - Nếu có ảnh, đính kèm + nhúng inline (cid:alert_image) cho client hiển thị trong nội dung.
        """
        smtp_host = str(self.db.get_setting("email_smtp_host", "")).strip()  # type: ignore[attr-defined]
        try:
            smtp_port = int(str(self.db.get_setting("email_smtp_port", "587")).strip() or "587")  # type: ignore[attr-defined]
        except ValueError:
            smtp_port = 587
        smtp_user = str(self.db.get_setting("email_smtp_user", "")).strip()  # type: ignore[attr-defined]
        smtp_pass = str(self.db.get_setting_secret("email_smtp_pass", ""))  # type: ignore[attr-defined]
        to_raw    = str(self.db.get_setting("email_to", "")).strip()  # type: ignore[attr-defined]

        if not smtp_host or not smtp_user or not smtp_pass or not to_raw:
            return False, "Email chưa được cấu hình đầy đủ (host/user/pass/to)."

        # Tách nhiều địa chỉ
        recipients = [a.strip() for a in to_raw.replace(";", ",").split(",") if a.strip()]
        if not recipients:
            return False, "Không có địa chỉ người nhận hợp lệ."

        msg = MIMEMultipart("related")
        msg["From"]    = smtp_user
        msg["To"]      = ", ".join(recipients)
        msg["Subject"] = subject

        # Nhúng ảnh inline nếu có
        body_html = html_body
        if image_path and os.path.isfile(str(image_path)):
            body_html = body_html.replace("{IMAGE_CID}", "cid:alert_image")
        else:
            body_html = body_html.replace("{IMAGE_CID}", "")

        msg.attach(MIMEText(body_html, "html", "utf-8"))

        if image_path and os.path.isfile(str(image_path)):
            try:
                with open(str(image_path), "rb") as f:
                    img_data = f.read()
                part = MIMEBase("image", "jpeg")
                part.set_payload(img_data)
                encoders.encode_base64(part)
                part.add_header("Content-ID", "<alert_image>")
                part.add_header("Content-Disposition", "inline",
                                filename=os.path.basename(str(image_path)))
                msg.attach(part)
            except Exception:
                pass

        try:
            if smtp_port == 465:
                # SSL từ đầu (Gmail SSL)
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_user, recipients, msg.as_string())
            else:
                # STARTTLS (Gmail 587 hoặc SMTP thường)
                with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                    server.ehlo()
                    try:
                        server.starttls()
                        server.ehlo()
                    except smtplib.SMTPException:
                        # Một số server nội bộ không hỗ trợ TLS — vẫn cho gửi
                        pass
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_user, recipients, msg.as_string())
            return True, f"Đã gửi đến {', '.join(recipients)}"
        except smtplib.SMTPAuthenticationError:
            return False, ("Xác thực thất bại. Với Gmail, bạn cần dùng "
                           "'App Password' (16 ký tự) thay vì mật khẩu thường.")
        except smtplib.SMTPException as exc:
            return False, f"Lỗi SMTP: {exc}"
        except OSError as exc:
            return False, f"Lỗi kết nối: {exc}"
        except Exception as exc:
            return False, f"Lỗi không xác định: {exc}"

    def _send_alert_email(self, data: Dict[str, Any]):
        """Gửi email cảnh báo trong daemon thread (không block UI). Có throttle 60 s."""
        # Throttle để tránh spam khi liên tục có alert
        now_ts = datetime.now().timestamp()
        last_ts = float(getattr(self, "_last_email_ts", 0.0))
        if now_ts - last_ts < 60.0:
            return
        self._last_email_ts = now_ts  # type: ignore[attr-defined]

        def _worker():
            try:
                label_type   = str(data.get("label", "fire"))
                source_name  = str(data.get("source_name", "-"))
                danger_level = str(data.get("danger_level") or "HIGH")
                image_path   = data.get("image_path")
                ts = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

                _level_vi = {"LOW": "THẤP", "MEDIUM": "TRUNG BÌNH",
                              "HIGH": "CAO", "CRITICAL": "NGUY HIỂM"}
                level_vi = _level_vi.get(danger_level, danger_level)
                icon = "🔥" if label_type == "fire" else "💨"
                color = "#ef4444" if danger_level == "CRITICAL" else "#f04e1a"
                subject = f"[FireGuard] {icon} CẢNH BÁO {label_type.upper()} - Cấp {level_vi} - {source_name}"

                body = (
                    f"<div style='font-family:Segoe UI,Arial,sans-serif;max-width:560px'>"
                    f"<h2 style='color:{color};margin:0 0 12px'>{icon} Phát hiện {label_type.upper()}</h2>"
                    f"<table style='border-collapse:collapse;font-size:14px'>"
                    f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Nguồn</td>"
                    f"<td style='padding:4px 0'><b>{source_name}</b></td></tr>"
                    f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Cấp độ nguy hiểm</td>"
                    f"<td style='padding:4px 0;color:{color}'><b>{level_vi}</b></td></tr>"
                    f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Thời gian</td>"
                    f"<td style='padding:4px 0'>{ts}</td></tr>"
                    f"</table>"
                    f"<p style='margin-top:16px'><img src='{{IMAGE_CID}}' "
                    f"style='max-width:520px;border:1px solid #ddd;border-radius:6px'></p>"
                    f"<p style='color:#666;font-size:12px;margin-top:16px'>"
                    f"Vui lòng kiểm tra hệ thống giám sát ngay lập tức.</p>"
                    f"</div>"
                )

                ok, info = self._smtp_send(subject, body, image_path)
                if ok:
                    self._log(f"✉  Đã gửi email cảnh báo: {info}")  # type: ignore[attr-defined]
                else:
                    self._log(f"Lỗi gửi email cảnh báo: {info}")  # type: ignore[attr-defined]
            except Exception as exc:
                self._log(f"Lỗi gửi email cảnh báo: {exc}")  # type: ignore[attr-defined]

        threading.Thread(target=_worker, daemon=True).start()

    def send_test_email(self) -> tuple[bool, str]:
        """Gửi email kiểm tra với cấu hình hiện tại. Dùng cho nút Test ở Admin."""
        ts = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        subject = "[FireGuard] Email kiểm tra cấu hình"
        body = (
            f"<div style='font-family:Segoe UI,Arial,sans-serif'>"
            f"<h2 style='color:#22c55e'>✓ Cấu hình email hoạt động</h2>"
            f"<p>Đây là email thử nghiệm gửi lúc <b>{ts}</b>.</p>"
            f"<p>Nếu bạn nhận được, hệ thống sẽ tự gửi cảnh báo khi phát hiện "
            f"<b>cháy/khói</b> ở mức HIGH hoặc CRITICAL.</p>"
            f"{{IMAGE_CID}}"
            f"</div>"
        )
        return self._smtp_send(subject, body, None)

    # ──────────────────────────────────────────────────────────────────
    #  Trang quản lý ảnh huấn luyện
    # ──────────────────────────────────────────────────────────────────

    def _create_training_page(self) -> tk.Frame:
        page = tk.Frame(self.page_container, bg=BG_DARK)  # type: ignore[attr-defined]

        hdr = tk.Frame(page, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(hdr, text="Ảnh huấn luyện", bg=BG_DARK, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Button(hdr, text="🔄  Làm mới", bg=BG_CARD, fg=TEXT_MUTED,
                  activebackground=BG_HOVER, activeforeground=TEXT_PRIMARY,
                  relief="flat", bd=0, padx=12, pady=6, font=("Segoe UI", 9),
                  cursor="hand2", command=self._refresh_training_page  # type: ignore[attr-defined]
                  ).pack(side="right")
        tk.Button(hdr, text="🗑  Xóa chọn", bg=BG_CARD, fg=DANGER,
                  activebackground=BG_HOVER, activeforeground=DANGER,
                  relief="flat", bd=0, padx=12, pady=6, font=("Segoe UI", 9),
                  cursor="hand2", command=self._delete_selected_training  # type: ignore[attr-defined]
                  ).pack(side="right", padx=(0, 8))
        tk.Button(hdr, text="✏  Đổi nhãn", bg=BG_CARD, fg="#a78bfa",
                  activebackground=BG_HOVER, activeforeground="#c4b5fd",
                  relief="flat", bd=0, padx=12, pady=6, font=("Segoe UI", 9),
                  cursor="hand2", command=self._relabel_selected_training_dialog  # type: ignore[attr-defined]
                  ).pack(side="right", padx=(0, 8))
        tk.Button(hdr, text="🚀  Huấn luyện", bg="#1d4ed8", fg="white",
                  activebackground="#1e40af", activeforeground="white",
                  relief="flat", bd=0, padx=12, pady=6, font=("Segoe UI", 9, "bold"),
                  cursor="hand2", command=self._start_training_dialog  # type: ignore[attr-defined]
                  ).pack(side="right", padx=(0, 8))

        tk.Frame(page, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(10, 0))

        # Filter toggle buttons
        flt_row = tk.Frame(page, bg=BG_DARK)
        flt_row.pack(fill="x", padx=24, pady=(8, 0))
        tk.Label(flt_row, text="Lọc:", bg=BG_DARK, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(side="left")

        self._training_filter_var = tk.StringVar(value="all")
        _filter_btns: Dict[str, tk.Button] = {}
        _filter_opts = [
            ("all",    "Tất cả",      TEXT_PRIMARY, BG_CARD),
            ("fire",   "🔥 Lửa",      ACCENT,       "#3a0800"),
            ("smoke",  "💨 Khói",     WARNING,      "#3a2800"),
            ("normal", "✓ Bình thường", "#56d364",  "#003a1a"),
        ]

        def _apply_filter(val: str):
            self._training_filter_var.set(val)
            for v, btn in _filter_btns.items():
                _, _, fg, bg = next(o for o in _filter_opts if o[0] == v)
                is_sel = v == val
                btn.config(
                    bg=bg if is_sel else BG_HOVER,
                    fg=fg if is_sel else TEXT_MUTED,
                    relief="solid" if is_sel else "flat",
                    bd=1 if is_sel else 0,
                )
            self._refresh_training_page()  # type: ignore[attr-defined]

        for val, txt, fg, bg in _filter_opts:
            b = tk.Button(
                flt_row, text=txt,
                bg=BG_HOVER, fg=TEXT_MUTED,
                activebackground=bg, activeforeground=fg,
                relief="flat", bd=0, padx=10, pady=4,
                font=("Segoe UI", 9), cursor="hand2",
                command=lambda v=val: _apply_filter(v),
            )
            b.pack(side="left", padx=(6, 0))
            _filter_btns[val] = b
        _apply_filter("all")   # highlight default

        self._training_info_var = tk.StringVar(value="")
        self._training_sel_var  = tk.StringVar(value="")
        info_row = tk.Frame(page, bg=BG_DARK)
        info_row.pack(fill="x", padx=24, pady=(4, 0))
        tk.Label(info_row, textvariable=self._training_info_var, bg=BG_DARK,
                 fg=TEXT_MUTED, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(info_row, textvariable=self._training_sel_var, bg=BG_DARK,
                 fg="#a78bfa", font=("Segoe UI", 9)).pack(side="left", padx=(12, 0))

        # Scrollable thumbnail grid
        outer = tk.Frame(page, bg=BG_CARD)
        outer.pack(fill="both", expand=True, padx=24, pady=(8, 20))
        canvas = tk.Canvas(outer, bg=BG_CARD, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self._training_inner  = tk.Frame(canvas, bg=BG_CARD)
        self._training_canvas = canvas
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        _win_id = canvas.create_window((0, 0), window=self._training_inner, anchor="nw")
        self._training_inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(_win_id, width=e.width))

        def _mw(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _mw))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self._training_selected: set = set()
        self._training_cells: Dict[str, Dict[str, Any]] = {}
        self._training_photo_refs: List = []

        self._refresh_training_page()
        return page

    def _refresh_training_page(self):
        if not hasattr(self, "_training_inner"):
            return
        for w in self._training_inner.winfo_children():
            w.destroy()
        self._training_photo_refs = []
        self._training_cells = {}

        flt = getattr(self, "_training_filter_var", None)
        label_filter = flt.get() if flt else "all"
        try:
            rows = self.db.get_training_captures(  # type: ignore[attr-defined]
                label=None if label_filter == "all" else label_filter, limit=2000)
        except Exception:
            rows = []

        # Scan disk for files not in DB
        disk_rows: List[Dict[str, Any]] = []
        td_root = os.path.abspath("training_data")
        if os.path.isdir(td_root):
            for lbl in os.listdir(td_root):
                lbl_dir = os.path.join(td_root, lbl)
                if not os.path.isdir(lbl_dir):
                    continue
                if label_filter not in ("all", lbl):
                    continue
                for fname in os.listdir(lbl_dir):
                    if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue
                    fpath = os.path.join(lbl_dir, fname)
                    if any(str(r.get("image_path")) == fpath for r in rows):
                        continue
                    try:
                        ts = datetime.fromtimestamp(
                            os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        ts = "-"
                    disk_rows.append({"id": None, "label": lbl, "timestamp": ts,
                                      "source_name": "-", "image_path": fpath})

        all_rows = list(rows) + disk_rows
        all_rows.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)

        # Update info label
        if hasattr(self, "_training_info_var"):
            cnts: Dict[str, int] = {}
            for r in all_rows:
                k = str(r.get("label") or "")
                cnts[k] = cnts.get(k, 0) + 1
            self._training_info_var.set(
                f"{len(all_rows)} ảnh  •  🔥 {cnts.get('fire', 0)}"
                f"  💨 {cnts.get('smoke', 0)}  ✓ {cnts.get('normal', 0)}")

        # Clean stale selection
        valid = {str(r.get("image_path") or "") for r in all_rows}
        self._training_selected = {p for p in self._training_selected if p in valid}
        self._update_training_sel_label()

        if not all_rows:
            tk.Label(self._training_inner,
                     text="Chưa có ảnh huấn luyện.\nBấm đúp tile camera → 📸 để chụp ảnh.",
                     bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 10),
                     justify="center").pack(padx=20, pady=40)
            return

        THUMB_W, THUMB_H, COLS = 180, 126, 4
        for c in range(COLS):
            self._training_inner.columnconfigure(c, weight=1)

        _badge_style = {
            "fire":   ("🔥 Lửa",        ACCENT,  "#3a0800"),
            "smoke":  ("💨 Khói",        WARNING, "#3a2800"),
            "normal": ("✓ Bình thường",  SUCCESS, "#003a1a"),
        }

        for idx, row in enumerate(all_rows):
            r_i, c_i   = divmod(idx, COLS)
            img_path   = str(row.get("image_path") or "")
            lbl        = str(row.get("label") or "fire")
            ts_str     = str(row.get("timestamp") or "")
            ts_short   = ts_str[5:16] if len(ts_str) >= 16 else ts_str
            is_sel     = img_path in self._training_selected

            # Outer border frame (highlights purple when selected)
            cell = tk.Frame(self._training_inner,
                            bg="#7c3aed" if is_sel else BG_CARD,
                            padx=2, pady=2, cursor="hand2")
            cell.grid(row=r_i, column=c_i, padx=5, pady=5, sticky="nsew")
            inner = tk.Frame(cell, bg=BG_DARK)
            inner.pack(fill="both", expand=True)
            self._training_cells[img_path] = {"frame": cell, "inner": inner, "data": row}

            # Thumbnail
            thumb_lbl: Optional[tk.Label] = None
            if _PIL_AVAILABLE and os.path.isfile(img_path):
                try:
                    img_obj = Image.open(img_path)
                    img_obj.thumbnail((THUMB_W, THUMB_H))
                    photo = ImageTk.PhotoImage(img_obj)
                    self._training_photo_refs.append(photo)
                    thumb_lbl = tk.Label(inner, image=photo, bg=BG_DARK, cursor="hand2")
                    thumb_lbl.image = photo  # type: ignore[attr-defined]
                    thumb_lbl.pack()
                except Exception:
                    thumb_lbl = None
            if thumb_lbl is None:
                thumb_lbl = tk.Label(inner, text="📷", bg=BG_DARK, fg=TEXT_MUTED,
                                     font=("Segoe UI", 24), width=18, height=5)
                thumb_lbl.pack()

            # Bottom bar: label badge | timestamp | ✏ button
            bot = tk.Frame(inner, bg=BG_DARK)
            bot.pack(fill="x", pady=(2, 0))
            badge_txt, badge_fg, badge_bg = _badge_style.get(lbl, ("?", TEXT_MUTED, BG_CARD))
            tk.Button(bot, text=badge_txt, bg=badge_bg, fg=badge_fg,
                      activebackground=BG_HOVER, activeforeground=badge_fg,
                      relief="flat", bd=0, padx=5, pady=2,
                      font=("Segoe UI", 8, "bold"), cursor="hand2",
                      command=lambda p=img_path, r=row: self._training_relabel_popup(p, r)
                      ).pack(side="left")
            tk.Button(bot, text="✏", bg=BG_DARK, fg="#9ba4b4",
                      activebackground=BG_HOVER, activeforeground="#a78bfa",
                      relief="flat", bd=0, padx=4, pady=2, font=("Segoe UI", 8),
                      cursor="hand2",
                      command=lambda p=img_path, r=row: self._training_relabel_popup(p, r)
                      ).pack(side="right")
            tk.Label(bot, text=ts_short, bg=BG_DARK, fg=TEXT_MUTED,
                     font=("Segoe UI", 7)).pack(side="right", padx=(0, 2))

            # Click = toggle select, double-click = view full
            def _make_fns(path, c_frame):
                def _toggle(e=None):
                    if path in self._training_selected:
                        self._training_selected.discard(path)
                        c_frame.config(bg=BG_CARD)
                    else:
                        self._training_selected.add(path)
                        c_frame.config(bg="#7c3aed")
                    self._update_training_sel_label()
                def _view(e=None):
                    if os.path.isfile(path):
                        self._gallery_view_full(path)
                return _toggle, _view

            tog, view = _make_fns(img_path, cell)
            for w in (cell, inner, thumb_lbl):
                if w:
                    w.bind("<Button-1>", tog)
                    w.bind("<Double-Button-1>", view)

    def _update_training_sel_label(self):
        if hasattr(self, "_training_sel_var"):
            n = len(self._training_selected)
            self._training_sel_var.set(f"  ({n} đang chọn)" if n else "")

    def _training_relabel_popup(self, img_path: str, row: Dict[str, Any]):
        """Mở label picker đổi nhãn cho 1 ảnh."""
        def _on_confirm(new_lbl, status_var, dialog):
            dialog.destroy()
            self._training_do_relabel([img_path], {img_path: row}, new_lbl)

        self._open_label_picker(
            title="Đổi nhãn",
            subtitle=os.path.basename(img_path),
            default_label=str(row.get("label") or "fire"),
            image_path=img_path,
            on_confirm=_on_confirm,
        )

    def _relabel_selected_training_dialog(self):
        """Đổi nhãn hàng loạt cho các ảnh đang chọn."""
        sel = getattr(self, "_training_selected", set())
        if not sel:
            from tkinter import messagebox
            messagebox.showinfo("Chưa chọn", "Bấm vào ảnh để chọn trước khi đổi nhãn.",
                                parent=self)  # type: ignore[arg-type]
            return

        def _on_confirm(new_lbl, status_var, dialog):
            paths = list(sel)
            rows_map = {p: self._training_cells.get(p, {}).get("data", {}) for p in paths}
            dialog.destroy()
            self._training_do_relabel(paths, rows_map, new_lbl)

        self._open_label_picker(
            title=f"Đổi nhãn  ({len(sel)} ảnh)",
            subtitle="Chọn nhãn mới cho tất cả ảnh đang chọn",
            default_label="fire",
            image_path=None,
            on_confirm=_on_confirm,
        )

    def _training_do_relabel(self, paths: List[str],
                              rows_map: Dict[str, Any], new_label: str):
        """Di chuyển file + cập nhật DB khi đổi nhãn."""
        import shutil
        for path in paths:
            if not os.path.isfile(path):
                continue
            new_dir = os.path.abspath(os.path.join("training_data", new_label))
            os.makedirs(new_dir, exist_ok=True)
            fname    = os.path.basename(path)
            new_path = os.path.join(new_dir, fname)
            if os.path.abspath(new_path) == os.path.abspath(path):
                continue  # đã đúng thư mục
            if os.path.exists(new_path):
                base, ext = os.path.splitext(fname)
                ts = datetime.now().strftime("%H%M%S%f")[:10]
                new_path = os.path.join(new_dir, f"{new_label}_{ts}{ext}")
            try:
                shutil.move(path, new_path)
            except Exception:
                continue
            row = rows_map.get(path) or {}
            rid = row.get("id")
            if rid is not None:
                try:
                    self.db.relabel_training_capture(  # type: ignore[attr-defined]
                        int(rid), new_label, new_path)
                except Exception:
                    pass
        self._training_selected.clear()
        self._refresh_training_page()

    def _delete_selected_training(self):
        sel = getattr(self, "_training_selected", set())
        if not sel:
            from tkinter import messagebox
            messagebox.showinfo("Chưa chọn", "Bấm vào ảnh để chọn trước khi xóa.",
                                parent=self)  # type: ignore[arg-type]
            return
        from tkinter import messagebox
        if not messagebox.askyesno("Xác nhận xóa",
                                   f"Xóa {len(sel)} ảnh đã chọn?\n(Xóa cả file trên đĩa)",
                                   parent=self):  # type: ignore[arg-type]
            return
        db_ids = []
        for path in list(sel):
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
            row = self._training_cells.get(path, {}).get("data", {})
            rid = row.get("id")
            if rid is not None:
                try:
                    db_ids.append(int(rid))
                except (ValueError, TypeError):
                    pass
        if db_ids:
            try:
                self.db.delete_training_captures_bulk(db_ids)  # type: ignore[attr-defined]
            except Exception:
                pass
        self._training_selected.clear()
        self._refresh_training_page()

    # ──────────────────────────────────────────────────────────────────
    #  Training launcher dialog
    # ──────────────────────────────────────────────────────────────────

    def _prepare_yolo_dataset(self, log_fn) -> int:
        """
        Chuẩn bị YOLO dataset từ training_data/ với auto-annotation.
        - fire / smoke → dùng model hiện tại để tạo bbox (pseudo-label)
        - normal       → ảnh âm (empty label)
        Trả về tổng số ảnh đã xử lý, hoặc 0 nếu thất bại.
        """
        import shutil
        import random

        label_map = {"fire": 0, "smoke": 1}
        all_items: List[tuple] = []

        for lbl in ("fire", "smoke", "normal"):
            d = os.path.join("training_data", lbl)
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    lid = label_map.get(lbl, -1)   # -1 = negative
                    all_items.append((os.path.join(d, f), lid))

        if not all_items:
            log_fn("[WARN] training_data/ trống. Chụp ảnh trước khi huấn luyện.")
            return 0

        log_fn(f"[INFO] Tìm thấy {len(all_items)} ảnh trong training_data/")
        random.shuffle(all_items)
        split_idx = max(1, int(len(all_items) * 0.8))
        splits = {"train": all_items[:split_idx], "val": all_items[split_idx:]}

        # Xóa dữ liệu cũ, tạo lại thư mục
        for sn in ("train", "val"):
            for sub in ("images", "labels"):
                p = os.path.join("data", sub, sn)
                if os.path.isdir(p):
                    shutil.rmtree(p)
                os.makedirs(p, exist_ok=True)

        detector = getattr(self, "detector", None)
        written = 0

        for split_name, items in splits.items():
            img_dir = os.path.join("data", "images", split_name)
            lbl_dir = os.path.join("data", "labels", split_name)
            log_fn(f"[INFO] Xử lý {split_name}: {len(items)} ảnh")

            for img_path, label_id in items:
                if not os.path.isfile(img_path):
                    continue
                fname    = os.path.basename(img_path)
                stem     = os.path.splitext(fname)[0]
                dst_img  = os.path.join(img_dir, fname)
                dst_lbl  = os.path.join(lbl_dir, stem + ".txt")

                shutil.copy2(img_path, dst_img)

                if label_id == -1:            # normal → empty label file
                    open(dst_lbl, "w").close()
                    written += 1
                    continue

                # Auto-annotate với detector đang chạy
                ann_lines: List[str] = []
                if detector is not None:
                    try:
                        import cv2
                        im = cv2.imread(img_path)
                        if im is not None:
                            ih, iw = im.shape[:2]
                            results = detector.model(img_path, verbose=False)
                            for r in results:
                                for box in r.boxes:
                                    cls = int(box.cls[0])
                                    if cls not in (0, 1):
                                        continue
                                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                                    cx = (x1 + x2) / 2 / iw
                                    cy = (y1 + y2) / 2 / ih
                                    bw = (x2 - x1) / iw
                                    bh = (y2 - y1) / ih
                                    ann_lines.append(
                                        f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                    except Exception:
                        pass

                if not ann_lines:
                    # Fallback: full-image bbox với nhãn đã gán tay
                    ann_lines = [f"{label_id} 0.5 0.5 1.0 1.0"]

                with open(dst_lbl, "w", encoding="utf-8") as f:
                    f.write("\n".join(ann_lines) + "\n")
                written += 1

        # Cập nhật data.yaml với đường dẫn tuyệt đối
        abs_data = os.path.abspath("data")
        yaml_txt = (
            f"path: {abs_data}\n"
            "train: images/train\n"
            "val:   images/val\n"
            "nc: 2\n"
            "names:\n"
            "  0: fire\n"
            "  1: smoke\n"
        )
        with open(os.path.join("data", "data.yaml"), "w", encoding="utf-8") as f:
            f.write(yaml_txt)

        log_fn(f"[INFO] ✓ Dataset sẵn sàng — "
               f"train: {len(splits['train'])}  val: {len(splits['val'])}")
        return written

    def _start_training_dialog(self):
        """Dialog cấu hình + tiến trình huấn luyện model."""
        dialog = tk.Toplevel(self)  # type: ignore[arg-type]
        dialog.title("Huấn luyện mô hình")
        dialog.configure(bg=BG_DARK)
        dialog.resizable(True, True)

        try:
            sw = self.winfo_screenwidth()   # type: ignore[attr-defined]
            sh = self.winfo_screenheight()  # type: ignore[attr-defined]
            dw, dh = 620, 560
            dialog.geometry(f"{dw}x{dh}+{(sw-dw)//2}+{(sh-dh)//2}")
        except Exception:
            dialog.geometry("620x560")

        # ── Header ──────────────────────────────────────────────────
        hdr = tk.Frame(dialog, bg="#1e3a5f", pady=13)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🚀  Huấn luyện mô hình AI",
                 bg="#1e3a5f", fg="#bfdbfe",
                 font=("Segoe UI", 12, "bold")).pack()
        tk.Label(hdr, text="Auto-annotate → chuẩn bị dataset → train YOLOv8",
                 bg="#1e3a5f", fg="#93c5fd",
                 font=("Segoe UI", 8)).pack(pady=(2, 0))

        # ── Dataset stats ────────────────────────────────────────────
        stats_frame = tk.Frame(dialog, bg=BG_DARK)
        stats_frame.pack(fill="x", padx=20, pady=(12, 0))

        counts = {"fire": 0, "smoke": 0, "normal": 0}
        for lbl in counts:
            d = os.path.join("training_data", lbl)
            if os.path.isdir(d):
                counts[lbl] = sum(
                    1 for f in os.listdir(d)
                    if f.lower().endswith((".jpg", ".jpeg", ".png")))
        total = sum(counts.values())

        stats_color = "#56d364" if total >= 10 else "#e3b341"
        tk.Label(stats_frame,
                 text=f"Dataset: {total} ảnh  •  🔥 {counts['fire']}  "
                      f"💨 {counts['smoke']}  ✓ {counts['normal']}",
                 bg=BG_DARK, fg=stats_color,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        if total < 10:
            tk.Label(stats_frame, text="⚠  Nên có ít nhất 10 ảnh để train hiệu quả",
                     bg=BG_DARK, fg="#e3b341",
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        # ── Config grid ──────────────────────────────────────────────
        cfg_outer = tk.Frame(dialog, bg=BG_CARD, pady=12, padx=16)
        cfg_outer.pack(fill="x", padx=20, pady=(10, 0))

        fields = [
            ("Epochs:",     "50",   4),
            ("Batch size:", "8",    4),
            ("Image size:", "640",  6),
        ]
        field_vars: List[tk.StringVar] = []
        for col, (label, default, w) in enumerate(fields):
            tk.Label(cfg_outer, text=label, bg=BG_CARD, fg=TEXT_MUTED,
                     font=("Segoe UI", 9)).grid(row=0, column=col * 2,
                                                 sticky="w", pady=4, padx=(0 if col == 0 else 12, 0))
            var = tk.StringVar(value=default)
            tk.Entry(cfg_outer, textvariable=var, width=w,
                     bg=BG_HOVER, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                     relief="flat", font=("Segoe UI", 9)).grid(row=0, column=col * 2 + 1,
                                                                sticky="w", padx=(4, 0), pady=4)
            field_vars.append(var)
        epochs_var, batch_var, imgsz_var = field_vars

        tk.Label(cfg_outer, text="Base model:", bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=4)
        model_opts = ["models/best.pt", "yolov8n.pt", "yolov8s.pt"]
        default_model = "models/best.pt" if os.path.isfile("models/best.pt") else "yolov8n.pt"
        model_var = tk.StringVar(value=default_model)
        ttk.Combobox(cfg_outer, textvariable=model_var, values=model_opts,
                     width=22, state="readonly").grid(row=1, column=1, columnspan=5,
                                                       sticky="w", padx=(4, 0), pady=4)

        # ── Action buttons ───────────────────────────────────────────
        btn_frame = tk.Frame(dialog, bg=BG_DARK)
        btn_frame.pack(fill="x", padx=20, pady=(10, 0))

        start_btn = tk.Button(
            btn_frame, text="▶  Bắt đầu huấn luyện",
            bg="#1d4ed8", fg="white",
            activebackground="#1e40af", activeforeground="white",
            relief="flat", bd=0, padx=18, pady=8,
            font=("Segoe UI", 10, "bold"), cursor="hand2")
        start_btn.pack(side="left")

        stop_btn = tk.Button(
            btn_frame, text="⬛  Dừng",
            bg=BG_HOVER, fg=TEXT_MUTED,
            activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
            relief="flat", bd=0, padx=14, pady=8,
            font=("Segoe UI", 9), cursor="hand2", state="disabled")
        stop_btn.pack(side="left", padx=(8, 0))

        deploy_btn = tk.Button(
            btn_frame, text="📁  Deploy → models/best.pt",
            bg="#065f46", fg="#6ee7b7",
            activebackground="#047857", activeforeground="white",
            relief="flat", bd=0, padx=14, pady=8,
            font=("Segoe UI", 9, "bold"), cursor="hand2", state="disabled")
        deploy_btn.pack(side="right")

        # ── Log area ─────────────────────────────────────────────────
        tk.Frame(dialog, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(10, 0))

        log_outer = tk.Frame(dialog, bg=BG_DARK)
        log_outer.pack(fill="both", expand=True, padx=20, pady=(6, 16))

        log_text = tk.Text(
            log_outer, bg="#0d1117", fg="#c9d1d9",
            font=("Consolas", 8), relief="flat",
            wrap="word", state="disabled",
            insertbackground=TEXT_PRIMARY)
        log_scroll = ttk.Scrollbar(log_outer, orient="vertical", command=log_text.yview)
        log_text.configure(yscrollcommand=log_scroll.set)
        log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        log_text.tag_configure("info",  foreground="#58a6ff")
        log_text.tag_configure("warn",  foreground="#e3b341")
        log_text.tag_configure("error", foreground="#f85149")
        log_text.tag_configure("ok",    foreground="#56d364")

        _proc_ref: List[Any] = [None]

        def _log(msg: str):
            def _append():
                log_text.config(state="normal")
                tag = ("ok"    if "✓" in msg or "hoàn tất" in msg.lower() else
                       "error" if "[ERROR]" in msg else
                       "warn"  if "[WARN]"  in msg else
                       "info"  if "[INFO]"  in msg else None)
                log_text.insert("end", msg + "\n", tag or "")
                log_text.see("end")
                log_text.config(state="disabled")
            try:
                dialog.after(0, _append)
            except Exception:
                pass

        def _on_complete(best_pt: str):
            start_btn.config(state="normal", text="▶  Bắt đầu lại")
            stop_btn.config(state="disabled")
            if best_pt and os.path.isfile(best_pt):
                deploy_btn.config(state="normal",
                                  command=lambda: _deploy(best_pt))
                _log(f"[INFO] ✓ Weights: {best_pt}")
            else:
                _log("[WARN] Không tìm thấy best.pt — kiểm tra runs/train/")

        def _deploy(best_pt: str):
            import shutil
            try:
                os.makedirs("models", exist_ok=True)
                shutil.copy2(best_pt, "models/best.pt")
                _log("[INFO] ✓ Đã copy → models/best.pt")
                deploy_btn.config(text="✓  Đã deploy", state="disabled")
                from tkinter import messagebox
                messagebox.showinfo(
                    "Deploy thành công",
                    "models/best.pt đã được cập nhật.\n"
                    "Khởi động lại ứng dụng để dùng model mới.",
                    parent=dialog)
            except Exception as exc:
                _log(f"[ERROR] {exc}")

        def _stop():
            proc = _proc_ref[0]
            if proc and proc.poll() is None:
                proc.terminate()
                _log("[WARN] Đã dừng quá trình huấn luyện.")
            stop_btn.config(state="disabled")
            start_btn.config(state="normal")

        stop_btn.config(command=_stop)

        def _start():
            try:
                epochs = int(epochs_var.get())
                batch  = int(batch_var.get())
                imgsz  = int(imgsz_var.get())
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror("Lỗi cấu hình",
                                     "Epochs, Batch, Image size phải là số nguyên.",
                                     parent=dialog)
                return

            start_btn.config(state="disabled")
            stop_btn.config(state="normal")
            deploy_btn.config(state="disabled")
            log_text.config(state="normal")
            log_text.delete("1.0", "end")
            log_text.config(state="disabled")

            cfg = {
                "epochs": epochs, "batch": batch,
                "imgsz": imgsz,   "model": model_var.get(),
            }

            def _worker():
                try:
                    # Bước 1: chuẩn bị dataset
                    n = self._prepare_yolo_dataset(_log)
                    if n == 0:
                        dialog.after(0, lambda: start_btn.config(state="normal"))
                        dialog.after(0, lambda: stop_btn.config(state="disabled"))
                        return

                    # Bước 2: chạy src/train.py subprocess
                    import subprocess
                    data_yaml = os.path.abspath(os.path.join("data", "data.yaml"))
                    cmd = [
                        sys.executable, "src/train.py",
                        "--epochs", str(cfg["epochs"]),
                        "--batch",  str(cfg["batch"]),
                        "--imgsz",  str(cfg["imgsz"]),
                        "--model",  cfg["model"],
                        "--data",   data_yaml,
                    ]
                    _log(f"[INFO] Chạy: {' '.join(cmd)}")

                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace",
                        cwd=os.getcwd(),
                    )
                    _proc_ref[0] = proc

                    for line in iter(proc.stdout.readline, ""):
                        line = line.rstrip()
                        if line:
                            _log(line)
                    proc.wait()

                    # Tìm best.pt
                    import glob
                    candidates = sorted(
                        glob.glob("runs/train/**/best.pt", recursive=True),
                        key=os.path.getmtime, reverse=True)
                    best_pt = candidates[0] if candidates else ""

                    if proc.returncode == 0:
                        _log("[INFO] ✓ Huấn luyện hoàn tất!")
                        dialog.after(0, lambda: _on_complete(best_pt))
                    else:
                        _log(f"[ERROR] Kết thúc với mã lỗi {proc.returncode}")
                        dialog.after(0, lambda: start_btn.config(state="normal"))
                        dialog.after(0, lambda: stop_btn.config(state="disabled"))

                except Exception as exc:
                    _log(f"[ERROR] {exc}")
                    try:
                        dialog.after(0, lambda: start_btn.config(state="normal"))
                        dialog.after(0, lambda: stop_btn.config(state="disabled"))
                    except Exception:
                        pass

            threading.Thread(target=_worker, daemon=True).start()

        start_btn.config(command=_start)
