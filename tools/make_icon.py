"""
tools/make_icon.py
Sinh icon ngọn lửa chibi (multi-size .ico) cho FireSmokeMonitor.exe.

Chạy:
    python tools/make_icon.py

Output: app.ico (chứa các kích thước 16/32/48/64/128/256)
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter
import os


def draw_chibi_flame(size: int) -> Image.Image:
    """Vẽ 1 con lửa chibi tròn vo, mặt cười dễ thương."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = size  # alias

    # === Thân ngọn lửa (lớp ngoài đỏ-cam) =================================
    # Hình giọt nước úp ngược: đỉnh nhọn, đáy tròn
    outer = [
        (s * 0.50, s * 0.06),   # đỉnh
        (s * 0.62, s * 0.22),
        (s * 0.72, s * 0.30),   # bướu phải
        (s * 0.68, s * 0.42),
        (s * 0.88, s * 0.58),
        (s * 0.92, s * 0.78),
        (s * 0.78, s * 0.94),
        (s * 0.50, s * 0.98),
        (s * 0.22, s * 0.94),
        (s * 0.08, s * 0.78),
        (s * 0.12, s * 0.58),
        (s * 0.32, s * 0.42),
        (s * 0.28, s * 0.30),
        (s * 0.38, s * 0.22),
    ]
    draw.polygon(outer, fill=(240, 78, 26, 255))  # cam đậm (ACCENT của app)

    # Lớp giữa cam sáng
    inner_orange = [
        (s * 0.50, s * 0.18),
        (s * 0.62, s * 0.34),
        (s * 0.74, s * 0.54),
        (s * 0.78, s * 0.74),
        (s * 0.62, s * 0.90),
        (s * 0.38, s * 0.90),
        (s * 0.22, s * 0.74),
        (s * 0.26, s * 0.54),
        (s * 0.38, s * 0.34),
    ]
    draw.polygon(inner_orange, fill=(255, 152, 28, 255))

    # Lõi vàng
    yellow_core = [
        (s * 0.50, s * 0.34),
        (s * 0.62, s * 0.52),
        (s * 0.66, s * 0.72),
        (s * 0.50, s * 0.86),
        (s * 0.34, s * 0.72),
        (s * 0.38, s * 0.52),
    ]
    draw.polygon(yellow_core, fill=(255, 214, 70, 255))

    # === Mặt chibi =========================================================
    # Mắt — chỉ vẽ nếu icon đủ lớn để nhìn rõ
    if s >= 24:
        eye_r = max(2, int(s * 0.055))
        eye_y = s * 0.62
        ex_l = s * 0.42
        ex_r = s * 0.58

        # Lòng trắng (thực ra trên chibi lửa thường là mắt đen tròn)
        for ex in (ex_l, ex_r):
            draw.ellipse(
                [ex - eye_r, eye_y - eye_r * 1.2,
                 ex + eye_r, eye_y + eye_r * 1.2],
                fill=(40, 24, 8, 255),
            )
            # Highlight trắng nhỏ
            hr = max(1, int(eye_r * 0.45))
            draw.ellipse(
                [ex - hr + eye_r * 0.25, eye_y - hr * 1.3 - eye_r * 0.1,
                 ex + hr + eye_r * 0.25, eye_y + hr * 0.7 - eye_r * 0.1],
                fill=(255, 255, 255, 255),
            )

        # Má hồng
        if s >= 48:
            cheek_r = int(s * 0.035)
            cheek_y = eye_y + eye_r * 1.4
            for cx in (s * 0.34, s * 0.66):
                draw.ellipse(
                    [cx - cheek_r, cheek_y - cheek_r * 0.7,
                     cx + cheek_r, cheek_y + cheek_r * 0.7],
                    fill=(255, 120, 110, 180),
                )

        # Miệng cười nhỏ
        mouth_w = max(3, int(s * 0.08))
        mouth_h = max(2, int(s * 0.04))
        mx = s * 0.50
        my = eye_y + eye_r * 1.7
        draw.arc(
            [mx - mouth_w, my - mouth_h, mx + mouth_w, my + mouth_h],
            start=0, end=180,
            fill=(40, 24, 8, 255),
            width=max(1, int(s * 0.018)),
        )

    return img


def main():
    out_path = os.path.abspath("app.ico")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    # Vẽ ở kích thước lớn nhất rồi để PIL downscale cho các size còn lại
    base = draw_chibi_flame(256)
    base.save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )
    # PNG preview
    base.save(os.path.abspath("app_icon_preview.png"), format="PNG")
    print(f"✓ Đã tạo {out_path}")
    print(f"✓ Preview: {os.path.abspath('app_icon_preview.png')}")


if __name__ == "__main__":
    main()
