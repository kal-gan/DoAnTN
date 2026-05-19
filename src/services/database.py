import importlib
import sqlite3
from typing import Any, Dict, List, Optional


class AppDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def initialize(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT,
                email TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                location TEXT,
                order_index INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                camera_id INTEGER,
                class_name TEXT,
                confidence REAL,
                image_path TEXT,
                video_path TEXT,
                bbox_x INTEGER,
                bbox_y INTEGER,
                bbox_w INTEGER,
                bbox_h INTEGER,
                FOREIGN KEY (camera_id) REFERENCES cameras(id)
            );

            CREATE TABLE IF NOT EXISTS stream_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                ended_at DATETIME,
                started_by_user_id INTEGER,
                total_sources INTEGER DEFAULT 0,
                model_path TEXT,
                conf_threshold REAL,
                target_fps INTEGER,
                inference_stride INTEGER,
                total_frames INTEGER DEFAULT 0,
                fire_frames INTEGER DEFAULT 0,
                smoke_frames INTEGER DEFAULT 0,
                alert_count INTEGER DEFAULT 0,
                avg_fps REAL DEFAULT 0,
                status TEXT DEFAULT 'running',
                FOREIGN KEY (started_by_user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS session_source_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                camera_id INTEGER,
                source_name TEXT,
                source_type TEXT,
                source_value TEXT,
                processed_frames INTEGER DEFAULT 0,
                fire_events INTEGER DEFAULT 0,
                smoke_events INTEGER DEFAULT 0,
                alert_events INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES stream_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (camera_id) REFERENCES cameras(id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS training_captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                label TEXT NOT NULL,
                image_path TEXT NOT NULL,
                source_name TEXT,
                captured_by INTEGER,
                FOREIGN KEY (captured_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        self._ensure_camera_order_column()
        self._ensure_detection_video_column()
        self._ensure_indexes()
        self.conn.commit()
        self._seed_default_users()

    def _ensure_camera_order_column(self):
        columns = self.conn.execute("PRAGMA table_info(cameras)").fetchall()
        column_names = {str(col["name"]) for col in columns}
        if "order_index" not in column_names:
            self.conn.execute("ALTER TABLE cameras ADD COLUMN order_index INTEGER DEFAULT 0")
            self.conn.execute(
                """
                UPDATE cameras
                SET order_index = id
                WHERE order_index = 0 OR order_index IS NULL
                """
            )

    def _ensure_detection_video_column(self):
        columns = self.conn.execute("PRAGMA table_info(detections)").fetchall()
        column_names = {str(col["name"]) for col in columns}
        if "video_path" not in column_names:
            self.conn.execute("ALTER TABLE detections ADD COLUMN video_path TEXT")

    def _ensure_indexes(self):
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_camera_class ON detections(camera_id, class_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_class ON detections(class_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON stream_sessions(started_at)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_session_metrics_session_id ON session_source_metrics(session_id)")

    @staticmethod
    def _bcrypt_module():
        return importlib.import_module("bcrypt")

    def _seed_default_users(self):
        # Hệ thống chỉ dùng tài khoản admin — không có người dùng thường.
        # Xóa các tài khoản không phải admin (kể cả role NULL/rỗng).
        self.conn.execute(
            "DELETE FROM users WHERE LOWER(COALESCE(role, '')) != 'admin' AND LOWER(username) != 'admin'"
        )
        # Nếu username='admin' đang tồn tại nhưng role không phải 'admin' → ép về 'admin'.
        self.conn.execute(
            "UPDATE users SET role='admin' WHERE LOWER(username)='admin' AND LOWER(COALESCE(role,'')) != 'admin'"
        )
        self.conn.commit()

        # Kiểm tra xem đã có tài khoản admin chưa
        existing = self.conn.execute(
            "SELECT id FROM users WHERE LOWER(username)='admin' LIMIT 1"
        ).fetchone()
        bcrypt_mod = self._bcrypt_module()
        if existing is None:
            admin_hash = bcrypt_mod.hashpw("admin123".encode("utf-8"), bcrypt_mod.gensalt()).decode("utf-8")
            admin_cur = self.conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name, email, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                ("admin", admin_hash, "admin", "Administrator", "admin@local"),
            )
            admin_id = int(admin_cur.lastrowid)
        else:
            admin_id = int(existing["id"])

        cam_row = self.conn.execute("SELECT COUNT(*) AS total FROM cameras").fetchone()
        if cam_row and int(cam_row["total"]) == 0:
            self.conn.execute(
                "INSERT INTO cameras (name, source, location, order_index, is_active, created_by) VALUES (?, ?, ?, ?, 1, ?)",
                ("Camera 0", "0", "Mặc định", 1, admin_id),
            )

        self.conn.commit()

    def verify_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT id, username, password_hash, role, full_name, is_active FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        if row is None or int(row["is_active"] or 0) != 1:
            return None

        stored_hash = str(row["password_hash"])
        bcrypt_mod = self._bcrypt_module()
        ok = bcrypt_mod.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        if not ok:
            return None

        return {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
            "full_name": str(row["full_name"] or row["username"]),
        }

    def update_last_login(self, user_id: int):
        self.conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        self.conn.commit()

    def update_user_password(self, user_id: int, new_password: str):
        bcrypt_mod = self._bcrypt_module()
        password_hash = bcrypt_mod.hashpw(new_password.encode("utf-8"), bcrypt_mod.gensalt()).decode("utf-8")
        self.conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, int(user_id)))
        self.conn.commit()

    def add_audit_log(self, user_id: Optional[int], action: str, details: str = ""):
        self.conn.execute(
            "INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details),
        )
        self.conn.commit()

    def get_active_cameras(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, name, source, location, order_index FROM cameras WHERE is_active = 1 ORDER BY order_index ASC, id ASC"
        ).fetchall()
        return [dict(row) for row in rows]

    def add_camera(self, name: str, source: str, location: str, created_by: int) -> int:
        row = self.conn.execute("SELECT COALESCE(MAX(order_index), 0) AS max_order FROM cameras").fetchone()
        next_order = int(row["max_order"] or 0) + 1
        cur = self.conn.execute(
            "INSERT INTO cameras (name, source, location, order_index, is_active, created_by) VALUES (?, ?, ?, ?, 1, ?)",
            (name, source, location, next_order, created_by),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_camera(self, camera_id: int, name: str, source: str, location: str):
        self.conn.execute(
            "UPDATE cameras SET name = ?, source = ?, location = ? WHERE id = ?",
            (name, source, location, int(camera_id)),
        )
        self.conn.commit()

    def update_camera_order(self, camera_ids: List[int]):
        for idx, camera_id in enumerate(camera_ids, start=1):
            self.conn.execute("UPDATE cameras SET order_index = ? WHERE id = ?", (idx, int(camera_id)))
        self.conn.commit()

    def deactivate_camera(self, camera_id: int):
        self.conn.execute("UPDATE cameras SET is_active = 0 WHERE id = ?", (camera_id,))
        self.conn.commit()

    def add_detection(
        self,
        camera_id: Optional[int],
        class_name: str,
        confidence: Optional[float] = None,
        image_path: Optional[str] = None,
        video_path: Optional[str] = None,
    ):
        self.conn.execute(
            """
            INSERT INTO detections (camera_id, class_name, confidence, image_path, video_path, bbox_x, bbox_y, bbox_w, bbox_h)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
            """,
            (camera_id, class_name, confidence, image_path, video_path),
        )
        self.conn.commit()

    def start_stream_session(
        self,
        started_by_user_id: Optional[int],
        total_sources: int,
        model_path: str,
        conf_threshold: float,
        target_fps: int,
        inference_stride: int,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO stream_sessions (
                started_by_user_id, total_sources, model_path, conf_threshold, target_fps, inference_stride, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'running')
            """,
            (
                int(started_by_user_id) if started_by_user_id is not None else None,
                int(total_sources),
                str(model_path),
                float(conf_threshold),
                int(target_fps),
                int(inference_stride),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def end_stream_session(
        self,
        session_id: int,
        status: str,
        total_frames: int,
        fire_frames: int,
        smoke_frames: int,
        alert_count: int,
        avg_fps: float,
    ):
        self.conn.execute(
            """
            UPDATE stream_sessions
            SET
                ended_at = CURRENT_TIMESTAMP,
                status = ?,
                total_frames = ?,
                fire_frames = ?,
                smoke_frames = ?,
                alert_count = ?,
                avg_fps = ?
            WHERE id = ?
            """,
            (
                str(status),
                int(total_frames),
                int(fire_frames),
                int(smoke_frames),
                int(alert_count),
                float(avg_fps),
                int(session_id),
            ),
        )
        self.conn.commit()

    def add_session_source_metric(
        self,
        session_id: int,
        camera_id: Optional[int],
        source_name: str,
        source_type: str,
        source_value: str,
        processed_frames: int,
        fire_events: int,
        smoke_events: int,
        alert_events: int,
    ):
        self.conn.execute(
            """
            INSERT INTO session_source_metrics (
                session_id, camera_id, source_name, source_type, source_value,
                processed_frames, fire_events, smoke_events, alert_events
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(session_id),
                int(camera_id) if camera_id is not None else None,
                str(source_name),
                str(source_type),
                str(source_value),
                int(processed_frames),
                int(fire_events),
                int(smoke_events),
                int(alert_events),
            ),
        )
        self.conn.commit()

    def get_detection_summary_by_source(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
                c.id AS camera_id,
                COALESCE(c.name, 'Không xác định') AS source_name,
                COALESCE(c.location, '') AS location,
                c.order_index AS order_index,
                COALESCE(SUM(CASE WHEN d.class_name = 'fire' THEN 1 ELSE 0 END), 0) AS fire_count,
                COALESCE(SUM(CASE WHEN d.class_name = 'smoke' THEN 1 ELSE 0 END), 0) AS smoke_count,
                COUNT(d.id) AS total_count
            FROM cameras c
            LEFT JOIN detections d ON d.camera_id = c.id
            GROUP BY c.id, c.name, c.location, c.order_index
            ORDER BY c.is_active DESC, c.order_index ASC, c.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_detection_summary_by_class(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT class_name, COUNT(*) AS total_count
            FROM detections
            GROUP BY class_name
            ORDER BY total_count DESC, class_name ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_detection_totals(self) -> Dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) AS total_events,
                COALESCE(SUM(CASE WHEN class_name = 'fire' THEN 1 ELSE 0 END), 0) AS fire_total,
                COALESCE(SUM(CASE WHEN class_name = 'smoke' THEN 1 ELSE 0 END), 0) AS smoke_total,
                COALESCE(SUM(CASE WHEN DATE(timestamp, 'localtime') = DATE('now', 'localtime') THEN 1 ELSE 0 END), 0) AS today_total
            FROM detections
            """
        ).fetchone()
        return dict(row) if row is not None else {"total_events": 0, "fire_total": 0, "smoke_total": 0, "today_total": 0}

    def get_detection_summary_by_hour(self, hours: int = 24) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
                STRFTIME('%Y-%m-%d %H:00', timestamp, 'localtime') AS time_bucket,
                COALESCE(SUM(CASE WHEN class_name = 'fire' THEN 1 ELSE 0 END), 0) AS fire_count,
                COALESCE(SUM(CASE WHEN class_name = 'smoke' THEN 1 ELSE 0 END), 0) AS smoke_count,
                COUNT(*) AS total_count
            FROM detections
            WHERE timestamp >= DATETIME('now', 'localtime', '-' || ? || ' hours')
            GROUP BY time_bucket
            ORDER BY time_bucket DESC
            """,
            (int(hours),),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_detection_summary_by_day(self, days: int = 7) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
                DATE(timestamp, 'localtime') AS day_bucket,
                COALESCE(SUM(CASE WHEN class_name = 'fire' THEN 1 ELSE 0 END), 0) AS fire_count,
                COALESCE(SUM(CASE WHEN class_name = 'smoke' THEN 1 ELSE 0 END), 0) AS smoke_count,
                COUNT(*) AS total_count
            FROM detections
            WHERE timestamp >= DATETIME('now', 'localtime', '-' || ? || ' days')
            GROUP BY day_bucket
            ORDER BY day_bucket DESC
            """,
            (int(days),),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_detections(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
                d.timestamp,
                COALESCE(c.name, 'Không xác định') AS source_name,
                d.class_name,
                d.confidence,
                d.image_path,
                d.video_path
            FROM detections d
            LEFT JOIN cameras c ON c.id = d.camera_id
            ORDER BY d.timestamp DESC, d.id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_avg_confidence_by_class(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
                class_name,
                COUNT(*) AS total_count,
                ROUND(AVG(CASE WHEN confidence IS NOT NULL THEN confidence END), 4) AS avg_confidence,
                ROUND(MAX(CASE WHEN confidence IS NOT NULL THEN confidence END), 4) AS max_confidence,
                ROUND(MIN(CASE WHEN confidence IS NOT NULL THEN confidence END), 4) AS min_confidence
            FROM detections
            GROUP BY class_name
            ORDER BY total_count DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_hour_detections(self, hours: int = 1) -> Dict[str, Any]:
        """Trả về tổng hợp phát hiện trong N giờ gần nhất để tính mức độ rủi ro."""
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                COALESCE(SUM(CASE WHEN class_name = 'fire' THEN 1 ELSE 0 END), 0) AS fire_count,
                COALESCE(SUM(CASE WHEN class_name = 'smoke' THEN 1 ELSE 0 END), 0) AS smoke_count,
                ROUND(AVG(CASE WHEN confidence IS NOT NULL THEN confidence END), 4) AS avg_confidence,
                ROUND(MAX(CASE WHEN class_name = 'fire' AND confidence IS NOT NULL THEN confidence END), 4) AS max_fire_conf
            FROM detections
            WHERE timestamp >= DATETIME('now', 'localtime', '-' || ? || ' hours')
            """,
            (int(hours),),
        ).fetchone()
        return dict(row) if row else {}

    def get_peak_detection_hour(self) -> Dict[str, Any]:
        """Trả về khung giờ có nhiều phát hiện nhất."""
        row = self.conn.execute(
            """
            SELECT
                STRFTIME('%H:00', timestamp, 'localtime') AS hour_label,
                COUNT(*) AS total_count
            FROM detections
            GROUP BY hour_label
            ORDER BY total_count DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else {}

    # ------------------------------------------------------------------ #
    #  Quản lý người dùng                                                  #
    # ------------------------------------------------------------------ #

    def get_all_users(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, username, role, full_name, email, last_login, is_active FROM users ORDER BY id ASC"
        ).fetchall()
        return [dict(row) for row in rows]

    def add_user(self, username: str, password: str, role: str, full_name: str, email: str = "") -> int:
        bcrypt_mod = self._bcrypt_module()
        pw_hash = bcrypt_mod.hashpw(password.encode("utf-8"), bcrypt_mod.gensalt()).decode("utf-8")
        cur = self.conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name, email, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (username.strip(), pw_hash, role.strip(), full_name.strip(), email.strip()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_user(self, user_id: int, full_name: str, email: str, role: str):
        self.conn.execute(
            "UPDATE users SET full_name = ?, email = ?, role = ? WHERE id = ?",
            (full_name.strip(), email.strip(), role.strip(), int(user_id)),
        )
        self.conn.commit()

    def update_user_password(self, user_id: int, new_password: str):
        bcrypt_mod = self._bcrypt_module()
        password_hash = bcrypt_mod.hashpw(new_password.encode("utf-8"), bcrypt_mod.gensalt()).decode("utf-8")
        self.conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, int(user_id)))
        self.conn.commit()

    def toggle_user_active(self, user_id: int):
        self.conn.execute(
            "UPDATE users SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (int(user_id),),
        )
        self.conn.commit()

    def get_audit_logs(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT al.timestamp,
                   COALESCE(u.username, 'system') AS username,
                   al.action,
                   al.details
            FROM audit_logs al
            LEFT JOIN users u ON u.id = al.user_id
            ORDER BY al.timestamp DESC, al.id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------ #
    #  Training captures                                                   #
    # ------------------------------------------------------------------ #

    def add_training_capture(self, image_path: str, label: str,
                              source_name: str = "", captured_by: Optional[int] = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO training_captures (image_path, label, source_name, captured_by) VALUES (?, ?, ?, ?)",
            (str(image_path), str(label), str(source_name), captured_by),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_training_captures(self, label: Optional[str] = None,
                               limit: int = 500) -> List[Dict[str, Any]]:
        if label:
            rows = self.conn.execute(
                "SELECT * FROM training_captures WHERE label = ? ORDER BY timestamp DESC LIMIT ?",
                (str(label), int(limit)),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM training_captures ORDER BY timestamp DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_training_capture(self, capture_id: int):
        self.conn.execute("DELETE FROM training_captures WHERE id = ?", (int(capture_id),))
        self.conn.commit()

    def delete_training_captures_bulk(self, ids: List[int]):
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.conn.execute(f"DELETE FROM training_captures WHERE id IN ({placeholders})", ids)
        self.conn.commit()

    def relabel_training_capture(self, capture_id: int, new_label: str, new_image_path: str):
        """Cập nhật nhãn + đường dẫn ảnh khi đổi nhãn."""
        self.conn.execute(
            "UPDATE training_captures SET label = ?, image_path = ? WHERE id = ?",
            (str(new_label), str(new_image_path), capture_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ #
    #  App settings (key-value store)                                      #
    # ------------------------------------------------------------------ #

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (str(key),)
        ).fetchone()
        return str(row["value"]) if row else str(default)

    def set_setting(self, key: str, value: str):
        self.conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(key), str(value)),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ #
    #  Settings có mã hoá (cho password, token, …)                        #
    # ------------------------------------------------------------------ #

    def get_setting_secret(self, key: str, default: str = "") -> str:
        """Đọc setting và giải mã. Tương thích ngược với plaintext cũ."""
        from .crypto import decrypt_secret
        raw = self.get_setting(key, "")
        if not raw:
            return str(default)
        return decrypt_secret(raw) or str(default)

    def set_setting_secret(self, key: str, value: str):
        """Mã hoá rồi lưu setting. Chuỗi rỗng được lưu nguyên (xoá)."""
        from .crypto import encrypt_secret
        self.set_setting(key, encrypt_secret(value) if value else "")

    def close(self):
        self.conn.close()

