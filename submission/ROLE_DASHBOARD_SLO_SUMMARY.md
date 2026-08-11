# Role summary — Dashboard, SLO & Alert

Chuẩn bị cho demo cuối giờ. Vai trò theo phân công trong [README.md](../README.md):
**Dashboard, SLO & Alert** — dựng 6 panel, threshold, SLO, alert rules và runbook.
Evidence phải bàn giao: validator pass + ảnh dashboard.

Nhánh làm việc: `viet/dashboard-slo-alert` (đã merge `feat/logging-pii` và
`feature/tracing-prompt-version` vào để có đủ log/tracing thật khi build dashboard).

## 1. Checklist hoàn thành

| # | Việc | File | Trạng thái |
|---|---|---|---|
| 1 | Dashboard tĩnh (HTML) đọc trực tiếp `data/logs.jsonl`, đủ 6 panel đúng contract | [scripts/build_dashboard.py](../scripts/build_dashboard.py) → `dashboard/index.html` | ✅ |
| 2 | Dashboard **live** cho demo — Streamlit, có nút bật/tắt incident và chạy load test ngay trên UI | [dashboard/streamlit_app.py](../dashboard/streamlit_app.py) | ✅ |
| 3 | 3 alert rule symptom-based | [config/alert_rules.yaml](../config/alert_rules.yaml) | ✅ |
| 4 | Runbook chi tiết cho từng alert | [docs/alerts.md](../docs/alerts.md) | ✅ |
| 5 | SLO target + lý do, đồng bộ với dashboard contract | [config/slo.yaml](../config/slo.yaml) | ✅ |
| 6 | `python scripts/validate_dashboard.py` | — | ✅ `HỢP LỆ: 6/6 panel` |
| 7 | `python scripts/validate_logs.py` (sau khi merge logging/PII) | — | ✅ `100/100` (correlation ID, enrichment, PII scrubbing, schema đều pass) |
| 8 | Chứng minh panel Latency phản ứng đúng khi bật incident `rag_slow` | `dashboard/index.baseline.html` vs `dashboard/index.incident.html` | ✅ P95 150ms → 2651ms |
| 9 | `python -m pytest -q` không bị phá sau merge | — | ✅ 26 passed |
| 10 | Dán output text của 2 validator vào evidence | `submission/evidence/validate_dashboard_output.txt`, `validate_logs_output.txt` | ✅ |
| 11 | Điền mục 5 (Dashboard, SLO, alerts) + dòng đóng góp cá nhân trong REPORT.md | `submission/REPORT.md` | ✅ (còn TODO: điền tên thật/MSSV vào bảng mục 7) |
| 12 | Chụp ảnh dashboard runtime để nộp | `submission/evidence/dashboard_baseline.png`, `dashboard_incident.png` | ⬜ **Còn thiếu — cần làm thủ công bằng trình duyệt, xem hướng dẫn lệnh ở tin nhắn trước** |

## 2. Giải thích chi tiết từng phần đã làm

### 2.1 Dashboard tĩnh — `scripts/build_dashboard.py`

Đây là generator: đọc từng dòng JSON trong `data/logs.jsonl`, tính toán đúng những
phép tổng hợp mà `config/dashboard.yaml` yêu cầu, rồi in ra một file HTML tự chứa
(không cần internet, không cần cài Grafana/Streamlit) để mở bằng trình duyệt và
chụp ảnh:

- **Latency**: lọc event `response_sent`, tính percentile P50/P95/P99 của
  `latency_ms` bằng đúng công thức "nearest-rank" giống `app/metrics.py` (để hai
  nơi không lệch số nhau), vẽ 3 cột với threshold P95 ≤ 3000ms.
- **Traffic**: đếm event `request_received`, gom theo từng phút (khớp
  `query: count() by 1m` trong contract) để vẽ bar chart theo thời gian.
- **Errors**: `error_rate_pct = failed/received*100`, breakdown theo
  `error_type` (đếm bằng `Counter`).
- **Cost**: tổng `cost_usd` theo phút + tổng toàn cửa sổ, threshold ≤ $2.5.
- **Tokens**: tổng `tokens_in`/`tokens_out`, threshold ≤ 50,000/field.
- **Quality**: trung bình `quality_score`, hiển thị dạng "meter" (thanh đầy tới
  giá trị hiện tại, có vạch threshold ≥ 0.75).

Mỗi panel có badge **PASS/FAIL** màu xanh/đỏ kèm chữ (không chỉ dựa vào màu, để
người mù màu vẫn đọc được — theo chuẩn thiết kế biểu đồ accessible). Màu sắc lấy
từ palette đã kiểm định sẵn (blue ramp cho magnitude, status xanh/đỏ cho
pass/fail) — không tự chọn màu bừa.

Chạy lại bất cứ lúc nào log đổi:
```bash
python scripts/build_dashboard.py
```

### 2.2 Dashboard live cho demo — `dashboard/streamlit_app.py`

