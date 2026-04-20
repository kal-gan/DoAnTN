# 🔥 Fire & Smoke Detection — YOLOv8 + OpenCV

Hệ thống phát hiện **lửa (fire)** và **khói (smoke)** theo thời gian thực sử dụng **YOLOv8** và **OpenCV**. Chạy được ngay sau khi `git clone` mà **không cần train lại** — script tự động tải mô hình pretrained về.

---

## ✨ Tính năng

- 🔥 Phát hiện lửa và khói theo thời gian thực
- 📷 Hỗ trợ **camera laptop (webcam)** và **video file**
- 🚨 Banner cảnh báo đỏ khi phát hiện nguy hiểm
- 💾 Tự động lưu ảnh cảnh báo vào thư mục `alerts/` (cooldown 5 giây)
- 📊 Hiển thị FPS góc dưới trái
- 🎯 Bounding box màu đỏ (fire) / xám (smoke) với nhãn & độ tin cậy

---

## 🖥️ Yêu cầu hệ thống

| Yêu cầu | Phiên bản tối thiểu |
|---------|---------------------|
| Python  | 3.8+                |
| CUDA    | 11.8+ *(tùy chọn, để tăng tốc GPU)* |
| RAM     | 4 GB+               |

---

## 🚀 Cài đặt

```bash
git clone https://github.com/hophuc53104-hub/demo3.git
cd demo3
pip install -r requirements.txt
```

---

## 🤖 Lấy mô hình pretrained (quan trọng)

Khi chạy lần đầu, script **tự động thử tải** mô hình fire/smoke về `models/best.pt`.

Nếu tải tự động thất bại, hãy tải thủ công từ một trong các nguồn sau rồi đặt file `best.pt` vào thư mục `models/`:

| Nguồn | Link |
|-------|------|
| spacewalk01 (khuyến nghị) | https://github.com/spacewalk01/yolov8-fire-and-smoke-detection |
| MuhammadMoinFaisal | https://github.com/MuhammadMoinFaisal/YOLOv8_Fire_and_Smoke_Detection |

```bash
# Ví dụ đặt file thủ công
cp /path/to/downloaded/best.pt models/best.pt
```

> **Lưu ý:** Nếu không có `models/best.pt` và tải tự động thất bại, script sẽ fallback sang `yolov8n.pt` (COCO model). Mô hình COCO **không có lớp fire/smoke** nên sẽ không phát hiện được — chỉ dùng để kiểm tra pipeline hoạt động.

---

## ▶️ Cách chạy

### Camera laptop (webcam)

```bash
python src/detect.py --source 0
```

### Video file

```bash
python src/detect.py --source videos/test.mp4
```

### Tuỳ chỉnh ngưỡng tin cậy

```bash
python src/detect.py --source 0 --conf 0.5
```

### Sử dụng mô hình khác

```bash
python src/detect.py --source 0 --model models/custom_best.pt
```

### Tất cả tham số

| Tham số | Mô tả | Mặc định |
|---------|-------|----------|
| `--source` | `0` = webcam, hoặc đường dẫn video | `0` |
| `--model`  | Đường dẫn file `.pt` | `models/best.pt` |
| `--conf`   | Ngưỡng tin cậy (0.0–1.0) | `0.45` |

---

## ⌨️ Phím tắt

| Phím | Chức năng |
|------|-----------|
| `Q`  | Thoát chương trình |

---

## 📁 Cấu trúc thư mục

```
demo3/
├── src/
│   ├── __init__.py
│   ├── detect.py         # Script phát hiện chính
│   └── train.py          # Script train (tùy chọn)
├── data/
│   └── data.yaml         # Cấu hình dataset YOLO
├── models/
│   └── .gitkeep          # Đặt best.pt vào đây
├── videos/
│   └── .gitkeep          # Đặt video test vào đây
├── alerts/               # Ảnh cảnh báo tự động lưu tại đây
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🏋️ (Tùy chọn) Train lại mô hình

Nếu bạn muốn huấn luyện mô hình với dataset của riêng mình:

1. Chuẩn bị dataset định dạng YOLO và đặt vào `data/images/` + `data/labels/`
2. Chỉnh sửa `data/data.yaml` nếu cần
3. Chạy:

```bash
python src/train.py
```

Mô hình tốt nhất sẽ lưu tại `runs/train/fire_smoke_detector/weights/best.pt`.  
Sao chép vào `models/` để dùng:

```bash
cp runs/train/fire_smoke_detector/weights/best.pt models/best.pt
```

**Nguồn dataset gợi ý:**
- [D-Fire Dataset](https://github.com/gaiasd/DFireDataset) (~21,000 ảnh có nhãn)
- [Roboflow Fire & Smoke](https://universe.roboflow.com/search?q=fire+smoke)

---

## 🔧 Troubleshooting

### ❌ Không mở được camera

```
[ERROR] Không thể mở nguồn: 0
```

- Kiểm tra webcam đã kết nối và không bị ứng dụng khác (Zoom, Teams…) chiếm dụng
- Thử `--source 1` hoặc `--source 2` nếu có nhiều camera

### ❌ Script chạy nhưng không phát hiện được lửa/khói

- Mô hình đang dùng là COCO (fallback) — tải `best.pt` chuyên dụng về `models/`
- Thử giảm ngưỡng: `--conf 0.3`

### ⚠️ FPS thấp

- Dùng GPU (CUDA) để tăng tốc
- Dùng mô hình nhỏ hơn (yolov8n.pt)
- Giảm độ phân giải đầu vào

---

## 📄 License

MIT License — Tự do sử dụng, chỉnh sửa và phân phối.