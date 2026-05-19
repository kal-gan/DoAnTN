"""
src/ui/app.py
FireSmokeMonitorApp - lớp ứng dụng chính, kết hợp các mixin chức năng.
UI được thiết kế lại: dark theme hiện đại với sidebar navigation.
"""
import os
import queue
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import tkinter as tk
from tkinter import messagebox, ttk

from .mixins.sources import SourcesMixin
from .mixins.detection import DetectionMixin
from .mixins.video_tiles import VideoTileMixin
from .mixins.statistics import StatsMixin
from .mixins.pages import PageBuilderMixin
from .mixins.alert_features import AlertFeaturesMixin
from .admin.controller import AdminController
from .widgets.alert_settings import AlertSettingsWindow

try:
    from src.services.database import AppDatabase
except ImportError:
    from services.database import AppDatabase  # type: ignore[no-redef]


# ── Màu sắc dark theme ──────────────────────────────────────────────────────
BG_DARK      = "#11141d"   # nền chính
BG_CARD      = "#1d212e"   # card / panel
BG_SIDEBAR   = "#0b0d15"   # sidebar
BG_HOVER     = "#2a3047"   # hover state
ACCENT       = "#f04e1a"   # cam đỏ — màu lửa
ACCENT2      = "#ff7a45"   # cam nhạt
TEXT_PRIMARY = "#f5f7fb"   # chữ chính
TEXT_MUTED   = "#9ba4b4"   # chữ phụ
TEXT_DIM     = "#4b5469"   # đường kẻ / divider
BORDER       = "#2b3047"   # viền
SUCCESS      = "#22c55e"   # xanh lá
WARNING      = "#fbbf24"   # vàng
DANGER       = "#ef4444"   # đỏ


