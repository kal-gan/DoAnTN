"""
src/ui/admin/auth.py
Dialog xác thực - dark theme.
"""
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, Optional

BG_DARK      = "#11141d"
BG_SIDEBAR   = "#13151e"
BG_CARD      = "#1d212e"
BG_HOVER     = "#2a3047"
ACCENT       = "#f04e1a"
TEXT_PRIMARY = "#f5f7fb"
TEXT_MUTED   = "#9ba4b4"
BORDER       = "#2b3047"


class AdminAuthDialog(tk.Toplevel):
    """Dialog đăng nhập - dark theme."""

    def __init__(self, parent: tk.Misc, action_label: str, title: str = "Xác thực hệ thống"):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=BG_DARK)
        self.geometry("400x240")

        self.result: Optional[Dict[str, str]] = None

        # Header
        hdr = tk.Frame(self, bg=BG_SIDEBAR, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙  FireGuard Admin",
                 bg=BG_SIDEBAR, fg=ACCENT, font=("Segoe UI", 12, "bold")).pack(padx=20, anchor="w")
        tk.Label(hdr, text=f"Hành động: {action_label}",
                 bg=BG_SIDEBAR, fg=TEXT_MUTED, font=("Segoe UI", 8)).pack(padx=20, anchor="w")

        # Form
        form = tk.Frame(self, bg=BG_DARK, padx=24, pady=18)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()

        tk.Label(form, text="Tài khoản:", bg=BG_DARK, fg=TEXT_MUTED,
                 font=("Segoe UI", 9), anchor="w").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 12))
        username_entry = tk.Entry(form, textvariable=self.username_var,
                                  bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                  relief="flat", bd=1, font=("Segoe UI", 10))
        username_entry.grid(row=0, column=1, sticky="ew", pady=6)

        tk.Label(form, text="Mật khẩu:", bg=BG_DARK, fg=TEXT_MUTED,
                 font=("Segoe UI", 9), anchor="w").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 12))
        password_entry = tk.Entry(form, textvariable=self.password_var, show="*",
                                  bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                  relief="flat", bd=1, font=("Segoe UI", 10))
        password_entry.grid(row=1, column=1, sticky="ew", pady=6)

        btn_row = tk.Frame(form, bg=BG_DARK)
        btn_row.grid(row=2, column=0, columnspan=2, sticky="e", pady=(14, 0))
        tk.Button(btn_row, text="Hủy",
                  bg=BG_HOVER, fg=TEXT_MUTED, relief="flat", bd=0,
                  padx=14, pady=7, cursor="hand2", font=("Segoe UI", 9),
                  activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
                  command=self._cancel).pack(side="right")
        tk.Button(btn_row, text="Đăng nhập",
                  bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", bd=0,
                  padx=14, pady=7, cursor="hand2", font=("Segoe UI", 9, "bold"),
                  activebackground="#c73508", activeforeground=TEXT_PRIMARY,
                  command=self._submit).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.update_idletasks()
        self._center_to_parent(parent)
        username_entry.focus_set()

    def _center_to_parent(self, parent: tk.Misc):
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + max(0, (pw - w) // 2)}+{py + max(0, (ph - h) // 2)}")

    def _submit(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            messagebox.showwarning("Thiếu thông tin",
                                   "Vui lòng nhập đầy đủ tài khoản và mật khẩu.", parent=self)
            return
        self.result = {"username": username, "password": password}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def prompt_admin_auth(parent: tk.Misc, db: Any, action_label: str) -> Optional[Dict[str, Any]]:
    """Hiển thị dialog - chỉ chấp nhận role admin."""
    while True:
        dialog = AdminAuthDialog(parent=parent, action_label=action_label)
        parent.wait_window(dialog)
        if dialog.result is None:
            return None
        user = db.verify_user(dialog.result["username"], dialog.result["password"])
        if user is None or str(user.get("role", "")).lower() != "admin":
            messagebox.showerror("Xác thực thất bại",
                                 "Thông tin đăng nhập không hợp lệ hoặc không đủ quyền quản trị.",
                                 parent=parent)
            continue
        return user


def prompt_any_user_auth(parent: tk.Misc, db: Any, action_label: str) -> Optional[Dict[str, Any]]:
    """Hiển thị dialog - chấp nhận bất kỳ tài khoản hợp lệ (admin hoặc user)."""
    while True:
        dialog = AdminAuthDialog(parent=parent, action_label=action_label,
                                 title="Đăng nhập hệ thống")
        parent.wait_window(dialog)
        if dialog.result is None:
            return None
        user = db.verify_user(dialog.result["username"], dialog.result["password"])
        if user is None:
            messagebox.showerror("Đăng nhập thất bại",
                                 "Tài khoản hoặc mật khẩu không đúng.", parent=parent)
            continue
        return user
