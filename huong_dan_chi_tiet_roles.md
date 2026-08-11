# Hướng dẫn chi tiết cầm tay chỉ việc - Bài Lab 13 - Tối ưu và Observability hệ thống AI

Bài hướng dẫn này được chia thành 4 phần tương ứng với 4 vai trò trong nhóm. Mỗi thành viên sẽ đọc kỹ phần của mình và làm theo từng bước để đảm bảo nhóm đạt điểm tối đa (100 điểm).

> [!IMPORTANT] 
> **Điều kiện tiên quyết cho TẤT CẢ mọi người:**
> Bạn phải tạo môi trường ảo (virtual environment) và cài đặt các thư viện từ `requirements.txt` trước khi làm (Xem `SETUP.md`). Đảm bảo lệnh `uvicorn app.main:app --reload --env-file .env` chạy thành công.

---

## Vai trò 1: Logging & PII (Quản lý Log và dữ liệu nhạy cảm)

**Nhiệm vụ chính:** Đảm bảo log đầu ra có đầy đủ các thông tin (correlation ID, metadata) và những thông tin nhạy cảm (PII - email, số thẻ, số điện thoại) đã bị mã hoá/xóa.

### Bước 1: Correlation ID (Theo dõi request từ đầu đến cuối)
Bạn cần thêm Correlation ID để liên kết tất cả các log của cùng một request với nhau.
1. Mở file `app/middleware.py`.
2. Tìm class xử lý request (có thể là `CorrelationIdMiddleware`).
3. Nhiệm vụ của bạn là lấy `X-Correlation-ID` từ request header, hoặc tạo một UUID mới nếu không có.
4. Gán ID này vào biến context/biến cục bộ (local context) để logger có thể sử dụng (Sử dụng thư viện `structlog` context).
5. Đừng quên làm sạch (clear) context trước và sau mỗi request.
6. Thêm `X-Correlation-ID` vào Header của response trả về.

### Bước 2: Metadata
Log phải chứa các thông tin như `user_id_hash`, `session_id`, `feature`, `model`, `env`.
1. Mở file `app/main.py` hoặc `app/agent.py`.
2. Tìm những chỗ log sự kiện như `request_received`. 
3. Trước dòng gọi lệnh ghi log (ví dụ: `logger.info("request_received")`), sử dụng lệnh `structlog.contextvars.bind_contextvars(...)` (hoặc tương tự tuỳ code của app) để chèn các biến `user_id_hash`, `session_id` v.v. vào context.
4. Nhờ vậy, mọi log sinh ra sau đó trong request này đều sẽ có metadata.

### Bước 3: PII Redaction (Che dấu thông tin cá nhân)
1. Mở file `app/pii.py` hoặc `app/logging_config.py`.
2. Tìm list các "processor" của structlog. Dữ liệu phải được làm sạch TRƯỚC KHI chuyển thành dạng JSON.
3. Trong hàm/class xóa PII, bạn sẽ dùng Regex (biểu thức chính quy) để thay thế Email, SĐT, Số thẻ thành ký tự `***` hoặc `[REDACTED]`.
4. Viết code chạy qua các values của log event dict, nếu là chuỗi (string) thì thực hiện hàm che PII.

### Bước 4: Kiểm tra (Validate)
- Chạy API của nhóm: `uvicorn app.main:app --reload --env-file .env`
- Mở terminal khác và tạo tải giả: `python scripts/load_test.py`
- Chạy script kiểm tra tự động: `python scripts/validate_logs.py`
- Đảm bảo kết quả phải đạt **tối thiểu 80/100**.

> [!TIP]
> Bằng chứng phải nộp: Chụp ảnh log hợp lệ và bằng chứng chỉ ra rằng không có dữ liệu PII bị lộ trong file `data/logs.jsonl`. Ghi vào file `submission/REPORT.md`.

---

## Vai trò 2: Tracing & Prompt Version (Theo dõi luồng và phiên bản Prompt)

**Nhiệm vụ chính:** Đảm bảo hệ thống kết nối thành công tới Langfuse, ghi nhận traces của các luồng xử lý và thay đổi prompt version an toàn.

### Bước 1: Setup Langfuse
1. Xin Lab Coach các thông tin về `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` và cập nhật vào file `.env` (Đừng commit `.env`).
2. Mở file `app/tracing.py` hoặc chỗ khởi tạo langfuse, kiểm tra cấu hình để đảm bảo app đang kết nối đúng host.

### Bước 2: Tạo Prompt trên Langfuse UI
1. Truy cập trang web Langfuse (theo HOST ở Bước 1).
2. Tạo một prompt mới tên là `day13-chat`.
3. Nhập đúng nội dung template:
```text
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```
4. Lưu version này (ví dụ Version 1) và gắn 2 nhãn (labels): `baseline` và `production`.

### Bước 3: Đổi version và test
1. Cấu hình biến môi trường `.env`: 
   `LANGFUSE_PROMPT_NAME=day13-chat` 
   `LANGFUSE_PROMPT_LABEL=production`
2. Chạy tải giả `python scripts/load_test.py`.
3. Kiểm tra trên màn hình Traces của Langfuse, bấm vào một trace bất kỳ, bạn sẽ thấy thông tin `prompt_name`, `prompt_label` và `prompt_version`.

### Bước 4: Thực hành Rollback
1. Tạo một Version 2 trên Langfuse với một vài tinh chỉnh format chữ. Gắn nhãn là `candidate`.
2. Chạy ứng dụng bằng `LANGFUSE_PROMPT_LABEL=candidate`. Chụp lại Trace ID chứng minh đã ăn version mới.
3. Chuyển nhãn `production` sang cho Version 2, chạy request.
4. Xóa nhãn `production` của Version 2 và gán lại cho Version 1 (Rollback). Lưu ảnh bằng chứng.

