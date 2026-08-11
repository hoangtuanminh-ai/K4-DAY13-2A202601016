# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: B2-2
- Repository URL: https://github.com/hoangtuanminh-ai/Day13-K4-B2-2.git
- Commit SHA cuối: (cập nhật sau khi push)
### Thành viên và vai trò

* **Lê Văn Tuấn** (2A202601016): Tracing & Prompt Version (Lead)
* **Hoàng Tuấn Minh** (2A202601500): Incident, Report & Demo
* **Cao Hương Giang** (2A202601420): Logging & PII
* **Vũ Hoàng Việt** (2A202601250): Dashboard, SLO & Alert

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 100/100
- Tổng số traces (unique correlation IDs): 200
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard: `dashboard/streamlit_app.py`

## 3. Logging và tracing

- Evidence correlation ID: Có trong mọi log API.
- Evidence PII redaction: Đã scrub sạch PII (credit card, v.v.).
- Evidence trace waterfall: evidence/trace_waterfall.png
- Giải thích một span đáng chú ý: Span `run` (generation) là span tốn thời gian nhất (~150ms), đây là bước agent gọi LLM (FakeLLM) để sinh câu trả lời. Bên trong span này chứa thông tin `prompt_version`, `prompt_label`, `doc_count`, `cost_usd` — cho thấy toàn bộ pipeline từ lấy tài liệu (RAG) đến sinh kết quả.

## 4. Prompt versioning

- Prompt name: day13-chat
- Version/label baseline: Version 1 / label `baseline` + `production`
- Version/label candidate: Version 2 / label `candidate`
- Trace ID của mỗi version:
  - Version 1 (baseline): `req-715acb16`
  - Version 2 (candidate): `req-8cae2fd1`
- Bằng chứng đổi label hoặc rollback: evidence/prompt_rollback1.png (sau rollback) và evidence/prompt_rollback2.png (trước rollback)

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.` (evidence/validate_dashboard_output.txt)
- Kết quả `validate_logs.py`: `100/100` — schema, correlation ID, enrichment, PII scrubbing đều pass (evidence/validate_logs_output.txt)
- Evidence dashboard: `dashboard/index.html` (generator: `scripts/build_dashboard.py`, đọc `data/logs.jsonl` theo đúng `config/dashboard.yaml`); bản live cho demo: `streamlit run dashboard/streamlit_app.py`. Ảnh chụp: evidence/dashboard_baseline.png, evidence/dashboard_incident.png *(chờ chụp thủ công)*.
- Bằng chứng dashboard phản ứng đúng khi bật incident `rag_slow`: latency P95 tăng từ 150ms (baseline) lên > 12000ms (khi incident bật), traffic tăng vọt do xếp hàng chờ — chi tiết ở `submission/ROLE_DASHBOARD_SLO_SUMMARY.md` mục 4.
- SLO đã chọn và lý do: giữ đúng threshold trong `config/dashboard.yaml` để dashboard và SLO đồng nhất — `latency_p95_ms ≤ 3000ms` (target 99.5%/28d), `error_rate_pct ≤ 2%` (99.0%), `daily_cost_usd ≤ 2.5` (100.0%), `quality_score_avg ≥ 0.75` (95.0%). Xem `config/slo.yaml`.
- Alert rules và runbook: 3 alert symptom-based trong `config/alert_rules.yaml` (`high_latency_p95` critical/5m, `elevated_error_rate` critical/5m, `quality_score_degradation` medium/15m — cửa sổ dài hơn vì quality_score dao động nhiều hơn theo từng câu hỏi đơn lẻ), runbook đầy đủ (SLI/SLO, ảnh hưởng người dùng, 3 bước kiểm tra đầu, mitigation, owner) trong `docs/alerts.md`.

## 6. Điều tra challenge

- Challenge ID: `day13-k4-observability-v1`
- Triệu chứng từ metrics: Latency P95 tăng vọt vượt mốc 12,000ms (quá xa so với ngưỡng SLO 3,000ms). Biểu đồ Traffic cũng dồn ứ.
- Trace ID liên quan: `req-0df6b35d`, `req-cd524a31`, `req-f4d30b36` (tuỳ trace thực tế).
- Log line/correlation ID liên quan: `"correlation_id": "req-f4d30b36", "event": "response_sent", "latency_ms": 12670`
- Root cause: Hệ thống Retrieval (Vector Database) bị nghẽn cổ chai (bottleneck) khi phải nhận nhiều request song song (Concurrency). Mỗi request mất 2.5s và khóa luồng xử lý (DB_LOCK), dẫn đến hiện tượng xếp hàng chờ cộng dồn (request thứ 5 phải chờ tới hơn 12 giây).
- Fix action: Scale up / Scale out hạ tầng Vector Database, tối ưu index tìm kiếm, đồng thời áp dụng cơ chế Caching (Redis/Memcached) để trả lời nhanh các câu hỏi trùng lặp mà không cần query lại DB.
- Preventive measure: Thiết lập Alert cho chỉ số P95 Latency và DB Connection Pool. Tách riêng giới hạn Timeout cho phần Retrieval để nếu RAG chậm quá thì fallback về câu trả lời mặc định.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Lê Văn Tuấn (2A202601016) | Tracing & Prompt Version: tạo prompt day13-chat V1/V2 trên Langfuse, gán labels baseline/candidate/production, sinh 81 traces với metadata đầy đủ, thực hiện rollback và lưu evidence | (cập nhật sau khi push) | Cách dùng Langfuse để quản lý prompt version và truy xuất trace theo từng phiên bản |
| Vũ Hoàng Việt (2A202601250) | Dashboard, SLO & Alert: sinh dashboard tĩnh 6 panel từ data, UI demo live Streamlit, thiết lập alert rules, SLO, pass 100/100 validate. | (cập nhật sau khi push) | P95 phản ánh trải nghiệm người dùng thực tế; Alert cần symptom-based; Hiểu rõ bản chất event loop blocking trong FastAPI. |
| Hoàng Tuấn Minh (2A202601500) | Incident, Report & Demo: Trực tiếp điều tra root cause challenge, demo các scenario, tổng hợp báo cáo. | (cập nhật sau khi push) | Hiểu rõ hiện tượng thắt nút cổ chai (Bottleneck) làm dồn ứ traffic và đẩy latency P95 lên cao. |
| Cao Hương Giang (2A202601420) | Logging & PII: Scrubbing dữ liệu PII, cấu hình logging chuẩn JSON, inject correlation ID. | (cập nhật sau khi push) | Tầm quan trọng của việc sanitize log trước khi đẩy vào hệ thống giám sát để tránh lộ lọt PII. |
