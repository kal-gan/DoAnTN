"""
src/ui/widgets/alert_settings.py
Cửa sổ cài đặt tham số cảnh báo (ngưỡng, cooldown, âm thanh, dung lượng...).
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

BG_DARK      = "#11141d"
BG_CARD      = "#1d212e"
BG_HOVER     = "#2a3047"
ACCENT       = "#f04e1a"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED   = "#9ba4b4"
BORDER       = "#2b3047"
SUCCESS      = "#22c55e"
WARNING      = "#fbbf24"


def _label(parent, text, muted=False, bold=False):
    font = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
    fg = TEXT_MUTED if muted else TEXT_PRIMARY
    return tk.Label(parent, text=text, bg=BG_CARD, fg=fg, font=font, anchor="w")


def _sep(parent):
    return tk.Frame(parent, bg=BORDER, height=1)


class AlertSettingsWindow(tk.Toplevel):
    """Cửa sổ cài đặt tham số cảnh báo phát hiện lửa/khói."""

    def __init__(
        self,
        parent: tk.Misc,
        conf_threshold: tk.DoubleVar,
        alert_frames: tk.IntVar,
        alert_cooldown: tk.DoubleVar,
        auto_save_alert: tk.BooleanVar,
        on_close: Callable[[], None],
        sound_alert_enabled: Optional[tk.BooleanVar] = None,
        sound_alert_volume: Optional[tk.IntVar] = None,
        alerts_max_mb: Optional[tk.IntVar] = None,
        alerts_max_days: Optional[tk.IntVar] = None,
        smoke_conf_threshold: Optional[tk.DoubleVar] = None,
    ):
        super().__init__(parent)
        self.title("Cài đặt cảnh báo")
        self.geometry("540x500")
        self.minsize(500, 460)
        self.resizable(True, True)
        self.transient(parent)
        self.configure(bg=BG_DARK)

        # ── Scrollable canvas ──────────────────────────────────────────
        canvas = tk.Canvas(self, bg=BG_DARK, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG_DARK)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_configure(e):
            canvas.itemconfig(inner_id, width=e.width)
        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # ── Section helper ─────────────────────────────────────────────
        def section(title: str) -> tk.Frame:
            hdr = tk.Frame(inner, bg=BG_DARK)
            hdr.pack(fill="x", padx=16, pady=(18, 2))
            tk.Label(hdr, text=title, bg=BG_DARK, fg=ACCENT,
                     font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Frame(hdr, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(10, 0), pady=4)
            card = tk.Frame(inner, bg=BG_CARD, padx=14, pady=10)
            card.pack(fill="x", padx=16, pady=(0, 4))
            card.columnconfigure(1, weight=1)
            return card

        def row(card, r, label_text, widget_fn):
            _label(card, label_text).grid(row=r, column=0, sticky="w", pady=5, padx=(0, 16))
            w = widget_fn(card)
            w.grid(row=r, column=1, sticky="ew", pady=5)
            return w

        # ─── Nhận dạng ────────────────────────────────────────────────
        card1 = section("⚙  Nhận dạng")

        # Confidence threshold
        _label(card1, "Ngưỡng tin cậy").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 16))
        conf_row = tk.Frame(card1, bg=BG_CARD)
        conf_row.grid(row=0, column=1, sticky="ew", pady=5)
        conf_row.columnconfigure(0, weight=1)
        conf_val_var = tk.StringVar(value=f"{conf_threshold.get():.2f}")
        def _on_conf(*_):
            conf_val_var.set(f"{conf_threshold.get():.2f}")
        conf_threshold.trace_add("write", _on_conf)
        tk.Scale(conf_row, from_=0.10, to=0.95, variable=conf_threshold,
                 orient="horizontal", resolution=0.01, showvalue=False,
                 bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT,
                 troughcolor=BG_HOVER, highlightthickness=0, bd=0).grid(row=0, column=0, sticky="ew")
        tk.Label(conf_row, textvariable=conf_val_var, width=5,
                 bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 9)).grid(row=0, column=1, padx=(8, 0))

        # Smoke confidence threshold (separate, tương đương cho khói để tránh nhầm sương/mờ cam)
        next_row = 1
        if smoke_conf_threshold is not None:
            _label(card1, "Ngưỡng tin cậy (khói)").grid(row=1, column=0, sticky="w", pady=5, padx=(0, 16))
            sconf_row = tk.Frame(card1, bg=BG_CARD)
            sconf_row.grid(row=1, column=1, sticky="ew", pady=5)
            sconf_row.columnconfigure(0, weight=1)
            sconf_val_var = tk.StringVar(value=f"{smoke_conf_threshold.get():.2f}")
            def _on_sconf(*_):
                sconf_val_var.set(f"{smoke_conf_threshold.get():.2f}")
            smoke_conf_threshold.trace_add("write", _on_sconf)
            tk.Scale(sconf_row, from_=0.10, to=0.95, variable=smoke_conf_threshold,
                     orient="horizontal", resolution=0.01, showvalue=False,
                     bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT,
                     troughcolor=BG_HOVER, highlightthickness=0, bd=0).grid(row=0, column=0, sticky="ew")
            tk.Label(sconf_row, textvariable=sconf_val_var, width=5,
                     bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 9)).grid(row=0, column=1, padx=(8, 0))
            next_row = 2

        # Alert frames
        _label(card1, "Số frame cảnh báo").grid(row=next_row, column=0, sticky="w", pady=5, padx=(0, 16))
        tk.Spinbox(card1, from_=1, to=300, textvariable=alert_frames, width=8,
                   bg=BG_HOVER, fg=TEXT_PRIMARY, buttonbackground=BG_HOVER,
                   insertbackground=TEXT_PRIMARY, relief="flat", bd=1,
                   font=("Segoe UI", 9)).grid(row=next_row, column=1, sticky="w", pady=5)

        # Cooldown
        _label(card1, "Cooldown (giây)").grid(row=next_row + 1, column=0, sticky="w", pady=5, padx=(0, 16))
        tk.Spinbox(card1, from_=0.5, to=60.0, increment=0.5, textvariable=alert_cooldown, width=8,
                   bg=BG_HOVER, fg=TEXT_PRIMARY, buttonbackground=BG_HOVER,
                   insertbackground=TEXT_PRIMARY, relief="flat", bd=1,
                   font=("Segoe UI", 9)).grid(row=next_row + 1, column=1, sticky="w", pady=5)

        # Auto save
        chk_save = tk.Checkbutton(card1, text="Tự động lưu ảnh cảnh báo",
                                  variable=auto_save_alert,
                                  bg=BG_CARD, fg=TEXT_PRIMARY, selectcolor=BG_HOVER,
                                  activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
                                  font=("Segoe UI", 9))
        chk_save.grid(row=next_row + 2, column=0, columnspan=2, sticky="w", pady=5)

        # ─── Âm thanh cảnh báo ────────────────────────────────────────
        card2 = section("🔊  Âm thanh cảnh báo")

        _snd_enabled = sound_alert_enabled if sound_alert_enabled is not None else tk.BooleanVar(value=True)
        _snd_volume  = sound_alert_volume  if sound_alert_volume  is not None else tk.IntVar(value=80)

        chk_sound = tk.Checkbutton(card2, text="Bật âm thanh cảnh báo",
                                   variable=_snd_enabled,
                                   bg=BG_CARD, fg=TEXT_PRIMARY, selectcolor=BG_HOVER,
                                   activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
                                   font=("Segoe UI", 9))
        chk_sound.grid(row=0, column=0, columnspan=2, sticky="w", pady=5)

        _label(card2, "Âm lượng (%)").grid(row=1, column=0, sticky="w", pady=5, padx=(0, 16))
        vol_row = tk.Frame(card2, bg=BG_CARD)
        vol_row.grid(row=1, column=1, sticky="ew", pady=5)
        vol_row.columnconfigure(0, weight=1)
        vol_val_var = tk.StringVar(value=str(_snd_volume.get()))
        def _on_vol(*_):
            vol_val_var.set(str(_snd_volume.get()))
            _vol_scale.config(state="normal" if _snd_enabled.get() else "disabled")
        _snd_volume.trace_add("write", _on_vol)
        _snd_enabled.trace_add("write", _on_vol)
        _vol_scale = tk.Scale(vol_row, from_=0, to=100, variable=_snd_volume,
                              orient="horizontal", resolution=1, showvalue=False,
                              bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT,
                              troughcolor=BG_HOVER, highlightthickness=0, bd=0)
        _vol_scale.grid(row=0, column=0, sticky="ew")
        tk.Label(vol_row, textvariable=vol_val_var, width=4,
                 bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 9)).grid(row=0, column=1, padx=(8, 0))

        # disable volume slider when sound is off
        def _toggle_vol(*_):
            _vol_scale.config(state="normal" if _snd_enabled.get() else "disabled")
        _snd_enabled.trace_add("write", _toggle_vol)
        _toggle_vol()

        # ─── Quản lý thư mục alerts/ ─────────────────────────────────
        card3 = section("🗂  Quản lý thư mục cảnh báo")

        _max_mb   = alerts_max_mb   if alerts_max_mb   is not None else tk.IntVar(value=300)
        _max_days = alerts_max_days if alerts_max_days is not None else tk.IntVar(value=7)

        _label(card3, "Dung lượng tối đa (MB)").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 16))
        tk.Spinbox(card3, from_=50, to=10000, increment=50, textvariable=_max_mb, width=8,
                   bg=BG_HOVER, fg=TEXT_PRIMARY, buttonbackground=BG_HOVER,
                   insertbackground=TEXT_PRIMARY, relief="flat", bd=1,
                   font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w", pady=5)

        _label(card3, "Tự động xóa sau (ngày)").grid(row=1, column=0, sticky="w", pady=5, padx=(0, 16))
        days_row = tk.Frame(card3, bg=BG_CARD)
        days_row.grid(row=1, column=1, sticky="ew", pady=5)
        days_row.columnconfigure(0, weight=1)
        days_val_var = tk.StringVar(value=f"{_max_days.get()} ngày")
        def _on_days(*_):
            days_val_var.set(f"{_max_days.get()} ngày")
        _max_days.trace_add("write", _on_days)
        tk.Scale(days_row, from_=1, to=7, variable=_max_days,
                 orient="horizontal", resolution=1, showvalue=False,
                 bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT,
                 troughcolor=BG_HOVER, highlightthickness=0, bd=0).grid(row=0, column=0, sticky="ew")
        tk.Label(days_row, textvariable=days_val_var, width=7,
                 bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 9)).grid(row=0, column=1, padx=(8, 0))

        _label(card3, "", muted=True).grid(row=2, column=0, columnspan=2, sticky="w", pady=0)
        tk.Label(card3, text="  File cũ hơn số ngày trên HOẶC vượt dung lượng sẽ bị xóa tự động.",
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 8), wraplength=350, justify="left",
                 anchor="w").grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 4))

        # ─── Nút đóng ─────────────────────────────────────────────────
        btn_row = tk.Frame(inner, bg=BG_DARK)
        btn_row.pack(fill="x", padx=16, pady=(12, 16), anchor="e")
        tk.Button(btn_row, text="Đóng",
                  bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", bd=0,
                  activebackground="#c73508", activeforeground=TEXT_PRIMARY,
                  font=("Segoe UI", 10, "bold"), padx=20, pady=7, cursor="hand2",
                  command=on_close).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", on_close)
