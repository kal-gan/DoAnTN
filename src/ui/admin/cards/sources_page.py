"""
src/ui/admin/cards/sources_page.py
Trang quản lý nguồn camera/video tách riêng khỏi ``workspace.py``.

Hàm ``build_sources_page(ws, parent)`` nhận về instance ``AdminWorkspaceWindow``
và frame cha, trả về frame trang đã build hoàn chỉnh. Các biến state (Treeview,
form_*, ...) được gán lên ``ws`` để các hàm khác trong workspace tiếp tục dùng.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..workspace import (
    BG_DARK, BG_CARD, BG_HOVER, BORDER,
    TEXT_PRIMARY, TEXT_MUTED, WARNING, DANGER,
)

if TYPE_CHECKING:  # pragma: no cover
    from ..workspace import AdminWorkspaceWindow


def build_sources_page(ws: "AdminWorkspaceWindow", parent: tk.Frame) -> tk.Frame:
    page = tk.Frame(parent, bg=BG_DARK)
    page.columnconfigure(0, weight=3)
    page.columnconfigure(1, weight=2)
    page.rowconfigure(1, weight=1)

    hdr = tk.Frame(page, bg=BG_DARK, pady=20, padx=24)
    hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
    tk.Label(hdr, text="Quản lý nguồn camera",
             bg=BG_DARK, fg=TEXT_PRIMARY, font=("Segoe UI", 16, "bold")).pack(side="left")
    if ws._is_admin:
        ws._accent_btn(hdr, "+ Video",  ws.controller.prepare_new_video,
                       secondary=True).pack(side="right")
        ws._accent_btn(hdr, "+ Camera", ws.controller.prepare_new_camera).pack(
            side="right", padx=(0, 8))

    list_card = tk.Frame(page, bg=BG_CARD, padx=12, pady=12)
    list_card.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=(0, 20))
    list_card.columnconfigure(0, weight=1)
    list_card.rowconfigure(1, weight=1)
    tk.Label(list_card, text="DANH SÁCH NGUỒN",
             bg=BG_CARD, fg=TEXT_MUTED, font=("Segoe UI", 7, "bold")).grid(
        row=0, column=0, sticky="w", pady=(0, 8))
    cols = ("#", "Tên", "Loại", "Nguồn", "Vị trí")
    ws.source_tree = ttk.Treeview(list_card, columns=cols, show="headings", height=16)
    for col in cols:
        ws.source_tree.heading(col, text=col)
    ws.source_tree.column("#",      width=40,  minwidth=30,  anchor="center")
    ws.source_tree.column("Tên",    width=160, minwidth=120)
    ws.source_tree.column("Loại",   width=70,  minwidth=60,  anchor="center")
    ws.source_tree.column("Nguồn",  width=160, minwidth=100)
    ws.source_tree.column("Vị trí", width=120, minwidth=80)
    vsb = ttk.Scrollbar(list_card, orient="vertical", command=ws.source_tree.yview)
    ws.source_tree.configure(yscrollcommand=vsb.set)
    ws.source_tree.grid(row=1, column=0, sticky="nsew")
    vsb.grid(row=1, column=1, sticky="ns")
    ws.source_tree.bind("<<TreeviewSelect>>", ws._on_source_select)

    detail_card = tk.Frame(page, bg=BG_CARD, padx=16, pady=16)
    detail_card.grid(row=1, column=1, sticky="nsew", padx=(0, 24), pady=(0, 20))
    detail_card.columnconfigure(1, weight=1)

    ws._source_form_widgets = []
    tk.Label(detail_card, textvariable=ws.details_title_var,
             bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

    def _fl(text, row):
        tk.Label(detail_card, text=text, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Segoe UI", 9), anchor="w").grid(
            row=row, column=0, sticky="w", pady=4, padx=(0, 10))

    def _fe(var, row, span=2, show=""):
        e = tk.Entry(detail_card, textvariable=var, bg=BG_HOVER, fg=TEXT_PRIMARY,
                     insertbackground=TEXT_PRIMARY, relief="flat", bd=1,
                     show=show, font=("Segoe UI", 9))
        e.grid(row=row, column=1, columnspan=span, sticky="ew", pady=4, padx=(4, 0))
        ws._source_form_widgets.append(e)
        return e

    _fl("Tên hiển thị", 1);  _fe(ws.form_name, 1)
    _fl("Vị trí",       2);  _fe(ws.form_location, 2)
    _fl("Loại nguồn",   3)
    type_cb = ttk.Combobox(detail_card, textvariable=ws.form_type,
                           state="readonly", values=["camera", "video"],
                           font=("Segoe UI", 9))
    type_cb.grid(row=3, column=1, columnspan=2, sticky="ew", pady=4, padx=(4, 0))
    ws._source_form_widgets.append(type_cb)

    _fl("Chỉ số / đường dẫn", 4)
    _fe(ws.form_source, 4, span=1)
    browse_btn = tk.Button(detail_card, text="📂", bg=BG_HOVER, fg=TEXT_PRIMARY,
                           relief="flat", bd=0, padx=6, pady=4, cursor="hand2",
                           font=("Segoe UI", 9), command=ws._browse_source_file)
    browse_btn.grid(row=4, column=2, sticky="ew", pady=4, padx=(4, 0))
    ws._source_form_widgets.append(browse_btn)

    if ws._is_admin:
        tk.Frame(detail_card, bg=BORDER, height=1).grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=10)
        ws._accent_btn(detail_card, "💾  Lưu thay đổi",
                       ws.controller.save_source).grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        tk.Button(detail_card, text="🗑  Xóa nguồn", bg=BG_HOVER, fg=DANGER,
                  relief="flat", bd=0, padx=10, pady=7, cursor="hand2",
                  font=("Segoe UI", 9),
                  command=ws.controller.remove_selected_source).grid(
            row=7, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        order_row = tk.Frame(detail_card, bg=BG_CARD)
        order_row.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        order_row.columnconfigure(0, weight=1)
        order_row.columnconfigure(1, weight=1)
        tk.Button(order_row, text="▲ Đưa lên", bg=BG_HOVER, fg=TEXT_MUTED,
                  relief="flat", bd=0, padx=6, pady=6, cursor="hand2",
                  font=("Segoe UI", 9),
                  command=lambda: ws.controller.move_selected_source(-1)).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Button(order_row, text="▼ Đưa xuống", bg=BG_HOVER, fg=TEXT_MUTED,
                  relief="flat", bd=0, padx=6, pady=6, cursor="hand2",
                  font=("Segoe UI", 9),
                  command=lambda: ws.controller.move_selected_source(1)).grid(
            row=0, column=1, sticky="ew")
    else:
        tk.Label(detail_card,
                 text="⚠  Chỉ xem — không có quyền chỉnh sửa nguồn camera.",
                 bg=BG_CARD, fg=WARNING, font=("Segoe UI", 8), wraplength=260).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=10)
        for w in ws._source_form_widgets:
            try:
                w.configure(state="disabled")
            except Exception:
                pass
    return page