> [!TIP]
> Bằng chứng phải nộp: 
> - Ảnh chụp 2 version của prompt trên giao diện Langfuse.
> - Hai mã Trace ID chứng minh 2 version/label hoạt động khác nhau.
> - Ảnh giao diện chứng tỏ bạn đã chuyển nhãn và rollback thành công. (Ghi tất cả vào báo cáo).

---

## Vai trò 3: Dashboard, SLO & Alert (Bảng điều khiển và Cảnh báo)

**Nhiệm vụ chính:** Dựng bảng điều khiển (Dashboard) gồm 6 panel chính từ file dữ liệu chuẩn `data/logs.jsonl`, tuân theo contract trong file `config/dashboard.yaml`.

### Bước 1: Đọc tài liệu Contract
1. Mở file `config/dashboard.yaml` và `docs/DASHBOARD_SETUP.md`.
2. Hiểu được 6 thông số cần đo: Latency (P50, P95, P99), Traffic, Errors (Error rate), Cost (Tổng USD), Tokens (Vào/Ra), Quality.

### Bước 2: Khởi tạo Dashboard
1. Nhóm có thể chọn công cụ: Streamlit, Jupyter Notebook, Grafana...
2. Nếu dùng Streamlit/Jupyter Notebook: Viết script Python đọc file `data/logs.jsonl` (Parse từng dòng JSON).
3. Code các chart (biểu đồ):
   - **Latency:** Lọc các log có `event == "response_sent"`, vẽ biểu đồ phân phối percentile của cột `latency_ms` với đường đỏ (SLO threshold) tại 3000ms.
   - **Traffic:** Lọc log `request_received`, đếm theo từng phút (requests per minute).
   - **Errors:** Tính tỉ lệ `(số request_failed / số request_received) * 100` theo thời gian.
   - **Cost & Token:** Sum các trường `cost_usd`, `tokens_in`, `tokens_out` theo thời gian thực.
   - **Quality:** Tính giá trị trung bình (`mean`) của trường `quality_score`.

### Bước 3: Chạy Validator
1. Chạy API và load test để có dữ liệu (`python scripts/load_test.py --concurrency 5`).
2. Chạy: `python scripts/validate_dashboard.py`
3. Terminal phải in ra `HỢP LỆ: 6/6 panel`. 

### Bước 4: Kiểm chứng tính phản ứng của Dashboard
1. Khởi động một incident: `python scripts/inject_incident.py --scenario rag_slow`
2. Chạy lại load test với cùng concurrency.
3. Nhìn trên Dashboard xem biểu đồ Latency có vọt lên báo đỏ vượt Threshold hay không.

> [!TIP]
> Bằng chứng phải nộp: Ảnh chụp màn hình Dashboard nhìn rõ tên panel, time range, các đường threshold (SLO line), và kết quả validator 6/6.

---

## Vai trò 4: Incident, Report & Demo (Xử lý sự cố và báo cáo)

**Nhiệm vụ chính:** Khi có lỗi xảy ra, bạn là người đọc số liệu, dò tìm nguyên nhân từ trên xuống dưới (Metrics -> Trace -> Log) và viết báo cáo cho team.

### Bước 1: Tiếp nhận Challenge
1. Chờ Lab Coach gửi file `config/challenge.json`. KHÔNG tự ý tạo hay sửa file này.
2. Chạy lệnh gây lỗi:
   ```bash
   python scripts/inject_incident.py
   python scripts/load_test.py --challenge --concurrency 5
   ```

### Bước 2: Điều tra theo luồng (Metrics -> Traces -> Logs)
1. **Metrics:** Mở Dashboard của (Vai trò 3) lên, xem biểu đồ nào đang "báo động" (Ví dụ: Error rate tăng cao? Hay Latency vọt lên?). Ghi nhận lại thời gian xảy ra triệu chứng.
2. **Traces:** Lên giao diện Langfuse (của Vai trò 2), khoanh vùng các request trong khung giờ đó. Mở các request bị lỗi/bị chậm lên. Xem sơ đồ thác (Waterfall), span nào đang ngốn thời gian nhất hoặc span nào bị đỏ? Lấy ID của span/request đó.
3. **Logs:** Quay về file `data/logs.jsonl`, tìm (Search - Ctrl F) bằng đúng cái ID bạn vừa lấy ở Trace (Đây chính là Correlation ID từ Vai trò 1). Bạn sẽ thấy toàn bộ log của quá trình đó.
4. Nhờ log, bạn sẽ phát hiện được chính xác dòng code nào, dịch vụ nào đang gây lỗi (Root cause).

### Bước 3: Viết Báo cáo & Đề xuất
1. Mở file `submission/REPORT.md`.
2. Trình bày chi tiết luồng tìm ra lỗi như ở Bước 2.
3. Đề xuất cách sửa (Fix action) và biện pháp phòng ngừa (Preventive measure).

### Bước 4: Hoàn tất nộp bài
1. Chạy lệnh: `python -m pytest -q` để đảm bảo code không hỏng chức năng.
2. Chạy: `git status --short`. Đảm bảo không commit file `.env`, không lộ API Key, không đưa file log có PII chưa được giấu lên GitHub.
3. Push code và cùng nhóm chuẩn bị báo cáo DEMO 5 phút thật mượt mà luồng Metrics -> Traces -> Logs.

> [!CAUTION]
> Tuyệt đối không gian lận bằng cách chỉnh sửa code để qua mặt validator. Mọi logic phải được xử lý thực tế trong source code. Điểm số dựa rất nhiều vào file `REPORT.md` và bằng chứng hình ảnh trong thư mục `submission/evidence/`.

Chúc các bạn xuất sắc vượt qua bài Lab 13!