class FireSmokeMonitorApp(
    SourcesMixin,
    DetectionMixin,
    VideoTileMixin,
    StatsMixin,
    PageBuilderMixin,
    AlertFeaturesMixin,
    tk.Tk,
):
    """
    Ứng dụng giám sát lửa và khói.
    Kết hợp các mixin chức năng để quản lý giao diện, phát hiện và thống kê.
    """

    def __init__(self):
        tk.Tk.__init__(self)
        self.title("FireGuard — Hệ thống giám sát Lửa & Khói")
        self.geometry("1400x860")
        self.minsize(1100, 720)
        self.configure(bg=BG_DARK)

        # ----- Database -----
        self.db = AppDatabase(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app_data.db"))
        )
        self.db.initialize()

        # ----- Trạng thái người dùng -----
        self.admin_user: Optional[Dict[str, Any]] = None

        # ----- Danh sách nguồn -----
        self.sources: List[Dict[str, Any]] = []

        # ----- Tham số model & phát hiện -----
        self.model_path = tk.StringVar(value="models/best.pt")
        self.conf_threshold = tk.DoubleVar(value=0.45)
        self.smoke_conf_threshold = tk.DoubleVar(value=0.55)
        self.target_fps = tk.IntVar(value=24)
        self.inference_stride = tk.IntVar(value=3)
        self.alert_frames = tk.IntVar(value=2)
        self.alert_cooldown = tk.DoubleVar(value=5.0)
        self.auto_save_alert = tk.BooleanVar(value=True)
        
        # ----- Data collection (controlled by admin) -----
        self.data_collection_enabled = False
        self.data_collector = None

        # ----- Cài đặt cảnh báo nâng cao -----
        self.sound_alert_enabled = tk.BooleanVar(value=True)
        self.sound_alert_volume = tk.IntVar(value=80)      # 0–100
        self.alerts_max_mb = tk.IntVar(value=300)          # MB tối đa
        self.alerts_max_days = tk.IntVar(value=7)          # ngày tối đa (1-7)
        # ----- Trạng thái vòng lặp phát hiện -----
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.ui_queue: "queue.Queue[tuple]" = queue.Queue(maxsize=4)  # non-frame events only
        self._latest_ui_frames: Dict[int, tuple] = {}  # tile_key → (tile_key, name, frame, labels)
        self._latest_ui_frames_lock = threading.Lock()
        self.detector = None
        self.alert_settings_window: Optional[AlertSettingsWindow] = None
        self.admin_controller = AdminController(self)
        self.stop_callback: Optional[Callable[[], None]] = None
        self.stop_poll_after_id: Optional[str] = None
        self.active_session_id: Optional[int] = None

        # ----- Trạng thái tile video -----
        self.stream_states: List[Dict[str, Any]] = []
        self.video_tiles: Dict[int, Dict[str, Any]] = {}
        self.latest_frames: Dict[int, Any] = {}
        self.tile_order: List[int] = []
        self.tile_layout_signature: Optional[tuple] = None
        self.focused_tile_key: Optional[int] = None

        # ----- Bộ đếm thống kê -----
        self.total_frames = 0
        self.fire_frames = 0
        self.smoke_frames = 0
        self.alert_count = 0
        self.current_fps = 0.0
        self.last_alert_time = 0.0
        self.consecutive_detection_frames = 0
        self.detection_icon_hold_seconds = 1.2
        self.background_detection_interval = 0.12

        # ----- Trang UI -----
        self.pages: Dict[str, tk.Frame] = {}
        self.current_page: Optional[str] = None
        self.source_summary = tk.StringVar(value="")

        # ----- StringVar thống kê -----
        self.stat_source = tk.StringVar(value="-")
        self.stat_total = tk.StringVar(value="0")
        self.stat_fps = tk.StringVar(value="0.0")
        self.stat_fire = tk.StringVar(value="0")
        self.stat_smoke = tk.StringVar(value="0")
        self.stat_alert = tk.StringVar(value="0")
        self.stat_risk = tk.StringVar(value="—")
        self.status_var = tk.StringVar(value="Sẵn sàng")

        # ----- Widget thống kê -----
        self.stats_ratio_figure = None
        self.stats_ratio_canvas = None
        self.stats_ratio_axes = None
        self.stats_source_figure = None
        self.stats_source_canvas = None
        self.stats_source_axes = None
        self.stats_trend_figure = None
        self.stats_trend_canvas = None
        self.stats_trend_axes = None
        self.risk_level_card: Optional[tk.Frame] = None
        self.risk_level_value_label: Optional[tk.Label] = None
        self.source_stats_tree = None
        self.class_stats_tree = None
        self.recent_stats_tree = None
        self.hourly_stats_tree = None
        self.daily_stats_tree = None
        self.stats_overview_text: Optional[tk.StringVar] = None
        self.log_text: Optional[tk.Text] = None

        # ----- Cache refresh thống kê -----
        self.last_stats_visual_refresh = 0.0
        self.last_stats_table_refresh = 0.0
        self.last_db_totals_refresh = 0.0
        self.db_total_events = 0
        self.db_fire_total = 0
        self.db_smoke_total = 0
        self.db_today_total = 0

        # ----- Sidebar nav button refs -----
        self._nav_buttons: Dict[str, tk.Label] = {}

        # ----- Khởi tạo giao diện -----
        self._configure_styles()
        self._build_layout()
        self._load_sources_from_db()
        self._load_runtime_settings()
        self._show_page("connection")
        self._set_status("Sẵn sàng")
        self.after(16, self._process_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ──────────────────────────────────────────────────────────────────────
    #  Lưu / nạp cấu hình runtime (DB)
    # ──────────────────────────────────────────────────────────────────────

    def _load_runtime_settings(self):
        """Nạp lại các tham số phát hiện / cảnh báo từ DB (nếu có)."""
        try:
            g = self.db.get_setting
        except Exception:
            return

        def _f(key, current, lo=None, hi=None):
            raw = g(key, "")
            if not raw:
                return current
            try:
                val = float(raw)
            except ValueError:
                return current
            if lo is not None: val = max(lo, val)
            if hi is not None: val = min(hi, val)
            return val

        def _i(key, current, lo=None, hi=None):
            raw = g(key, "")
            if not raw:
                return current
            try:
                val = int(float(raw))
            except ValueError:
                return current
            if lo is not None: val = max(lo, val)
            if hi is not None: val = min(hi, val)
            return val

        try:
            self.conf_threshold.set(_f("conf_threshold", self.conf_threshold.get(), 0.10, 0.95))
            self.smoke_conf_threshold.set(_f("smoke_conf_threshold", self.smoke_conf_threshold.get(), 0.10, 0.95))
            self.alert_frames.set(_i("alert_frames", self.alert_frames.get(), 1, 300))
            self.alert_cooldown.set(_f("alert_cooldown", self.alert_cooldown.get(), 0.5, 60.0))
            raw_auto = g("auto_save_alert", "")
            if raw_auto:
                self.auto_save_alert.set(raw_auto == "1")
            raw_snd = g("sound_alert_enabled", "")
            if raw_snd:
                self.sound_alert_enabled.set(raw_snd == "1")
            self.sound_alert_volume.set(_i("sound_alert_volume", self.sound_alert_volume.get(), 0, 100))
            self.alerts_max_mb.set(_i("alerts_max_mb", self.alerts_max_mb.get(), 50, 10000))
            self.alerts_max_days.set(_i("alerts_max_days", self.alerts_max_days.get(), 1, 7))
            mp = g("model_path", "")
            if mp and os.path.isfile(mp):
                self.model_path.set(mp)
        except Exception:
            pass

    def save_runtime_settings(self):
        """Lưu các tham số phát hiện / cảnh báo xuống DB."""
        try:
            s = self.db.set_setting
        except Exception:
            return
        try:
            s("conf_threshold",       f"{float(self.conf_threshold.get()):.3f}")
            s("smoke_conf_threshold", f"{float(self.smoke_conf_threshold.get()):.3f}")
            s("alert_frames",         str(int(self.alert_frames.get())))
            s("alert_cooldown",       f"{float(self.alert_cooldown.get()):.2f}")
            s("auto_save_alert",      "1" if bool(self.auto_save_alert.get()) else "0")
            s("sound_alert_enabled",  "1" if bool(self.sound_alert_enabled.get()) else "0")
            s("sound_alert_volume",   str(int(self.sound_alert_volume.get())))
            s("alerts_max_mb",        str(int(self.alerts_max_mb.get())))
            s("alerts_max_days",      str(int(self.alerts_max_days.get())))
            s("model_path",           str(self.model_path.get() or ""))
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────
    #  Styles
    # ──────────────────────────────────────────────────────────────────────

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Global ttk overrides
        style.configure(".",
            background=BG_DARK, foreground=TEXT_PRIMARY,
            fieldbackground=BG_CARD, bordercolor=BORDER,
            troughcolor=BG_CARD, selectbackground=ACCENT,
            selectforeground=TEXT_PRIMARY, font=("Segoe UI", 10),
        )
        style.configure("TFrame", background=BG_DARK)
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_PRIMARY)
        style.configure("TLabelframe",
            background=BG_CARD, foreground=TEXT_PRIMARY,
            bordercolor=BORDER, relief="flat",
        )
        style.configure("TLabelframe.Label",
            background=BG_CARD, foreground=TEXT_PRIMARY,
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("TNotebook",
            background=BG_DARK, bordercolor=BORDER, tabmargins=[0, 0, 0, 0],
        )
        style.configure("TNotebook.Tab",
            background=BG_CARD, foreground=TEXT_MUTED,
            padding=[18, 10], font=("Segoe UI", 10),
        )
        style.map("TNotebook.Tab",
            background=[("selected", BG_DARK)],
            foreground=[("selected", TEXT_PRIMARY)],
        )
        style.configure("Treeview",
            background=BG_CARD, foreground=TEXT_PRIMARY,
            fieldbackground=BG_CARD, rowheight=32,
            bordercolor=BORDER, relief="flat",
            font=("Segoe UI", 10),
        )
        style.configure("Treeview.Heading",
            background=BG_SIDEBAR, foreground=TEXT_PRIMARY,
            relief="flat", font=("Segoe UI", 10, "bold"),
            padding=[8, 6],
        )
        style.map("Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#ffffff")],
        )
        style.configure("TScrollbar",
            background=BG_CARD, troughcolor=BG_DARK,
            arrowcolor=TEXT_MUTED, relief="flat",
        )
        style.configure("Header.TLabel",
            font=("Segoe UI", 18, "bold"),
            background=BG_DARK, foreground=TEXT_PRIMARY,
        )
        style.configure("Muted.TLabel",
            foreground=TEXT_MUTED, background=BG_DARK,
            font=("Segoe UI", 10),
        )
        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("CardMuted.TLabel",
            foreground=TEXT_MUTED, background=BG_CARD,
            font=("Segoe UI", 10),
        )
        style.configure("CardValue.TLabel",
            foreground=TEXT_PRIMARY, background=BG_CARD,
            font=("Segoe UI", 24, "bold"),
        )
        style.configure("CardTitle.TLabel",
            foreground=TEXT_PRIMARY, background=BG_CARD,
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("SummaryValue.TLabel",
            font=("Segoe UI", 13, "bold"), background=BG_CARD,
        )
        # ttk Entry / Combobox / Spinbox padding for readability
        style.configure("TEntry", padding=6, fieldbackground=BG_CARD,
                        foreground=TEXT_PRIMARY, insertcolor=TEXT_PRIMARY)
        style.configure("TCombobox", padding=6, fieldbackground=BG_CARD,
                        foreground=TEXT_PRIMARY, arrowcolor=TEXT_PRIMARY)
        style.configure("TSpinbox", padding=6, fieldbackground=BG_CARD,
                        foreground=TEXT_PRIMARY, arrowcolor=TEXT_PRIMARY)
        style.configure("TButton", padding=[14, 8], font=("Segoe UI", 10))
        # ttk Progressbar
        style.configure("Horizontal.TProgressbar",
                        background=ACCENT, troughcolor=BG_CARD,
                        bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)

    # ──────────────────────────────────────────────────────────────────────
    #  Layout tổng thể
    # ──────────────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.columnconfigure(0, weight=0)  # sidebar cố định
        self.columnconfigure(1, weight=1)  # content
        self.rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()

    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg=BG_SIDEBAR, width=248)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)

        # Logo / brand
        brand = tk.Frame(sidebar, bg=BG_SIDEBAR, pady=26)
        brand.grid(row=0, column=0, sticky="ew")
        tk.Label(
            brand, text="🔥 FireGuard",
            bg=BG_SIDEBAR, fg=ACCENT,
            font=("Segoe UI", 17, "bold"),
        ).pack(padx=22, anchor="w")
        tk.Label(
            brand, text="Hệ thống giám sát Lửa & Khói",
            bg=BG_SIDEBAR, fg=TEXT_MUTED,
            font=("Segoe UI", 9),
        ).pack(padx=22, anchor="w", pady=(2, 0))

        # Divider
        tk.Frame(sidebar, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew", padx=18)

        # Section label
        tk.Label(sidebar, text="ĐIỀU HƯỚNG",
                 bg=BG_SIDEBAR, fg=TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).grid(
            row=2, column=0, sticky="w", padx=22, pady=(14, 4))

        # Nav items
        nav_frame = tk.Frame(sidebar, bg=BG_SIDEBAR)
        nav_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))

        nav_items = [
            ("connection", "▶", "Giám sát"),
            ("stats",      "📊", "Thống kê"),
            ("gallery",    "🎥", "Video cảnh báo"),
            ("log",        "📋", "Nhật ký"),
        ]
        for page_key, icon, label in nav_items:
            row = tk.Frame(nav_frame, bg=BG_SIDEBAR)
            row.pack(fill="x", pady=1)
            # left accent bar (hidden by default)
            accent_bar = tk.Frame(row, bg=BG_SIDEBAR, width=3)
            accent_bar.pack(side="left", fill="y")
            btn = tk.Label(
                row, text=f"  {icon}   {label}",
                bg=BG_SIDEBAR, fg=TEXT_MUTED,
                font=("Segoe UI", 11),
                pady=11, padx=16, anchor="w", cursor="hand2",
            )
            btn.pack(side="left", fill="x", expand=True)
            for w in (row, btn, accent_bar):
                w.bind("<Button-1>", lambda e, k=page_key: self._show_page(k))
            btn.bind("<Enter>", lambda e, b=btn: self._nav_hover(b, True))
            btn.bind("<Leave>", lambda e, b=btn: self._nav_hover(b, False))
            self._nav_buttons[page_key] = btn
            # Store accent bar reference for active state
            btn._accent_bar = accent_bar  # type: ignore[attr-defined]

        # Divider
        tk.Frame(sidebar, bg=BORDER, height=1).grid(row=4, column=0, sticky="ew", padx=18)

        # Section label
        tk.Label(sidebar, text="ĐIỀU KHIỂN",
                 bg=BG_SIDEBAR, fg=TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).grid(
            row=5, column=0, sticky="w", padx=22, pady=(14, 6))

        # Control buttons
        ctrl_frame = tk.Frame(sidebar, bg=BG_SIDEBAR)
        ctrl_frame.grid(row=6, column=0, sticky="ew", pady=(0, 8))

        start_btn = tk.Button(
            ctrl_frame, text="▶  Bắt đầu giám sát",
            bg=ACCENT, fg="#ffffff",
            activebackground=ACCENT2, activeforeground="#ffffff",
            relief="flat", bd=0, pady=11, padx=20,
            font=("Segoe UI", 11, "bold"), cursor="hand2",
            command=lambda: self.start_detection(require_admin=True),
        )
        start_btn.pack(fill="x", padx=18, pady=(0, 8))

        stop_btn = tk.Button(
            ctrl_frame, text="■  Dừng",
            bg=BG_HOVER, fg=TEXT_PRIMARY,
            activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
            relief="flat", bd=0, pady=10, padx=20,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            command=lambda: self.stop_detection(require_admin=True),
        )
        stop_btn.pack(fill="x", padx=18)

        # Spacer
        spacer = tk.Frame(sidebar, bg=BG_SIDEBAR)
        spacer.grid(row=7, column=0, sticky="nsew")
        sidebar.rowconfigure(7, weight=1)

        # Bottom area
        bottom = tk.Frame(sidebar, bg=BG_SIDEBAR, pady=14)
        bottom.grid(row=8, column=0, sticky="ew")
        tk.Frame(bottom, bg=BORDER, height=1).pack(fill="x", padx=18, pady=(0, 12))

        admin_btn = tk.Button(
            bottom, text="⚙   Bảng quản trị",
            bg=BG_SIDEBAR, fg=TEXT_PRIMARY,
            activebackground=BG_HOVER, activeforeground=TEXT_PRIMARY,
            relief="flat", bd=0, pady=10, padx=20,
            font=("Segoe UI", 10), cursor="hand2", anchor="w",
            command=self.admin_controller.open_admin_panel,
        )
        admin_btn.pack(fill="x", padx=18)

        # Status dot + text
        status_row = tk.Frame(sidebar, bg=BG_SIDEBAR, pady=10)
        status_row.grid(row=9, column=0, sticky="ew", padx=22)
        self._status_dot = tk.Label(status_row, text="●", bg=BG_SIDEBAR, fg=TEXT_MUTED, font=("Segoe UI", 12))
        self._status_dot.pack(side="left")
        tk.Label(
            status_row, textvariable=self.status_var,
            bg=BG_SIDEBAR, fg=TEXT_PRIMARY,
            font=("Segoe UI", 9), wraplength=190, justify="left",
        ).pack(side="left", padx=(8, 0))

    def _nav_hover(self, btn: tk.Label, hovering: bool):
        page_key = next((k for k, v in self._nav_buttons.items() if v is btn), None)
        is_active = page_key and page_key == self.current_page
        if is_active:
            btn.config(bg=BG_CARD, fg=TEXT_PRIMARY)
        elif hovering:
            btn.config(bg=BG_HOVER, fg=TEXT_PRIMARY)
        else:
            btn.config(bg=BG_SIDEBAR, fg=TEXT_MUTED)

    def _nav_leave(self, btn: tk.Label):
        """Compat alias used elsewhere."""
        self._nav_hover(btn, False)

    def _build_content_area(self):
        self.page_container = tk.Frame(self, bg=BG_DARK)
        self.page_container.grid(row=0, column=1, sticky="nsew")
        self.page_container.columnconfigure(0, weight=1)
        self.page_container.rowconfigure(0, weight=1)

        self.pages["connection"] = self._create_connection_page()
        self.pages["stats"] = self._create_stats_page()
        self.pages["gallery"] = self._create_gallery_page()
        self.pages["log"] = self._create_log_page()

        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

    # ──────────────────────────────────────────────────────────────────────
    #  Điều hướng trang
    # ──────────────────────────────────────────────────────────────────────

    def _show_page(self, page_key: str):
        page = self.pages.get(page_key)
        if page is None:
            return
        page.tkraise()
        self.current_page = page_key

        # Highlight active nav: brighter bg + accent left bar
        for k, btn in self._nav_buttons.items():
            bar = getattr(btn, "_accent_bar", None)
            if k == page_key:
                btn.config(bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 11, "bold"))
                if bar is not None:
                    bar.config(bg=ACCENT)
            else:
                btn.config(bg=BG_SIDEBAR, fg=TEXT_MUTED, font=("Segoe UI", 11))
                if bar is not None:
                    bar.config(bg=BG_SIDEBAR)

    def _show_connection_page(self):
        self._show_page("connection")

    def _show_stats_page(self):
        self._show_page("stats")
        self._update_stats_display(force_visual_refresh=True, force_table_refresh=True)

    def _show_log_page(self):
        self._show_page("log")

    def _open_alert_settings_from_menu(self):
        self._show_connection_page()
        self.open_alert_settings_window()

    def _export_statistics_from_menu(self):
        self._show_stats_page()
        self.export_statistics_csv()

    def _export_statistics_pdf_from_menu(self):
        self._show_stats_page()
        self.export_statistics_pdf()

    def _reset_statistics_from_menu(self):
        self._show_stats_page()
        self._reset_statistics()

    def _clear_log_from_menu(self):
        self._show_log_page()
        self._clear_log()

    # ──────────────────────────────────────────────────────────────────────
    #  Nhật ký và trạng thái
    # ──────────────────────────────────────────────────────────────────────

    def _set_status(self, text: str):
        self.status_var.set(text)
        # Đổi màu dot theo trạng thái
        if hasattr(self, "_status_dot"):
            if "Đang chạy" in text or "chạy" in text.lower():
                self._status_dot.config(fg=SUCCESS)
            elif "Dừng" in text or "dừng" in text.lower() or "Đã" in text:
                self._status_dot.config(fg=TEXT_MUTED)
            elif "lỗi" in text.lower() or "thất bại" in text.lower():
                self._status_dot.config(fg=DANGER)
            else:
                self._status_dot.config(fg=WARNING)

    def _log(self, text: str):
        if self.log_text is None:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {text}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        if self.log_text is None:
            return
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self._log("Đã xóa nhật ký sự kiện.")

    # ──────────────────────────────────────────────────────────────────────
    #  Về chúng tôi
    # ──────────────────────────────────────────────────────────────────────

    def _show_about(self):
        messagebox.showinfo(
            title="Giới thiệu",
            message=(
                "FireGuard — Hệ thống giám sát Lửa & Khói\n"
                "- Hỗ trợ giao diện đa trang\n"
                "- Toàn bộ menu và nhãn đã Việt hóa\n"
                "- Hỗ trợ giám sát nhiều camera/video cùng lúc"
            ),
        )

    # ──────────────────────────────────────────────────────────────────────
    #  Đóng ứng dụng
    # ──────────────────────────────────────────────────────────────────────

    def _on_close(self):
        if self.is_running:
            self.stop_detection(require_admin=False, on_stopped=self._complete_close)
            return
        self._complete_close()

    def _complete_close(self):
        try:
            self.save_runtime_settings()
        except Exception:
            pass
        self.admin_controller.close_admin_panel()
        self.admin_controller.close_settings_window()
        self._close_alert_settings_window()
        self.admin_controller.close_source_window()
        try:
            if self.admin_user is not None:
                self.db.add_audit_log(int(self.admin_user["id"]), "logout", f"username={self.admin_user['username']}")
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass
        self.destroy()


def main():
    app = FireSmokeMonitorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
