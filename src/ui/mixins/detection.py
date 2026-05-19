"""
src/ui/mixins/detection.py
DetectionMixin - quản lý vòng đời phát hiện (start/stop/loop worker thread).
"""
import queue
import threading
import time
import os
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import cv2
from tkinter import messagebox

try:
    from src.ui.utils.danger_level import (
        compute_danger_level, level_requires_sound, level_requires_email,
    )
except ImportError:
    try:
        from ui.utils.danger_level import (  # type: ignore[no-redef]
            compute_danger_level, level_requires_sound, level_requires_email,
        )
    except ImportError:
        def compute_danger_level(detections, fh, fw): return "LOW"  # type: ignore[misc]
        def level_requires_sound(level): return level in ("MEDIUM", "HIGH", "CRITICAL")  # type: ignore[misc]
        def level_requires_email(level): return level in ("HIGH", "CRITICAL")  # type: ignore[misc]

try:
    from src.core.data_collector import DataCollector
except ImportError:
    try:
        from core.data_collector import DataCollector  # type: ignore[no-redef]
    except ImportError:
        DataCollector = None  # type: ignore[misc]


class DetectionMixin:
    """Mixin xử lý toàn bộ logic bắt đầu / dừng / vòng lặp phát hiện đa luồng."""

    # ------------------------------------------------------------------ #
    #  Xây dựng detector và stream                                         #
    # ------------------------------------------------------------------ #

    def _resolve_sources(self) -> Optional[List[Dict[str, Any]]]:
        if not self.sources:  # type: ignore[attr-defined]
            messagebox.showwarning("Thiếu nguồn", "Vui lòng thêm ít nhất một camera hoặc video trong menu Nguồn.")
            return None
        return [dict(source) for source in self.sources]  # type: ignore[attr-defined]

    def _build_detector(self):
        model = self.model_path.get().strip()  # type: ignore[attr-defined]
        if not model:
            messagebox.showwarning("Thiếu model", "Vui lòng nhập đường dẫn model.")
            return None
        try:
            from src.core.detector import FireSmokeDetector
            detector = FireSmokeDetector(
                model_path=model,
                conf=float(self.conf_threshold.get()),  # type: ignore[attr-defined]
                smoke_conf=float(self.smoke_conf_threshold.get()),  # type: ignore[attr-defined]
                alert_cooldown=float(self.alert_cooldown.get()),  # type: ignore[attr-defined]
                auto_save_alert=False,
                max_inference_size=640,
            )
            return detector
        except ImportError:
            from core.detector import FireSmokeDetector  # type: ignore[no-redef]
            detector = FireSmokeDetector(
                model_path=model,
                conf=float(self.conf_threshold.get()),  # type: ignore[attr-defined]
                smoke_conf=float(self.smoke_conf_threshold.get()),  # type: ignore[attr-defined]
                alert_cooldown=float(self.alert_cooldown.get()),  # type: ignore[attr-defined]
                auto_save_alert=False,
                max_inference_size=640,
            )
            return detector
        except Exception as exc:
            messagebox.showerror("Lỗi model", f"Không tải được model:\n{exc}")
            return None

    def _open_stream_capture(self, source_type: str, source_value: Any):
        if source_type == "camera":
            # Hỗ trợ cả index camera (vd 0, "1") và URL stream (rtsp://, http://)
            sv = str(source_value).strip()
            try:
                cam_arg: Any = int(sv)
            except (TypeError, ValueError):
                cam_arg = sv
            cap = cv2.VideoCapture(cam_arg)
            if cap is not None and cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap

        import os as _os
        video_path = _os.path.normpath(str(source_value))
        if not _os.path.exists(video_path):
            return None

        # Giảm rủi ro lỗi FFmpeg pthread async_lock trên một số máy/build OpenCV.
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "threads;1")

        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            return cap

        if hasattr(cv2, "CAP_FFMPEG"):
            cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
            if cap.isOpened():
                return cap

        return None

    @staticmethod
    def _merge_boxes(detections: List[Dict[str, Any]]) -> Optional[tuple]:
        if not detections:
            return None
        min_x = min(int(item["bbox"][0]) for item in detections)
        min_y = min(int(item["bbox"][1]) for item in detections)
        max_x = max(int(item["bbox"][2]) for item in detections)
        max_y = max(int(item["bbox"][3]) for item in detections)
        return (min_x, min_y, max_x, max_y)

    @staticmethod
    def _bbox_iou(a: Optional[tuple], b: Optional[tuple]) -> float:
        if a is None or b is None:
            return 0.0
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1); ih = max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _draw_single_alert_box(frame: Any, merged_box: Optional[tuple], labels_set: set, max_conf: float):
        """Legacy helper — vẫn dùng style mới nếu có detector, fallback đơn giản."""
        if merged_box is None or not labels_set:
            return frame

        x1, y1, x2, y2 = merged_box
        out = frame.copy()

        label = "fire" if "fire" in labels_set else "smoke"
        color      = (0, 100, 255) if label == "fire" else (180, 160, 100)
        fill_color = (0, 60, 200)  if label == "fire" else (120, 110, 70)

        # Semi-transparent fill
        overlay = out.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), fill_color, -1)
        cv2.addWeighted(overlay, 0.18, out, 0.82, 0, out)

        bw, bh = x2 - x1, y2 - y1
        corner_len = max(12, min(28, int(min(bw, bh) * 0.20)))
        corners = [
            [(x1, y1 + corner_len), (x1, y1), (x1 + corner_len, y1)],
            [(x2 - corner_len, y1), (x2, y1), (x2, y1 + corner_len)],
            [(x1, y2 - corner_len), (x1, y2), (x1 + corner_len, y2)],
            [(x2 - corner_len, y2), (x2, y2), (x2, y2 - corner_len)],
        ]
        for pts in corners:
            for i in range(len(pts) - 1):
                cv2.line(out, pts[i], pts[i + 1], color, 3, cv2.LINE_AA)

        tag_text = f"{'+'.join(sorted(l.upper() for l in labels_set))} {max_conf:.0%}"
        font = cv2.FONT_HERSHEY_DUPLEX
        (tw, th), _ = cv2.getTextSize(tag_text, font, 0.52, 1)
        pad = 5
        tag_y1 = max(0, y1 - th - pad * 2)
        cv2.rectangle(out, (x1, tag_y1), (min(out.shape[1], x1 + tw + pad * 2), y1), color, -1)
        cv2.putText(out, tag_text, (x1 + pad, y1 - pad + 1), font, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
        return out

    # ------------------------------------------------------------------ #
    #  Bắt đầu / dừng phát hiện                                           #
    # ------------------------------------------------------------------ #

    def start_detection(self, require_admin: bool = True):
        if require_admin and not self.admin_controller.ensure_admin("kết nối camera"):  # type: ignore[attr-defined]
            return

        if self.is_running:  # type: ignore[attr-defined]
            self._log("Tiến trình nhận diện đang chạy.")  # type: ignore[attr-defined]
            return

        sources = self._resolve_sources()
        if sources is None:
            return

        detector = self._build_detector()
        if detector is None:
            return

        self.detector = detector  # type: ignore[attr-defined]
        self.stop_event.clear()  # type: ignore[attr-defined]
        self.is_running = True  # type: ignore[attr-defined]
        self.last_alert_time = 0.0  # type: ignore[attr-defined]
        self.consecutive_detection_frames = 0  # type: ignore[attr-defined]
        self.latest_frames.clear()  # type: ignore[attr-defined]
        self.focused_tile_key = None  # type: ignore[attr-defined]
        self.active_session_id = None  # type: ignore[attr-defined]
        self._update_focus_state()
        self._set_status("Đang kết nối nguồn...")  # type: ignore[attr-defined]

        source_text = ", ".join(self._source_to_text(source) for source in sources)  # type: ignore[attr-defined]
        self.stat_source.set(f"{len(sources)} nguồn")  # type: ignore[attr-defined]
        self._ensure_video_tiles()  # type: ignore[attr-defined]
        self._log(f"Bắt đầu nhận diện với {len(sources)} nguồn: {source_text}")  # type: ignore[attr-defined]

        self.worker_thread = threading.Thread(  # type: ignore[attr-defined]
            target=self._run_detection_loop, args=(sources,), daemon=True,
        )
        self.worker_thread.start()  # type: ignore[attr-defined]
        self._show_page("connection")  # type: ignore[attr-defined]

    def stop_detection(self, require_admin: bool = True, on_stopped: Optional[Callable[[], None]] = None):
        if require_admin and not self.admin_controller.ensure_admin("ngắt camera"):  # type: ignore[attr-defined]
            return

        if not self.is_running:  # type: ignore[attr-defined]
            self._clear_video_tiles("Đã ngắt kết nối")  # type: ignore[attr-defined]
            self._set_status("Không có nguồn nào đang chạy")  # type: ignore[attr-defined]
            self._log("Yêu cầu ngắt: hiện không có nguồn đang chạy.")  # type: ignore[attr-defined]
            if on_stopped is not None:
                self.after(0, on_stopped)  # type: ignore[attr-defined]
            return

        self.stop_callback = on_stopped  # type: ignore[attr-defined]
        self.stop_event.set()  # type: ignore[attr-defined]
        self.is_running = False  # type: ignore[attr-defined]
        self._set_status("Đang dừng nhận diện...")  # type: ignore[attr-defined]
        self._release_stream_captures()
        self._clear_video_tiles("Đã ngắt kết nối")  # type: ignore[attr-defined]
        # Chờ worker thread thực sự kết thúc rồi mới finalize/restart
        # (tránh 2 thread chạy đồng thời gây đè frame lên nhau)
        if self.worker_thread and self.worker_thread.is_alive():  # type: ignore[attr-defined]
            self._schedule_stop_poll()
        else:
            self._finalize_stop_detection()

    def stop_all_streams(self):
        self.stop_detection(require_admin=False)

    # ------------------------------------------------------------------ #
    #  Quản lý dừng (poll / finalize)                                      #
    # ------------------------------------------------------------------ #

    def _schedule_stop_poll(self):
        if self.stop_poll_after_id is not None:  # type: ignore[attr-defined]
            try:
                self.after_cancel(self.stop_poll_after_id)  # type: ignore[attr-defined]
            except Exception:
                pass
        self.stop_poll_after_id = self.after(50, self._poll_stop_completion)  # type: ignore[attr-defined]

    def _poll_stop_completion(self):
        self.stop_poll_after_id = None  # type: ignore[attr-defined]
        if self.worker_thread and self.worker_thread.is_alive():  # type: ignore[attr-defined]
            self._schedule_stop_poll()
            return
        self._finalize_stop_detection()

    def _release_stream_captures(self):
        for stream in list(self.stream_states):  # type: ignore[attr-defined]
            cap = stream.get("cap")
            if cap is None:
                continue
            try:
                cap.release()
            except Exception:
                pass

    def _flush_ui_queue(self):
        # Clear latest frames dict
        with self._latest_ui_frames_lock:  # type: ignore[attr-defined]
            self._latest_ui_frames.clear()  # type: ignore[attr-defined]

        retained_logs: deque = deque()
        while True:
            try:
                event, payload = self.ui_queue.get_nowait()  # type: ignore[attr-defined]
            except queue.Empty:
                break
            if event == "log":
                retained_logs.append((event, payload))

        for item in retained_logs:
            try:
                self.ui_queue.put_nowait(item)  # type: ignore[attr-defined]
            except queue.Full:
                break

    def _finalize_stop_detection(self):
        if self.stop_poll_after_id is not None:  # type: ignore[attr-defined]
            try:
                self.after_cancel(self.stop_poll_after_id)  # type: ignore[attr-defined]
            except Exception:
                pass
            self.stop_poll_after_id = None  # type: ignore[attr-defined]
        self._flush_ui_queue()
        self.stream_states = []  # type: ignore[attr-defined]
        self.latest_frames.clear()  # type: ignore[attr-defined]
        self.focused_tile_key = None  # type: ignore[attr-defined]
        self._update_focus_state()
        self.worker_thread = None  # type: ignore[attr-defined]
        self._set_status("Đã dừng")  # type: ignore[attr-defined]
        self._log("Đã ngắt toàn bộ camera/video.")  # type: ignore[attr-defined]

        callback = self.stop_callback  # type: ignore[attr-defined]
        self.stop_callback = None  # type: ignore[attr-defined]
        if callback is not None:
            self.after(0, callback)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    #  Vòng lặp phát hiện (worker thread)                                  #
    # ------------------------------------------------------------------ #

    def _run_detection_loop(self, sources: List[Dict[str, Any]]):
        streams: List[Dict[str, Any]] = []
        all_streams: List[Dict[str, Any]] = []
        for source_idx, source in enumerate(sources):
            source_type = str(source.get("type", "camera"))
            source_value = source["value"]
            cap = self._open_stream_capture(source_type, source_value)
            if cap is None or not cap.isOpened():
                self.ui_queue.put(("log", f"Không mở được nguồn: {self._source_to_text(source)}"))  # type: ignore[attr-defined]
                continue

            if source_type == "camera":
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            stream_info: Dict[str, Any] = {
                "camera_id": source.get("id"),
                "tile_key": int(source.get("id")) if source.get("id") is not None else source_idx,
                "name": self._source_to_text(source),  # type: ignore[attr-defined]
                "type": source_type,
                "cap": cap,
                "source_value": source_value,
                "source_fps": cap.get(cv2.CAP_PROP_FPS) if source_type == "video" else 0.0,
                "playback_start": time.perf_counter(),
                "fail_reads": 0,
                "consecutive_detection_frames": 0,
                "last_alert_time": 0.0,
                "frame_index": 0,
                "processed_frames": 0,
                "fire_events": 0,
                "smoke_events": 0,
                "alert_events": 0,
                "active_labels": set(),
                "last_detection_ts": 0.0,
                "last_infer_perf": 0.0,
                "active_box": None,
                "active_conf": 0.0,
                "last_ui_push_perf": 0.0,
                "inference_future": None,
                "inference_frame": None,
                "frame_buffer": deque(maxlen=600),  # ~20 s pre-roll for video clip (đủ 15-20s)
                "video_writer": None,
                "video_frames_left": 0,
                "danger_level": "LOW",
                "display_fps": 0.0,
                "_display_fps_t": 0.0,
                "_display_fps_frames": 0,
            }
            streams.append(stream_info)
            all_streams.append(stream_info)

        if not streams:
            self.ui_queue.put(("status", "Kết nối nguồn thất bại"))  # type: ignore[attr-defined]
            self.is_running = False  # type: ignore[attr-defined]
            return

        # DataCollector được khởi tạo khi admin approve từ training tab (không tự động)
        self.data_collector = None  # type: ignore[attr-defined]
        
        self.stream_states = streams  # type: ignore[attr-defined]
        try:
            self.active_session_id = self.db.start_stream_session(  # type: ignore[attr-defined]
                started_by_user_id=int(self.admin_user["id"]) if self.admin_user is not None else None,  # type: ignore[attr-defined]
                total_sources=len(streams),
                model_path=self.model_path.get().strip(),  # type: ignore[attr-defined]
                conf_threshold=float(self.conf_threshold.get()),  # type: ignore[attr-defined]
                target_fps=int(self.target_fps.get()),  # type: ignore[attr-defined]
                inference_stride=int(self.inference_stride.get()),  # type: ignore[attr-defined]
            )
        except Exception as exc:
            self.active_session_id = None  # type: ignore[attr-defined]
            self.ui_queue.put(("log", f"Lỗi tạo phiên giám sát DB: {exc}"))  # type: ignore[attr-defined]

        self.ui_queue.put(("grid", None))  # type: ignore[attr-defined]
        self.ui_queue.put(("status", f"Đang chạy - {len(streams)} nguồn"))  # type: ignore[attr-defined]
        last_stats_emit = 0.0

        with ThreadPoolExecutor(max_workers=max(1, len(streams))) as _infer_pool:
            while not self.stop_event.is_set():  # type: ignore[attr-defined]
                cycle_start = time.perf_counter()
                processed_in_cycle = 0
                stats_emit_requested = False
                target_display_fps = int(self.target_fps.get())  # type: ignore[attr-defined]
                if target_display_fps <= 0:
                    target_display_fps = 24
                min_display_interval = 1.0 / max(5, min(60, target_display_fps))

                for stream in list(streams):
                    # ── 1. Collect completed inference result (non-blocking) ──
                    inf_future = stream.get("inference_future")
                    if inf_future is not None and inf_future.done():
                        stream["inference_future"] = None
                        try:
                            detections = inf_future.result()
                            labels_set = {str(item["label"]) for item in detections}
                            stream["active_box"] = self._merge_boxes(detections)
                            stream["active_conf"] = max(
                                (float(item["confidence"]) for item in detections), default=0.0
                            )
                            stream["processed_frames"] = int(stream.get("processed_frames", 0)) + 1
                            stream["active_labels"] = labels_set
                            stream["last_detection_ts"] = time.time()

                            # ── Thu thập dữ liệu khi admin approve ──────────────
                            if self.data_collection_enabled and self.data_collector is not None and len(detections) > 0 and stream.get("inference_frame") is not None:  # type: ignore[attr-defined]
                                try:
                                    inf_frame = stream["inference_frame"]
                                    detection_list = []
                                    for det in detections:
                                        bbox = det.get("bbox", (0, 0, 0, 0))
                                        detection_list.append({
                                            "class_id": int(det.get("class_id", 0)),
                                            "class_name": str(det.get("label", "unknown")),
                                            "conf": float(det.get("confidence", 0.0)),
                                            "x1": int(bbox[0]),
                                            "y1": int(bbox[1]),
                                            "x2": int(bbox[2]),
                                            "y2": int(bbox[3]),
                                        })
                                    
                                    self.data_collector.save_detection(  # type: ignore[attr-defined]
                                        frame=inf_frame,
                                        detections=detection_list,
                                        source_name=str(stream.get("name", "unknown")),
                                    )
                                except Exception as e:
                                    pass  # Silent fail

                            # ── Danger level ──────────────────────────────
                            inf_frame = stream.get("inference_frame")
                            if inf_frame is not None and len(detections) > 0:
                                fh, fw = inf_frame.shape[:2]
                                stream["danger_level"] = compute_danger_level(detections, fh, fw)
                            elif not labels_set:
                                stream["danger_level"] = "LOW"

                            self.total_frames += 1  # type: ignore[attr-defined]
                            if "fire" in labels_set:
                                self.fire_frames += 1  # type: ignore[attr-defined]
                                stream["fire_events"] = int(stream.get("fire_events", 0)) + 1
                            if "smoke" in labels_set:
                                self.smoke_frames += 1  # type: ignore[attr-defined]
                                stream["smoke_events"] = int(stream.get("smoke_events", 0)) + 1
                            stats_emit_requested = True

                            if labels_set:
                                stream["consecutive_detection_frames"] = int(stream.get("consecutive_detection_frames", 0)) + 1
                                stream["miss_frames"] = 0
                            else:
                                # Tạm thời cho phép 1 frame "trống" giữa chuỗi phát hiện
                                # (khói hay nhấp nháy) — chỉ reset khi quá 2 frame liên tiếp không có.
                                stream["miss_frames"] = int(stream.get("miss_frames", 0)) + 1
                                if int(stream.get("miss_frames", 0)) >= 2:
                                    stream["consecutive_detection_frames"] = 0

                            # Per-class consecutive (smoke khắt khe hơn để tránh nhầm sương/mờ cam)
                            if "fire" in labels_set:
                                stream["fire_consecutive"] = int(stream.get("fire_consecutive", 0)) + 1
                            else:
                                stream["fire_consecutive"] = 0
                            if "smoke" in labels_set:
                                # Kiểm tra liên tục về không gian: bbox khói hiện tại phải chồng lấn
                                # bbox khói lần trước (IoU ≥ 0.15). Sương/mờ cam thường nhảy ngẫu nhiên.
                                smoke_dets = [d for d in detections if str(d.get("label")) == "smoke"]
                                cur_smoke_bbox = self._merge_boxes(smoke_dets)
                                prev_smoke_bbox = stream.get("last_smoke_bbox")
                                iou = self._bbox_iou(cur_smoke_bbox, prev_smoke_bbox)
                                if prev_smoke_bbox is None or iou >= 0.15:
                                    stream["smoke_consecutive"] = int(stream.get("smoke_consecutive", 0)) + 1
                                else:
                                    # Vị trí khác hẳn → coi như khởi đầu chuỗi mới
                                    stream["smoke_consecutive"] = 1
                                stream["last_smoke_bbox"] = cur_smoke_bbox
                            else:
                                stream["smoke_consecutive"] = 0
                                stream["last_smoke_bbox"] = None

                            now_alert = time.time()
                            threshold = max(1, int(self.alert_frames.get()))  # type: ignore[attr-defined]
                            cooldown = max(0.1, float(self.alert_cooldown.get()))  # type: ignore[attr-defined]
                            # Fire → ngưỡng nhanh; smoke → cần nhiều hơn (x3) để giảm false-positive.
                            fire_ok = int(stream.get("fire_consecutive", 0)) >= threshold
                            smoke_ok = int(stream.get("smoke_consecutive", 0)) >= max(threshold, threshold * 3)
                            if (
                                (fire_ok or smoke_ok)
                                and (now_alert - float(stream.get("last_alert_time", 0.0))) >= cooldown
                            ):
                                alert_label = "fire" if fire_ok else "smoke"
                                danger_level = str(stream.get("danger_level") or "LOW")
                                self.alert_count += 1  # type: ignore[attr-defined]
                                stream["alert_events"] = int(stream.get("alert_events", 0)) + 1
                                stream["last_alert_time"] = now_alert
                                stream["consecutive_detection_frames"] = 0

                                saved_path = None
                                if self.auto_save_alert.get() and self.detector is not None and inf_frame is not None:  # type: ignore[attr-defined]
                                    saved_path = self.detector.save_alert_frame(inf_frame, alert_label)  # type: ignore[attr-defined]

                                # Tính trước đường dẫn video clip để lưu vào DB cùng lần (file sẽ được ghi ngay bên dưới)
                                video_clip_path: Optional[str] = None
                                if self.auto_save_alert.get() and stream.get("video_writer") is None:  # type: ignore[attr-defined]
                                    try:
                                        video_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        video_clip_path = os.path.join(
                                            "alerts", f"video_{alert_label}_{video_ts}.avi"
                                        )
                                    except Exception:
                                        video_clip_path = None

                                try:
                                    camera_id = stream.get("camera_id")
                                    self.db.add_detection(  # type: ignore[attr-defined]
                                        camera_id=int(camera_id) if camera_id is not None else None,
                                        class_name=alert_label,
                                        confidence=stream["active_conf"],
                                        image_path=saved_path,
                                        video_path=video_clip_path,
                                    )
                                except Exception as exc:
                                    self.ui_queue.put(("log", f"Lỗi ghi detections DB: {exc}"))  # type: ignore[attr-defined]

                                level_vi = {"LOW": "THẤP", "MEDIUM": "TRUNG BÌNH",
                                             "HIGH": "CAO", "CRITICAL": "NGUY HIỂM"}.get(danger_level, danger_level)
                                self.ui_queue.put(("log",  # type: ignore[attr-defined]
                                    f"🚨 CẢNH BÁO [{level_vi}]: {alert_label.upper()} ở {stream['name']}"))

                                # ── Tiered alert dispatch ──────────────────
                                try:
                                    self.ui_queue.put_nowait(("alert_popup", {  # type: ignore[attr-defined]
                                        "label": alert_label,
                                        "source_name": str(stream["name"]),
                                        "image_path": saved_path,
                                        "danger_level": danger_level,
                                        "confidence": float(stream.get("active_conf", 0.0)),
                                        "tile_key": stream["tile_key"],
                                    }))
                                except queue.Full:
                                    pass

                                if level_requires_sound(danger_level):
                                    try:
                                        self.ui_queue.put_nowait(("alert_sound", danger_level))  # type: ignore[attr-defined]
                                    except queue.Full:
                                        pass

                                if level_requires_email(danger_level):
                                    try:
                                        self.ui_queue.put_nowait(("alert_email", {  # type: ignore[attr-defined]
                                            "label": alert_label,
                                            "source_name": str(stream["name"]),
                                            "danger_level": danger_level,
                                            "image_path": saved_path,
                                        }))
                                    except queue.Full:
                                        pass

                                # Start video clip recording (pre-roll ~15-20s + 8s post-roll)
                                if self.auto_save_alert.get() and stream.get("video_writer") is None and video_clip_path:  # type: ignore[attr-defined]
                                    try:
                                        os.makedirs("alerts", exist_ok=True)
                                        vpath = video_clip_path
                                        _ref_frame = inf_frame if inf_frame is not None else frame
                                        h, w = _ref_frame.shape[:2]
                                        fps_v = float(max(10, target_display_fps))
                                        fourcc = cv2.VideoWriter_fourcc(*"XVID")
                                        writer = cv2.VideoWriter(vpath, fourcc, fps_v, (w, h))
                                        # Giới hạn pre-roll trong khoảng 20 giây gần nhất
                                        preroll_max = int(fps_v * 20)
                                        preroll = list(stream["frame_buffer"])[-preroll_max:]
                                        for bf in preroll:
                                            writer.write(bf)
                                        stream["video_writer"] = writer
                                        stream["video_frames_left"] = int(fps_v * 8)
                                    except Exception:
                                        pass

                                # Schedule alerts/ folder cleanup
                                try:
                                    self.ui_queue.put_nowait(("cleanup_alerts", None))  # type: ignore[attr-defined]
                                except queue.Full:
                                    pass

                        except Exception as exc:
                            self.ui_queue.put_nowait(("log", f"Lỗi xử lý kết quả inference: {exc}"))  # type: ignore[attr-defined]

                    # ── 2. Read next frame (no extra grab — buffersize=1 keeps it fresh) ──
                    cap = stream["cap"]
                    ok, frame = cap.read()

                    if not ok and stream["type"] == "video":
                        try:
                            cap.release()
                        except Exception:
                            pass
                        reopened_cap = self._open_stream_capture("video", stream.get("source_value"))
                        if reopened_cap is not None and reopened_cap.isOpened():
                            stream["cap"] = reopened_cap
                            cap = reopened_cap
                            stream["playback_start"] = time.perf_counter()
                            ok, frame = cap.read()
                    elif not ok and stream["type"] == "camera":
                        # Tự động kết nối lại camera/RTSP mỗi 30 frame fail (~1s).
                        fails = int(stream.get("fail_reads", 0))
                        if fails > 0 and fails % 30 == 0:
                            try:
                                cap.release()
                            except Exception:
                                pass
                            reopened_cap = self._open_stream_capture("camera", stream.get("source_value"))
                            if reopened_cap is not None and reopened_cap.isOpened():
                                stream["cap"] = reopened_cap
                                cap = reopened_cap
                                self.ui_queue.put(("log", f"Đã kết nối lại camera: {stream['name']}"))  # type: ignore[attr-defined]
                                ok, frame = cap.read()

                    if not ok:
                        stream["fail_reads"] = int(stream.get("fail_reads", 0)) + 1
                        if stream["type"] == "video" and stream["fail_reads"] >= 30:
                            self.ui_queue.put(("log", f"Nguồn video lỗi/không đọc được frame: {stream['name']}"))  # type: ignore[attr-defined]
                            cap.release()
                            streams.remove(stream)
                            self.ui_queue.put(("tile-message", (stream["tile_key"], "Mất kết nối")))  # type: ignore[attr-defined]
                        elif stream["type"] == "camera" and stream["fail_reads"] >= 90:
                            self.ui_queue.put(("log", f"Nguồn camera mất tín hiệu: {stream['name']}"))  # type: ignore[attr-defined]
                            cap.release()
                            streams.remove(stream)
                            self.ui_queue.put(("tile-message", (stream["tile_key"], "Mất tín hiệu")))  # type: ignore[attr-defined]
                        continue

                    stream["fail_reads"] = 0

                    # Buffer frame for video pre-roll
                    stream["frame_buffer"].append(frame)

                    if self.detector is None:  # type: ignore[attr-defined]
                        self.stop_event.set()  # type: ignore[attr-defined]
                        break

                    # ── 3. Submit inference to background thread (non-blocking) ──
                    stream["frame_index"] = int(stream.get("frame_index", 0)) + 1
                    stride = max(1, int(self.inference_stride.get()))  # type: ignore[attr-defined]
                    now_perf = time.perf_counter()
                    if (
                        (int(stream["frame_index"]) % stride) == 0
                        and stream.get("inference_future") is None
                        and (now_perf - float(stream.get("last_infer_perf") or 0.0)) >= self.background_detection_interval  # type: ignore[attr-defined]
                    ):
                        stream["last_infer_perf"] = now_perf
                        # Cập nhật ngưỡng theo thời gian thực (admin có thể chỉnh slider khi đang chạy)
                        try:
                            self.detector.conf = float(self.conf_threshold.get())  # type: ignore[attr-defined]
                            smoke_var = getattr(self, "smoke_conf_threshold", None)
                            if smoke_var is not None:
                                self.detector.smoke_conf = max(0.0, min(1.0, float(smoke_var.get())))
                        except Exception:
                            pass
                        frame_copy = frame.copy()
                        stream["inference_frame"] = frame_copy
                        stream["inference_future"] = _infer_pool.submit(
                            self.detector.detect_labels, frame_copy  # type: ignore[attr-defined]
                        )

                    # ── 4. Display current frame (rate-limited) ──
                    display_frame = frame
                    active_labels = set(stream.get("active_labels") or [])
                    last_detect_ts = float(stream.get("last_detection_ts") or 0.0)
                    show_alert_border = bool(active_labels and (time.time() - last_detect_ts) <= self.detection_icon_hold_seconds)  # type: ignore[attr-defined]

                    if show_alert_border:
                        display_frame = self._draw_single_alert_box(
                            frame,
                            stream.get("active_box"),
                            active_labels,
                            float(stream.get("active_conf") or 0.0),
                        )

                    now_perf = time.perf_counter()
                    last_ui_push = float(stream.get("last_ui_push_perf") or 0.0)

                    # Write to video recording if active (every frame regardless of rate-limit)
                    if stream.get("video_writer") is not None:
                        try:
                            stream["video_writer"].write(frame)
                            stream["video_frames_left"] = max(0, stream.get("video_frames_left", 0) - 1)
                            if stream["video_frames_left"] <= 0:
                                stream["video_writer"].release()
                                stream["video_writer"] = None
                        except Exception:
                            stream["video_writer"] = None

                    if (now_perf - last_ui_push) < min_display_interval:
                        continue
                    stream["last_ui_push_perf"] = now_perf

                    # Track per-stream display FPS
                    stream["_display_fps_frames"] = int(stream.get("_display_fps_frames") or 0) + 1
                    t0 = float(stream.get("_display_fps_t") or 0.0)
                    if t0 == 0.0:
                        stream["_display_fps_t"] = now_perf
                    elif (now_perf - t0) >= 1.0:
                        stream["display_fps"] = round(
                            stream["_display_fps_frames"] / (now_perf - t0), 1)
                        stream["_display_fps_frames"] = 0
                        stream["_display_fps_t"] = now_perf

                    with self._latest_ui_frames_lock:  # type: ignore[attr-defined]
                        self._latest_ui_frames[stream["tile_key"]] = (  # type: ignore[attr-defined]
                            stream["tile_key"],
                            str(stream["name"]),
                            display_frame,
                            active_labels if show_alert_border else set(),
                        )
                    processed_in_cycle += 1

                cycle_elapsed = max(time.perf_counter() - cycle_start, 1e-6)
                self.current_fps = processed_in_cycle / cycle_elapsed if processed_in_cycle > 0 else 0.0  # type: ignore[attr-defined]

                target = int(self.target_fps.get())  # type: ignore[attr-defined]
                if target > 0:
                    min_cycle = 1.0 / target
                    if cycle_elapsed < min_cycle:
                        time.sleep(min_cycle - cycle_elapsed)

                if stats_emit_requested and (time.perf_counter() - last_stats_emit) >= 0.25:
                    self._queue_stats_update()
                    last_stats_emit = time.perf_counter()

                if not streams:
                    self.ui_queue.put(("log", "Tất cả nguồn đã mất kết nối hoặc không đọc được frame."))  # type: ignore[attr-defined]
                    break

                if processed_in_cycle == 0:
                    time.sleep(0.005)

            # Cancel any pending inference futures before the executor shuts down
            for stream in streams:
                fut = stream.get("inference_future")
                if fut is not None:
                    fut.cancel()

        for stream in streams:
            stream["cap"].release()

        self._finalize_session_metrics(all_streams)
        self.stream_states = []  # type: ignore[attr-defined]
        self.is_running = False  # type: ignore[attr-defined]
        self.ui_queue.put(("status", "Đã dừng"))  # type: ignore[attr-defined]

    def _finalize_session_metrics(self, all_streams: List[Dict[str, Any]]):
        session_id = self.active_session_id  # type: ignore[attr-defined]
        if session_id is None:
            return
        try:
            for stream in all_streams:
                self.db.add_session_source_metric(  # type: ignore[attr-defined]
                    session_id=session_id,
                    camera_id=int(stream["camera_id"]) if stream.get("camera_id") is not None else None,
                    source_name=str(stream.get("name") or "-"),
                    source_type=str(stream.get("type") or "-"),
                    source_value=str(stream.get("source_value") or "-"),
                    processed_frames=int(stream.get("processed_frames") or 0),
                    fire_events=int(stream.get("fire_events") or 0),
                    smoke_events=int(stream.get("smoke_events") or 0),
                    alert_events=int(stream.get("alert_events") or 0),
                )
            final_status = "stopped" if self.stop_event.is_set() else "completed"  # type: ignore[attr-defined]
            self.db.end_stream_session(  # type: ignore[attr-defined]
                session_id=session_id,
                status=final_status,
                total_frames=int(self.total_frames),  # type: ignore[attr-defined]
                fire_frames=int(self.fire_frames),  # type: ignore[attr-defined]
                smoke_frames=int(self.smoke_frames),  # type: ignore[attr-defined]
                alert_count=int(self.alert_count),  # type: ignore[attr-defined]
                avg_fps=float(self.current_fps),  # type: ignore[attr-defined]
            )
        except Exception as exc:
            self.ui_queue.put(("log", f"Lỗi lưu metrics phiên giám sát: {exc}"))  # type: ignore[attr-defined]
        finally:
            self.active_session_id = None  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    #  UI Queue processing                                                 #
    # ------------------------------------------------------------------ #

    def _process_ui_queue(self):
        # Drain latest frames from the per-tile dict (always most-recent, no queue buildup)
        if not (self.stop_event.is_set() and not self.is_running):  # type: ignore[attr-defined]
            with self._latest_ui_frames_lock:  # type: ignore[attr-defined]
                frames_snapshot = dict(self._latest_ui_frames)  # type: ignore[attr-defined]
                self._latest_ui_frames.clear()  # type: ignore[attr-defined]
            video_tiles = getattr(self, "video_tiles", {})
            for tile_key, (stream_idx, stream_name, frame, active_labels) in frames_snapshot.items():
                # Bỏ qua nếu tile đã bị xóa/rebuild (tránh frame cũ đè lên tile mới)
                if tile_key not in video_tiles:
                    continue
                self._update_video(stream_idx, stream_name, frame, active_labels)  # type: ignore[attr-defined]

        # Drain non-frame events from queue
        try:
            while True:
                event, payload = self.ui_queue.get_nowait()  # type: ignore[attr-defined]
                if event == "log":
                    self._log(payload)  # type: ignore[attr-defined]
                elif event == "status":
                    self._set_status(payload)  # type: ignore[attr-defined]
                elif event == "stats":
                    self._update_stats_display()  # type: ignore[attr-defined]
                elif event == "grid":
                    self._ensure_video_tiles()  # type: ignore[attr-defined]
                elif event == "tile-message":
                    tile_key, message = payload
                    self._set_tile_message(tile_key, message)  # type: ignore[attr-defined]
                elif event == "alert_popup":
                    if hasattr(self, "_show_alert_popup"):
                        self._show_alert_popup(payload)  # type: ignore[attr-defined]
                elif event == "alert_sound":
                    if hasattr(self, "_play_alert_sound"):
                        self._play_alert_sound(payload)  # type: ignore[attr-defined]
                elif event == "alert_email":
                    if hasattr(self, "_send_alert_email"):
                        self._send_alert_email(payload)  # type: ignore[attr-defined]
                elif event == "cleanup_alerts":
                    if hasattr(self, "_cleanup_alerts_folder"):
                        threading.Thread(target=self._cleanup_alerts_folder, daemon=True).start()  # type: ignore[attr-defined]
        except queue.Empty:
            pass

        self.after(16, self._process_ui_queue)  # type: ignore[attr-defined]

    def _queue_stats_update(self):
        if self.ui_queue.full():  # type: ignore[attr-defined]
            retained_items = []
            while True:
                try:
                    item = self.ui_queue.get_nowait()  # type: ignore[attr-defined]
                except queue.Empty:
                    break
                if item[0] != "stats":
                    retained_items.append(item)
            for item in retained_items:
                try:
                    self.ui_queue.put_nowait(item)  # type: ignore[attr-defined]
                except queue.Full:
                    break
        try:
            self.ui_queue.put_nowait(("stats", None))  # type: ignore[attr-defined]
        except queue.Full:
            pass

    # ------------------------------------------------------------------ #
    #  Restart / focus                                                     #
    # ------------------------------------------------------------------ #

    def _restart_monitoring(self):
        if self.is_running:  # type: ignore[attr-defined]
            self.stop_detection(require_admin=False, on_stopped=lambda: self.start_detection(require_admin=False))
            return

        if self.focused_tile_key is None:  # type: ignore[attr-defined]
            return
        self.focused_tile_key = None  # type: ignore[attr-defined]
        self._update_focus_state()
        self._ensure_video_tiles(force=True)  # type: ignore[attr-defined]
        self._redraw_all_tiles()  # type: ignore[attr-defined]

    def _update_focus_state(self):
        if hasattr(self, "restore_layout_button"):
            self.restore_layout_button.configure(state="normal")  # type: ignore[attr-defined]