Đây là phần **mới thêm theo yêu cầu "tạo UI bằng Streamlit để nhóm demo test luồng
cho thuận tiện"**. Nó dùng lại (import) đúng logic tính toán từ
`scripts/build_dashboard.py` — không viết lại công thức lần hai — nhưng hiển thị
bằng Streamlit + Altair để:

- Tự động **refresh mỗi 30 giây** (`st.fragment(run_every=30)`) đúng theo
  `dashboard.yaml.refresh_seconds`, không cần bấm F5.
- Có **sidebar điều khiển demo**:
  - Bật/tắt incident practice (`rag_slow` / `tool_fail` / `cost_spike`) bằng nút
    bấm — gọi thẳng `/incidents/{name}/enable|disable`, không cần gõ lệnh terminal.
  - Nút "Run load test" — gửi toàn bộ `data/sample_queries.jsonl` tới `/chat`
    ngay trong UI, có progress bar.
- Bảng **"Recent logs"** ở cuối trang, hiện `correlation_id` của 20 request gần
  nhất — để khi demo, cả nhóm chỉ 1 cửa sổ vẫn nối được
  **Metrics (panel) → Logs (bảng) → Trace (mở Langfuse bằng đúng correlation_id
  đó)** mà không phải chuyển qua lại nhiều terminal/tab.

Chạy:
```bash
streamlit run dashboard/streamlit_app.py
```
Cần API (`uvicorn`) đang chạy song song ở `http://127.0.0.1:8000` thì các nút mới
hoạt động; nếu API tắt, phần 6 panel bên dưới vẫn đọc được `data/logs.jsonl` bình
thường (chỉ mất phần điều khiển).

**Vì sao có logic `call_with_retry`?** — xem mục 3 bên dưới, đây là cách né một
lỗi hạ tầng đã phát hiện được (server reload liên tục), không phải bug của
Streamlit.

### 2.3 Alert rules & runbook

`config/alert_rules.yaml` — 3 alert, cả 3 đều **symptom-based** (dựa trên triệu
chứng người dùng thấy được, không dựa tên hàm nội bộ):

| Alert | Severity | Điều kiện |
|---|---|---|
| `high_latency_p95` | Critical | P95 latency > 3000ms, duy trì 5 phút |
| `elevated_error_rate` | Critical | Error rate > 2%, duy trì 5 phút |
| `quality_score_degradation` | Medium | Mean quality_score < 0.75, duy trì 15 phút |

`docs/alerts.md` điền đủ cho mỗi alert: SLI/SLO liên quan, ảnh hưởng người dùng,
3 bước kiểm tra đầu tiên, mitigation tạm thời, owner. Ví dụ tư duy: alert 3 dùng
cửa sổ 15 phút (dài hơn 2 alert kia) vì quality_score là proxy dao động nhiều
theo từng câu hỏi đơn lẻ hơn latency/error — cửa sổ ngắn dễ báo giả.

### 2.4 SLO — `config/slo.yaml`

Không tạo bộ số riêng — giữ đúng giá trị threshold đã có trong
`config/dashboard.yaml` để dashboard và SLO không lệch nhau, chỉ bổ sung ghi chú
giải thích lý do cho `latency_p95_ms` (99.5% request trong 28 ngày phải đạt P95 ≤
3000ms).

## 3. Phát hiện quan trọng: lỗi hạ tầng khi chạy load test

Khi chạy `python scripts/load_test.py --concurrency 5`, request đầu tiên luôn
thành công nhưng các request sau đó báo `WinError 10061 (connection refused)`.
Đã điều tra và xác định nguyên nhân: `uvicorn --reload` đang theo dõi **toàn bộ
thư mục project**, bao gồm cả `data/`. Mỗi lần một request được xử lý, server ghi
thêm dòng vào `data/logs.jsonl` → uvicorn coi đó là "file thay đổi" → tự restart
server → trong lúc restart (1-2 giây), mọi request khác bị từ chối kết nối.

**Không sửa app code hay cách chạy server của nhóm** (ngoài phạm vi vai trò
Dashboard) — thay vào đó, `streamlit_app.py` và các script kiểm chứng của tôi tự
retry (chờ ~1.5s rồi gọi lại, tối đa 6 lần) để không bị ảnh hưởng bởi hiện tượng
này. **Khuyến nghị cho cả nhóm** (đặc biệt vai trò Logging & PII / người chạy
server chính): nếu muốn `load_test.py` chạy mượt không cần retry, khởi động lại
server với:
```bash
uvicorn app.main:app --reload --reload-dir app --env-file .env
```
(giới hạn phạm vi theo dõi reload về mỗi `app/`, không còn theo dõi `data/`).

## 4. Bằng chứng runtime: dashboard phản ứng đúng với incident

Đã reset `data/logs.jsonl` (file này nằm trong `.gitignore`, không ảnh hưởng
git/đồng đội) để có dữ liệu sạch 100% sau khi logging/PII đã merge, rồi làm lại
đúng quy trình trong [docs/DASHBOARD_SETUP.md](../docs/DASHBOARD_SETUP.md):

