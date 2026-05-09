Đóng vai là một Quantitative Developer và System Architect. Hãy viết code cho một Telegram Signal Bot chuyên quét dữ liệu Crypto Futures trên sàn Binance với các yêu cầu kỹ thuật chi tiết sau:

token telegram : 8566576698:AAGQ37XtAati3YM88z9UsO7ZDTKdF9TdmW0 

id chat : 7048596156 

**1\. Data & Khung thời gian (Timeframe)**

**Universe:** Quét toàn bộ các cặp giao dịch USDT-M Futures trên Binance. Phải gọi API động (dynamic fetch) để tự động cập nhật các cặp coin mới được list mà không cần hard-code.

**Timeframe quét chính:** 4H.

**Timeframe xác nhận:** M30.

**Chu kỳ thực thi (Cronjob):** Thực thi hàm quét ngay tại thời điểm cây nến 4H vừa đóng cửa (đầu giờ của các nến 4H tiếp theo).

**2\. Điều kiện kích hoạt (Trigger Conditions cho nến 4H vừa đóng)** Một nến 4H hợp lệ phải thỏa mãn ĐỒNG THỜI các điều kiện sau:

**Condition 1 (Hình thái nến):** Chiều dài thân nến (Body) \> 50% tổng chiều dài toàn nến (High \- Low).

**Condition 2 (Biên độ nến):** Tổng chiều dài toàn nến (High \- Low) phải \> 10% và \< 30% giá mở cửa của nến đó.

**Condition 3 (Đột biến Volume):** Khối lượng giao dịch (Volume) của nến hiện tại \>= 2 lần Volume của cây nến 4H liền kề trước đó.

**3\. Logic Xác định Xu hướng (Setup Long/Short)**

**Setup LONG:**

Là nến xanh (Close \> Open).

Giá Close (4H) \> đường EMA 34 (4H).

Kiểm tra đa khung thời gian: Chuyển sang khung M30, mức giá hiện tại (Current Price) phải nằm TRÊN cả 3 đường: EMA 89, EMA 144, và EMA 257 của khung M30.

**Setup SHORT:**

Là nến đỏ (Close \< Open).

Giá Close (4H) \< đường EMA 34 (4H).

Kiểm tra đa khung thời gian: Chuyển sang khung M30, mức giá hiện tại (Current Price) phải nằm DƯỚI cả 3 đường: EMA 89, EMA 144, và EMA 257 của khung M30.

Nếu thoả mãn toàn bộ điều kiện sẽ tín hành gửi tín hiệu đến telegram cho user , dưới đây là format tôi cần bạn thực hiện ( ví dụ cho cặp BNB , tín hiệu long và short ) : 

LONG 🟢 

$BNB 

Entry : ( giá lúc h4 vừa đóng ) 

SL :  ( giá thấp nhất của cây nến h4 vừa đóng ) \- ( % từ entry đến sl ) 

TP1 : 1R ( \= % từ entry đến sl ) 

TP2 : 2R ( \= 2 lần % từ entry đến sl ) 

Đơn thương độc mã duy ngã độc tôn 

Cặp ô tôi mở ngoặc bạn hãy tính toán ra số thật để thay vào 

Ngược lại nếu nến đó có giá đóng cửa thấp hơn giá mở cửa ( nến đỏ ) và thoả mãn toàn bộ điều kiện  thì bạn sẽ báo về telegram ( ví dụ cặp BNB ) 

—----------------------------------------------------------------

SHORT 🔴

$BNB 

Entry : ( giá lúc h4 vừa đóng ) 

SL :  ( giá cao nhất của cây nến h4 vừa đóng ) \- ( % từ entry đến sl ) 

TP1 : 1R ( \= % từ entry đến sl ) 

TP2 : 2R ( \= 2 lần % từ entry đến sl ) 

Đơn thương độc mã duy ngã độc tôn 

