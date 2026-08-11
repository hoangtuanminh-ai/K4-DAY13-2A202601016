# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:B2-2
- Repository URL:https://github.com/hoangtuanminh-ai/Day13-K4-B2-2.git
- Commit SHA cuối:
### Thành viên và vai trò

* **Lê Văn Tuấn** (Lead): Tracing & Prompt Version
* **Hoàng Tuấn Minh**: Incident, Report & Demo
* **Cao Hương Giang**: Logging & PII
* **Vũ Hoàng Việt**: Dashboard, SLO & Alert

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`:
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence correlation ID:
- Evidence PII redaction:
- Evidence trace waterfall: evidence/trace_waterfall.png
- Giải thích một span đáng chú ý: Span `run` (generation) là span tốn thời gian nhất (~150ms), đây là bước agent gọi LLM (FakeLLM) để sinh câu trả lời. Bên trong span này chứa thông tin `prompt_version`, `prompt_label`, `doc_count`, `cost_usd` — cho thấy toàn bộ pipeline từ lấy tài liệu (RAG) đến sinh kết quả.

## 4. Prompt versioning

- Prompt name: day13-chat
- Version/label baseline: Version 1 / label `baseline` + `production`
- Version/label candidate: Version 2 / label `candidate`
- Trace ID của mỗi version:
  - Version 1 (baseline): `a6a260c4e46f434b25897246f760fbf6`
  - Version 2 (candidate): `6f8390db9bc2c53b6e331a1d8a06d771`
- Bằng chứng đổi label hoặc rollback: evidence/prompt_rollback1.png (sau rollback) và evidence/prompt_rollback2.png (trước rollback)

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.` (evidence/validate_dashboard_output.txt)
- Kết quả `validate_logs.py`: `100/100` — schema, correlation ID, enrichment, PII scrubbing đều pass (evidence/validate_logs_output.txt)
- Evidence dashboard: `dashboard/index.html` (generator: `scripts/build_dashboard.py`, đọc `data/logs.jsonl` theo đúng `config/dashboard.yaml`); bản live cho demo: `streamlit run dashboard/streamlit_app.py`. Ảnh chụp: evidence/dashboard_baseline.png, evidence/dashboard_incident.png *(chờ chụp thủ công)*.
- Bằng chứng dashboard phản ứng đúng khi bật incident `rag_slow`: latency P95 tăng từ 150ms (baseline) lên 2651ms (khi incident bật), traffic 20 → 30 request trong cửa sổ 60 phút — chi tiết ở `submission/ROLE_DASHBOARD_SLO_SUMMARY.md` mục 4.
- SLO đã chọn và lý do: giữ đúng threshold trong `config/dashboard.yaml` để dashboard và SLO đồng nhất — `latency_p95_ms ≤ 3000ms` (target 99.5%/28d), `error_rate_pct ≤ 2%` (99.0%), `daily_cost_usd ≤ 2.5` (100.0%), `quality_score_avg ≥ 0.75` (95.0%). Xem `config/slo.yaml`.
- Alert rules và runbook: 3 alert symptom-based trong `config/alert_rules.yaml` (`high_latency_p95` critical/5m, `elevated_error_rate` critical/5m, `quality_score_degradation` medium/15m — cửa sổ dài hơn vì quality_score dao động nhiều hơn theo từng câu hỏi đơn lẻ), runbook đầy đủ (SLI/SLO, ảnh hưởng người dùng, 3 bước kiểm tra đầu, mitigation, owner) trong `docs/alerts.md`.

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Lê Văn Tuấn (2A202601016) | Tracing & Prompt Version: tạo prompt day13-chat V1/V2 trên Langfuse, gán labels baseline/candidate/production, sinh 81 traces với metadata đầy đủ, thực hiện rollback và lưu evidence | (cập nhật sau khi push) | Cách dùng Langfuse để quản lý prompt version và truy xuất trace theo từng phiên bản |
| TODO: điền tên (MSSV) — nhánh `viet/dashboard-slo-alert` | Dashboard, SLO & Alert: viết `scripts/build_dashboard.py` sinh dashboard tĩnh 6 panel đúng contract từ `data/logs.jsonl`, viết `dashboard/streamlit_app.py` làm UI demo live (auto-refresh, nút bật/tắt incident, chạy load test), điền `config/alert_rules.yaml` + `docs/alerts.md` (3 alert symptom-based có runbook), điền lý do target trong `config/slo.yaml`, xác nhận `validate_dashboard.py` 6/6 và `validate_logs.py` 100/100 sau khi merge logging/tracing | (cập nhật sau khi push) | P95 phản ánh trải nghiệm người dùng chậm nhất tốt hơn mean; alert nên symptom-based để không phải sửa lại khi đổi implementation nội bộ; phát hiện `uvicorn --reload` theo dõi cả `data/` gây restart liên tục khi load test |
