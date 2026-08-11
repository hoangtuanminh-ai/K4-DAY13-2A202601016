# Role summary — Dashboard, SLO & Alert

Chuẩn bị cho demo cuối giờ. Vai trò theo phân công trong [README.md](../README.md):
**Dashboard, SLO & Alert** — dựng 6 panel, threshold, SLO, alert rules và runbook.
Evidence phải bàn giao: validator pass + ảnh dashboard.

## 1. Đã làm được (không cần chờ role khác)

| # | Việc | File | Trạng thái |
|---|---|---|---|
| 1 | Dựng dashboard runtime đọc trực tiếp `data/logs.jsonl`, sinh HTML tĩnh có đủ 6 panel đúng contract | [scripts/build_dashboard.py](../scripts/build_dashboard.py) → xuất ra `dashboard/index.html` | ✅ Xong |
| 2 | Điền 3 alert rule symptom-based | [config/alert_rules.yaml](../config/alert_rules.yaml) | ✅ Xong |
| 3 | Điền runbook chi tiết cho từng alert (severity, SLI/SLO, điều kiện, ảnh hưởng, 3 bước kiểm tra, mitigation, owner) | [docs/alerts.md](../docs/alerts.md) | ✅ Xong |
| 4 | Xác nhận/ghi rõ lý do target SLO latency (đồng bộ với `dashboard.yaml`) | [config/slo.yaml](../config/slo.yaml) | ✅ Xong |
| 5 | Chạy `validate_dashboard.py` | — | ✅ `HỢP LỆ: 6/6 panel` |
| 6 | Xác nhận panel Latency phản ứng đúng khi bật incident practice `rag_slow` | `dashboard/index.baseline.html` vs `dashboard/index.incident.html` | ✅ Xong (xem mục 3) |

**Không đổi** `config/dashboard.yaml` — đây là contract chấm điểm dùng chung, chỉ đọc và bám theo mapping của nó (xem [docs/DASHBOARD_SETUP.md](../docs/DASHBOARD_SETUP.md)).

## 2. Cách dashboard hoạt động

- Nguồn dữ liệu: `data/logs.jsonl` (không cần Langfuse — đúng như quy định trong README: "nguồn chuẩn của 6 panel dashboard là `data/logs.jsonl`").
- Công cụ: script Python tự viết (`scripts/build_dashboard.py`), không phụ thuộc thư viện ngoài ngoài `PyYAML`/stdlib đã có sẵn trong `requirements.txt` — không cần cài thêm Streamlit/Grafana.
- Mỗi lần log thay đổi, chạy lại:
  ```bash
  python scripts/build_dashboard.py
  ```
  rồi mở `dashboard/index.html` bằng trình duyệt để xem/chụp ảnh.
- 6 panel bám sát `config/dashboard.yaml`:
  1. **Latency** — bar P50/P95/P99 (ms), threshold P95 ≤ 3000ms
  2. **Traffic** — bar theo phút (request/phút), threshold ≥ 1 req/min
  3. **Errors** — error rate % (stat) + breakdown theo `error_type` (bar ngang)
  4. **Cost** — bar theo phút + tổng cửa sổ (USD), threshold ≤ $2.5
  5. **Tokens** — so sánh tổng tokens_in vs tokens_out, threshold ≤ 50,000/field
  6. **Quality** — meter mean `quality_score`, threshold ≥ 0.75
- Time range 60 phút, refresh contract 30s (ghi chú "regenerate script" vì đây là file tĩnh, không có server live-refresh).
- Mỗi panel có badge PASS/FAIL màu status (xanh/đỏ) so với threshold, không chỉ dựa vào màu — có label chữ đi kèm.

## 3. Bằng chứng runtime: dashboard phản ứng đúng với incident

Làm theo quy trình ở [docs/DASHBOARD_SETUP.md](../docs/DASHBOARD_SETUP.md):

| Bước | Lệnh | Kết quả |
|---|---|---|
| Baseline | `python scripts/load_test.py --concurrency 5` | P50=150ms, **P95=1400ms**, P99=1400ms, traffic=20, error=0%, cost=$0.0401 |
| Bật incident | `python scripts/inject_incident.py --scenario rag_slow` | `rag_slow: true` |
| Load lại cùng input | `python scripts/load_test.py --concurrency 5` | Latency từng request tăng lên **10,633–13,292 ms** (so với ~150–3,200ms lúc baseline) |
| Dashboard cửa sổ 60 phút (gộp cả baseline+incident) | `python scripts/build_dashboard.py` | P50=150ms, **P95=2,651ms** (tăng so với 1,400ms baseline), traffic=30 |
| Tắt incident | `python scripts/inject_incident.py --scenario rag_slow --disable` | `rag_slow: false` |

→ Panel Latency tăng đúng hướng khi `rag_slow` bật, đúng như mô tả trong DASHBOARD_SETUP.md ("P95 phải tăng rõ ràng"). File `dashboard/index.baseline.html` và `dashboard/index.incident.html` lưu lại hai snapshot để so sánh trước khi chụp ảnh cuối cùng.