| Bước | Lệnh | P50 / P95 / P99 latency | Traffic |
|---|---|---|---|
| Baseline | `load_test.py` (20 request) | 150 / **150** / 150 ms | 20 |
| Bật `rag_slow` | `inject_incident.py --scenario rag_slow` | — | — |
| Load lại cùng input | 10 request | (từng request 10–13 giây) | — |
| Dashboard cửa sổ 60 phút (baseline + incident cộng dồn) | `build_dashboard.py` | 150 / **2651** / 2651 ms | 30 |
| Tắt incident | `inject_incident.py --scenario rag_slow --disable` | — | — |

→ P95 tăng từ **150ms → 2651ms** — panel Latency phản ứng đúng hướng và rõ rệt
như yêu cầu. Hai file `dashboard/index.baseline.html` và
`dashboard/index.incident.html` lưu lại snapshot trước/sau để đối chiếu khi chụp
evidence.

## 5. Kết quả kiểm tra kỹ thuật cuối cùng

```text
$ python scripts/validate_dashboard.py
HỢP LỆ: 6/6 panel có trong dashboard contract.

$ python scripts/validate_logs.py
Total log records analyzed: 62
Records with missing required fields: 0
Records with missing enrichment (context): 0
Unique correlation IDs found: 32
Potential PII leaks detected: 0
Estimated Score: 100/100

$ python -m pytest -q
26 passed
```

## 6. Việc còn lại (chỉ thao tác thủ công bằng trình duyệt)

- [ ] Mở `dashboard/index.html` (hoặc `streamlit run dashboard/streamlit_app.py`)
      bằng trình duyệt thật, chụp ảnh thấy rõ tên panel/time range/đơn vị/threshold
      → lưu vào `submission/evidence/dashboard_baseline.png` (và tuỳ chọn
      `dashboard_incident.png` sau khi bật `rag_slow` một lần nữa để có ảnh so sánh).
- [ ] Sau khi chụp, thêm dòng `Evidence dashboard: evidence/dashboard_baseline.png`
      vào mục 5 của `submission/REPORT.md` (đã điền sẵn phần còn lại).
- [ ] Sửa dòng "TODO: điền tên (MSSV)" trong bảng mục 7 của `submission/REPORT.md`
      thành tên thật + MSSV của bạn.
- [ ] Commit + push (xem hướng dẫn lệnh Claude đã đưa — chạy `git status` trước
      để soát lại danh sách file).

## 7. File đã thay đổi/thêm trên nhánh `viet/dashboard-slo-alert`

- `scripts/build_dashboard.py` (mới) — generator dashboard tĩnh
- `dashboard/streamlit_app.py` (mới) — UI live cho demo
- `dashboard/index.html`, `index.baseline.html`, `index.incident.html` (mới,
  sinh ra — có thể loại khỏi commit nếu nhóm muốn gọn, chỉ cần giữ ảnh chụp)
- `config/alert_rules.yaml`, `docs/alerts.md`, `config/slo.yaml` (điền TODO)
- `requirements.txt` (+ `streamlit`, `altair`, `pandas`)
- `submission/ROLE_DASHBOARD_SLO_SUMMARY.md` (file này)
- Đã merge vào nhánh: `feat/logging-pii`, `feature/tracing-prompt-version`

## 8. Câu hỏi có thể bị hỏi khi demo (B1 rubric)

- **Vì sao P95 thay vì trung bình (mean)?** Mean bị pha loãng bởi các request
  nhanh, không phản ánh trải nghiệm của nhóm người dùng chậm nhất; P95 là chuẩn
  phổ biến cho latency SLO.
- **Vì sao alert dựa trên triệu chứng (symptom-based)?** Alert cần báo đúng lúc
  người dùng bị ảnh hưởng, không phụ thuộc nguyên nhân nội bộ là RAG chậm, LLM
  chậm hay network — tránh phải sửa alert mỗi khi đổi implementation.
- **Vì sao alert Quality dùng cửa sổ 15 phút, dài hơn Latency/Error (5 phút)?**
  `quality_score` là proxy, dao động nhiều theo từng câu hỏi hơn latency/error;
  cửa sổ dài hơn tránh cảnh báo giả.
- **Dashboard lấy dữ liệu từ đâu, có cần Langfuse không?** Không — nguồn chuẩn là
  `data/logs.jsonl` theo đúng quy định README; Langfuse chỉ dùng để mở
  trace/prompt version khi điều tra sâu hơn.
- **Vì sao load_test đôi lúc lỗi "connection refused" lúc đầu buổi?** Đã tìm ra:
  `uvicorn --reload` theo dõi cả `data/`, mỗi request ghi log lại kích hoạt
  restart — xem mục 3. Đã né bằng retry logic trong tool demo, không phải lỗi ở
  phần logging hay dashboard.
