"""
src/ui/admin/training_tab.py
Tab huấn luyện gia tăng trong admin panel - CHỈ ADMIN DÙNG.
Admin phải approve từng lần huấn luyện.
"""
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from typing import Any, Optional
import threading


def create_training_tab(parent: tk.Frame, admin_workspace: Any) -> tk.Frame:
    """
    Tạo tab huấn luyện gia tăng (Admin only).
    
    Args:
        parent: Frame cha
        admin_workspace: Đối tượng AdminWorkspaceWindow
    
    Returns:
        Frame chứa UI huấn luyện
    """
    
    BG_DARK      = "#11141d"
    BG_CARD      = "#1d212e"
    BG_HOVER     = "#2a3047"
    ACCENT       = "#f04e1a"
    TEXT_PRIMARY = "#f5f7fb"
    TEXT_MUTED   = "#9ba4b4"
    BORDER       = "#2b3047"
    SUCCESS      = "#22c55e"
    WARNING      = "#fbbf24"
    
    frame = tk.Frame(parent, bg=BG_DARK)
    
    # ────────────────────────────────────────────────────────────────
    # Title
    # ────────────────────────────────────────────────────────────────
    title_frame = tk.Frame(frame, bg=BG_DARK)
    title_frame.pack(fill=tk.X, padx=20, pady=(10, 6))
    
    title_lbl = tk.Label(
        title_frame,
        text="📚 Huấn luyện gia tăng (Admin)",
        font=("Segoe UI", 14, "bold"),
        bg=BG_DARK,
        fg=TEXT_PRIMARY,
    )
    title_lbl.pack(anchor="w")
    
    # ─────────────────────────────────────────────────────────────
    # Content area
    # ─────────────────────────────────────────────────────────────
    content_frame = tk.Frame(frame, bg=BG_DARK)
    content_frame.pack(fill=tk.X, expand=False, padx=20, pady=(4, 4))
    
    # Left column - Data Collection
    left_frame = tk.Frame(content_frame, bg=BG_DARK)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
    
    # Collection header
    collect_label = tk.Label(
        left_frame,
        text="📂 Thu thập dữ liệu",
        font=("Segoe UI", 10, "bold"),
        bg=BG_DARK,
        fg=TEXT_PRIMARY,
    )
    collect_label.pack(anchor="w", pady=(0, 4))
    
    # Collection status
    collect_status_frame = tk.Frame(left_frame, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER)
    collect_status_frame.pack(fill=tk.X, pady=(0, 5))
    
    tk.Label(collect_status_frame, text="Trạng thái", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=10, pady=(4, 0))
    
    collect_status_var = tk.StringVar(value="❌ Tắt")
    collect_status_label = tk.Label(collect_status_frame, textvariable=collect_status_var, font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=WARNING)
    collect_status_label.pack(anchor="w", padx=10, pady=(0, 4))
    
    # Stats
    stat1_frame = tk.Frame(left_frame, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER)
    stat1_frame.pack(fill=tk.X, pady=(0, 5))
    
    tk.Label(stat1_frame, text="📷 Ảnh thu thập", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=10, pady=(4, 0))
    
    collected_images_var = tk.StringVar(value="0")
    tk.Label(stat1_frame, textvariable=collected_images_var, font=("Segoe UI", 13, "bold"), bg=BG_CARD, fg=ACCENT).pack(anchor="w", padx=10, pady=(0, 4))
    
    stat2_frame = tk.Frame(left_frame, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER)
    stat2_frame.pack(fill=tk.X)
    
    tk.Label(stat2_frame, text="🎯 Tổng detection", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=10, pady=(4, 0))
    
    total_detections_var = tk.StringVar(value="0")
    tk.Label(stat2_frame, textvariable=total_detections_var, font=("Segoe UI", 13, "bold"), bg=BG_CARD, fg=SUCCESS).pack(anchor="w", padx=10, pady=(0, 4))
    
    # Right column - Training
    right_frame = tk.Frame(content_frame, bg=BG_DARK)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(15, 0))
    
    controls_label = tk.Label(
        right_frame,
        text="⚙️ Huấn luyện mô hình",
        font=("Segoe UI", 10, "bold"),
        bg=BG_DARK,
        fg=TEXT_PRIMARY,
    )
    controls_label.pack(anchor="w", pady=(0, 4))
    
    # Training parameters
    params_frame = tk.Frame(right_frame, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER)
    params_frame.pack(fill=tk.X, pady=(0, 5))
    
    tk.Label(params_frame, text="Số epoch", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=10, pady=(4, 0))
    epochs_var = tk.StringVar(value="10")
    epochs_entry = tk.Entry(
        params_frame,
        textvariable=epochs_var,
        font=("Segoe UI", 10),
        bg="#2b3047",
        fg=TEXT_PRIMARY,
        insertbackground=ACCENT,
        relief=tk.FLAT,
        width=20,
    )
    epochs_entry.pack(fill=tk.X, padx=10, pady=(0, 4))
    
    tk.Label(params_frame, text="Batch size", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", padx=10, pady=(0, 0))
    batch_var = tk.StringVar(value="16")
    batch_entry = tk.Entry(
        params_frame,
        textvariable=batch_var,
        font=("Segoe UI", 10),
        bg="#2b3047",
        fg=TEXT_PRIMARY,
        insertbackground=ACCENT,
        relief=tk.FLAT,
        width=20,
    )
    batch_entry.pack(fill=tk.X, padx=10, pady=(0, 4))
    
    # Training status
    training_status_var = tk.StringVar(value="Sẵn sàng")
    status_label = tk.Label(right_frame, textvariable=training_status_var, font=("Segoe UI", 10, "bold"), bg=BG_DARK, fg=TEXT_MUTED)
    status_label.pack(anchor="w", pady=(0, 4))
    
    def update_status_color(*args):
        text = training_status_var.get()
        if "Sẵn sàng" in text:
            status_label.config(fg=TEXT_MUTED)
        elif "Đang" in text:
            status_label.config(fg=WARNING)
        elif "✓" in text:
            status_label.config(fg=SUCCESS)
        else:
            status_label.config(fg="#ff6b6b")
    
    training_status_var.trace("w", update_status_color)
    
    # Buttons frame
    buttons_frame = tk.Frame(right_frame, bg=BG_DARK)
    buttons_frame.pack(fill=tk.X, pady=(4, 0))
    
    # Functions
    def on_refresh_stats():
        try:
            from src.core.data_collector import DataCollector
            collector = DataCollector()
            stats = collector.get_collection_stats()
            collected_images_var.set(str(stats["total_images"]))
            total_detections_var.set(str(stats["total_detections"]))
        except Exception as e:
            collected_images_var.set("0")
            total_detections_var.set("0")
    
    def on_enable_collection():
        if messagebox.askyesno("Xác nhận", "Bạn muốn bắt đầu thu thập dữ liệu trong lần giám sát tiếp theo?"):
            try:
                from src.core.data_collector import DataCollector
                admin_workspace.app.data_collection_enabled = True  # type: ignore[attr-defined]
                if admin_workspace.app.detector is not None:  # type: ignore[attr-defined]
                    admin_workspace.app.data_collector = DataCollector(  # type: ignore[attr-defined]
                        collection_dir="training_data/collected"
                    )
                    if hasattr(admin_workspace.app.detector, "class_names"):  # type: ignore[attr-defined]
                        admin_workspace.app.data_collector.set_class_map(  # type: ignore[attr-defined]
                            admin_workspace.app.detector.class_names  # type: ignore[attr-defined]
                        )
                collect_status_var.set("✅ Bật")
                collect_status_label.config(fg=SUCCESS)
                messagebox.showinfo("Thành công", "Thu thập dữ liệu sẽ bắt đầu ở lần giám sát tiếp theo")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi: {e}")
    
    def on_disable_collection():
        admin_workspace.app.data_collection_enabled = False  # type: ignore[attr-defined]
        admin_workspace.app.data_collector = None  # type: ignore[attr-defined]
        collect_status_var.set("❌ Tắt")
        collect_status_label.config(fg=WARNING)
    
    def on_start_training():
        if not collected_images_var.get() or collected_images_var.get() == "0":
            messagebox.showwarning("Thiếu dữ liệu", "Chưa có ảnh thu thập để huấn luyện.")
            return
        
        try:
            epochs = int(epochs_var.get())
            batch = int(batch_var.get())
            
            if epochs <= 0 or batch <= 0:
                messagebox.showwarning("Lỗi", "Epoch và batch phải > 0")
                return
        
        except ValueError:
            messagebox.showerror("Lỗi", "Epoch và batch phải là số nguyên")
            return
        
        if not messagebox.askyesno("Xác nhận", f"Bắt đầu huấn luyện với {epochs} epoch, batch {batch}?"):
            return
        
        training_status_var.set("Đang huấn luyện...")
        
        def training_worker():
            try:
                from src.core.incremental_trainer import IncrementalTrainer
                
                def log_progress(msg: str):
                    training_status_var.set(msg.split("]")[-1].strip() if "]" in msg else msg)
                
                trainer = IncrementalTrainer(progress_callback=log_progress)
                
                # Chuẩn bị dữ liệu
                training_status_var.set("Chuẩn bị dữ liệu...")
                if not trainer.prepare_combined_dataset():
                    training_status_var.set("Lỗi: Không thể chuẩn bị dữ liệu")
                    return
                
                # Huấn luyện
                if trainer.train_incremental(
                    epochs=epochs,
                    batch=batch,
                    data_yaml="data/combined/data.yaml",
                ):
                    # Sau khi huấn luyện thành công -> xóa toàn bộ ảnh đã dùng
                    try:
                        from src.core.data_collector import DataCollector
                        DataCollector().clear_collected_data()
                    except Exception:
                        pass
                    training_status_var.set("✓ Huấn luyện thành công! (đã dọn ảnh)")
                    on_refresh_stats()
                    try:
                        training_gallery_ref["obj"].refresh()  # type: ignore[union-attr]
                    except Exception:
                        pass
                    messagebox.showinfo("Thành công", "✓ Huấn luyện gia tăng hoàn tất!\nMô hình mới: models/best_incremental.pt\nẢnh huấn luyện đã được dọn sạch.")
                else:
                    training_status_var.set("Lỗi: Huấn luyện thất bại")
            
            except Exception as e:
                training_status_var.set(f"Lỗi: {str(e)[:30]}")
                messagebox.showerror("Lỗi", f"Lỗi huấn luyện: {e}")
        
        thread = threading.Thread(target=training_worker, daemon=True)
        thread.start()
    
    def on_clear_data():
        if messagebox.askyesno("Xác nhận", "Xóa tất cả dữ liệu thu thập? (Không thể hoàn tác)"):
            try:
                from src.core.data_collector import DataCollector
                collector = DataCollector()
                if collector.clear_collected_data():
                    collected_images_var.set("0")
                    total_detections_var.set("0")
                    messagebox.showinfo("Thành công", "Đã xóa dữ liệu thu thập")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi xóa dữ liệu: {e}")
    
    # Buttons
    btn_enable = tk.Button(
        buttons_frame,
        text="📌 Bật",
        command=on_enable_collection,
        font=("Segoe UI", 9, "bold"),
        bg=SUCCESS,
        fg="#ffffff",
        relief=tk.FLAT,
        width=12,
        pady=5,
        cursor="hand2",
    )
    btn_enable.pack(side=tk.LEFT, padx=(0, 4))
    
    btn_disable = tk.Button(
        buttons_frame,
        text="⏹ Tắt",
        command=on_disable_collection,
        font=("Segoe UI", 9),
        bg=BG_CARD,
        fg=TEXT_PRIMARY,
        relief=tk.FLAT,
        width=12,
        pady=5,
        cursor="hand2",
    )
    btn_disable.pack(side=tk.LEFT, padx=(0, 4))
    
    # Training buttons
    buttons_frame2 = tk.Frame(right_frame, bg=BG_DARK)
    buttons_frame2.pack(fill=tk.X, pady=(4, 0))
    
    # btn_train sẽ được tạo phía dưới (sau khi gallery khai báo) để biết được
    # ảnh đã chọn -> chạy on_train_selected; nếu không -> chạy on_start_training
    btn_train_placeholder = tk.Frame(buttons_frame2, bg=BG_DARK)
    btn_train_placeholder.pack(side=tk.LEFT, padx=(0, 4))

    # ────────────────────────────────────────────────────────────────
    # Dán nhãn thủ công
    # ────────────────────────────────────────────────────────────────
    # forward-decl để on_open_annotation có thể tham chiếu gallery
    training_gallery_ref: dict = {"obj": None}

    def _on_saved_callback():
        gal = training_gallery_ref.get("obj")
        if gal is not None:
            try:
                gal.refresh()
            except Exception:
                pass

    def on_open_annotation(image_path=None):
        try:
            from src.ui.admin.annotation_tool import open_annotation_window
            if image_path:
                open_annotation_window(frame, initial_image=image_path, on_saved=_on_saved_callback)
            else:
                open_annotation_window(frame, initial_dir="training_data/collected/images", on_saved=_on_saved_callback)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được công cụ dán nhãn: {e}")

    btn_annotate = tk.Button(
        buttons_frame2,
        text="✏️ Dán nhãn",
        command=lambda: on_open_annotation(None),
        font=("Segoe UI", 9, "bold"),
        bg="#2563eb",
        fg="#ffffff",
        relief=tk.FLAT,
        width=12,
        pady=5,
        cursor="hand2",
    )
    btn_annotate.pack(side=tk.LEFT)

    # ────────────────────────────────────────────────────────────────
    # Gallery ảnh huấn luyện (tick chọn để train)
    # ────────────────────────────────────────────────────────────────
    from src.ui.admin.training_gallery import TrainingGallery

    gallery_section = tk.Frame(frame, bg=BG_DARK)
    gallery_section.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4, 4))

    training_gallery = TrainingGallery(gallery_section, on_open_annotation=on_open_annotation)
    training_gallery.pack(fill=tk.BOTH, expand=True)
    training_gallery_ref["obj"] = training_gallery

    # Sau khi annotation tool đóng, làm mới gallery để cập nhật phân loại
    def _refresh_gallery_after_delay():
        try:
            training_gallery.refresh()
        except Exception:
            pass

    # Nút huấn luyện ảnh đã chọn (sub-set)
    def on_train_selected():
        selected = training_gallery.selected_paths()
        if not selected:
            messagebox.showwarning("Chưa chọn ảnh", "Hãy tick chọn ít nhất 1 ảnh trong gallery để huấn luyện.")
            return

        try:
            epochs = int(epochs_var.get())
            batch = int(batch_var.get())
            if epochs <= 0 or batch <= 0:
                messagebox.showwarning("Lỗi", "Epoch và batch phải > 0")
                return
        except ValueError:
            messagebox.showerror("Lỗi", "Epoch và batch phải là số nguyên")
            return

        if not messagebox.askyesno(
            "Xác nhận huấn luyện",
            f"Huấn luyện trên {len(selected)} ảnh đã chọn?\n\nEpochs: {epochs}  |  Batch: {batch}",
        ):
            return

        training_status_var.set(f"Chuẩn bị {len(selected)} ảnh...")

        def worker():
            import shutil
            from pathlib import Path

            sel_root = Path("training_data/_selected")
            try:
                if sel_root.exists():
                    shutil.rmtree(sel_root, ignore_errors=True)
                (sel_root / "images").mkdir(parents=True, exist_ok=True)
                (sel_root / "labels").mkdir(parents=True, exist_ok=True)

                src_labels = Path("training_data/collected/labels")
                copied = 0
                for img_str in selected:
                    img = Path(img_str)
                    if not img.is_file():
                        continue
                    shutil.copy2(img, sel_root / "images" / img.name)
                    lbl = src_labels / f"{img.stem}.txt"
                    if lbl.exists():
                        shutil.copy2(lbl, sel_root / "labels" / lbl.name)
                    copied += 1

                if copied == 0:
                    training_status_var.set("Lỗi: không copy được ảnh nào")
                    return

                from src.core.incremental_trainer import IncrementalTrainer

                def log_progress(msg: str):
                    training_status_var.set(msg.split("]")[-1].strip() if "]" in msg else msg)

                trainer = IncrementalTrainer(progress_callback=log_progress)
                training_status_var.set("Chuẩn bị dữ liệu...")
                if not trainer.prepare_combined_dataset(new_data_dir=str(sel_root)):
                    training_status_var.set("Lỗi: chuẩn bị dữ liệu thất bại")
                    return

                if trainer.train_incremental(
                    epochs=epochs,
                    batch=batch,
                    data_yaml="data/combined/data.yaml",
                ):
                    # Sau huấn luyện thành công -> xóa chính các ảnh + label đã dùng
                    src_labels = Path("training_data/collected/labels")
                    deleted = 0
                    for img_str in selected:
                        img = Path(img_str)
                        try:
                            if img.is_file():
                                img.unlink()
                            lbl = src_labels / f"{img.stem}.txt"
                            if lbl.exists():
                                lbl.unlink()
                            manual = src_labels / f"{img.stem}.manual"
                            if manual.exists():
                                manual.unlink()
                            deleted += 1
                        except Exception:
                            pass
                    training_status_var.set(f"✓ Huấn luyện thành công! (đã dọn {deleted} ảnh)")
                    on_refresh_stats()
                    try:
                        training_gallery.refresh()
                    except Exception:
                        pass
                    messagebox.showinfo(
                        "Thành công",
                        f"✓ Huấn luyện hoàn tất trên {copied} ảnh đã chọn!\nModel mới: models/best_incremental.pt\nĐã dọn {deleted} ảnh khỏi thư mục thu thập.",
                    )
                else:
                    training_status_var.set("Lỗi: huấn luyện thất bại")

            except Exception as e:
                training_status_var.set(f"Lỗi: {str(e)[:40]}")
                messagebox.showerror("Lỗi", f"Lỗi huấn luyện: {e}")
            finally:
                # Dọn temp
                try:
                    if sel_root.exists():
                        shutil.rmtree(sel_root, ignore_errors=True)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    # Nút huấn luyện tổng hợp: nếu có ảnh đã chọn -> huấn luyện sub-set,
    # ngược lại -> huấn luyện toàn bộ dữ liệu thu thập.
    def on_train_smart():
        try:
            selected = training_gallery.selected_paths()
        except Exception:
            selected = []
        if selected:
            on_train_selected()
        else:
            on_start_training()

    btn_train = tk.Button(
        btn_train_placeholder,
        text="▶ Huấn luyện",
        command=on_train_smart,
        font=("Segoe UI", 9, "bold"),
        bg=ACCENT,
        fg="#ffffff",
        relief=tk.FLAT,
        width=12,
        pady=5,
        cursor="hand2",
    )
    btn_train.pack()

    # Load initial stats
    on_refresh_stats()
    
    return frame
