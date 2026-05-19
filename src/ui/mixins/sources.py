"""
src/ui/mixins/sources.py
SourcesMixin - quản lý danh sách nguồn camera/video.
"""
import os
from tkinter import filedialog
from typing import Any, Dict, List, Optional


class SourcesMixin:
    """Mixin xử lý tải, hiển thị và cập nhật nguồn camera/video."""

    # ------------------------------------------------------------------ #
    #  Helpers tĩnh                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_source(source_text: str) -> Dict[str, Any]:
        source_text = source_text.strip()
        if source_text.isdigit():
            return {"type": "camera", "value": int(source_text)}
        return {"type": "video", "value": source_text}

    @staticmethod
    def _source_to_text(source: Dict[str, Any]) -> str:
        if source.get("name"):
            return str(source["name"])
        if source["type"] == "camera":
            return f"Camera {source['value']}"
        return os.path.basename(str(source["value"]))

    # ------------------------------------------------------------------ #
    #  Tải từ DB                                                           #
    # ------------------------------------------------------------------ #

    def _load_sources_from_db(self):
        rows = self.db.get_active_cameras()  # type: ignore[attr-defined]
        self.sources: List[Dict[str, Any]] = []
        for row in rows:
            parsed = self._parse_source(str(row["source"]))
            self.sources.append(
                {
                    "id": int(row["id"]),
                    "name": str(row["name"]),
                    "location": str(row.get("location") or ""),
                    "type": parsed["type"],
                    "value": parsed["value"],
                }
            )
        self._update_source_summary()  # type: ignore[attr-defined]
        self._ensure_video_tiles()     # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    #  Cập nhật tóm tắt nguồn                                             #
    # ------------------------------------------------------------------ #

    def _update_source_summary(self):
        if not self.sources:  # type: ignore[attr-defined]
            self.source_summary.set("Chưa có nguồn camera")  # type: ignore[attr-defined]
            self.stat_source.set("0 nguồn")  # type: ignore[attr-defined]
            return

        labels = [self._source_to_text(source) for source in self.sources]  # type: ignore[attr-defined]
        summary = ", ".join(labels[:3])
        if len(labels) > 3:
            summary += ", ..."
        self.source_summary.set(f"{len(self.sources)} nguồn: {summary}")  # type: ignore[attr-defined]
        self.stat_source.set(f"{len(self.sources)} nguồn")  # type: ignore[attr-defined]
        if "connection" in self.pages and hasattr(self, "video_panel"):  # type: ignore[attr-defined]
            try:
                self.video_panel["text"] = f"Camera giám sát - {self.source_summary.get()}"  # type: ignore[attr-defined]
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  Áp dụng thay đổi nguồn trong khi đang chạy                         #
    # ------------------------------------------------------------------ #

    def _apply_source_changes(self):
        if not self.sources:  # type: ignore[attr-defined]
            if self.is_running:  # type: ignore[attr-defined]
                self._log("Đang áp dụng cấu hình nguồn mới...")  # type: ignore[attr-defined]
                self.stop_detection(require_admin=False)  # type: ignore[attr-defined]
            self._set_status("Đã dừng - không còn nguồn camera")  # type: ignore[attr-defined]
            self._ensure_video_tiles()  # type: ignore[attr-defined]
            return

        if self.is_running:  # type: ignore[attr-defined]
            self._log("Đang áp dụng cấu hình nguồn mới...")  # type: ignore[attr-defined]
            self.stop_detection(  # type: ignore[attr-defined]
                require_admin=False,
                on_stopped=lambda: self.start_detection(require_admin=False),  # type: ignore[attr-defined]
            )
            return

        self.start_detection(require_admin=False)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    #  Chọn model                                                          #
    # ------------------------------------------------------------------ #

    def choose_model(self):
        path = filedialog.askopenfilename(
            title="Chọn model YOLO (.pt)",
            filetypes=[("Model PyTorch", "*.pt"), ("Tất cả", "*.*")],
        )
        if path:
            self.model_path.set(path)  # type: ignore[attr-defined]
            self._log(f"Đã cập nhật model: {path}")  # type: ignore[attr-defined]
