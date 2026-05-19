"""
src/ui/admin/cards/email_card.py
Card cấu hình SMTP/Email cảnh báo, tách khỏi ``workspace.py``.

Hàm ``build_email_card(ws, parent, section_factory, lbl_factory)`` nhận:
  - ``ws``: instance ``AdminWorkspaceWindow`` (để truy cập ``app.db``, các
    ``StringVar`` đã khởi tạo trong ``__init__``).
  - ``parent``: frame chứa (thường là ``inner`` của trang settings).
  - ``section_factory(icon, title) -> tk.Frame``: factory tạo card có header.
  - ``lbl_factory(card, text, row, col)``: factory tạo label đầu cột.

Trả về frame card đã build.
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Callable

from ..workspace import (
    BG_CARD, BG_HOVER, ACCENT, BORDER,
    TEXT_PRIMARY, TEXT_MUTED,
)

if TYPE_CHECKING:  # pragma: no cover
    from ..workspace import AdminWorkspaceWindow


def build_email_card(
    ws: "AdminWorkspaceWindow",
    parent: tk.Frame,  # noqa: ARG001 (kept for parity; section_factory uses inner)
    section_factory: Callable[[str, str], tk.Frame],
    lbl_factory: Callable[[tk.Frame, str, int, int], None],
) -> tk.Frame:
    c6 = section_factory("✉", "Email cảnh báo (cho mức HIGH/CRITICAL)")
    # Load saved settings from DB
    try:
        db = ws.app.db  # type: ignore[attr-defined]
        ws.email_smtp_host.set(db.get_setting("email_smtp_host", "smtp.gmail.com"))
        ws.email_smtp_port.set(db.get_setting("email_smtp_port", "587"))
        ws.email_smtp_user.set(db.get_setting("email_smtp_user", ""))
        ws.email_smtp_pass.set(db.get_setting_secret("email_smtp_pass", ""))
        ws.email_to.set(db.get_setting("email_to", ""))
    except Exception:
        pass

    def _entry(card, var, row, col, show="", span=1):
        e = tk.Entry(card, textvariable=var, show=show,
                     bg=BG_HOVER, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                     relief="flat", bd=1, font=("Segoe UI", 9))
        e.grid(row=row, column=col, columnspan=span, sticky="ew", pady=5, padx=(0, 12))
        return e

    lbl_factory(c6, "SMTP Host",  0, 0); _entry(c6, ws.email_smtp_host, 0, 1)
    lbl_factory(c6, "Port",       0, 2); _entry(c6, ws.email_smtp_port,  0, 3)
    lbl_factory(c6, "Username",   1, 0); _entry(c6, ws.email_smtp_user,  1, 1, span=3)
    lbl_factory(c6, "Password",   2, 0); _entry(c6, ws.email_smtp_pass,  2, 1, show="*", span=3)
    lbl_factory(c6, "Gửi đến",   3, 0); _entry(c6, ws.email_to,         3, 1, span=3)

    tk.Label(
        c6,
        text="Gmail: dùng smtp.gmail.com / 587, mật khẩu là App Password 16 ký tự "
             "(tạo tại myaccount.google.com → Security → App passwords). "
             "Nhiều người nhận: phân tách bằng dấu phẩy. "
             "Mật khẩu được mã hoá AES-128 trước khi lưu vào CSDL.",
        bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 8), wraplength=560, justify="left",
    ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def _save_email():
        try:
            db = ws.app.db  # type: ignore[attr-defined]
            db.set_setting("email_smtp_host", ws.email_smtp_host.get().strip())
            db.set_setting("email_smtp_port", ws.email_smtp_port.get().strip())
            db.set_setting("email_smtp_user", ws.email_smtp_user.get().strip())
            db.set_setting_secret("email_smtp_pass", ws.email_smtp_pass.get().strip())
            db.set_setting("email_to",        ws.email_to.get().strip())
            from tkinter import messagebox
            messagebox.showinfo("Đã lưu", "Cấu hình email đã được lưu.", parent=ws)  # type: ignore[arg-type]
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", str(exc), parent=ws)  # type: ignore[arg-type]

    def _test_email():
        from tkinter import messagebox
        # Lưu trước rồi mới test để đảm bảo dùng giá trị mới nhất
        try:
            db = ws.app.db  # type: ignore[attr-defined]
            db.set_setting("email_smtp_host", ws.email_smtp_host.get().strip())
            db.set_setting("email_smtp_port", ws.email_smtp_port.get().strip())
            db.set_setting("email_smtp_user", ws.email_smtp_user.get().strip())
            db.set_setting_secret("email_smtp_pass", ws.email_smtp_pass.get().strip())
            db.set_setting("email_to",        ws.email_to.get().strip())
        except Exception:
            pass
        send_fn = getattr(ws.app, "send_test_email", None)
        if not callable(send_fn):
            messagebox.showerror("Lỗi", "Không tìm thấy hàm gửi email.", parent=ws)  # type: ignore[arg-type]
            return
        ok, info = send_fn()
        if ok:
            messagebox.showinfo("Thành công", f"Đã gửi email kiểm tra.\n{info}", parent=ws)  # type: ignore[arg-type]
        else:
            messagebox.showerror("Gửi thất bại", info, parent=ws)  # type: ignore[arg-type]

    btn_email_row = tk.Frame(c6, bg=BG_CARD)
    btn_email_row.grid(row=5, column=0, columnspan=4, sticky="e", pady=(8, 0))
    tk.Button(btn_email_row, text="✉  Gửi email kiểm tra", bg=BG_HOVER, fg=TEXT_PRIMARY,
              relief="flat", bd=0, padx=12, pady=7, cursor="hand2",
              activebackground=BORDER, activeforeground=TEXT_PRIMARY,
              font=("Segoe UI", 9), command=_test_email).pack(side="left", padx=(0, 8))
    tk.Button(btn_email_row, text="💾  Lưu cấu hình email", bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", bd=0,
              padx=14, pady=7, cursor="hand2", font=("Segoe UI", 9, "bold"),
              command=_save_email).pack(side="left")

    return c6