**Lưu ý khi chụp evidence cuối:** `correlation_id` trả về `MISSING` trong output `load_test.py` — do phần **Logging & PII** (`app/main.py` TODO enrich context) và middleware correlation ID chưa hoàn thiện, không thuộc phạm vi vai trò này. Cần re-run `load_test.py` + `build_dashboard.py` và chụp lại ảnh **sau khi** đồng đội hoàn thiện phần đó, để log có đủ correlation ID/metadata khi demo nối Metrics → Traces → Logs.

## 4. SLO đã chọn (`config/slo.yaml`)

| SLI | Objective | Target (28d) | Đồng bộ với |
|---|---|---|---|
| `latency_p95_ms` | ≤ 3000ms | 99.5% | panel Latency threshold |
| `error_rate_pct` | ≤ 2% | 99.0% | panel Errors threshold |
| `daily_cost_usd` | ≤ 2.5 | 100.0% | panel Cost threshold |
| `quality_score_avg` | ≥ 0.75 | 95.0% | panel Quality threshold |

Lý do: giữ nguyên giá trị threshold đã có sẵn trong `config/dashboard.yaml` (contract chấm điểm) để SLO và dashboard nhất quán — không đặt ra hai bộ số khác nhau cho cùng một chỉ số.

## 5. Alert rules (`config/alert_rules.yaml` + `docs/alerts.md`)

| Alert | Severity | Điều kiện | Runbook |
|---|---|---|---|
| `high_latency_p95` | Critical | P95 latency > 3000ms, duy trì 5 phút | [docs/alerts.md#alert-1](../docs/alerts.md#alert-1) |
| `elevated_error_rate` | Critical | Error rate > 2%, duy trì 5 phút | [docs/alerts.md#alert-2](../docs/alerts.md#alert-2) |
| `quality_score_degradation` | Medium | Mean quality_score < 0.75, duy trì 15 phút | [docs/alerts.md#alert-3](../docs/alerts.md#alert-3) |

Cả 3 alert đều **symptom-based** (dựa trên triệu chứng người dùng thấy được: chậm, lỗi, chất lượng kém) thay vì tên hàm/service nội bộ, theo đúng yêu cầu trong template.

## 6. Việc còn lại trước khi nộp/demo

- [ ] Chụp ảnh dashboard **cuối cùng** (sau khi Logging & PII + Tracing xong) → lưu vào `submission/evidence/`
- [ ] Dán kết quả `validate_dashboard.py` vào `submission/evidence/`
- [ ] Điền mục "5. Dashboard, SLO và alerts" trong [submission/REPORT.md](REPORT.md) (kết quả validator, đường dẫn evidence, SLO đã chọn + lý do, alert/runbook)
- [ ] Điền dòng của mình vào bảng "Đóng góp cá nhân" (mục 7 của REPORT.md) với commit cụ thể
- [ ] Sau khi `config/challenge.json` được release: chạy lại `build_dashboard.py` để dashboard phản ánh đúng dữ liệu challenge trước khi demo

## 7. File đã thay đổi/thêm (dùng cho commit & bảng đóng góp cá nhân)

- `scripts/build_dashboard.py` (mới)
- `dashboard/index.html`, `dashboard/index.baseline.html`, `dashboard/index.incident.html` (mới, sinh ra — có thể không commit bản binary/snapshot phụ nếu nhóm muốn gọn, chỉ cần `index.html` + ảnh chụp)
- `config/alert_rules.yaml` (điền TODO)
- `docs/alerts.md` (điền TODO)
- `config/slo.yaml` (làm rõ note cho `latency_p95_ms`)
- `submission/ROLE_DASHBOARD_SLO_SUMMARY.md` (mới, file này)

## 8. Câu hỏi có thể bị hỏi khi demo (B1 rubric)

- **Vì sao P95 thay vì trung bình (mean)?** Mean bị pha loãng bởi các request nhanh, không phản ánh trải nghiệm của nhóm người dùng chậm nhất; P95 là chuẩn phổ biến cho latency SLO.
- **Vì sao alert dựa trên triệu chứng (symptom-based) chứ không phải nguyên nhân?** Vì alert nên báo đúng lúc người dùng bị ảnh hưởng, không phụ thuộc việc nguyên nhân là do RAG chậm, LLM chậm hay network — tránh phải sửa alert mỗi khi đổi implementation nội bộ.
- **Vì sao threshold Quality dùng cửa sổ 15 phút, dài hơn Latency/Error (5 phút)?** `quality_score` là proxy, dao động nhiều theo từng câu hỏi đơn lẻ hơn latency/error; cửa sổ dài hơn tránh cảnh báo giả (false positive) từ một vài câu trả lời kém ngẫu nhiên.
- **Dashboard lấy dữ liệu từ đâu, có cần Langfuse không?** Không — nguồn chuẩn là `data/logs.jsonl` theo đúng quy định trong README; Langfuse chỉ dùng để mở trace/prompt version khi điều tra sâu hơn.
