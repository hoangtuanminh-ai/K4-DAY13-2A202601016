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

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

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
