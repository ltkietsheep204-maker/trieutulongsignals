# 🤖 Telegram Crypto Futures Signal Bot

Bot tự động quét toàn bộ **USDT-M Futures** trên **Binance** và gửi tín hiệu **LONG / SHORT** qua **Telegram**.

---

## 📋 Tính năng

| # | Tính năng | Chi tiết |
|---|-----------|---------|
| 1 | **Dynamic Universe** | Tự động fetch toàn bộ cặp USDT-M Futures — không hard-code |
| 2 | **Multi-Timeframe** | Quét nến 4H + xác nhận EMA trên M30 |
| 2b | **H1 Spike Signal** | Quét thêm nến H1 độc lập với điều kiện spike riêng |
| 3 | **3 Điều kiện nến** | Body ratio > 50%, Range 10-30% Open, Volume spike ≥ 2x |
| 4 | **EMA Confirmation** | EMA 34 (4H) + EMA 89/144/257 (M30) |
| 5 | **Auto-Schedule** | Tự động quét khi nến 4H đóng (00/04/08/12/16/20 UTC) |
| 6 | **Telegram Alert** | Gửi tín hiệu với Entry, SL, TP1 (1R), TP2 (2R) |
| 7 | **D1 Daily Summary** | 07:00 UTC+7 mỗi ngày gửi 1 tin tổng hợp D1 Long/Short (Body >= 50%, Range >= 25%, Volume >= 3x nến trước) |

---

## 🚀 Cài đặt & Chạy

### 1. Yêu cầu
- Python 3.11+

### 2. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 3. Cấu hình Telegram
Tạo hoặc cập nhật file `.env` trong thư mục project:

```env
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Bot hiện đã tự đọc `.env`, không cần export biến môi trường thủ công.

### 4. Chạy bot bằng local web UI
```bash
python web_ui.py
```

Hoặc trên macOS có thể double click file `start_bot.command`.

Web UI có:
- form nhập và lưu `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID`
- `Service`: chạy liên tục, tự scan lần đầu và bám scheduler 4H/D1
- `Run once`: quét một vòng rồi thoát
- `Stop`: dừng bot
- vùng log realtime để theo dõi bot

Web UI chạy trực tiếp `python bot.py` trên máy local, không phụ thuộc Docker.

### 5. Chạy bot trực tiếp bằng CLI
```bash
python bot.py
```

Bot sẽ:
1. Quét ngay lần đầu (test)
2. Tự động schedule quét mỗi khi nến 4H đóng
3. Tự động schedule quét H1 mỗi đầu giờ
4. Lúc 07:00 UTC+7 mỗi ngày, quét D1 và gửi 1 tin tổng hợp:
	- D1 Long : ...
	- D1 Short : ...

Lưu ý khi chạy bằng chế độ `--once` (ví dụ job trên Azure):
- Bot vẫn quét 4H như cũ.
- Nếu execution rơi vào 00:00 UTC (07:00 UTC+7), bot sẽ tự chạy thêm lượt tổng hợp D1.

---

## 📊 Logic tín hiệu

### Điều kiện kích hoạt (nến 4H vừa đóng)
1. **Body > 50%** tổng chiều dài nến
2. **Range > 10% và < 30%** giá Open, với công thức **(High - Low) / Open**
3. **Volume ≥ 2x** nến 4H trước đó

### Điều kiện kích hoạt bổ sung (nến H1 vừa đóng)
1. **Body > 50%** tổng chiều dài nến
2. **Range từ 5% đến 20%** giá Open, với công thức **(High - Low) / Open**
3. **Volume ≥ 5x** nến H1 trước đó

Khi có tín hiệu H1, bot gửi theo cùng format tín hiệu như 4H (Entry/SL/TP1/TP2),
nhưng SL dùng đáy/đỉnh của chính nến H1 vừa đóng, từ đó TP1 và TP2 được tính lại theo R.

### Setup LONG 🟢
- Nến xanh (Close > Open)
- Close > EMA 34 (4H)
- Price > EMA 89, 144, 257 (M30)

### Setup SHORT 🔴
- Nến đỏ (Close < Open)
- Close < EMA 34 (4H)
- Price < EMA 89, 144, 257 (M30)

### Quản lý vị thế
- **Entry**: Giá Close nến 4H vừa đóng
- **SL (Long)**: Low nến tín hiệu | **SL (Short)**: High nến tín hiệu
- **TP1**: 1R (= % SL)
- **TP2**: 2R (= 2x % SL)

---

## ⚠️ Lưu ý

- Bot chỉ sử dụng **public API** — không cần API key Binance
- Điều kiện Range 10-30% Open là rất rộng cho crypto; nếu muốn điều chỉnh, sửa `RANGE_PERCENT_MIN` / `RANGE_PERCENT_MAX` trong `bot.py`
- Nên chạy trên **VPS** để bot hoạt động 24/7
