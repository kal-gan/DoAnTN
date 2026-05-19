"""
src/ui/admin/workspace.py
Cửa sổ quản trị tổng hợp - dark theme, 5 trang, phân quyền theo role.

Role admin : Tổng quan / Nguồn camera / Hệ thống / Người dùng / Nhật ký HĐ
Role user  : Tổng quan / Nguồn camera (chỉ xem)
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

BG_DARK      = "#11141d"
BG_SIDEBAR   = "#13151e"
BG_CARD      = "#1d212e"
BG_HOVER     = "#2a3047"
ACCENT       = "#f04e1a"
ACCENT2      = "#c73508"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED   = "#9ba4b4"
BORDER       = "#2b3047"
WARNING      = "#fbbf24"
DANGER       = "#ef4444"
SUCCESS      = "#22c55e"

ROLE_LABELS = {"admin": "Quản trị viên", "user": "Người dùng"}



class AdminWorkspaceWindow(tk.Toplevel):
    """Cửa sổ quản trị - dark theme, phân quyền theo role."""

    def __init__(self, parent: tk.Misc, controller: "Any"):
        super().__init__(parent)
        self.controller = controller
        self.app = controller.app

        self._user_role = str((self.app.admin_user or {}).get("role", "user")).lower()
        self._is_admin  = self._user_role == "admin"

        self.title("Trung tâm quản trị")
        self.geometry("1280x800")
        self.minsize(1060, 640)
        self.transient(parent)
        self.configure(bg=BG_DARK)

        self.current_page = "overview"
        self.selected_source_id: Optional[int] = None
        self._poll_id: Optional[str] = None

        self.status_text     = tk.StringVar(value="Sẵn sàng")
        self.summary_running = tk.StringVar(value="Tắt")
        self.summary_sources = tk.StringVar(value="0")
        self.summary_alerts  = tk.StringVar(value="0")
        self.summary_user    = tk.StringVar(value="-")
        self.conf_value_var  = tk.StringVar(value="0.50")

        self.form_name         = tk.StringVar()
        self.form_location     = tk.StringVar()
        self.form_type         = tk.StringVar(value="camera")
        self.form_source       = tk.StringVar()
        self.form_mode         = tk.StringVar(value="new")
        self.details_title_var = tk.StringVar(value="Tạo nguồn mới")

        self.password_current = tk.StringVar()
        self.password_new     = tk.StringVar()
        self.password_confirm = tk.StringVar()

        # Email SMTP config — loaded from DB in _build_settings_page
        self.email_smtp_host = tk.StringVar()
        self.email_smtp_port = tk.StringVar(value="587")
        self.email_smtp_user = tk.StringVar()
        self.email_smtp_pass = tk.StringVar()
        self.email_to        = tk.StringVar()

        self.user_form_username  = tk.StringVar()
        self.user_form_fullname  = tk.StringVar()
        self.user_form_email     = tk.StringVar()
        self.user_form_role      = tk.StringVar(value="user")
        self.user_form_password  = tk.StringVar()
        self.user_form_selected_id: Optional[int] = None

        self.page_buttons: Dict[str, tk.Label]       = {}
        self.pages:        Dict[str, tk.Frame]        = {}
        self.source_tree:  Optional[ttk.Treeview]    = None
        self.user_tree:    Optional[ttk.Treeview]    = None
        self.audit_tree:   Optional[ttk.Treeview]    = None
        self._recent_tree: Optional[ttk.Treeview]    = None
        self._uf_username: Optional[tk.Entry]        = None
        self._user_form_title: Optional[tk.Label]    = None
        self._source_form_widgets: List[tk.Widget]   = []

        self._configure_styles()
        self._build_layout()
        self._show_page("overview")
        self._bind_events()
        self.refresh()
        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self._schedule_poll()

    # ------------------------------------------------------------------ #
    #  Styles                                                              #
    # ------------------------------------------------------------------ #

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", background=BG_DARK, foreground=TEXT_PRIMARY,
                        fieldbackground=BG_CARD, bordercolor=BORDER,
                        troughcolor=BG_CARD, selectbackground=ACCENT,
                        selectforeground=TEXT_PRIMARY, font=("Segoe UI", 9))
        style.configure("TFrame", background=BG_DARK)
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_PRIMARY)
        style.configure("Treeview", background=BG_CARD, foreground=TEXT_PRIMARY,
                        fieldbackground=BG_CARD, rowheight=28, bordercolor=BORDER,
                        relief="flat", font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=BG_DARK, foreground=TEXT_MUTED,
                        relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", TEXT_PRIMARY)])
        style.configure("TScrollbar", background=BG_CARD, troughcolor=BG_DARK,
                        arrowcolor=TEXT_MUTED, relief="flat")

    # ------------------------------------------------------------------ #
    #  Layout                                                              #
    # ------------------------------------------------------------------ #

    def _build_layout(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_content()

    def _build_sidebar(self):
        sb = tk.Frame(self, bg=BG_SIDEBAR, width=220)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.columnconfigure(0, weight=1)

        brand = tk.Frame(sb, bg=BG_SIDEBAR, pady=20)
        brand.grid(row=0, column=0, sticky="ew")
        tk.Label(brand, text="⚙  Admin Panel",
                 bg=BG_SIDEBAR, fg=ACCENT, font=("Segoe UI", 13, "bold")).pack(padx=16, anchor="w")
        tk.Label(brand, textvariable=self.summary_user,
                 bg=BG_SIDEBAR, fg=TEXT_MUTED, font=("Segoe UI", 8),
                 wraplength=192, justify="left").pack(padx=16, anchor="w")

        tk.Frame(sb, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew", padx=12)

        nav = tk.Frame(sb, bg=BG_SIDEBAR)
        nav.grid(row=2, column=0, sticky="ew", pady=10)

        # Hệ thống chỉ có vai trò admin
        nav_items: List[tuple] = [
            ("overview", "📊  Tổng quan"),
            ("sources",  "📷  Nguồn camera"),
            ("training", "📚  Huấn luyện (cần phê duyệt)"),
            ("settings", "⚙  Hệ thống"),
            ("audit",    "📋  Nhật ký HĐ"),
        ]

        for page_key, label in nav_items:
            btn = tk.Label(nav, text=label, bg=BG_SIDEBAR, fg=TEXT_MUTED,
                           font=("Segoe UI", 9), pady=9, padx=16, anchor="w", cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, k=page_key: self._show_page(k))
            btn.bind("<Enter>",    lambda e, b=btn: b.config(bg=BG_HOVER, fg=TEXT_PRIMARY))
            btn.bind("<Leave>",    lambda e, b=btn: self._nav_leave(b))
            self.page_buttons[page_key] = btn

        tk.Frame(sb, bg=BORDER, height=1).grid(row=3, column=0, sticky="ew", padx=12)

        if self._is_admin:
            qa = tk.Frame(sb, bg=BG_SIDEBAR, pady=10)
            qa.grid(row=4, column=0, sticky="ew")
            tk.Label(qa, text="TÁC VỤ NHANH", bg=BG_SIDEBAR, fg=TEXT_MUTED,
                     font=("Segoe UI", 7, "bold")).pack(padx=16, anchor="w", pady=(0, 4))
            self._qa_btn(qa, "▶  Bật giám sát", SUCCESS, self.controller.start_detection)
            self._qa_btn(qa, "■  Ngắt toàn bộ", DANGER,  self.controller.stop_detection)

        spacer = tk.Frame(sb, bg=BG_SIDEBAR)
        spacer.grid(row=5, column=0, sticky="nsew")
        sb.rowconfigure(5, weight=1)

        foot = tk.Frame(sb, bg=BG_SIDEBAR, pady=12)
        foot.grid(row=6, column=0, sticky="ew")
        tk.Frame(foot, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(foot, textvariable=self.status_text, bg=BG_SIDEBAR, fg=TEXT_MUTED,
                 font=("Segoe UI", 7), wraplength=190, justify="left").pack(
            padx=16, anchor="w", pady=(0, 8))
        tk.Button(foot, text="Đóng", bg=BG_HOVER, fg=TEXT_MUTED, relief="flat", bd=0,
                  activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
                  font=("Segoe UI", 9), pady=7, cursor="hand2",
                  command=self._handle_close).pack(fill="x", padx=12)

    def _qa_btn(self, parent: tk.Frame, text: str, color: str, command):
        tk.Button(parent, text=text, bg=BG_SIDEBAR, fg=color, relief="flat", bd=0,
                  activebackground=BG_HOVER, activeforeground=TEXT_PRIMARY,
                  font=("Segoe UI", 9), pady=6, padx=16, anchor="w", cursor="hand2",
                  command=command).pack(fill="x")

    def _nav_leave(self, btn: tk.Label):
        key = next((k for k, v in self.page_buttons.items() if v is btn), None)
        if key and key == self.current_page:
            btn.config(bg=BG_HOVER, fg=TEXT_PRIMARY)
        else:
            btn.config(bg=BG_SIDEBAR, fg=TEXT_MUTED)

    def _build_content(self):
        container = tk.Frame(self, bg=BG_DARK)
        container.grid(row=0, column=1, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.pages["overview"] = self._build_overview_page(container)
        self.pages["sources"]  = self._build_sources_page(container)
        self.pages["training"] = self._build_training_page(container)
        self.pages["settings"] = self._build_settings_page(container)
        self.pages["audit"]    = self._build_audit_page(container)

        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

    # ------------------------------------------------------------------ #
    #  Page: Tổng quan                                                     #
    # ------------------------------------------------------------------ #

    def _build_overview_page(self, parent: tk.Frame) -> tk.Frame:
        page = tk.Frame(parent, bg=BG_DARK)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)

        hdr = tk.Frame(page, bg=BG_DARK, pady=20, padx=24)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="Tổng quan hệ thống",
                 bg=BG_DARK, fg=TEXT_PRIMARY, font=("Segoe UI", 16, "bold")).pack(side="left")

        cards_row = tk.Frame(page, bg=BG_DARK, padx=24)
        cards_row.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        for i in range(4):
            cards_row.columnconfigure(i, weight=1, uniform="c")
        self._stat_card(cards_row, 0, "Trạng thái giám sát", self.summary_running, SUCCESS)
        self._stat_card(cards_row, 1, "Số nguồn camera",     self.summary_sources, ACCENT)
        self._stat_card(cards_row, 2, "Tổng cảnh báo",       self.summary_alerts,  DANGER)
        self._stat_card(cards_row, 3, "Người dùng hiện tại", self.summary_user,    TEXT_MUTED, small=True)

        det_card = tk.Frame(page, bg=BG_CARD, padx=14, pady=12)
        det_card.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 20))
        det_card.columnconfigure(0, weight=1)
        det_card.rowconfigure(1, weight=1)
        tk.Label(det_card, text="PHÁT HIỆN GẦN ĐÂY",
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 7, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        cols = ("Thời gian", "Nguồn", "Loại", "Hình ảnh")
        self._recent_tree = ttk.Treeview(det_card, columns=cols, show="headings", height=12)
        for col in cols:
            self._recent_tree.heading(col, text=col)
        self._recent_tree.column("Thời gian", width=160, minwidth=130)
        self._recent_tree.column("Nguồn",     width=180, minwidth=130)
        self._recent_tree.column("Loại",      width=80,  minwidth=60,  anchor="center")
        self._recent_tree.column("Hình ảnh",  width=340, minwidth=180)
        vsb = ttk.Scrollbar(det_card, orient="vertical", command=self._recent_tree.yview)
        self._recent_tree.configure(yscrollcommand=vsb.set)
        self._recent_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        return page

    def _stat_card(self, parent, col, title, var, color, small=False):
        card = tk.Frame(parent, bg=BG_CARD, padx=14, pady=12)
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0))
        tk.Label(card, text=title, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=var, bg=BG_CARD, fg=color,
                 font=("Segoe UI", 9 if small else 20, "bold"),
                 wraplength=180, justify="left").pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------ #
    #  Page: Nguồn camera                                                  #
    # ------------------------------------------------------------------ #

    def _build_sources_page(self, parent: tk.Frame) -> tk.Frame:
        # Thân trang được tách sang src/ui/admin/cards/sources_page.py
        from .cards.sources_page import build_sources_page
        return build_sources_page(self, parent)

    # ------------------------------------------------------------------ #
    #  Page: Huấn luyện gia tăng (admin only)                             #
    # ------------------------------------------------------------------ #

    def _build_training_page(self, parent: tk.Frame) -> tk.Frame:
        """Tạo trang huấn luyện gia tăng."""
        try:
            from .training_tab import create_training_tab
            return create_training_tab(parent, self)
        except Exception as e:
            # Fallback nếu có lỗi import
            page = tk.Frame(parent, bg=BG_DARK)
            error_label = tk.Label(
                page,
                text=f"Lỗi tải trang huấn luyện: {e}",
                bg=BG_DARK,
                fg="#ff6b6b",
                font=("Segoe UI", 11),
            )
            error_label.pack(padx=20, pady=20, anchor="w")
            return page

    # ------------------------------------------------------------------ #
    #  Page: Hệ thống (admin only)                                         #
    # ------------------------------------------------------------------ #

    def _build_settings_page(self, parent: tk.Frame) -> tk.Frame:
        page = tk.Frame(parent, bg=BG_DARK)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)

        canvas = tk.Canvas(page, bg=BG_DARK, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG_DARK)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(inner_id, width=e.width))

        def _scroll(e):
            try:
                canvas.yview_scroll(-1 * (e.delta // 120), "units")
            except Exception:
                pass

        canvas.bind("<MouseWheel>", _scroll)
        inner.bind("<MouseWheel>", _scroll)

        def _section(icon, title):
            h = tk.Frame(inner, bg=BG_DARK)
            h.pack(fill="x", padx=24, pady=(18, 4))
            tk.Label(h, text=f"{icon}  {title}", bg=BG_DARK, fg=ACCENT,
                     font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Frame(h, bg=BORDER, height=1).pack(
                side="left", fill="x", expand=True, padx=(10, 24), pady=5)
            c = tk.Frame(inner, bg=BG_CARD, padx=20, pady=14)
            c.pack(fill="x", padx=24, pady=(0, 4))
            c.columnconfigure(1, weight=1)
            c.columnconfigure(3, weight=1)
            return c

        def _lbl(card, text, row, col):
            tk.Label(card, text=text, bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 9),
                     anchor="w").grid(row=row, column=col, sticky="w", pady=5, padx=(0, 12))

        def _spin(card, var, lo, hi, row, col, incr=1, w=8):
            sb = tk.Spinbox(card, from_=lo, to=hi, increment=incr, textvariable=var,
                            width=w, bg=BG_HOVER, fg=TEXT_PRIMARY,
                            insertbackground=TEXT_PRIMARY, buttonbackground=BG_HOVER,
                            relief="flat", bd=1, font=("Segoe UI", 9))
            sb.grid(row=row, column=col, sticky="w", pady=5)
            return sb

        def _chk(card, text, var, row):
            cb = tk.Checkbutton(card, text=text, variable=var, bg=BG_CARD, fg=TEXT_PRIMARY,
                                selectcolor=BG_HOVER, activebackground=BG_CARD,
                                activeforeground=TEXT_PRIMARY, font=("Segoe UI", 9))
            cb.grid(row=row, column=0, columnspan=4, sticky="w", pady=5)

        def _scale_row(card, var, lo, hi, row, col, res=0.01, suffix="", width=5):
            f = tk.Frame(card, bg=BG_CARD)
            f.grid(row=row, column=col, sticky="ew", pady=5, padx=(0, 12))
            f.columnconfigure(0, weight=1)
            fmtfn = (lambda v: f"{float(v):.2f}") if res < 1 else (lambda v: f"{int(v)}{suffix}")
            val_var = tk.StringVar(value=fmtfn(var.get()))
            var.trace_add("write", lambda *_: val_var.set(fmtfn(var.get())))
            tk.Scale(f, from_=lo, to=hi, variable=var, orient="horizontal", resolution=res,
                     showvalue=False, bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=ACCENT,
                     troughcolor=BG_HOVER, highlightthickness=0, bd=0).grid(
                row=0, column=0, sticky="ew")
            tk.Label(f, textvariable=val_var, width=width, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Segoe UI", 9)).grid(row=0, column=1, padx=(8, 0))

        # ── Model ──────────────────────────────────────────────────────
        c1 = _section("🤖", "Mô hình nhận dạng")
        _lbl(c1, "File Model (.pt)", 0, 0)
        mr = tk.Frame(c1, bg=BG_CARD)
        mr.grid(row=0, column=1, columnspan=3, sticky="ew", pady=5)
        mr.columnconfigure(0, weight=1)
        tk.Entry(mr, textvariable=self.app.model_path,
                 bg=BG_HOVER, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                 relief="flat", bd=1, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="ew")
        tk.Button(mr, text="Chọn", command=self.app.choose_model,
                  bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", bd=0,
                  padx=10, pady=3, cursor="hand2", font=("Segoe UI", 9)).grid(
            row=0, column=1, padx=(8, 0))

        _lbl(c1, "Ngưỡng tin cậy", 1, 0)
        self.conf_value_var = tk.StringVar(value=f"{self.app.conf_threshold.get():.2f}")
        self.app.conf_threshold.trace_add("write", self._update_conf_value)
        _scale_row(c1, self.app.conf_threshold, 0.10, 0.95, 1, 1, res=0.01, width=5)

        _lbl(c1, "Ngưỡng tin cậy (khói)", 2, 0)
        _scale_row(c1, self.app.smoke_conf_threshold, 0.10, 0.95, 2, 1, res=0.01, width=5)

        # ── Phát hiện ──────────────────────────────────────────────────
        c2 = _section("🔔", "Phát hiện cảnh báo")
        _lbl(c2, "Frame cảnh báo liên tiếp", 0, 0)
        _spin(c2, self.app.alert_frames, 1, 300, 0, 1)
        _lbl(c2, "Cooldown (giây)", 0, 2)
        _spin(c2, self.app.alert_cooldown, 0.5, 60.0, 0, 3, incr=0.5)
        _chk(c2, "Tự động lưu ảnh cảnh báo", self.app.auto_save_alert, 1)

        # ── Âm thanh ───────────────────────────────────────────────────
        c3 = _section("🔊", "Âm thanh cảnh báo")
        _snd_en  = getattr(self.app, "sound_alert_enabled", None) or tk.BooleanVar(value=True)
        _snd_vol = getattr(self.app, "sound_alert_volume",  None) or tk.IntVar(value=80)
        _chk(c3, "Bật âm thanh cảnh báo", _snd_en, 0)
        _lbl(c3, "Âm lượng (%)", 1, 0)
        _scale_row(c3, _snd_vol, 0, 100, 1, 1, res=1, suffix="%", width=4)

        # ── Lưu trữ ────────────────────────────────────────────────────
        c4 = _section("🗂", "Lưu trữ cảnh báo")
        _max_mb   = getattr(self.app, "alerts_max_mb",   None) or tk.IntVar(value=300)
        _max_days = getattr(self.app, "alerts_max_days", None) or tk.IntVar(value=7)
        _lbl(c4, "Dung lượng tối đa (MB)", 0, 0)
        _spin(c4, _max_mb, 50, 10000, 0, 1, incr=50)
        _lbl(c4, "Tự động xóa sau (ngày)", 1, 0)
        _scale_row(c4, _max_days, 1, 7, 1, 1, res=1, suffix=" ngày", width=7)

        # ── Đổi mật khẩu ───────────────────────────────────────────────
        c5 = _section("🔒", "Đổi mật khẩu admin")
        for r, (label, var) in enumerate([
            ("Mật khẩu hiện tại", self.password_current),
            ("Mật khẩu mới",      self.password_new),
            ("Xác nhận mật khẩu", self.password_confirm),
        ]):
            _lbl(c5, label, r, 0)
            tk.Entry(c5, textvariable=var, show="*",
                     bg=BG_HOVER, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                     relief="flat", bd=1, font=("Segoe UI", 9)).grid(
                row=r, column=1, columnspan=3, sticky="ew", pady=5)
        tk.Button(c5, text="Đổi mật khẩu", bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", bd=0,
                  padx=16, pady=7, cursor="hand2", font=("Segoe UI", 9, "bold"),
                  command=self.controller.change_admin_password).grid(
            row=3, column=0, columnspan=4, sticky="e", pady=(8, 0))

        # ── Email cảnh báo ──────────────────────────────────────────────
        from .cards.email_card import build_email_card
        build_email_card(self, inner, _section, _lbl)

        btn_row = tk.Frame(inner, bg=BG_DARK)
        btn_row.pack(fill="x", padx=24, pady=(12, 28))
        self._accent_btn(btn_row, "⚙  Áp dụng cấu hình",
                         self.controller.apply_runtime_settings).pack(side="left")
        tk.Button(btn_row, text="▶  Bật giám sát", bg=SUCCESS, fg="#fff",
                  relief="flat", bd=0, padx=12, pady=7, cursor="hand2",
                  activebackground="#0d9b6d", activeforeground="#fff",
                  font=("Segoe UI", 9, "bold"),
                  command=self.controller.start_detection).pack(side="left", padx=(8, 0))
        tk.Button(btn_row, text="■  Ngắt toàn bộ", bg=BG_HOVER, fg=DANGER,
                  relief="flat", bd=0, padx=12, pady=7, cursor="hand2",
                  activebackground=BG_CARD, activeforeground=DANGER,
                  font=("Segoe UI", 9),
                  command=self.controller.stop_detection).pack(side="left", padx=(8, 0))
        return page

    # ------------------------------------------------------------------ #
    #  Page: Người dùng (admin only)                                       #
    # ------------------------------------------------------------------ #

    def _build_users_page(self, parent: tk.Frame) -> tk.Frame:
        page = tk.Frame(parent, bg=BG_DARK)
        page.columnconfigure(0, weight=3)
        page.columnconfigure(1, weight=2)
        page.rowconfigure(1, weight=1)

        hdr = tk.Frame(page, bg=BG_DARK, pady=20, padx=24)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Label(hdr, text="Quản lý người dùng",
                 bg=BG_DARK, fg=TEXT_PRIMARY, font=("Segoe UI", 16, "bold")).pack(side="left")
        self._accent_btn(hdr, "+ Tạo người dùng mới", self._new_user_form).pack(side="right")

        list_card = tk.Frame(page, bg=BG_CARD, padx=12, pady=12)
        list_card.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=(0, 20))
        list_card.columnconfigure(0, weight=1)
        list_card.rowconfigure(1, weight=1)
        tk.Label(list_card, text="DANH SÁCH NGƯỜI DÙNG",
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 7, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8))

        u_cols = ("Tài khoản", "Họ tên", "Vai trò", "Trạng thái", "Đăng nhập lần cuối")
        self.user_tree = ttk.Treeview(list_card, columns=u_cols, show="headings", height=16)
        for col in u_cols:
            self.user_tree.heading(col, text=col)
        self.user_tree.column("Tài khoản",          width=120, minwidth=90)
        self.user_tree.column("Họ tên",             width=160, minwidth=110)
        self.user_tree.column("Vai trò",            width=120, minwidth=80,  anchor="center")
        self.user_tree.column("Trạng thái",         width=90,  minwidth=60,  anchor="center")
        self.user_tree.column("Đăng nhập lần cuối", width=160, minwidth=120)
        vsb = ttk.Scrollbar(list_card, orient="vertical", command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=vsb.set)
        self.user_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        self.user_tree.bind("<<TreeviewSelect>>", self._on_user_select)

        u_detail = tk.Frame(page, bg=BG_CARD, padx=16, pady=16)
        u_detail.grid(row=1, column=1, sticky="nsew", padx=(0, 24), pady=(0, 20))
        u_detail.columnconfigure(1, weight=1)

        self._user_form_title = tk.Label(u_detail, text="Tạo người dùng mới",
                                         bg=BG_CARD, fg=TEXT_PRIMARY,
                                         font=("Segoe UI", 11, "bold"))
        self._user_form_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        def _ul(text, row):
            tk.Label(u_detail, text=text, bg=BG_CARD, fg=TEXT_MUTED,
                     font=("Segoe UI", 9), anchor="w").grid(
                row=row, column=0, sticky="w", pady=4, padx=(0, 10))

        def _ue(var, row, show=""):
            e = tk.Entry(u_detail, textvariable=var, bg=BG_HOVER, fg=TEXT_PRIMARY,
                         insertbackground=TEXT_PRIMARY, relief="flat", bd=1,
                         show=show, font=("Segoe UI", 9))
            e.grid(row=row, column=1, sticky="ew", pady=4)
            return e

        _ul("Tài khoản", 1);  self._uf_username = _ue(self.user_form_username, 1)
        _ul("Họ tên",    2);  _ue(self.user_form_fullname, 2)
        _ul("Email",     3);  _ue(self.user_form_email, 3)
        _ul("Mật khẩu", 4);  _ue(self.user_form_password, 4, show="*")
        _ul("Vai trò",   5)
        role_cb = ttk.Combobox(u_detail, textvariable=self.user_form_role,
                               state="readonly", values=["admin", "user"],
                               font=("Segoe UI", 9))
        role_cb.grid(row=5, column=1, sticky="ew", pady=4)

        tk.Frame(u_detail, bg=BORDER, height=1).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=10)
        self._accent_btn(u_detail, "💾  Lưu người dùng",
                         self.controller.save_user).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        tk.Button(u_detail, text="⊘  Bật / Tắt tài khoản", bg=BG_HOVER, fg=WARNING,
                  relief="flat", bd=0, padx=10, pady=7, cursor="hand2",
                  font=("Segoe UI", 9),
                  command=self.controller.toggle_user_active).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        tk.Button(u_detail, text="＋  Tạo tài khoản mới", bg=BG_HOVER, fg=TEXT_MUTED,
                  relief="flat", bd=0, padx=10, pady=7, cursor="hand2",
                  font=("Segoe UI", 9),
                  command=self._new_user_form).grid(
            row=9, column=0, columnspan=2, sticky="ew")
        return page

    # ------------------------------------------------------------------ #
    #  Page: Nhật ký HĐ (admin only)                                       #
    # ------------------------------------------------------------------ #

    def _build_audit_page(self, parent: tk.Frame) -> tk.Frame:
        page = tk.Frame(parent, bg=BG_DARK)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)

        hdr = tk.Frame(page, bg=BG_DARK, pady=20, padx=24)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="Nhật ký hoạt động hệ thống",
                 bg=BG_DARK, fg=TEXT_PRIMARY, font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Button(hdr, text="↻  Làm mới", bg=BG_HOVER, fg=TEXT_MUTED, relief="flat", bd=0,
                  padx=12, pady=6, cursor="hand2", font=("Segoe UI", 9),
                  activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
                  command=self._refresh_audit_log).pack(side="right")

        audit_card = tk.Frame(page, bg=BG_CARD, padx=12, pady=12)
        audit_card.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        audit_card.columnconfigure(0, weight=1)
        audit_card.rowconfigure(0, weight=1)
        a_cols = ("Thời gian", "Người dùng", "Hành động", "Chi tiết")
        self.audit_tree = ttk.Treeview(audit_card, columns=a_cols, show="headings")
        for col in a_cols:
            self.audit_tree.heading(col, text=col)
        self.audit_tree.column("Thời gian",  width=160, minwidth=120)
        self.audit_tree.column("Người dùng", width=120, minwidth=90)
        self.audit_tree.column("Hành động",  width=160, minwidth=100)
        self.audit_tree.column("Chi tiết",   width=480, minwidth=200)
        vsb = ttk.Scrollbar(audit_card, orient="vertical", command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=vsb.set)
        self.audit_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        return page

    # ------------------------------------------------------------------ #
    #  Widget helpers                                                      #
    # ------------------------------------------------------------------ #

    def _accent_btn(self, parent, text: str, command, secondary: bool = False) -> tk.Button:
        return tk.Button(parent, text=text,
                         bg=BG_HOVER if secondary else ACCENT,
                         fg=TEXT_PRIMARY, relief="flat", bd=0,
                         padx=12, pady=7, cursor="hand2",
                         activebackground=BG_CARD if secondary else ACCENT2,
                         activeforeground=TEXT_PRIMARY,
                         font=("Segoe UI", 9, "bold"), command=command)

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def _show_page(self, page_key: str):
        if page_key not in self.pages:
            return
        self.current_page = page_key
        self.pages[page_key].tkraise()
        for key, btn in self.page_buttons.items():
            btn.config(bg=(BG_HOVER if key == page_key else BG_SIDEBAR),
                       fg=(TEXT_PRIMARY if key == page_key else TEXT_MUTED))
        if page_key == "audit":
            self._refresh_audit_log()

    # ------------------------------------------------------------------ #
    #  Poll / refresh                                                      #
    # ------------------------------------------------------------------ #

    def _schedule_poll(self):
        self._poll_id = self.after(800, self._poll_state)

    def _poll_state(self):
        self._poll_id = None
        if self.winfo_exists():
            self.refresh()
            self._schedule_poll()

    def refresh(self, selected_source_id: Optional[int] = None):
        if selected_source_id is not None:
            self.selected_source_id = selected_source_id
            self.form_mode.set("edit")

        if self.selected_source_id is None and self.app.sources and self.form_mode.get() != "new":
            first_id = self.app.sources[0].get("id")
            self.selected_source_id = int(first_id) if first_id is not None else None

        admin_user = self.app.admin_user
        if admin_user:
            role_label = ROLE_LABELS.get(str(admin_user.get("role", "")),
                                         str(admin_user.get("role", "")))
            self.summary_user.set(f"{admin_user['full_name']} ({role_label})")
        else:
            self.summary_user.set("-")

        self.summary_running.set("Đang chạy" if self.app.is_running else "Đã dừng")
        self.summary_sources.set(str(len(self.app.sources)))
        self.summary_alerts.set(str(self.app.alert_count))
        self.status_text.set(self.app.status_var.get())

        self._refresh_source_tree()
        self._sync_form_from_selection()
        self._refresh_recent_detections()

    # ------------------------------------------------------------------ #
    #  Source tree                                                         #
    # ------------------------------------------------------------------ #

    def _refresh_source_tree(self):
        if self.source_tree is None:
            return
        self.source_tree.delete(*self.source_tree.get_children())
        active_ids = {
            int(s["camera_id"])
            for s in self.app.stream_states
            if s.get("camera_id") is not None
        }
        for idx, source in enumerate(self.app.sources, 1):
            sid  = source.get("id")
            mark = "●" if sid is not None and int(sid) in active_ids else "○"
            name = str(source.get("name") or self.app._source_to_text(source))
            self.source_tree.insert("", "end",
                                    iid=str(sid) if sid is not None else f"_s{idx}",
                                    values=(f"{mark} {idx}", name,
                                            str(source.get("type", "camera")),
                                            str(source.get("value", "")),
                                            str(source.get("location", ""))))
        if self.selected_source_id is not None:
            try:
                self.source_tree.selection_set(str(self.selected_source_id))
                self.source_tree.see(str(self.selected_source_id))
            except Exception:
                pass

    def _refresh_recent_detections(self):
        if self._recent_tree is None:
            return
        try:
            rows = self.app.db.get_recent_detections(limit=20)
        except Exception:
            return
        self._recent_tree.delete(*self._recent_tree.get_children())
        for row in rows:
            self._recent_tree.insert("", "end", values=(
                str(row.get("timestamp", "")),
                str(row.get("source_name", "")),
                str(row.get("class_name", "")),
                str(row.get("image_path", "") or ""),
            ))

    # ------------------------------------------------------------------ #
    #  User tree                                                           #
    # ------------------------------------------------------------------ #

    def _refresh_user_tree(self):
        if self.user_tree is None:
            return
        try:
            users = self.app.db.get_all_users()
        except Exception:
            return
        self.user_tree.delete(*self.user_tree.get_children())
        for u in users:
            role_label = ROLE_LABELS.get(str(u.get("role", "")), str(u.get("role", "")))
            active_str = "✔ Hoạt động" if int(u.get("is_active", 0)) else "✘ Bị khóa"
            self.user_tree.insert("", "end", iid=str(u["id"]),
                                  values=(str(u.get("username", "")),
                                          str(u.get("full_name", "")),
                                          role_label, active_str,
                                          str(u.get("last_login", "") or "Chưa đăng nhập")))
            if not int(u.get("is_active", 1)):
                self.user_tree.tag_configure("locked", foreground=TEXT_MUTED)
                self.user_tree.item(str(u["id"]), tags=("locked",))
        if self.user_form_selected_id is not None:
            try:
                self.user_tree.selection_set(str(self.user_form_selected_id))
            except Exception:
                pass

    def _refresh_audit_log(self):
        if self.audit_tree is None:
            return
        try:
            logs = self.app.db.get_audit_logs(limit=200)
        except Exception:
            return
        self.audit_tree.delete(*self.audit_tree.get_children())
        for log in logs:
            self.audit_tree.insert("", "end", values=(
                str(log.get("timestamp", "")),
                str(log.get("username", "") or "hệ thống"),
                str(log.get("action", "")),
                str(log.get("details", "")),
            ))

    # ------------------------------------------------------------------ #
    #  Source form helpers                                                 #
    # ------------------------------------------------------------------ #

    def _on_source_select(self, event=None):
        if self.source_tree is None:
            return
        sel = self.source_tree.selection()
        if not sel:
            return
        try:
            cam_id = int(sel[0])
        except (ValueError, TypeError):
            return
        self.selected_source_id = cam_id
        self.form_mode.set("edit")
        self._sync_form_from_selection()

    def _find_selected_source(self) -> Optional[Dict[str, Any]]:
        if self.selected_source_id is None:
            return None
        for source in self.app.sources:
            source_id = source.get("id")
            if source_id is not None and int(source_id) == self.selected_source_id:
                return source
        return None

    def _sync_form_from_selection(self):
        source = self._find_selected_source()
        if source is None:
            if self.form_mode.get() != "new":
                self._prepare_new_source()
            return
        if self.form_mode.get() == "new" and self.form_name.get().strip():
            return
        self.details_title_var.set(
            f"Đang sửa: {source.get('name') or self.app._source_to_text(source)}")
        self.form_mode.set("edit")
        self.form_name.set(str(source.get("name") or ""))
        self.form_location.set(str(source.get("location") or ""))
        self.form_type.set(str(source.get("type") or "camera"))
        self.form_source.set(str(source.get("value") or ""))

    def _prepare_new_source(self):
        self.selected_source_id = None
        self.form_mode.set("new")
        self.details_title_var.set("Tạo nguồn mới")
        self.form_name.set("")
        self.form_location.set("")
        self.form_type.set("camera")
        self.form_source.set("0")
        self._show_page("sources")

    def prepare_new_source(self, source_type: str):
        self._prepare_new_source()
        self.form_type.set(source_type)
        self.form_source.set("0" if source_type == "camera" else "")
        self.details_title_var.set(
            "Tạo nguồn camera mới" if source_type == "camera" else "Tạo nguồn video mới")

    def _browse_source_file(self):
        if self.form_type.get() != "video":
            return
        path = filedialog.askopenfilename(
            title="Chọn tệp video",
            filetypes=[("Tệp video", "*.mp4 *.avi *.mov *.mkv"), ("Tất cả", "*.*")],
            parent=self,
        )
        if path:
            self.form_source.set(path)
            if not self.form_name.get().strip():
                self.form_name.set(os.path.basename(path))

    def get_form_payload(self) -> Dict[str, Any]:
        return {
            "camera_id": self.selected_source_id,
            "mode":      self.form_mode.get(),
            "name":      self.form_name.get().strip(),
            "location":  self.form_location.get().strip(),
            "type":      self.form_type.get().strip() or "camera",
            "source":    self.form_source.get().strip(),
        }

    # ------------------------------------------------------------------ #
    #  User form helpers                                                   #
    # ------------------------------------------------------------------ #

    def _on_user_select(self, event=None):
        if self.user_tree is None:
            return
        sel = self.user_tree.selection()
        if not sel:
            return
        try:
            uid = int(sel[0])
        except (ValueError, TypeError):
            return
        self.user_form_selected_id = uid
        try:
            users = self.app.db.get_all_users()
            for u in users:
                if int(u["id"]) == uid:
                    self.user_form_username.set(str(u.get("username", "")))
                    self.user_form_fullname.set(str(u.get("full_name", "")))
                    self.user_form_email.set(str(u.get("email", "") or ""))
                    self.user_form_role.set(str(u.get("role", "user")))
                    self.user_form_password.set("")
                    if self._user_form_title:
                        self._user_form_title.config(
                            text=f"Đang sửa: {u.get('username', '')}")
                    if self._uf_username:
                        self._uf_username.config(state="disabled")
                    break
        except Exception:
            pass

    def _new_user_form(self):
        self.user_form_selected_id = None
        self.user_form_username.set("")
        self.user_form_fullname.set("")
        self.user_form_email.set("")
        self.user_form_password.set("")
        self.user_form_role.set("user")
        if self._user_form_title:
            self._user_form_title.config(text="Tạo người dùng mới")
        if self._uf_username:
            self._uf_username.config(state="normal")
        self._show_page("users")

    def get_user_form_payload(self) -> Dict[str, Any]:
        return {
            "user_id":   self.user_form_selected_id,
            "username":  self.user_form_username.get().strip(),
            "full_name": self.user_form_fullname.get().strip(),
            "email":     self.user_form_email.get().strip(),
            "password":  self.user_form_password.get(),
            "role":      self.user_form_role.get().strip() or "user",
        }

    # ------------------------------------------------------------------ #
    #  Password form                                                       #
    # ------------------------------------------------------------------ #

    def get_password_payload(self) -> Dict[str, str]:
        return {
            "current_password": self.password_current.get(),
            "new_password":     self.password_new.get(),
            "confirm_password": self.password_confirm.get(),
        }

    def clear_password_form(self):
        self.password_current.set("")
        self.password_new.set("")
        self.password_confirm.set("")

    # ------------------------------------------------------------------ #
    #  Conf value trace                                                    #
    # ------------------------------------------------------------------ #

    def _update_conf_value(self, *_args):
        try:
            self.conf_value_var.set(f"{self.app.conf_threshold.get():.2f}")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Notifications                                                       #
    # ------------------------------------------------------------------ #

    def notify(self, text: str):
        self.status_text.set(text)

    def show_error(self, title: str, message: str):
        messagebox.showerror(title, message, parent=self)

    def show_warning(self, title: str, message: str):
        messagebox.showwarning(title, message, parent=self)

    def ask_confirm(self, title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message, parent=self))

    # ------------------------------------------------------------------ #
    #  Misc                                                                #
    # ------------------------------------------------------------------ #

    def _bind_events(self):
        self.bind("<Escape>", lambda _: self._handle_close())

    def _handle_close(self):
        # Auto logout admin khi đóng admin panel
        self.app.admin_user = None  # type: ignore[attr-defined]
        
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        self.controller.close_admin_panel()
