# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: `high_latency_p95`
- Severity: Critical
- SLI/SLO liên quan: `latency_p95_ms` ([config/slo.yaml](../config/slo.yaml)) — objective ≤ 3000ms, target 99.5%
- Điều kiện và thời gian duy trì: P95 của `response_sent.latency_ms` > 3000ms, duy trì liên tục 5 phút
- Ảnh hưởng tới người dùng: Người dùng chờ câu trả lời lâu bất thường, có thể gặp timeout ở phía client hoặc bỏ ngang phiên chat
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency trên dashboard, xác nhận P50/P95/P99 và thời điểm bắt đầu tăng
  2. Mở trace của một request chậm trong cùng khung giờ, tìm span chiếm nhiều thời gian nhất (ví dụ retrieval/RAG, gọi LLM, hoặc network)
  3. Đối chiếu log theo `correlation_id` của trace đó để xem có lỗi/timeout/retry ở downstream không
- Mitigation tạm thời: Bật lại incident practice tương ứng nếu là do RAG chậm (`python scripts/inject_incident.py --scenario rag_slow --disable` để tắt nếu đây là do inject); nếu do tải cao, giảm concurrency nguồn gây tải hoặc tạm thời giới hạn rate ở client
- Owner: Dashboard, SLO & Alert on-call (nhóm Day13)

## Alert 2

- Tên: `elevated_error_rate`
- Severity: Critical
- SLI/SLO liên quan: `error_rate_pct` ([config/slo.yaml](../config/slo.yaml)) — objective ≤ 2%, target 99.0%
- Điều kiện và thời gian duy trì: (`request_failed` / `request_received`) × 100 > 2%, duy trì liên tục 5 phút
- Ảnh hưởng tới người dùng: Một phần request trả lỗi 5xx, người dùng không nhận được câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors, xem breakdown theo `error_type` để biết lỗi nào chiếm đa số
  2. Mở trace của một request lỗi gần nhất, xác định span/exception gây lỗi
  3. Tra log `request_failed` cùng `correlation_id` để đọc `error_type` và `detail` cụ thể
- Mitigation tạm thời: Nếu lỗi tập trung ở một dependency (RAG/LLM mock), tắt incident đang inject hoặc rollback prompt/version vừa đổi bằng bước rollback trong [PROMPT_VERSIONING.md](PROMPT_VERSIONING.md); nếu lỗi do input không hợp lệ, trả thông báo lỗi rõ ràng hơn cho client thay vì retry vô hạn
- Owner: Dashboard, SLO & Alert on-call (nhóm Day13)

## Alert 3

- Tên: `quality_score_degradation`
- Severity: Medium
- SLI/SLO liên quan: `quality_score_avg` ([config/slo.yaml](../config/slo.yaml)) — objective ≥ 0.75, target 95.0%
- Điều kiện và thời gian duy trì: Mean `response_sent.quality_score` < 0.75, duy trì liên tục 15 phút (window dài hơn 2 alert trên vì quality proxy biến động nhiều hơn theo từng request đơn lẻ)
- Ảnh hưởng tới người dùng: Câu trả lời có xu hướng kém liên quan/kém chính xác hơn dù request vẫn thành công (không thấy qua error rate hay latency)
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Quality, xác nhận mean quality_score giảm và thời điểm bắt đầu giảm
  2. Kiểm tra `prompt_label`/`prompt_version` trên các trace gần thời điểm giảm — có vừa đổi label/rollback không (xem [PROMPT_VERSIONING.md](PROMPT_VERSIONING.md))
  3. Đọc `answer_preview` trong log `response_sent` của vài request quality thấp để xem lỗi nội dung là gì
- Mitigation tạm thời: Rollback prompt về version/label đã biết hoạt động tốt trước đó; nếu không liên quan prompt, kiểm tra nguồn RAG/context đầu vào có bị incident practice làm nhiễu không
- Owner: Dashboard, SLO & Alert on-call (nhóm Day13)
