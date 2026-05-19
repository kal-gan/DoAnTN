"""
src/ui/admin/controller.py
AdminController - điều phối logic nghiệp vụ liên quan đến quản trị.
"""
import os
from typing import Any, Dict, Optional

from .auth import prompt_admin_auth
from .workspace import AdminWorkspaceWindow


class AdminController:
    """Điều phối các hành động quản trị: xác thực, quản lý nguồn, cài đặt."""

    def __init__(self, app: Any):
        self.app = app
        self.admin_panel_window: Optional[AdminWorkspaceWindow] = None

    # ------------------------------------------------------------------ #
    #  Xác thực                                                            #
    # ------------------------------------------------------------------ #

    def ensure_admin(self, action_label: str) -> bool:
        """Đảm bảo admin đã đăng nhập; hiển thị dialog nếu chưa."""
        if self.app.admin_user is not None:
            return True

        user = prompt_admin_auth(self.app, self.app.db, action_label)
        if user is None:
            return False

        self.app.admin_user = user
        user_id = int(user["id"])
        self.app.db.update_last_login(user_id)
        self.app.db.add_audit_log(user_id, "login", f"username={user['username']}, role=admin, action={action_label}")
        self.app._log(f"Xác thực admin thành công: {user['full_name']}")
        return True

    # ------------------------------------------------------------------ #
    #  Mở / đóng bảng admin                                               #
    # ------------------------------------------------------------------ #

    # Hệ thống chỉ có tài khoản admin — mọi tác vụ quản trị đều cần admin
    def ensure_login(self, action_label: str) -> bool:
        return self.ensure_admin(action_label)

    def open_admin_panel(self):
        if not self.ensure_admin("mở bảng quản trị"):
            return

        if self.admin_panel_window and self.admin_panel_window.winfo_exists():
            self.admin_panel_window.lift()
            self.admin_panel_window.focus_force()
            self.admin_panel_window.refresh()
            return

        self.admin_panel_window = AdminWorkspaceWindow(parent=self.app, controller=self)

    def close_admin_panel(self):
        if self.admin_panel_window and self.admin_panel_window.winfo_exists():
            self.admin_panel_window.destroy()
        self.admin_panel_window = None

    def close_settings_window(self):
        self.close_admin_panel()

    def close_source_window(self):
        self.close_admin_panel()

    def open_settings_window(self):
        self.open_admin_panel()
        if self.admin_panel_window and self.admin_panel_window.winfo_exists():
            self.admin_panel_window._show_page("settings")

    def open_source_window(self):
        self.open_admin_panel()
        if self.admin_panel_window and self.admin_panel_window.winfo_exists():
            self.admin_panel_window._show_page("sources")

    def refresh_admin_panel(self, selected_source_id: Optional[int] = None, status_text: Optional[str] = None):
        if self.admin_panel_window and self.admin_panel_window.winfo_exists():
            if status_text:
                self.admin_panel_window.notify(status_text)
            self.admin_panel_window.refresh(selected_source_id=selected_source_id)

    # ------------------------------------------------------------------ #
    #  Tác vụ nhanh (bật/tắt/cấu hình)                                    #
    # ------------------------------------------------------------------ #

    def prepare_new_camera(self):
        self.open_source_window()
        if self.admin_panel_window and self.admin_panel_window.winfo_exists():
            self.admin_panel_window.prepare_new_source("camera")

    def prepare_new_video(self):
        self.open_source_window()
        if self.admin_panel_window and self.admin_panel_window.winfo_exists():
            self.admin_panel_window.prepare_new_source("video")
            self.admin_panel_window._browse_source_file()

    def start_detection(self):
        self.app.start_detection(require_admin=False)
        self.refresh_admin_panel(status_text="Đã gửi lệnh bật giám sát")

    def stop_detection(self):
        self.app.stop_detection(require_admin=False)
        self.refresh_admin_panel(status_text="Đã gửi lệnh ngắt toàn bộ")

    def apply_runtime_settings(self):
        # Lưu xuống DB trước để cấu hình được giữ sau khi khởi động lại
        try:
            self.app.save_runtime_settings()
        except Exception:
            pass
        if self.app.is_running:
            self.app.stop_detection(require_admin=False, on_stopped=lambda: self.app.start_detection(require_admin=False))
            self.app._log("Đã áp dụng cấu hình mới và khởi động lại giám sát.")
            self.refresh_admin_panel(status_text="Đang áp dụng cấu hình mới")
            return

        self.app._log("Đã cập nhật cấu hình giám sát.")
        self.app._set_status("Đã cập nhật cấu hình")
        self.refresh_admin_panel(status_text="Đã cập nhật cấu hình")

    # ------------------------------------------------------------------ #
    #  Đổi mật khẩu                                                        #
    # ------------------------------------------------------------------ #

    def change_admin_password(self):
        if not self.ensure_admin("đổi mật khẩu admin") or self.app.admin_user is None:
            return

        if self.admin_panel_window is None or not self.admin_panel_window.winfo_exists():
            return

        payload = self.admin_panel_window.get_password_payload()
        current_password = payload["current_password"]
        new_password = payload["new_password"]
        confirm_password = payload["confirm_password"]

        if not current_password or not new_password or not confirm_password:
            self.admin_panel_window.show_warning("Thiếu thông tin", "Vui lòng nhập đầy đủ thông tin đổi mật khẩu.")
            return

        if len(new_password) < 6:
            self.admin_panel_window.show_warning("Mật khẩu quá ngắn", "Mật khẩu mới phải có ít nhất 6 ký tự.")
            return

        if new_password != confirm_password:
            self.admin_panel_window.show_warning("Xác nhận không khớp", "Mật khẩu xác nhận không trùng với mật khẩu mới.")
            return

        verified_user = self.app.db.verify_user(str(self.app.admin_user["username"]), current_password)
        if verified_user is None:
            self.admin_panel_window.show_error("Sai mật khẩu", "Mật khẩu hiện tại không đúng.")
            return

        self.app.db.update_user_password(int(self.app.admin_user["id"]), new_password)
        self.app.db.add_audit_log(int(self.app.admin_user["id"]), "change_password", "admin_password_updated")
        self.app._log("Admin đã đổi mật khẩu thành công.")
        self.app._set_status("Đã đổi mật khẩu admin")
        self.admin_panel_window.clear_password_form()
        self.refresh_admin_panel(status_text="Đã đổi mật khẩu admin")

    # ------------------------------------------------------------------ #
    #  Quản lý nguồn camera                                                #
    # ------------------------------------------------------------------ #

    def save_source(self):
        if not self.ensure_admin("kết nối camera") or self.app.admin_user is None:
            return

        if self.admin_panel_window is None or not self.admin_panel_window.winfo_exists():
            return

        payload = self.admin_panel_window.get_form_payload()
        source_type = payload["type"]
        source_value = payload["source"]
        name = payload["name"]
        location = payload["location"]

        if source_type not in {"camera", "video"}:
            self.admin_panel_window.show_warning("Loại nguồn không hợp lệ", "Chỉ hỗ trợ camera hoặc video.")
            return

        if source_type == "camera":
            if not source_value.isdigit():
                self.admin_panel_window.show_warning("Sai chỉ số camera", "Nguồn camera phải là số nguyên như 0, 1, 2.")
                return
            normalized_source = str(int(source_value))
            normalized_value: Any = int(normalized_source)
            default_name = f"Camera {normalized_source}"
        else:
            if not source_value:
                self.admin_panel_window.show_warning("Thiếu đường dẫn", "Vui lòng chọn tệp video.")
                return
            normalized_source = os.path.normpath(source_value)
            normalized_value = normalized_source
            default_name = os.path.basename(normalized_source)

        display_name = name or default_name
        admin_id = int(self.app.admin_user["id"])
        camera_id = payload.get("camera_id")

        if payload["mode"] == "edit" and camera_id is not None:
            self.app.db.update_camera(int(camera_id), display_name, normalized_source, location)
            for source in self.app.sources:
                if source.get("id") is not None and int(source["id"]) == int(camera_id):
                    source["name"] = display_name
                    source["location"] = location
                    source["type"] = source_type
                    source["value"] = normalized_value
                    break
            self.app.db.add_audit_log(admin_id, "update_camera", f"camera_id={camera_id}, source={normalized_source}")
            self.app._log(f"Đã cập nhật nguồn: {display_name}")
            selected_id = int(camera_id)
        else:
            selected_id = self.app.db.add_camera(display_name, normalized_source, location, admin_id)
            self.app.sources.append(
                {"id": selected_id, "type": source_type, "value": normalized_value, "name": display_name, "location": location}
            )
            self.app.db.add_audit_log(admin_id, "add_camera", f"camera_id={selected_id}, source={normalized_source}")
            self.app._log(f"Đã thêm nguồn: {display_name}")

        self.app.latest_frames.clear()
        self.app._update_source_summary()
        self.app._apply_source_changes()
        self.refresh_admin_panel(selected_source_id=selected_id, status_text="Đã lưu cấu hình nguồn")

    def remove_selected_source(self):
        if not self.ensure_admin("kết nối camera") or self.app.admin_user is None:
            return

        selected = self._get_selected_source()
        if selected is None or self.admin_panel_window is None:
            return

        if not self.admin_panel_window.ask_confirm("Xóa nguồn", f"Xóa nguồn '{self.app._source_to_text(selected)}'?"):
            return

        idx = self.app.sources.index(selected)
        removed = self.app.sources.pop(idx)
        camera_id = removed.get("id")
        if camera_id is not None:
            self.app.db.deactivate_camera(int(camera_id))
            self.app.db.add_audit_log(int(self.app.admin_user["id"]), "delete_camera", f"camera_id={camera_id}")

        next_selection = None
        if self.app.sources:
            next_index = min(idx, len(self.app.sources) - 1)
            next_selection = int(self.app.sources[next_index]["id"])

        self.app.latest_frames.clear()
        self.app._update_source_summary()
        self.app._apply_source_changes()
        self.app._log(f"Đã xóa nguồn: {self.app._source_to_text(removed)}")
        self.refresh_admin_panel(selected_source_id=next_selection, status_text="Đã xóa nguồn")

    def move_selected_source(self, step: int):
        if not self.ensure_admin("kết nối camera") or self.app.admin_user is None:
            return

        selected = self._get_selected_source()
        if selected is None:
            return

        old_idx = self.app.sources.index(selected)
        new_idx = old_idx + step
        if new_idx < 0 or new_idx >= len(self.app.sources):
            return

        self.app.sources[old_idx], self.app.sources[new_idx] = self.app.sources[new_idx], self.app.sources[old_idx]
        ordered_ids = [int(source["id"]) for source in self.app.sources if source.get("id") is not None]
        if ordered_ids:
            self.app.db.update_camera_order(ordered_ids)
            self.app.db.add_audit_log(int(self.app.admin_user["id"]), "reorder_camera", f"old={old_idx},new={new_idx}")

        self.app._update_source_summary()
        self.app._ensure_video_tiles()
        self.app._redraw_all_tiles()
        selected_id = selected.get("id")
        self.refresh_admin_panel(
            selected_source_id=int(selected_id) if selected_id is not None else None,
            status_text="Đã đổi thứ tự nguồn",
        )

    def _get_selected_source(self) -> Optional[Dict[str, Any]]:
        if self.admin_panel_window is None or not self.admin_panel_window.winfo_exists():
            return None
        selected_id = self.admin_panel_window.selected_source_id
        if selected_id is None:
            return None
        for source in self.app.sources:
            source_id = source.get("id")
            if source_id is not None and int(source_id) == int(selected_id):
                return source
        return None

    # ------------------------------------------------------------------ #
    #  Quản lý người dùng (admin only)                                     #
    # ------------------------------------------------------------------ #

    def save_user(self):
        """Tạo mới hoặc cập nhật người dùng từ form trên trang users."""
        if not self.ensure_admin("quản lý người dùng") or self.app.admin_user is None:
            return
        if self.admin_panel_window is None or not self.admin_panel_window.winfo_exists():
            return

        payload = self.admin_panel_window.get_user_form_payload()
        admin_id = int(self.app.admin_user["id"])

        if payload["user_id"] is None:
            # Tạo mới
            username = payload["username"]
            password = payload["password"]
            if not username:
                self.admin_panel_window.show_warning("Thiếu thông tin", "Tài khoản không được để trống.")
                return
            if not password or len(password) < 6:
                self.admin_panel_window.show_warning("Mật khẩu yếu", "Mật khẩu phải có ít nhất 6 ký tự.")
                return
            try:
                new_id = self.app.db.add_user(
                    username=username,
                    password=password,
                    role=payload["role"],
                    full_name=payload["full_name"],
                    email=payload["email"],
                )
                self.app.db.add_audit_log(admin_id, "add_user",
                    f"new_user={username}, role={payload['role']}")
                self.app._log(f"Đã tạo người dùng mới: {username}")
                self.admin_panel_window.user_form_selected_id = new_id
            except Exception as exc:
                self.admin_panel_window.show_error("Lỗi tạo người dùng", str(exc))
                return
        else:
            # Cập nhật
            uid = int(payload["user_id"])
            new_pwd = payload["password"]
            self.app.db.update_user(
                user_id=uid,
                role=payload["role"],
                full_name=payload["full_name"],
                email=payload["email"],
                is_active=1,
            )
            if new_pwd and len(new_pwd) >= 6:
                self.app.db.update_user_password(uid, new_pwd)
            elif new_pwd:
                self.admin_panel_window.show_warning("Mật khẩu yếu",
                    "Mật khẩu mới phải có ít nhất 6 ký tự. Thông tin khác đã được lưu.")
            self.app.db.add_audit_log(admin_id, "update_user",
                f"user_id={uid}, role={payload['role']}")
            self.app._log(f"Đã cập nhật người dùng id={uid}")

        self.refresh_admin_panel(status_text="Đã lưu thông tin người dùng")

    def toggle_user_active(self):
        """Bật/tắt trạng thái hoạt động của người dùng được chọn."""
        if not self.ensure_admin("quản lý người dùng") or self.app.admin_user is None:
            return
        if self.admin_panel_window is None or not self.admin_panel_window.winfo_exists():
            return

        uid = self.admin_panel_window.user_form_selected_id
        if uid is None:
            self.admin_panel_window.show_warning("Chưa chọn", "Vui lòng chọn người dùng cần thay đổi trạng thái.")
            return

        # Không cho phép tự khóa chính mình
        if int(uid) == int(self.app.admin_user["id"]):
            self.admin_panel_window.show_warning("Không hợp lệ", "Không thể khóa tài khoản đang đăng nhập.")
            return

        try:
            users = self.app.db.get_all_users()
            target = next((u for u in users if int(u["id"]) == int(uid)), None)
            if target is None:
                return
            is_active = int(target.get("is_active", 1))
            new_state = 0 if is_active else 1
            self.app.db.update_user(
                user_id=int(uid),
                role=str(target.get("role", "user")),
                full_name=str(target.get("full_name", "")),
                email=str(target.get("email") or ""),
                is_active=new_state,
            )
            action = "activate_user" if new_state else "deactivate_user"
            self.app.db.add_audit_log(int(self.app.admin_user["id"]), action,
                f"user_id={uid}, username={target.get('username')}")
            state_label = "kích hoạt" if new_state else "vô hiệu hóa"
            self.app._log(f"Đã {state_label} tài khoản: {target.get('username')}")
        except Exception as exc:
            self.admin_panel_window.show_error("Lỗi", str(exc))
            return

        self.refresh_admin_panel(status_text="Đã cập nhật trạng thái tài khoản")
