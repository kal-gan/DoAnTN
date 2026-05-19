"""
src/ui/mixins/pages.py
PageBuilderMixin - xây dựng các trang UI (giám sát, thống kê, nhật ký).
UI thiết kế lại: dark theme hiện đại, card layout, clean typography.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Màu sắc (mirror từ app.py)
BG_DARK    = "#11141d"
BG_CARD    = "#1d212e"
BG_HOVER   = "#2a3047"
ACCENT     = "#f04e1a"
ACCENT2    = "#ff7a45"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED   = "#9ba4b4"
BORDER       = "#2b3047"
SUCCESS      = "#22c55e"
WARNING      = "#fbbf24"
DANGER       = "#ef4444"


def _make_card(parent, **kwargs) -> tk.Frame:
    """Tạo card với background BG_CARD + viền 1px để dễ nhìn."""
    kwargs.setdefault("highlightbackground", BORDER)
    kwargs.setdefault("highlightcolor", BORDER)
    kwargs.setdefault("highlightthickness", 1)
    kwargs.setdefault("bd", 0)
    return tk.Frame(parent, bg=BG_CARD, **kwargs)


def _label(parent, text="", textvariable=None, size=10, bold=False,
           color=TEXT_PRIMARY, bg=BG_CARD, **kwargs):
    font = ("Segoe UI", size, "bold" if bold else "normal")
    kw = dict(bg=bg, fg=color, font=font)
    if textvariable is not None:
        kw["textvariable"] = textvariable
    else:
        kw["text"] = text
    return tk.Label(parent, **kw, **kwargs)


class PageBuilderMixin:
    """Mixin chứa các phương thức tạo trang UI cho ứng dụng."""

    # ──────────────────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────────────────

    def _page_header(self, parent: tk.Frame, title: str, subtitle: str = ""):
        hdr = tk.Frame(parent, bg=BG_DARK)
        hdr.pack(fill="x", padx=28, pady=(22, 0))
        _label(hdr, text=title, size=20, bold=True, bg=BG_DARK).pack(anchor="w")
        if subtitle:
            _label(hdr, text=subtitle, size=10, color=TEXT_MUTED, bg=BG_DARK).pack(anchor="w", pady=(4, 0))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=28, pady=(14, 0))

    def _stat_card(self, parent, label: str, var: tk.StringVar,
                   accent_color=TEXT_PRIMARY, col=0) -> tk.Frame:
        card = _make_card(parent, padx=22, pady=18)
        _label(card, text=label, size=10, color=TEXT_MUTED).pack(anchor="w")
        _label(card, textvariable=var, size=28, bold=True, color=accent_color).pack(anchor="w", pady=(6, 0))
        return card

    @staticmethod
    def _stat_row(parent, row: int, name: str, value_var: tk.StringVar):
        """Compat method cho StatsMixin."""
        ttk.Label(parent, text=f"{name}:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Label(parent, textvariable=value_var, font=("Segoe UI", 11, "bold")).grid(
            row=row, column=1, sticky="e", pady=4)

    def _section_label(self, parent, text: str):
        f = tk.Frame(parent, bg=BG_DARK)
        f.pack(fill="x", padx=28, pady=(22, 8))
        _label(f, text=text, size=11, bold=True, color=TEXT_PRIMARY, bg=BG_DARK).pack(anchor="w")

    # ──────────────────────────────────────────────────────────────────
    #  Trang Giám sát (connection)
    # ──────────────────────────────────────────────────────────────────

    def _create_connection_page(self) -> tk.Frame:
        page = tk.Frame(self.page_container, bg=BG_DARK)  # type: ignore[attr-defined]

        # Header row với stat cards
        self._page_header(page, "Giám sát trực tiếp")

        # Mini stat strip
        stat_strip = tk.Frame(page, bg=BG_DARK)
        stat_strip.pack(fill="x", padx=28, pady=(12, 0))
        for col in range(4):
            stat_strip.columnconfigure(col, weight=1, uniform="ministat")

        mini_stats = [
            ("Nguồn",         self.stat_source,  TEXT_PRIMARY),  # type: ignore[attr-defined]
            ("Lửa",           self.stat_fire,    ACCENT),        # type: ignore[attr-defined]
            ("Khói",          self.stat_smoke,   WARNING),       # type: ignore[attr-defined]
            ("Cảnh báo",      self.stat_alert,   DANGER),        # type: ignore[attr-defined]
        ]
        for i, (lbl, var, color) in enumerate(mini_stats):
            card = _make_card(stat_strip, padx=14, pady=10)
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 8 if i < 3 else 0))
            _label(card, text=lbl, size=9, color=TEXT_MUTED).pack(anchor="w")
            _label(card, textvariable=var, size=20, bold=True, color=color).pack(anchor="w", pady=(2, 0))

        # Risk strip
        risk_strip = tk.Frame(page, bg=BG_DARK)
        risk_strip.pack(fill="x", padx=28, pady=(6, 0))
        risk_card = _make_card(risk_strip, padx=16, pady=8)
        risk_card.pack(fill="x")
        _label(risk_card, text="Mức rủi ro hiện tại", size=9, color=TEXT_MUTED).pack(side="left")
        self.monitor_risk_label = tk.Label(  # type: ignore[attr-defined]
            risk_card, textvariable=self.stat_risk,  # type: ignore[attr-defined]
            bg=BG_CARD, fg=SUCCESS,
            font=("Segoe UI", 13, "bold"),
        )
        self.monitor_risk_label.pack(side="left", padx=(10, 0))  # type: ignore[attr-defined]

        # Toolbar
        toolbar = tk.Frame(page, bg=BG_DARK)
        toolbar.pack(fill="x", padx=28, pady=(8, 0))
        self.restore_layout_button = tk.Button(  # type: ignore[attr-defined]
            toolbar, text="↺  Khôi phục layout",
            bg=BG_CARD, fg=TEXT_PRIMARY,
            activebackground=BG_HOVER, activeforeground=TEXT_PRIMARY,
            relief="flat", bd=0, padx=14, pady=6,
            font=("Segoe UI", 9), cursor="hand2",
            command=self._restart_monitoring,  # type: ignore[attr-defined]
        )
        self.restore_layout_button.pack(side="right")

        # Video area — phóng to: giảm padding, lấp đầy phần còn lại
        video_outer = _make_card(page)
        video_outer.pack(fill="both", expand=True, padx=20, pady=(6, 14))

        self.video_panel = video_outer  # type: ignore[attr-defined]
        self.video_panel.rowconfigure(0, weight=1)  # type: ignore[attr-defined]
        self.video_panel.columnconfigure(0, weight=1)  # type: ignore[attr-defined]

        self.video_grid_container = tk.Frame(self.video_panel, bg=BG_CARD)  # type: ignore[attr-defined]
        self.video_grid_container.pack(fill="both", expand=True, padx=8, pady=8)  # type: ignore[attr-defined]

        self.video_panel.bind("<Configure>", self._redraw_all_tiles)  # type: ignore[attr-defined]

        self._update_source_summary()  # type: ignore[attr-defined]
        self._ensure_video_tiles()     # type: ignore[attr-defined]

        return page

    # ──────────────────────────────────────────────────────────────────
    #  Trang Thống kê
    # ──────────────────────────────────────────────────────────────────

    def _create_stats_page(self) -> tk.Frame:
        page = tk.Frame(self.page_container, bg=BG_DARK)  # type: ignore[attr-defined]
        self._page_header(page, "Thống kê giám sát", "Dữ liệu phát hiện tích lũy theo thời gian")

        # Export toolbar
        export_bar = tk.Frame(page, bg=BG_DARK)
        export_bar.pack(fill="x", padx=24, pady=(8, 0))
        tk.Button(
            export_bar, text="⬇  Xuất PDF",
            bg=ACCENT, fg=TEXT_PRIMARY,
            activebackground=ACCENT2, activeforeground=TEXT_PRIMARY,
            relief="flat", bd=0, padx=14, pady=6,
            font=("Segoe UI", 9, "bold"), cursor="hand2",
            command=self.export_statistics_pdf,  # type: ignore[attr-defined]
        ).pack(side="left")
        tk.Button(
            export_bar, text="⬇  Xuất CSV",
            bg=BG_CARD, fg=TEXT_MUTED,
            activebackground=BG_HOVER, activeforeground=TEXT_PRIMARY,
            relief="flat", bd=0, padx=14, pady=6,
            font=("Segoe UI", 9), cursor="hand2",
            command=self.export_statistics_csv,  # type: ignore[attr-defined]
        ).pack(side="left", padx=(8, 0))

        notebook = ttk.Notebook(page)
        notebook.pack(fill="both", expand=True, padx=24, pady=(16, 20))

        overview_tab = tk.Frame(notebook, bg=BG_DARK)
        charts_tab   = tk.Frame(notebook, bg=BG_DARK)
        tables_tab   = tk.Frame(notebook, bg=BG_DARK)

        notebook.add(overview_tab, text="  Tổng quan  ")
        notebook.add(charts_tab,   text="  Biểu đồ  ")
        notebook.add(tables_tab,   text="  Bảng dữ liệu  ")

        # ── Tab Tổng quan ──
        cards_row = tk.Frame(overview_tab, bg=BG_DARK)
        cards_row.pack(fill="x", pady=(16, 0))
        for col in range(3):
            cards_row.columnconfigure(col, weight=1, uniform="scard")

        overview_data = [
            ("Tổng frames",      self.stat_total,  TEXT_PRIMARY),   # type: ignore[attr-defined]
            ("Frames có lửa",    self.stat_fire,   ACCENT),         # type: ignore[attr-defined]
            ("Frames có khói",   self.stat_smoke,  WARNING),        # type: ignore[attr-defined]
        ]
        for i, (lbl, var, color) in enumerate(overview_data):
            card = _make_card(cards_row, padx=20, pady=20)
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 10 if i < 2 else 0))
            _label(card, text=lbl, size=9, color=TEXT_MUTED).pack(anchor="w")
            _label(card, textvariable=var, size=32, bold=True, color=color).pack(anchor="w", pady=(4, 0))

        # Second row of cards
        cards_row2 = tk.Frame(overview_tab, bg=BG_DARK)
        cards_row2.pack(fill="x", pady=(10, 0))
        for col in range(3):
            cards_row2.columnconfigure(col, weight=1, uniform="scard2")

        overview_data2 = [
            ("Cảnh báo",   self.stat_alert,   DANGER),    # type: ignore[attr-defined]
            ("Nguồn đang theo dõi", self.stat_source, TEXT_MUTED),  # type: ignore[attr-defined]
        ]
        for i, (lbl, var, color) in enumerate(overview_data2):
            card = _make_card(cards_row2, padx=20, pady=20)
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 10))
            _label(card, text=lbl, size=9, color=TEXT_MUTED).pack(anchor="w")
            _label(card, textvariable=var, size=32, bold=True, color=color).pack(anchor="w", pady=(4, 0))

        # Risk level card (dynamic color)
        self.risk_level_card = _make_card(cards_row2, padx=20, pady=20)  # type: ignore[attr-defined]
        self.risk_level_card.grid(row=0, column=2, sticky="nsew")  # type: ignore[attr-defined]
        _label(self.risk_level_card, text="MỨC ĐỘ RỦI RO", size=9, color=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")  # type: ignore[attr-defined]
        self.risk_level_value_label = tk.Label(  # type: ignore[attr-defined]
            self.risk_level_card, textvariable=self.stat_risk,  # type: ignore[attr-defined]
            bg=BG_CARD, fg=SUCCESS,
            font=("Segoe UI", 20, "bold"),
        )
        self.risk_level_value_label.pack(anchor="w", pady=(4, 0))  # type: ignore[attr-defined]

        # Nhận định
        insight_card = _make_card(overview_tab, padx=20, pady=16)
        insight_card.pack(fill="x", pady=(12, 0))
        _label(insight_card, text="NHẬN ĐỊNH NHANH", size=8, bold=True, color=TEXT_MUTED).pack(anchor="w")
        self.stats_overview_text = tk.StringVar(value="Chưa có dữ liệu phát hiện.")  # type: ignore[attr-defined]
        _label(insight_card, textvariable=self.stats_overview_text,  # type: ignore[attr-defined]
               size=10, color=TEXT_PRIMARY, wraplength=600, justify="left").pack(
            anchor="w", pady=(6, 0))

        # ── Tab Biểu đồ ──
        charts_tab.columnconfigure(0, weight=1)
        charts_tab.columnconfigure(1, weight=1)
        charts_tab.rowconfigure(0, weight=1)
        charts_tab.rowconfigure(1, weight=1)

        ratio_card = _make_card(charts_tab, padx=12, pady=12)
        ratio_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(12, 4))
        _label(ratio_card, text="TỶ LỆ CHÁY / KHÓI", size=8, bold=True, color=TEXT_MUTED).pack(anchor="w", pady=(0, 8))
        self.stats_ratio_figure = Figure(figsize=(4.5, 3.5), dpi=100)  # type: ignore[attr-defined]
        self.stats_ratio_figure.patch.set_facecolor(BG_CARD)
        self.stats_ratio_axes = self.stats_ratio_figure.add_subplot(111)  # type: ignore[attr-defined]
        self.stats_ratio_axes.set_facecolor(BG_CARD)
        self.stats_ratio_canvas = FigureCanvasTkAgg(self.stats_ratio_figure, master=ratio_card)  # type: ignore[attr-defined]
        self.stats_ratio_canvas.get_tk_widget().configure(bg=BG_CARD, highlightthickness=0)  # type: ignore[attr-defined]
        self.stats_ratio_canvas.get_tk_widget().pack(fill="both", expand=True)  # type: ignore[attr-defined]

        source_chart_card = _make_card(charts_tab, padx=12, pady=12)
        source_chart_card.grid(row=0, column=1, sticky="nsew", pady=(12, 4))
        _label(source_chart_card, text="PHÁT HIỆN THEO NGUỒN", size=8, bold=True, color=TEXT_MUTED).pack(anchor="w", pady=(0, 8))
        self.stats_source_figure = Figure(figsize=(5.2, 3.5), dpi=100)  # type: ignore[attr-defined]
        self.stats_source_figure.patch.set_facecolor(BG_CARD)
        self.stats_source_axes = self.stats_source_figure.add_subplot(111)  # type: ignore[attr-defined]
        self.stats_source_axes.set_facecolor(BG_CARD)
        self.stats_source_canvas = FigureCanvasTkAgg(self.stats_source_figure, master=source_chart_card)  # type: ignore[attr-defined]
        self.stats_source_canvas.get_tk_widget().configure(bg=BG_CARD, highlightthickness=0)  # type: ignore[attr-defined]
        self.stats_source_canvas.get_tk_widget().pack(fill="both", expand=True)  # type: ignore[attr-defined]

        # Trend chart (spans full width, row 1)
        trend_card = _make_card(charts_tab, padx=12, pady=12)
        trend_card.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 12))
        _label(trend_card, text="XU HƯỚNG PHÁT HIỆN 24H GẦN NHẤT", size=8, bold=True, color=TEXT_MUTED).pack(anchor="w", pady=(0, 8))
        self.stats_trend_figure = Figure(figsize=(9.5, 2.8), dpi=100)  # type: ignore[attr-defined]
        self.stats_trend_figure.patch.set_facecolor(BG_CARD)
        self.stats_trend_axes = self.stats_trend_figure.add_subplot(111)  # type: ignore[attr-defined]
        self.stats_trend_axes.set_facecolor(BG_CARD)
        self.stats_trend_canvas = FigureCanvasTkAgg(self.stats_trend_figure, master=trend_card)  # type: ignore[attr-defined]
        self.stats_trend_canvas.get_tk_widget().configure(bg=BG_CARD, highlightthickness=0)  # type: ignore[attr-defined]
        self.stats_trend_canvas.get_tk_widget().pack(fill="both", expand=True)  # type: ignore[attr-defined]

        # ── Tab Bảng dữ liệu ──
        tables_tab.columnconfigure(0, weight=2)
        tables_tab.columnconfigure(1, weight=1)
        tables_tab.rowconfigure(0, weight=1)

        source_table_panel = _make_card(tables_tab, padx=12, pady=12)
        source_table_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=12)
        source_table_panel.columnconfigure(0, weight=1)
        source_table_panel.rowconfigure(1, weight=1)
        _label(source_table_panel, text="THỐNG KÊ THEO NGUỒN", size=8, bold=True, color=TEXT_MUTED).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        source_columns = ("rank", "source", "location", "fire", "smoke", "total", "fire_ratio")
        self.source_stats_tree = ttk.Treeview(source_table_panel, columns=source_columns, show="headings", height=10)  # type: ignore[attr-defined]
        for col, head, w in [
            ("rank", "STT", 50), ("source", "Nguồn", 180), ("location", "Vị trí", 120),
            ("fire", "Cháy", 60), ("smoke", "Khói", 60), ("total", "Tổng", 60), ("fire_ratio", "Tỷ lệ", 80),
        ]:
            self.source_stats_tree.heading(col, text=head)  # type: ignore[attr-defined]
            anchor = "center" if col not in ("source", "location") else "w"
            self.source_stats_tree.column(col, width=w, anchor=anchor)  # type: ignore[attr-defined]
        self.source_stats_tree.grid(row=1, column=0, sticky="nsew")  # type: ignore[attr-defined]
        src_scroll = ttk.Scrollbar(source_table_panel, command=self.source_stats_tree.yview)  # type: ignore[attr-defined]
        src_scroll.grid(row=1, column=1, sticky="ns")
        self.source_stats_tree.configure(yscrollcommand=src_scroll.set)  # type: ignore[attr-defined]

        detail_panel = _make_card(tables_tab, padx=12, pady=12)
        detail_panel.grid(row=0, column=1, sticky="nsew", pady=12)
        detail_panel.columnconfigure(0, weight=1)
        detail_panel.rowconfigure(1, weight=1)
        _label(detail_panel, text="CHI TIẾT", size=8, bold=True, color=TEXT_MUTED).grid(
            row=0, column=0, sticky="w", pady=(0, 8))

        detail_notebook = ttk.Notebook(detail_panel)
        detail_notebook.grid(row=1, column=0, sticky="nsew")

        class_tab   = tk.Frame(detail_notebook, bg=BG_CARD)
        recent_tab  = tk.Frame(detail_notebook, bg=BG_CARD)
        hourly_tab  = tk.Frame(detail_notebook, bg=BG_CARD)
        daily_tab   = tk.Frame(detail_notebook, bg=BG_CARD)
        detail_notebook.add(class_tab,  text=" Loại ")
        detail_notebook.add(recent_tab, text=" Gần đây ")
        detail_notebook.add(hourly_tab, text=" 24h ")
        detail_notebook.add(daily_tab,  text=" 7 ngày ")

        for tab in [class_tab, recent_tab, hourly_tab, daily_tab]:
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)

        # Treeview helper
        def _tv(parent, cols):
            tv = ttk.Treeview(parent, columns=cols, show="headings", height=10)
            sc = ttk.Scrollbar(parent, command=tv.yview)
            tv.configure(yscrollcommand=sc.set)
            tv.grid(row=0, column=0, sticky="nsew")
            sc.grid(row=0, column=1, sticky="ns")
            return tv

        self.class_stats_tree = _tv(class_tab, ("label", "count", "ratio", "avg_conf", "max_conf", "risk"))  # type: ignore[attr-defined]
        for col, h, w in [
            ("label", "Loại", 75), ("count", "Số lần", 60), ("ratio", "Tỷ trọng", 65),
            ("avg_conf", "TC trung bình", 95), ("max_conf", "TC cao nhất", 90), ("risk", "Mức rủi ro", 100),
        ]:
            self.class_stats_tree.heading(col, text=h)  # type: ignore[attr-defined]
            self.class_stats_tree.column(col, width=w, anchor="center" if col != "label" else "w")  # type: ignore[attr-defined]

        self.recent_stats_tree = _tv(recent_tab, ("time", "source", "label", "conf"))  # type: ignore[attr-defined]
        for col, h, w in [("time", "Thời gian", 140), ("source", "Nguồn", 120), ("label", "Loại", 70), ("conf", "Tin cậy", 70)]:
            self.recent_stats_tree.heading(col, text=h)  # type: ignore[attr-defined]
            self.recent_stats_tree.column(col, width=w, anchor="center" if col not in ("source",) else "w")  # type: ignore[attr-defined]

        self.hourly_stats_tree = _tv(hourly_tab, ("bucket", "fire", "smoke", "total"))  # type: ignore[attr-defined]
        for col, h, w in [("bucket", "Khung giờ", 140), ("fire", "Cháy", 70), ("smoke", "Khói", 70), ("total", "Tổng", 80)]:
            self.hourly_stats_tree.heading(col, text=h)  # type: ignore[attr-defined]
            self.hourly_stats_tree.column(col, width=w, anchor="center" if col != "bucket" else "w")  # type: ignore[attr-defined]

        self.daily_stats_tree = _tv(daily_tab, ("bucket", "fire", "smoke", "total"))  # type: ignore[attr-defined]
        for col, h, w in [("bucket", "Ngày", 140), ("fire", "Cháy", 70), ("smoke", "Khói", 70), ("total", "Tổng", 80)]:
            self.daily_stats_tree.heading(col, text=h)  # type: ignore[attr-defined]
            self.daily_stats_tree.column(col, width=w, anchor="center" if col != "bucket" else "w")  # type: ignore[attr-defined]

        self._update_stats_display(force_visual_refresh=True, force_table_refresh=True)  # type: ignore[attr-defined]
        return page

    # ──────────────────────────────────────────────────────────────────
    #  Trang Nhật ký
    # ──────────────────────────────────────────────────────────────────

    def _create_log_page(self) -> tk.Frame:
        page = tk.Frame(self.page_container, bg=BG_DARK)  # type: ignore[attr-defined]
        self._page_header(page, "Nhật ký sự kiện", "Lịch sử phát hiện theo thời gian thực")

        log_card = _make_card(page, padx=0, pady=0)
        log_card.pack(fill="both", expand=True, padx=24, pady=(16, 0))
        log_card.rowconfigure(0, weight=1)
        log_card.columnconfigure(0, weight=1)

        self.log_text = tk.Text(  # type: ignore[attr-defined]
            log_card, wrap="word", height=14, state="disabled",
            bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
            selectbackground=ACCENT, relief="flat", bd=0,
            font=("Cascadia Code", 9) if True else ("Consolas", 9),
            padx=16, pady=12,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")  # type: ignore[attr-defined]
        scroll = ttk.Scrollbar(log_card, command=self.log_text.yview)  # type: ignore[attr-defined]
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)  # type: ignore[attr-defined]

        # Toolbar
        btn_row = tk.Frame(page, bg=BG_DARK)
        btn_row.pack(fill="x", padx=24, pady=(10, 20))
        tk.Button(
            btn_row, text="🗑  Xóa nhật ký",
            bg=BG_CARD, fg=TEXT_MUTED,
            activebackground=BG_HOVER, activeforeground=DANGER,
            relief="flat", bd=0, padx=14, pady=7,
            font=("Segoe UI", 9), cursor="hand2",
            command=self._clear_log,  # type: ignore[attr-defined]
        ).pack(side="left")

        return page

    # ──────────────────────────────────────────────────────────────────
    #  Cửa sổ cài đặt cảnh báo
    # ──────────────────────────────────────────────────────────────────

    def open_alert_settings_window(self):
        if self.alert_settings_window and self.alert_settings_window.winfo_exists():  # type: ignore[attr-defined]
            self.alert_settings_window.lift()  # type: ignore[attr-defined]
            self.alert_settings_window.focus_force()  # type: ignore[attr-defined]
            return
        try:
            from src.ui.widgets.alert_settings import AlertSettingsWindow
        except ImportError:
            from ui.widgets.alert_settings import AlertSettingsWindow  # type: ignore[no-redef]

        self.alert_settings_window = AlertSettingsWindow(  # type: ignore[attr-defined]
            parent=self,
            conf_threshold=self.conf_threshold,  # type: ignore[attr-defined]
            alert_frames=self.alert_frames,  # type: ignore[attr-defined]
            alert_cooldown=self.alert_cooldown,  # type: ignore[attr-defined]
            auto_save_alert=self.auto_save_alert,  # type: ignore[attr-defined]
            on_close=self._close_alert_settings_window,
            sound_alert_enabled=getattr(self, "sound_alert_enabled", None),
            sound_alert_volume=getattr(self, "sound_alert_volume", None),
            alerts_max_mb=getattr(self, "alerts_max_mb", None),
            alerts_max_days=getattr(self, "alerts_max_days", None),
            smoke_conf_threshold=getattr(self, "smoke_conf_threshold", None),
        )

    def _close_alert_settings_window(self):
        if self.alert_settings_window and self.alert_settings_window.winfo_exists():  # type: ignore[attr-defined]
            self.alert_settings_window.destroy()  # type: ignore[attr-defined]
        self.alert_settings_window = None  # type: ignore[attr-defined]
