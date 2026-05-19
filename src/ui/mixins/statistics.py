"""
src/ui/mixins/statistics.py
StatsMixin - hiển thị, vẽ biểu đồ và xuất thống kê phát hiện.
"""
import csv
import os
import time
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Optional

from matplotlib.figure import Figure
try:
    from matplotlib.backends.backend_pdf import PdfPages, FigureCanvasPdf as _FigureCanvasPdf
except ImportError:
    try:
        from matplotlib.backends.backend_pdf import PdfPages
        from matplotlib.backends.backend_agg import FigureCanvasAgg as _FigureCanvasPdf  # type: ignore[assignment]
    except ImportError:
        PdfPages = None  # type: ignore[assignment,misc]
        _FigureCanvasPdf = None  # type: ignore[assignment]


class StatsMixin:
    """Mixin xử lý tổng hợp, hiển thị và xuất thống kê phát hiện lửa/khói."""

    # ------------------------------------------------------------------ #
    #  Cập nhật thống kê tổng quan                                         #
    # ------------------------------------------------------------------ #

    def _update_stats_display(self, force_visual_refresh: bool = False, force_table_refresh: bool = False):
        self._refresh_db_totals(force=force_visual_refresh or force_table_refresh)
        self.stat_total.set(str(self.total_frames))  # type: ignore[attr-defined]
        self.stat_fire.set(str(self.db_fire_total))  # type: ignore[attr-defined]
        self.stat_smoke.set(str(self.db_smoke_total))  # type: ignore[attr-defined]
        self.stat_alert.set(str(self.db_total_events))  # type: ignore[attr-defined]
        self.stat_fps.set(f"{self.current_fps:.1f}")  # type: ignore[attr-defined]
        self._refresh_stats_overview()

        if self.current_page != "stats" and not force_visual_refresh and not force_table_refresh:  # type: ignore[attr-defined]
            return

        now = time.perf_counter()
        should_refresh_visuals = force_visual_refresh or (now - self.last_stats_visual_refresh) >= 0.75  # type: ignore[attr-defined]
        should_refresh_tables = force_table_refresh or (now - self.last_stats_table_refresh) >= 1.5  # type: ignore[attr-defined]

        if should_refresh_visuals:
            self._render_stats_charts()
            self.last_stats_visual_refresh = now  # type: ignore[attr-defined]

        if should_refresh_tables:
            self._refresh_stats_tables()
            self._refresh_risk_level()
            self.last_stats_table_refresh = now  # type: ignore[attr-defined]

    def _refresh_db_totals(self, force: bool = False):
        now = time.perf_counter()
        if not force and (now - self.last_db_totals_refresh) < 1.5:  # type: ignore[attr-defined]
            return
        totals = self.db.get_detection_totals()  # type: ignore[attr-defined]
        self.db_total_events = int(totals.get("total_events") or 0)  # type: ignore[attr-defined]
        self.db_fire_total = int(totals.get("fire_total") or 0)  # type: ignore[attr-defined]
        self.db_smoke_total = int(totals.get("smoke_total") or 0)  # type: ignore[attr-defined]
        self.db_today_total = int(totals.get("today_total") or 0)  # type: ignore[attr-defined]
        self.last_db_totals_refresh = now  # type: ignore[attr-defined]

    def _reset_statistics(self):
        self.total_frames = 0  # type: ignore[attr-defined]
        self.fire_frames = 0  # type: ignore[attr-defined]
        self.smoke_frames = 0  # type: ignore[attr-defined]
        self.alert_count = 0  # type: ignore[attr-defined]
        self.current_fps = 0.0  # type: ignore[attr-defined]
        self.consecutive_detection_frames = 0  # type: ignore[attr-defined]
        self._update_stats_display(force_visual_refresh=True, force_table_refresh=True)
        self._log("Đã đặt lại thống kê.")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    #  Đánh giá mức độ rủi ro cháy                                         #
    # ------------------------------------------------------------------ #

    def _compute_fire_risk(self):
        """Tính mức độ rủi ro dựa trên tần suất và độ tin cậy phát hiện gần nhất.
        Trả về (label, color, description).
        """
        try:
            recent = self.db.get_recent_hour_detections(hours=1)  # type: ignore[attr-defined]
        except Exception:
            return "KHÔNG XÁC ĐỊNH", "#9ba4b4", "Không thể lấy dữ liệu rủi ro."

        fire_1h   = int(recent.get("fire_count") or 0)
        smoke_1h  = int(recent.get("smoke_count") or 0)
        total_1h  = int(recent.get("total_count") or 0)
        avg_conf  = float(recent.get("avg_confidence") or 0.0)
        max_f_conf = float(recent.get("max_fire_conf") or 0.0)

        fire_ratio = fire_1h / total_1h if total_1h > 0 else 0.0

        if total_1h == 0:
            return "AN TOÀN", "#22c55e", "Không ghi nhận sự kiện nào trong 1 giờ qua."

        if fire_1h >= 10 or (fire_1h >= 5 and max_f_conf >= 0.75):
            label = "CỰC NGUY HIỂM"
            color = "#ef4444"
            desc  = (f"Cảnh báo khẩn: {fire_1h} sự kiện cháy trong 1h, "
                     f"độ tin cậy tối đa {max_f_conf:.0%}. Cần ứng phó ngay!")
        elif fire_1h >= 4 or (fire_ratio >= 0.5 and avg_conf >= 0.6):
            label = "NGUY HIỂM"
            color = "#f97316"
            desc  = (f"{fire_1h} sự kiện cháy / {smoke_1h} khói trong 1h. "
                     f"Tỷ lệ lửa {fire_ratio:.0%}. Cần kiểm tra ngay.")
        elif fire_1h >= 2 or fire_ratio >= 0.3:
            label = "CẢNH BÁO"
            color = "#fbbf24"
            desc  = (f"{fire_1h} lửa, {smoke_1h} khói trong 1h. "
                     f"Mức tin cậy trung bình {avg_conf:.0%}. Theo dõi sát.")
        elif total_1h >= 1:
            label = "THEO DÕI"
            color = "#38bdf8"
            desc  = (f"Phát hiện {smoke_1h} khói trong 1h. "
                     f"Mức độ thấp, tiếp tục theo dõi.")
        else:
            label = "AN TOÀN"
            color = "#22c55e"
            desc  = "Không ghi nhận sự kiện nào trong 1 giờ qua."

        return label, color, desc

    def _refresh_risk_level(self):
        label, color, _desc = self._compute_fire_risk()
        self.stat_risk.set(label)  # type: ignore[attr-defined]
        if self.risk_level_value_label is not None:  # type: ignore[attr-defined]
            try:
                self.risk_level_value_label.configure(fg=color)  # type: ignore[attr-defined]
            except Exception:
                pass
        # Update monitor page risk label color too
        monitor_risk = getattr(self, "monitor_risk_label", None)
        if monitor_risk is not None:
            try:
                monitor_risk.configure(fg=color)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  Tổng quan nhanh                                                     #
    # ------------------------------------------------------------------ #

    def _refresh_stats_overview(self):
        total_detected = self.db_fire_total + self.db_smoke_total  # type: ignore[attr-defined]
        if total_detected <= 0:
            self.stats_overview_text.set(  # type: ignore[attr-defined]
                "Chưa có dữ liệu phát hiện. Hãy bật giám sát để bắt đầu ghi nhận cháy và khói."
            )
            return

        dominant_label = "cháy" if self.db_fire_total >= self.db_smoke_total else "khói"  # type: ignore[attr-defined]
        dominant_count = max(self.db_fire_total, self.db_smoke_total)  # type: ignore[attr-defined]
        dominant_ratio = dominant_count / total_detected * 100.0

        # Lấy thêm dữ liệu confidence và giờ cao điểm
        try:
            conf_rows = self.db.get_avg_confidence_by_class()  # type: ignore[attr-defined]
            conf_info_parts = []
            for row in conf_rows:
                cn = "Cháy" if str(row.get("class_name")) == "fire" else "Khói"
                avg_c = row.get("avg_confidence")
                if avg_c is not None:
                    conf_info_parts.append(f"{cn}: {float(avg_c):.0%}")
            conf_info = "  |  Độ tin cậy TB — " + ", ".join(conf_info_parts) if conf_info_parts else ""

            peak = self.db.get_peak_detection_hour()  # type: ignore[attr-defined]
            peak_info = f"  |  Giờ cao điểm: {peak['hour_label']}" if peak.get("hour_label") else ""
        except Exception:
            conf_info = ""
            peak_info = ""

        _risk_label, _risk_color, risk_desc = self._compute_fire_risk()

        self.stats_overview_text.set(  # type: ignore[attr-defined]
            f"Tổng sự kiện: {self.db_total_events}  |  Hôm nay: {self.db_today_total}  |  "  # type: ignore[attr-defined]
            f"Loại xuất hiện nhiều hơn: {dominant_label} ({dominant_ratio:.1f}%){conf_info}{peak_info}\n"
            f"Đánh giá rủi ro hiện tại: {risk_desc}"
        )

    # ------------------------------------------------------------------ #
    #  Bảng dữ liệu                                                        #
    # ------------------------------------------------------------------ #

    def _refresh_stats_tables(self):
        if self.source_stats_tree is not None:  # type: ignore[attr-defined]
            for item in self.source_stats_tree.get_children():  # type: ignore[attr-defined]
                self.source_stats_tree.delete(item)  # type: ignore[attr-defined]
            for index, row in enumerate(self.db.get_detection_summary_by_source(), start=1):  # type: ignore[attr-defined]
                total_count = int(row.get("total_count") or 0)
                fire_count = int(row.get("fire_count") or 0)
                smoke_count = int(row.get("smoke_count") or 0)
                fire_ratio = (fire_count / total_count * 100.0) if total_count > 0 else 0.0
                self.source_stats_tree.insert(  # type: ignore[attr-defined]
                    "", "end",
                    values=(
                        index,
                        row.get("source_name") or "-",
                        row.get("location") or "-",
                        fire_count, smoke_count, total_count,
                        f"{fire_ratio:.1f}%",
                    ),
                )

        if self.class_stats_tree is not None:  # type: ignore[attr-defined]
            for item in self.class_stats_tree.get_children():  # type: ignore[attr-defined]
                self.class_stats_tree.delete(item)  # type: ignore[attr-defined]
            conf_rows = self.db.get_avg_confidence_by_class()  # type: ignore[attr-defined]
            grand_total = sum(int(row.get("total_count") or 0) for row in conf_rows)
            for row in conf_rows:
                total_count = int(row.get("total_count") or 0)
                ratio = (total_count / grand_total * 100.0) if grand_total > 0 else 0.0
                class_name = str(row.get("class_name"))
                label = "Cháy" if class_name == "fire" else "Khói"
                avg_c = row.get("avg_confidence")
                max_c = row.get("max_confidence")
                avg_conf_str = f"{float(avg_c):.0%}" if avg_c is not None else "-"
                max_conf_str = f"{float(max_c):.0%}" if max_c is not None else "-"
                # Mức rủi ro theo class + max confidence
                mc = float(max_c) if max_c is not None else 0.0
                if class_name == "fire":
                    if total_count >= 10 or mc >= 0.75:
                        risk_label = "NGUY HIỂM"
                    elif mc >= 0.50 or total_count >= 3:
                        risk_label = "CẢNH BÁO"
                    else:
                        risk_label = "THEO DÕI"
                else:
                    risk_label = "CẢNH BÁO" if total_count >= 5 else "THEO DÕI"
                self.class_stats_tree.insert(  # type: ignore[attr-defined]
                    "", "end",
                    values=(label, total_count, f"{ratio:.1f}%", avg_conf_str, max_conf_str, risk_label),
                )

        if self.recent_stats_tree is not None:  # type: ignore[attr-defined]
            for item in self.recent_stats_tree.get_children():  # type: ignore[attr-defined]
                self.recent_stats_tree.delete(item)  # type: ignore[attr-defined]
            for row in self.db.get_recent_detections(limit=12):  # type: ignore[attr-defined]
                label = "Cháy" if str(row.get("class_name")) == "fire" else "Khói"
                conf = row.get("confidence")
                conf_str = f"{float(conf):.0%}" if conf is not None else "-"
                self.recent_stats_tree.insert(  # type: ignore[attr-defined]
                    "", "end",
                    values=(str(row.get("timestamp") or "-"), str(row.get("source_name") or "-"), label, conf_str),
                )

        if self.hourly_stats_tree is not None:  # type: ignore[attr-defined]
            for item in self.hourly_stats_tree.get_children():  # type: ignore[attr-defined]
                self.hourly_stats_tree.delete(item)  # type: ignore[attr-defined]
            for row in self.db.get_detection_summary_by_hour(hours=24):  # type: ignore[attr-defined]
                self.hourly_stats_tree.insert(  # type: ignore[attr-defined]
                    "", "end",
                    values=(
                        str(row.get("time_bucket") or "-"),
                        int(row.get("fire_count") or 0),
                        int(row.get("smoke_count") or 0),
                        int(row.get("total_count") or 0),
                    ),
                )

        if self.daily_stats_tree is not None:  # type: ignore[attr-defined]
            for item in self.daily_stats_tree.get_children():  # type: ignore[attr-defined]
                self.daily_stats_tree.delete(item)  # type: ignore[attr-defined]
            for row in self.db.get_detection_summary_by_day(days=7):  # type: ignore[attr-defined]
                self.daily_stats_tree.insert(  # type: ignore[attr-defined]
                    "", "end",
                    values=(
                        str(row.get("day_bucket") or "-"),
                        int(row.get("fire_count") or 0),
                        int(row.get("smoke_count") or 0),
                        int(row.get("total_count") or 0),
                    ),
                )

    # ------------------------------------------------------------------ #
    #  Biểu đồ                                                             #
    # ------------------------------------------------------------------ #

    def _render_stats_charts(self):
        if self.stats_ratio_axes is None or self.stats_ratio_canvas is None:  # type: ignore[attr-defined]
            return

        self.stats_ratio_axes.clear()  # type: ignore[attr-defined]
        fire_total = max(0, self.db_fire_total)  # type: ignore[attr-defined]
        smoke_total = max(0, self.db_smoke_total)  # type: ignore[attr-defined]
        total_detected = fire_total + smoke_total

        if total_detected == 0:
            self.stats_ratio_axes.text(0.5, 0.5, "Chưa có dữ liệu", ha="center", va="center", fontsize=11)  # type: ignore[attr-defined]
            self.stats_ratio_axes.set_axis_off()  # type: ignore[attr-defined]
        else:
            values = [fire_total, smoke_total]
            labels = ["Cháy", "Khói"]
            colors = ["#e53935", "#546e7a"]
            self.stats_ratio_axes.pie(  # type: ignore[attr-defined]
                values, labels=labels, colors=colors,
                autopct=lambda pct: f"{pct:.1f}%" if pct > 0 else "",
                startangle=90, wedgeprops={"linewidth": 1, "edgecolor": "white"},
            )
            self.stats_ratio_axes.set_title("Tỷ lệ xuất hiện cháy/khói", fontsize=11)  # type: ignore[attr-defined]
            self.stats_ratio_axes.axis("equal")  # type: ignore[attr-defined]

        self.stats_ratio_figure.tight_layout()  # type: ignore[attr-defined]
        self.stats_ratio_canvas.draw_idle()  # type: ignore[attr-defined]

        if self.stats_source_axes is None or self.stats_source_canvas is None:  # type: ignore[attr-defined]
            return

        self.stats_source_axes.clear()  # type: ignore[attr-defined]
        source_rows = self.db.get_detection_summary_by_source()  # type: ignore[attr-defined]
        labels = [str(row.get("source_name") or "-") for row in source_rows]
        totals = [int(row.get("total_count") or 0) for row in source_rows]

        if not labels or sum(totals) == 0:
            self.stats_source_axes.text(0.5, 0.5, "Chưa có dữ liệu", ha="center", va="center", fontsize=11)  # type: ignore[attr-defined]
            self.stats_source_axes.set_axis_off()  # type: ignore[attr-defined]
        else:
            x_positions = list(range(len(labels)))
            self.stats_source_axes.bar(x_positions, totals, color="#1e88e5")  # type: ignore[attr-defined]
            self.stats_source_axes.set_title("Số lần phát hiện theo nguồn", fontsize=11)  # type: ignore[attr-defined]
            self.stats_source_axes.set_ylabel("Số lần")  # type: ignore[attr-defined]
            self.stats_source_axes.set_xticks(x_positions)  # type: ignore[attr-defined]
            self.stats_source_axes.set_xticklabels(labels, rotation=20, ha="right")  # type: ignore[attr-defined]

        self.stats_source_figure.tight_layout()  # type: ignore[attr-defined]
        self.stats_source_canvas.draw_idle()  # type: ignore[attr-defined]

        # ── Biểu đồ xu hướng theo giờ ──────────────────────────────────
        if self.stats_trend_axes is None or self.stats_trend_canvas is None:  # type: ignore[attr-defined]
            return

        self.stats_trend_axes.clear()  # type: ignore[attr-defined]
        hourly_rows = self.db.get_detection_summary_by_hour(hours=24)  # type: ignore[attr-defined]

        if not hourly_rows:
            self.stats_trend_axes.text(0.5, 0.5, "Chưa có dữ liệu 24h", ha="center", va="center", fontsize=11)  # type: ignore[attr-defined]
            self.stats_trend_axes.set_axis_off()  # type: ignore[attr-defined]
        else:
            hourly_rows_sorted = sorted(hourly_rows, key=lambda r: str(r.get("time_bucket") or ""))
            x_labels = [str(r.get("time_bucket") or "")[-5:] for r in hourly_rows_sorted]  # HH:00
            fire_vals  = [int(r.get("fire_count") or 0) for r in hourly_rows_sorted]
            smoke_vals = [int(r.get("smoke_count") or 0) for r in hourly_rows_sorted]
            x_pos = list(range(len(x_labels)))

            ax = self.stats_trend_axes  # type: ignore[attr-defined]
            ax.plot(x_pos, fire_vals,  color="#e53935", linewidth=2, marker="o", markersize=4, label="Cháy")
            ax.plot(x_pos, smoke_vals, color="#546e7a", linewidth=2, marker="s", markersize=4, label="Khói")
            ax.fill_between(x_pos, fire_vals,  alpha=0.15, color="#e53935")
            ax.fill_between(x_pos, smoke_vals, alpha=0.12, color="#546e7a")
            ax.set_xticks(x_pos)
            ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=7)
            ax.set_ylabel("Số lần", fontsize=8)
            ax.set_title("Số lần phát hiện theo giờ (24h gần nhất)", fontsize=9)
            ax.legend(facecolor="#1d212e", labelcolor="#f5f7fb", fontsize=8)
            ax.tick_params(colors="#9ba4b4")
            for sp in ax.spines.values():
                sp.set_color("#2b3047")

        self.stats_trend_figure.tight_layout()  # type: ignore[attr-defined]
        self.stats_trend_canvas.draw_idle()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    #  Xuất CSV                                                            #
    # ------------------------------------------------------------------ #

    def export_statistics_csv(self):
        self._refresh_db_totals(force=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"thong_ke_{timestamp}.csv"
        file_path = filedialog.asksaveasfilename(
            title="Xuất thống kê ra CSV",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("Tệp CSV", "*.csv"), ("Tất cả", "*.*")],
        )
        if not file_path:
            return

        rows = [
            ["chỉ_số", "giá_trị"],
            ["thời_gian", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["số_nguồn", str(len(self.sources))],  # type: ignore[attr-defined]
            ["đường_dẫn_model", self.model_path.get()],  # type: ignore[attr-defined]
            ["ngưỡng_tin_cậy", f"{self.conf_threshold.get():.2f}"],  # type: ignore[attr-defined]
            ["fps_mục_tiêu", str(self.target_fps.get())],  # type: ignore[attr-defined]
            ["nhịp_nhận_diện", str(self.inference_stride.get())],  # type: ignore[attr-defined]
            ["số_frame_cảnh_báo", str(self.alert_frames.get())],  # type: ignore[attr-defined]
            ["cooldown_cảnh_báo_giây", f"{self.alert_cooldown.get():.1f}"],  # type: ignore[attr-defined]
            ["tự_động_lưu_ảnh", str(self.auto_save_alert.get())],  # type: ignore[attr-defined]
            ["tổng_frame", str(self.total_frames)],  # type: ignore[attr-defined]
            ["fps_thực_tế", f"{self.current_fps:.1f}"],  # type: ignore[attr-defined]
            ["sự_kiện_cháy", str(self.db_fire_total)],  # type: ignore[attr-defined]
            ["sự_kiện_khói", str(self.db_smoke_total)],  # type: ignore[attr-defined]
            ["tổng_sự_kiện", str(self.db_total_events)],  # type: ignore[attr-defined]
            ["sự_kiện_hôm_nay", str(self.db_today_total)],  # type: ignore[attr-defined]
        ]

        # Mức độ rủi ro
        try:
            risk_label, _c, risk_desc = self._compute_fire_risk()
            rows.append(["mức_độ_rủi_ro", risk_label])
            rows.append(["mô_tả_rủi_ro", risk_desc])
        except Exception:
            pass

        # Confidence theo loại
        try:
            conf_rows = self.db.get_avg_confidence_by_class()  # type: ignore[attr-defined]
            for row in conf_rows:
                cn = row.get("class_name", "")
                rows.append([f"tb_conf_{cn}", f"{float(row.get('avg_confidence') or 0):.4f}"])
                rows.append([f"max_conf_{cn}", f"{float(row.get('max_confidence') or 0):.4f}"])
        except Exception:
            pass

        for idx, source in enumerate(self.sources, start=1):  # type: ignore[attr-defined]
            rows.append([f"nguồn_{idx}", f"{source['type']}:{source['value']}"])

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerows(rows)
            self._log(f"Đã xuất thống kê CSV: {file_path}")  # type: ignore[attr-defined]
            self._set_status("Xuất CSV thành công")  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Lỗi xuất file", f"Không thể xuất CSV:\n{exc}")
            self._log(f"Xuất CSV thất bại: {exc}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    #  Xuất PDF                                                            #
    # ------------------------------------------------------------------ #

    def export_statistics_pdf(self):
        if PdfPages is None or _FigureCanvasPdf is None:
            messagebox.showerror("Thiếu thư viện", "Không tìm thấy matplotlib PDF backend.\npip install matplotlib")
            return
        self._refresh_db_totals(force=True)  # type: ignore[attr-defined]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"bao_cao_{timestamp}.pdf"
        file_path = filedialog.asksaveasfilename(
            title="Xuất báo cáo PDF",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("Tệp PDF", "*.pdf"), ("Tất cả", "*.*")],
        )
        if not file_path:
            return

        DARK    = "#1d212e"
        DARKER  = "#11141d"
        MUTED   = "#9ba4b4"
        PRIMARY = "#f5f7fb"
        RED     = "#f04e1a"
        ORANGE  = "#fbbf24"
        SLATE   = "#546e7a"
        BORDER_C = "#2b3047"

        def _make_fig() -> Figure:
            fig = Figure(figsize=(8.27, 11.69))  # A4 portrait
            _FigureCanvasPdf(fig)  # attach PDF canvas so savefig works
            fig.patch.set_facecolor(DARK)
            return fig

        def _blank_ax(fig, rect):
            ax = fig.add_axes(rect)
            ax.set_facecolor(DARK)
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(BORDER_C)
            return ax

        def _page_footer(fig, page_num, total_pages):
            fig.text(0.5, 0.015,
                     f"FireGuard — Trang {page_num}/{total_pages} — "
                     f"Tạo lúc {datetime.now().strftime('%H:%M:%S  %d/%m/%Y')}",
                     ha="center", fontsize=7, color=MUTED)

        def _draw_table_ax(ax, cols, data, title=""):
            if title:
                ax.text(0.0, 1.04, title, ha="left", fontsize=9,
                        fontweight="bold", color=MUTED, transform=ax.transAxes)
            if not data:
                ax.text(0.5, 0.5, "Chưa có dữ liệu", ha="center", va="center",
                        color=MUTED, transform=ax.transAxes)
                return
            tbl = ax.table(cellText=data, colLabels=cols,
                           loc="upper center", cellLoc="center")
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(8)
            tbl.scale(1, 1.5)
            for (r, c), cell in tbl.get_celld().items():
                cell.set_facecolor(DARKER if r > 0 else "#2a3047")
                cell.set_text_props(color=PRIMARY if r > 0 else MUTED)
                cell.set_edgecolor(BORDER_C)

        try:
            with PdfPages(file_path) as pdf:
                # ── Page 1: Overview ──────────────────────────────────────────
                fig1 = _make_fig()

                ax_hdr = fig1.add_axes([0.0, 0.88, 1.0, 0.12])
                ax_hdr.set_facecolor(RED)
                ax_hdr.set_xticks([])
                ax_hdr.set_yticks([])
                for sp in ax_hdr.spines.values():
                    sp.set_visible(False)
                ax_hdr.text(0.5, 0.65, "BÁO CÁO GIÁM SÁT LỬA & KHÓI",
                            ha="center", va="center", fontsize=18,
                            fontweight="bold", color="white",
                            transform=ax_hdr.transAxes)
                ax_hdr.text(0.5, 0.22,
                            f"FireGuard  —  Xuất ngày {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                            ha="center", va="center", fontsize=9,
                            color="white", alpha=0.85, transform=ax_hdr.transAxes)

                # System info
                ax_info = _blank_ax(fig1, [0.05, 0.74, 0.9, 0.12])
                try:
                    model_v   = str(self.model_path.get())  # type: ignore[attr-defined]
                    conf_v    = f"{float(self.conf_threshold.get()):.2f}"  # type: ignore[attr-defined]
                    fps_v     = str(self.target_fps.get())  # type: ignore[attr-defined]
                    stride_v  = str(self.inference_stride.get())  # type: ignore[attr-defined]
                    src_count = str(len(self.sources))  # type: ignore[attr-defined]
                    fps_real  = f"{float(self.current_fps):.1f}"  # type: ignore[attr-defined]
                    cooldown_v = f"{float(self.alert_cooldown.get()):.1f}s"  # type: ignore[attr-defined]
                except Exception:
                    model_v = conf_v = fps_v = stride_v = src_count = fps_real = cooldown_v = "-"

                info_lines = [
                    f"Model: {model_v}",
                    f"Ngưỡng tin cậy: {conf_v}   FPS mục tiêu: {fps_v}   Nhịp nhận diện: {stride_v}",
                    f"Số nguồn: {src_count}   FPS thực tế: {fps_real}   Cooldown: {cooldown_v}",
                ]
                for i, line in enumerate(info_lines):
                    ax_info.text(0.02, 0.80 - i * 0.28, line, ha="left", va="center",
                                 fontsize=9, color=PRIMARY, transform=ax_info.transAxes)

                # Stat cards
                risk_label, risk_color, risk_desc = self._compute_fire_risk()
                stat_data = [
                    ("TỔNG SỰ KIỆN",  str(self.db_total_events), RED),   # type: ignore[attr-defined]
                    ("SỰ KIỆN LỬA",   str(self.db_fire_total),   "#e53935"),  # type: ignore[attr-defined]
                    ("SỰ KIỆN KHÓI",  str(self.db_smoke_total),  SLATE),  # type: ignore[attr-defined]
                    ("HÔM NAY",       str(self.db_today_total),  ORANGE),  # type: ignore[attr-defined]
                    ("MỨC ĐỘ RỦI RO", risk_label,               risk_color),
                ]
                card_w = 0.155
                for i, (lbl, val, color) in enumerate(stat_data):
                    x = 0.04 + i * (card_w + 0.025)
                    ax_c = _blank_ax(fig1, [x, 0.60, card_w, 0.12])
                    ax_c.set_facecolor(color)
                    for sp in ax_c.spines.values():
                        sp.set_visible(False)
                    ax_c.text(0.5, 0.72, val, ha="center", va="center",
                              fontsize=18 if len(val) > 8 else 22, fontweight="bold", color="white",
                              transform=ax_c.transAxes)
                    ax_c.text(0.5, 0.22, lbl, ha="center", va="center",
                              fontsize=7, color="white", alpha=0.9,
                              transform=ax_c.transAxes)

                # Source stats table
                source_rows = self.db.get_detection_summary_by_source()  # type: ignore[attr-defined]

                # Risk assessment text block
                ax_risk = _blank_ax(fig1, [0.05, 0.53, 0.9, 0.06])
                ax_risk.set_facecolor("#2a3047")
                for sp in ax_risk.spines.values():
                    sp.set_color(BORDER_C)
                ax_risk.text(0.01, 0.70, f"ĐÁNH GIÁ RỦI RO:", ha="left", va="center",
                             fontsize=8, fontweight="bold", color=risk_color, transform=ax_risk.transAxes)
                ax_risk.text(0.18, 0.70, risk_desc, ha="left", va="center",
                             fontsize=8, color=PRIMARY, transform=ax_risk.transAxes)

                # Confidence by class
                try:
                    conf_rows = self.db.get_avg_confidence_by_class()  # type: ignore[attr-defined]
                    conf_data = []
                    for row in conf_rows:
                        cn = "Cháy" if str(row.get("class_name")) == "fire" else "Khói"
                        avg_c = row.get("avg_confidence")
                        max_c = row.get("max_confidence")
                        min_c = row.get("min_confidence")
                        conf_data.append([
                            cn,
                            str(int(row.get("total_count") or 0)),
                            f"{float(avg_c):.1%}" if avg_c is not None else "-",
                            f"{float(max_c):.1%}" if max_c is not None else "-",
                            f"{float(min_c):.1%}" if min_c is not None else "-",
                        ])
                except Exception:
                    conf_data = []

                tbl_data = []
                for row in source_rows:
                    total_c = int(row.get("total_count") or 0)
                    fire_c  = int(row.get("fire_count") or 0)
                    smoke_c = int(row.get("smoke_count") or 0)
                    ratio   = f"{fire_c / total_c * 100:.1f}%" if total_c > 0 else "0%"
                    tbl_data.append([
                        str(row.get("source_name") or "-")[:24],
                        str(row.get("location") or "-")[:18],
                        str(fire_c), str(smoke_c), str(total_c), ratio,
                    ])

                ax_conf = _blank_ax(fig1, [0.05, 0.37, 0.9, 0.14])
                _draw_table_ax(ax_conf,
                               ["Loại", "Tổng", "TB Conf", "Max Conf", "Min Conf"],
                               conf_data, title="ĐỘ TIN CẬY THEO LOẠI (CONFIDENCE)")

                ax_tbl = _blank_ax(fig1, [0.05, 0.08, 0.9, 0.27])
                _draw_table_ax(ax_tbl,
                               ["Nguồn", "Vị trí", "Cháy", "Khói", "Tổng", "Tỷ lệ"],
                               tbl_data, title="THỐNG KÊ THEO NGUỒN")
                _page_footer(fig1, 1, 4)
                pdf.savefig(fig1, facecolor=DARK)
                fig1.clear()

                # ── Page 2: Charts ────────────────────────────────────────────
                fig2 = _make_fig()
                fig2.text(0.5, 0.96, "BIỂU ĐỒ PHÂN TÍCH",
                          ha="center", fontsize=16, fontweight="bold", color=PRIMARY)

                # Pie chart
                ax_pie = fig2.add_axes([0.05, 0.55, 0.38, 0.36])
                ax_pie.set_facecolor(DARK)
                fire_total  = max(0, self.db_fire_total)   # type: ignore[attr-defined]
                smoke_total = max(0, self.db_smoke_total)  # type: ignore[attr-defined]
                if fire_total + smoke_total > 0:
                    wedges, texts, autotexts = ax_pie.pie(
                        [fire_total, smoke_total],
                        labels=["Cháy", "Khói"],
                        colors=[RED, SLATE],
                        autopct="%1.1f%%",
                        startangle=90,
                        wedgeprops={"linewidth": 2, "edgecolor": DARK},
                    )
                    for t in texts + autotexts:
                        t.set_color(PRIMARY)
                    ax_pie.set_title("Tỷ lệ phát hiện Cháy / Khói",
                                     color=PRIMARY, fontsize=11, pad=10)
                else:
                    ax_pie.text(0.5, 0.5, "Chưa có dữ liệu", ha="center", va="center",
                                color=MUTED, fontsize=10)
                    ax_pie.set_axis_off()

                # Bar chart (grouped by source)
                ax_bar = fig2.add_axes([0.52, 0.55, 0.43, 0.36])
                ax_bar.set_facecolor(DARK)
                if source_rows:
                    names  = [str(r.get("source_name") or "-")[:15] for r in source_rows]
                    fires  = [int(r.get("fire_count") or 0) for r in source_rows]
                    smokes = [int(r.get("smoke_count") or 0) for r in source_rows]
                    x_pos  = list(range(len(names)))
                    ax_bar.bar([p - 0.2 for p in x_pos], fires,  width=0.4, color=RED,   label="Cháy")
                    ax_bar.bar([p + 0.2 for p in x_pos], smokes, width=0.4, color=SLATE, label="Khói")
                    ax_bar.set_xticks(x_pos)
                    ax_bar.set_xticklabels(names, rotation=20, ha="right", color=PRIMARY, fontsize=8)
                    ax_bar.set_title("Số lần phát hiện theo nguồn", color=PRIMARY, fontsize=11, pad=10)
                    ax_bar.set_ylabel("Số lần", color=MUTED, fontsize=8)
                    ax_bar.tick_params(colors=MUTED)
                    for sp in ax_bar.spines.values():
                        sp.set_color(MUTED)
                    ax_bar.legend(facecolor=DARK, labelcolor=PRIMARY, fontsize=8)
                else:
                    ax_bar.text(0.5, 0.5, "Chưa có dữ liệu", ha="center", va="center",
                                color=MUTED, fontsize=10)
                    ax_bar.set_axis_off()

                # Trend line chart (24h)
                ax_trend = fig2.add_axes([0.07, 0.10, 0.88, 0.36])
                ax_trend.set_facecolor(DARK)
                hourly_rows = self.db.get_detection_summary_by_hour(hours=24)  # type: ignore[attr-defined]
                if hourly_rows:
                    hrn = sorted(hourly_rows, key=lambda r: str(r.get("time_bucket") or ""))
                    xl  = [str(r.get("time_bucket") or "")[-5:] for r in hrn]
                    fv  = [int(r.get("fire_count") or 0) for r in hrn]
                    sv  = [int(r.get("smoke_count") or 0) for r in hrn]
                    xp  = list(range(len(xl)))
                    ax_trend.plot(xp, fv, color=RED,   linewidth=1.8, marker="o", markersize=3, label="Cháy")
                    ax_trend.plot(xp, sv, color=SLATE, linewidth=1.8, marker="s", markersize=3, label="Khói")
                    ax_trend.fill_between(xp, fv, alpha=0.15, color=RED)
                    ax_trend.fill_between(xp, sv, alpha=0.12, color=SLATE)
                    ax_trend.set_xticks(xp)
                    ax_trend.set_xticklabels(xl, rotation=45, ha="right", fontsize=7, color=PRIMARY)
                    ax_trend.set_ylabel("Số lần", color=MUTED, fontsize=8)
                    ax_trend.set_title("Xu hướng phát hiện theo giờ (24h gần nhất)",
                                       color=PRIMARY, fontsize=11, pad=8)
                    ax_trend.tick_params(colors=MUTED)
                    for sp in ax_trend.spines.values():
                        sp.set_color(MUTED)
                    ax_trend.legend(facecolor=DARK, labelcolor=PRIMARY, fontsize=8)
                else:
                    ax_trend.text(0.5, 0.5, "Chưa có dữ liệu 24h", ha="center", va="center",
                                  color=MUTED, fontsize=10)
                    ax_trend.set_axis_off()

                _page_footer(fig2, 2, 4)
                pdf.savefig(fig2, facecolor=DARK)
                fig2.clear()

                # ── Page 3: Time tables ───────────────────────────────────────
                fig3 = _make_fig()
                fig3.text(0.5, 0.96, "DỮ LIỆU THEO THỜI GIAN",
                          ha="center", fontsize=16, fontweight="bold", color=PRIMARY)

                hourly_data = [
                    [str(r.get("time_bucket") or "-"),
                     str(int(r.get("fire_count") or 0)),
                     str(int(r.get("smoke_count") or 0)),
                     str(int(r.get("total_count") or 0))]
                    for r in hourly_rows
                ]
                ax_h = _blank_ax(fig3, [0.05, 0.54, 0.9, 0.38])
                _draw_table_ax(ax_h, ["Khung giờ", "Cháy", "Khói", "Tổng"],
                               hourly_data, title="THỐNG KÊ 24H GẦN NHẤT")

                daily_rows = self.db.get_detection_summary_by_day(days=7)  # type: ignore[attr-defined]
                daily_data = [
                    [str(r.get("day_bucket") or "-"),
                     str(int(r.get("fire_count") or 0)),
                     str(int(r.get("smoke_count") or 0)),
                     str(int(r.get("total_count") or 0))]
                    for r in daily_rows
                ]
                ax_d = _blank_ax(fig3, [0.05, 0.08, 0.9, 0.38])
                _draw_table_ax(ax_d, ["Ngày", "Cháy", "Khói", "Tổng"],
                               daily_data, title="THỐNG KÊ 7 NGÀY GẦN NHẤT")

                _page_footer(fig3, 3, 4)
                pdf.savefig(fig3, facecolor=DARK)
                fig3.clear()

                # ── Page 4: Recent detections ─────────────────────────────────
                fig4 = _make_fig()
                fig4.text(0.5, 0.96, "SỰ KIỆN PHÁT HIỆN GẦN ĐÂY",
                          ha="center", fontsize=16, fontweight="bold", color=PRIMARY)

                recent_rows_pdf = self.db.get_recent_detections(limit=30)  # type: ignore[attr-defined]
                recent_data = []
                for row in recent_rows_pdf:
                    lbl = "Cháy" if str(row.get("class_name")) == "fire" else "Khói"
                    conf = row.get("confidence")
                    conf_str = f"{float(conf):.1%}" if conf is not None else "-"
                    recent_data.append([
                        str(row.get("timestamp") or "-")[:19],
                        str(row.get("source_name") or "-")[:20],
                        lbl,
                        conf_str,
                    ])
                ax_rec = _blank_ax(fig4, [0.05, 0.08, 0.9, 0.84])
                _draw_table_ax(ax_rec, ["Thời gian", "Nguồn", "Loại", "Tin cậy"],
                               recent_data, title=f"30 SỰ KIỆN GẦN NHẤT")

                _page_footer(fig4, 4, 4)
                pdf.savefig(fig4, facecolor=DARK)
                fig4.clear()

            self._log(f"Đã xuất báo cáo PDF: {file_path}")  # type: ignore[attr-defined]
            self._set_status("Xuất PDF thành công")  # type: ignore[attr-defined]
            messagebox.showinfo("Xuất PDF thành công", f"Đã lưu báo cáo:\n{file_path}")
        except Exception as exc:
            messagebox.showerror("Lỗi xuất PDF", f"Không thể xuất PDF:\n{exc}")
            self._log(f"Xuất PDF thất bại: {exc}")  # type: ignore[attr-defined]
