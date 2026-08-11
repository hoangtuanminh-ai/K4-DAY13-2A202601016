# Hướng dẫn hoàn thành Lab Day 13 — Observability cho hệ thống AI

Tài liệu này viết theo đúng source code trong repo (đã đọc từng file, từng dòng) và đã kiểm chứng bằng cách chạy thật. Mỗi bước có: **file:dòng cần sửa → code đầy đủ → giải thích → lệnh kiểm chứng → output mong đợi**.

- Bản tóm tắt ngắn: [huong_dan_chi_tiet_roles.md](huong_dan_chi_tiet_roles.md)
- Quy định chấm điểm: [RUBRIC.md](RUBRIC.md) · Quy định thi: [RULES.md](RULES.md) · Nộp bài: [SUBMISSION.md](SUBMISSION.md)

> [!CAUTION]
> Theo [RULES.md](RULES.md): không hard-code output để vượt validator, không sửa `config/challenge.json`, không làm giả trace/screenshot/commit history. Mọi kết luận về incident phải kèm trace ID, log line hoặc metric cụ thể. Tài liệu này chỉ hướng dẫn hoàn thiện các khối `TODO` bằng logic thật.

---

## Mục lục

- [Phần 0 — Chung cho cả nhóm](#phần-0--chung-cho-cả-nhóm)
- [Phần 1 — Vai trò 1: Logging & PII](#phần-1--vai-trò-1-logging--pii)
- [Phần 2 — Vai trò 2: Tracing & Prompt Version](#phần-2--vai-trò-2-tracing--prompt-version)
- [Phần 3 — Vai trò 3: Dashboard, SLO & Alert](#phần-3--vai-trò-3-dashboard-slo--alert)
- [Phần 4 — Vai trò 4: Incident, Report & Demo](#phần-4--vai-trò-4-incident-report--demo)
- [Phần 5 — Phụ lục](#phần-5--phụ-lục)

---

# Phần 0 — Chung cho cả nhóm

## 0.1. Bài lab này thực chất là gì

Repo đã có một API AI chạy được: `POST /chat` → lấy tài liệu (fake RAG) → dựng prompt → gọi fake LLM → tính cost/quality → trả lời. Nó chạy đúng nhưng **không quan sát được**: log không có ID để lần theo, không có metadata, chưa nối với trace, chưa có dashboard, chưa có alert.

Toàn bộ bài lab nằm ở **4 khối `TODO`** cộng với **2 file config còn trống**:

| # | Vị trí | Thiếu gì | Vai trò | Điểm liên quan |
|---|---|---|---|---|
| 1 | [app/middleware.py:13-30](app/middleware.py#L13-L30) | correlation ID: clear → sinh ID → bind → trả header | 1 | A1 (10đ) |
| 2 | [app/main.py:47](app/main.py#L47) | bind metadata `user_id_hash / session_id / feature / model / env` | 1 | A1 |
| 3 | [app/logging_config.py:45](app/logging_config.py#L45) | đăng ký processor `scrub_event` vào chuỗi structlog | 1 | A1 |
| 4 | [app/pii.py:11](app/pii.py#L11) | bổ sung pattern PII | 1 | A1 |
| 5 | [config/alert_rules.yaml](config/alert_rules.yaml) | 3 alert đang là chữ `TODO` | 3 | A1 |
| 6 | [docs/alerts.md](docs/alerts.md) | 3 runbook đang trống | 3 | A1 |

Ngoài code, còn 4 việc **không phải code**: tạo prompt v1/v2 trên Langfuse (vai trò 2), dựng dashboard runtime (vai trò 3), điều tra challenge (vai trò 4), viết `submission/REPORT.md` + thu evidence (cả nhóm).

> [!IMPORTANT]
> `app/tracing.py`, `app/prompt_management.py`, `app/metrics.py`, `app/challenge.py`, `config/dashboard.yaml`, `config/slo.yaml` và toàn bộ `scripts/` **đã hoàn chỉnh**. Đừng sửa. 22 public test đang xanh, sửa vào là gãy.

## 0.2. Setup (10 phút, làm một lần)

```powershell
# Windows PowerShell, tại thư mục repo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở **2 terminal** và giữ nguyên suốt buổi lab:

```powershell
# Terminal 1 — API (để chạy liên tục)
uvicorn app.main:app --reload --env-file .env

# Terminal 2 — chạy lệnh
python -m pytest -q
```

Kiểm chứng:

```powershell
curl.exe http://127.0.0.1:8000/health
```

Kỳ vọng: `{"ok":true,"tracing_enabled":false,"incidents":{"rag_slow":false,"tool_fail":false,"cost_spike":false}}`
(`tracing_enabled` sẽ thành `true` sau khi vai trò 2 điền key Langfuse.)

`python -m pytest -q` phải ra **`22 passed`**. Nếu chưa, dừng lại sửa môi trường trước khi làm gì khác.

## 0.3. Checkpoint 0 — LẤY BASELINE TRƯỚC KHI SỬA BẤT KỲ DÒNG NÀO

[CHECKPOINTS.md](CHECKPOINTS.md) bắt buộc lưu baseline. Đây cũng là bằng chứng "trước/sau" đẹp nhất cho báo cáo:

```powershell
python scripts/load_test.py           # Terminal 2, khi API đang chạy
python scripts/validate_logs.py
```

Output baseline (đã kiểm chứng trên repo này):

```text
--- Lab Verification Results ---
Total log records analyzed: 22
Records with missing required fields: 20
Records with missing enrichment (context): 20
Unique correlation IDs found: 0
Potential PII leaks detected: 0

--- Grading Scorecard (Estimates) ---
- [FAILED] Missing required fields (ts, level, etc.)
- [FAILED] Correlation ID propagation (less than 2 unique IDs)
- [FAILED] Log enrichment (missing user_id_hash, etc.)
+ [PASSED] PII scrubbing

Estimated Score: 30/100
```

**Chụp màn hình ngay** → lưu `submission/evidence/00-baseline-validate-logs.png`.

> [!NOTE]
> Baseline đã `[PASSED] PII scrubbing` rồi. Không phải nhóm bạn giỏi — mà vì [app/main.py:53](app/main.py#L53) gọi sẵn `summarize_text()` trước khi log. Đọc kỹ [Bước 1.3](#bước-13--đăng-ký-scrub_event-vào-chuỗi-processor) để hiểu vì sao vẫn phải làm `scrub_event` và giải thích thế nào khi bị hỏi.

## 0.4. Timeline 4 giờ và điểm bàn giao

Bốn vai trò **không song song hoàn toàn** — có 3 chỗ chặn nhau:

```text
0:00 ──────── 0:30 ──────── 1:30 ──────── 2:30 ──────── 3:30 ──── 4:00
  Checkpoint 0   Checkpoint 1   Checkpoint 2   Checkpoint 3   Wrap-up

VT1  [setup]  [====== code logging + PII ======]  ↘ bàn giao logs.jsonl
VT2  [setup]  [ xin key, tạo prompt v1/v2 trên Langfuse ]  ↘ bàn giao trace
VT3  [setup]  [ đọc contract, cài streamlit, viết code ] [ dựng dashboard ] ↘ bàn giao metrics
VT4  [setup]  [ đọc RULES + docs, soạn khung REPORT.md ] [ ĐIỀU TRA ] [ viết report + demo ]
```

| Bàn giao | Từ → đến | Nội dung | Deadline |
|---|---|---|---|
| B1 | VT1 → VT3 | `data/logs.jsonl` có `correlation_id` + 4 trường enrichment | 1:30 |
| B2 | VT2 → VT4 | Langfuse project + ≥10 trace có `prompt_source: langfuse` | 2:30 |
| B3 | VT3 → VT4 | Dashboard chạy được để đọc triệu chứng | 2:30 |

**Trong lúc chờ**, không ai được ngồi không:
- VT3 trước 1:30: chạy `python scripts/validate_dashboard.py` lấy bằng chứng ngay, đọc [config/dashboard.yaml](config/dashboard.yaml), cài streamlit, viết xong code dashboard (test bằng chính `data/logs.jsonl` baseline).
- VT4 trước 2:30: đọc [RULES.md](RULES.md), [docs/GUIDE.md](docs/GUIDE.md), điền mục 1 của `submission/REPORT.md`, và **tập trước với `--scenario rag_slow`** (practice luôn được phép).

## 0.5. Điểm đến từ đâu ([RUBRIC.md](RUBRIC.md))

| Mục | Điểm | Ai chịu trách nhiệm chính |
|---|---:|---|
| A1 — JSON logging, correlation ID, metadata, PII | 10 | VT1 |
| A1 — traces, prompt v1/v2, label, rollback | 10 | VT2 |
| A1 — dashboard contract, 6 panel, SLO, alert, runbook | 10 | VT3 |
| A2 — điều tra incident (triệu chứng, root cause, Metrics→Traces→Logs, fix + preventive) | 10 | VT4 |
| A3 — demo, hệ thống chạy được, mỗi người giải thích phần mình | 20 | **cả 4** |
| B1 — báo cáo cá nhân + trả lời được câu hỏi | 20 | **mỗi cá nhân** |
| B2 — commit/PR cụ thể, khớp với khai báo trong report | 20 | **mỗi cá nhân** |
| Bonus | +10 | tuỳ chọn |

> [!WARNING]
> **40/100 điểm là điểm cá nhân.** Người làm hộ nhau sẽ mất B1 và B2. Mỗi người phải tự commit phần của mình bằng tài khoản Git của mình, và phải trả lời được câu hỏi về phần đó. Mỗi vai trò trong tài liệu này đều có mục "Vấn đáp" ở cuối — học thuộc phần của mình.

## 0.6. Quy ước đặt tên evidence

[SUBMISSION.md](SUBMISSION.md) yêu cầu 10 loại evidence. Đặt tên theo số thứ tự để dễ dẫn link trong report:

```text
submission/evidence/
├── 00-baseline-validate-logs.png        # VT1 — trước khi sửa (Checkpoint 0)
├── 01-validate-logs-final.png           # VT1 — 100/100
├── 02-log-correlation-id.png            # VT1 — 2 dòng cùng correlation_id
├── 03-log-pii-redacted.png              # VT1 — [REDACTED_EMAIL] trong log
├── 04-langfuse-trace-list.png           # VT2 — danh sách >= 10 trace
├── 05-langfuse-trace-waterfall.png      # VT2 — 1 waterfall đầy đủ
├── 06-prompt-two-versions.png           # VT2 — v1 + v2 trên UI
├── 07-trace-prompt-baseline.png         # VT2 — trace gắn label baseline
├── 08-trace-prompt-candidate.png        # VT2 — trace gắn label candidate
├── 09-prompt-rollback.png               # VT2 — trước/sau khi rollback production
├── 10-validate-dashboard.png            # VT3 — "HỢP LỆ: 6/6 panel"
├── 11-dashboard-baseline.png            # VT3 — 6 panel, bình thường
├── 12-dashboard-incident.png            # VT3 — 6 panel, khi rag_slow bật
├── 13-challenge-metrics.png             # VT4 — triệu chứng từ /metrics
├── 14-challenge-trace.png               # VT4 — span chậm trên Langfuse
├── 15-challenge-logs.png                # VT4 — log cùng correlation_id
└── 16-challenge-loadtest-output.png     # VT4 — output client-side của load_test
```

---

# Phần 1 — Vai trò 1: Logging & PII

> **Mục tiêu:** `python scripts/validate_logs.py` từ 30/100 lên **100/100** với đủ 4 dòng `+ [PASSED]`.
> **Bạn chặn ai:** VT3 và VT4 không làm được gì tử tế trước khi bạn xong. **Làm nhanh nhất có thể.**

## Bước 1.1 — Correlation ID trong middleware

**File:** [app/middleware.py](app/middleware.py) — thay toàn bộ nội dung file bằng:

```python
from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Xoá context của request trước để không rò rỉ metadata sang request này.
        clear_contextvars()

        # 2. Nhận correlation ID từ upstream nếu có, không thì tự sinh.
        #    Header trong Starlette là case-insensitive nên "x-request-id" bắt được cả
        #    "X-Request-ID" client gửi lên.
        correlation_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:8]}"

        # 3. Bind vào structlog contextvars. Mọi log sinh ra sau đây trong cùng request
        #    sẽ tự có trường correlation_id nhờ processor merge_contextvars.
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)

        # 4. Trả ID về client để họ đối chiếu được với log của mình.
        #    Header value bắt buộc là chuỗi.
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"

        return response
```

### Vì sao là `req-<8 hex>` chứ không phải `str(uuid.uuid4())`

> [!CAUTION]
> **Dùng UUID đầy đủ sẽ làm bạn mất 30 điểm PII một cách oan uổng.**
>
> [scripts/validate_logs.py:12](scripts/validate_logs.py#L12) có detector CCCD là `\b\d{12}\b`. UUID chuẩn có dạng `550e8400-e29b-41d4-a716-446655440000` — nhóm cuối cùng dài đúng **12 ký tự**, và dấu `-` là word boundary. Khi 12 ký tự đó tình cờ toàn chữ số, validator kết luận log của bạn lộ số CCCD.
>
> Đo thật trên máy này: **10/2000 UUID (0,5%) bị dính**. Một lượt `load_test.py` sinh ~21 dòng log có ID → xác suất dính ít nhất một dòng là **~10%**. Cứ 10 nhóm dùng UUID thì 1 nhóm mất 30 điểm mà không hiểu tại sao.
>
> Format `req-` + 8 ký tự hex tối đa chỉ có 8 chữ số → **0/2000** với cả `cccd` lẫn `phone_vn`. Đây cũng đúng format mà comment TODO gốc gợi ý.

### Vì sao header lấy từ biến local, không lấy từ contextvars

Đã kiểm chứng trên Starlette 0.48 (bản đang cài):

```text
endpoint nhìn thấy lúc vào    : {'correlation_id': 'req-deadbeef'}
endpoint nhìn thấy sau khi bind: {'correlation_id': ..., 'user_id_hash': ..., 'feature': ...}
middleware nhìn thấy sau đó    : {'correlation_id': 'req-deadbeef'}
```

`BaseHTTPMiddleware.call_next` chạy endpoint bằng `task_group.start_soon(coro)`, mà `start_soon` **copy** context tại thời điểm spawn. Nên:

- Bind **trước** `await call_next(request)` → endpoint nhìn thấy. ✅
- Những gì endpoint bind thêm **không** quay ngược về middleware. ❌ → header phải dùng biến `correlation_id` local.

### Kiểm chứng

```powershell
# Terminal 1 tự reload nhờ --reload
curl.exe -i -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"user_id\":\"u01\",\"session_id\":\"s01\",\"feature\":\"qa\",\"message\":\"hello\"}"
```

Kỳ vọng trong phần header của response:

```text
x-request-id: req-3f9a1c2b
x-response-time-ms: 168.4
```

Và trong body JSON, `correlation_id` phải là `req-3f9a1c2b` chứ không còn là `MISSING`.

Thử luôn trường hợp client tự gửi ID:

```powershell
curl.exe -i -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -H "x-request-id: req-fromclient" -d "{\"user_id\":\"u01\",\"session_id\":\"s01\",\"feature\":\"qa\",\"message\":\"hello\"}"
```

Kỳ vọng: `x-request-id: req-fromclient` (đi mượn ID của upstream, không sinh mới).

---

## Bước 1.2 — Bind metadata cho log API

**File:** [app/main.py:47](app/main.py#L47) — thay 2 dòng comment TODO bằng:

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    # Bind TRƯỚC dòng log đầu tiên, để cả request_received / response_sent / request_failed
    # đều mang cùng bộ metadata. user_id KHÔNG BAO GIỜ được log thô — chỉ log hash.
    bind_contextvars(
        user_id_hash=hash_user_id(body.user_id),
        session_id=body.session_id,
        feature=body.feature,
        model=agent.model,
        env=os.getenv("APP_ENV", "dev"),
    )

    log.info(
        "request_received",
        service="api",
        payload={"message_preview": summarize_text(body.message)},
    )
    ...  # phần còn lại giữ nguyên
```

**Không cần thêm import nào.** [app/main.py:3](app/main.py#L3), [:7](app/main.py#L7), [:14](app/main.py#L14) đã import sẵn `os`, `bind_contextvars` và `hash_user_id` — chúng đang bị bỏ không, đó chính là gợi ý của đề bài.

Giải thích từng trường:

| Trường | Giá trị | Vì sao |
|---|---|---|
| `user_id_hash` | `hash_user_id(body.user_id)` → sha256 cắt 12 ký tự ([app/pii.py:27](app/pii.py#L27)) | Vẫn nhóm được log theo người dùng mà không lưu danh tính. Cũng chính là `user_id` mà Langfuse nhận ở [app/agent.py:47](app/agent.py#L47) → đây là cầu nối log ↔ trace. |
| `session_id` | `body.session_id` | Nối nhiều request của cùng phiên; Langfuse cũng nhận trường này. |
| `feature` | `body.feature` | Cắt lát metric theo tính năng; challenge K4 nhắm vào `feature=monitoring`. |
| `model` | `agent.model` = `"claude-sonnet-4-5"` | Đổi model là đổi cost/latency — không có trường này thì không giải thích được biến động. |
| `env` | `os.getenv("APP_ENV", "dev")` | Tách log dev/prod. |

> [!NOTE]
> [scripts/validate_logs.py:8](scripts/validate_logs.py#L8) chỉ đòi 4 trường (`user_id_hash`, `session_id`, `feature`, `model`) và chỉ với record `service == "api"`. `env` là yêu cầu của [CHECKPOINTS.md](CHECKPOINTS.md) chứ không phải của script — vẫn phải có, giám khảo đọc checkpoint.
>
> Vì middleware đã `clear_contextvars()` mỗi request, các log `service: "control"` (bật/tắt incident) và `app_started` sẽ không mang enrichment — **đúng như vậy**, validator không phạt vì chúng không phải `service == "api"`.

---

## Bước 1.3 — Đăng ký `scrub_event` vào chuỗi processor

**File:** [app/logging_config.py:45](app/logging_config.py#L45) — bỏ comment, đặt đúng vị trí:

```python
def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            scrub_event,                       # <-- PHẢI đứng trước JsonlFileProcessor
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            JsonlFileProcessor(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
```

> [!IMPORTANT]
> **Vị trí quan trọng hơn bản thân dòng code.** Chuỗi processor của structlog chạy tuần tự từ trên xuống. `JsonlFileProcessor.__call__` ([app/logging_config.py:19-21](app/logging_config.py#L19-L21)) **tự render JSON và tự ghi xuống đĩa bên trong nó** — nó không đợi `JSONRenderer` ở cuối:
>
> ```python
> rendered = structlog.processors.JSONRenderer()(logger, method_name, event_dict)
> with LOG_PATH.open("a", encoding="utf-8") as f:
>     f.write(rendered + "\n")
> ```
>
> Nếu bạn đặt `scrub_event` **sau** `JsonlFileProcessor()`, PII đã nằm trong `data/logs.jsonl` rồi — scrub xong cũng vô nghĩa. Đây chính là ý của [docs/GUIDE.md](docs/GUIDE.md): *"dữ liệu phải được scrub trước khi JSON được render và ghi xuống file"*.

### Nói thật về điểm PII (rất quan trọng khi vấn đáp)

`validate_logs.py` đã báo `+ [PASSED] PII scrubbing` **từ trước khi bạn làm gì cả**. Lý do: [app/main.py](app/main.py) gọi `summarize_text()` ngay tại chỗ log, mà `summarize_text` đã gọi `scrub_text` bên trong ([app/pii.py:22-24](app/pii.py#L22-L24)).

Vậy `scrub_event` để làm gì? Nó là **lớp phòng thủ thứ hai**:

- Lớp 1 (`summarize_text` tại call site): phụ thuộc việc lập trình viên nhớ gọi. Ai đó thêm một `log.info(..., payload={"raw": body.message})` là thủng.
- Lớp 2 (`scrub_event` trong pipeline): chặn ở cửa duy nhất mà **mọi** log đều phải đi qua. Không ai quên được.

**Đừng chụp ảnh log không có email rồi bảo "nhờ scrub_event"** — giám khảo hỏi một câu là lộ. Bằng chứng đúng là test gọi thẳng `scrub_event` với payload thô. Tạo `tests/test_logging_scrub.py`:

```python
from __future__ import annotations

from app.logging_config import scrub_event


def test_scrub_event_redacts_payload_that_call_site_forgot_to_summarize() -> None:
    event_dict = {
        "event": "request_received",
        "service": "api",
        "correlation_id": "req-1a2b3c4d",
        "payload": {
            # Mô phỏng một lời gọi log quên dùng summarize_text()
            "raw_message": "Liên hệ student@vinuni.edu.vn hoặc 0987654321, thẻ 4111 1111 1111 1111",
            "doc_count": 3,
        },
    }

    scrubbed = scrub_event(None, "info", event_dict)

    raw = scrubbed["payload"]["raw_message"]
    assert "student@vinuni.edu.vn" not in raw
    assert "0987654321" not in raw
    assert "4111 1111 1111 1111" not in raw
    assert "[REDACTED_EMAIL]" in raw
    assert "[REDACTED_PHONE_VN]" in raw
    assert "[REDACTED_CREDIT_CARD]" in raw
    # Trường không phải chuỗi phải giữ nguyên, không bị đụng vào
    assert scrubbed["payload"]["doc_count"] == 3
    # correlation_id không nằm trong payload nên không bị scrub
    assert scrubbed["correlation_id"] == "req-1a2b3c4d"
```

Chạy: `python -m pytest tests/test_logging_scrub.py -q` → kỳ vọng `1 passed`.

> [!WARNING]
> **Không refactor `JsonlFileProcessor` để nhận `LOG_PATH` trong `__init__`.** [tests/test_chat_observability.py:16](tests/test_chat_observability.py#L16) monkeypatch `logging_config.LOG_PATH` ở cấp module; processor bắt buộc phải đọc biến global tại thời điểm gọi. Đổi là gãy test.

---

## Bước 1.4 — Bổ sung pattern PII

**File:** [app/pii.py:11](app/pii.py#L11):

```python
PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    # Hộ chiếu VN: 1 chữ in hoa + 7 chữ số (B1234567, C1234567...)
    "passport_vn": r"\b[A-Z]\d{7}\b",
    # Địa chỉ VN: bắt cụm bắt đầu bằng từ khoá hành chính, dừng ở dấu câu
    "address_vn": r"(?i)\b(?:số nhà|đường|phố|phường|quận|huyện|thị trấn|tổ dân phố)\b[^,.;\n]{0,60}",
    # Mã số thuế cá nhân 10 số, tách riêng khỏi cccd 12 số
    "tax_code_vn": r"(?<!\d)\d{10}(?!\d)",
}
```

> [!WARNING]
> **Regex tham lam sẽ tự bắn vào chân bạn.** Trước khi thêm bất kỳ pattern nào, thử ngay xem nó có ăn nhầm dữ liệu hợp lệ không:
>
> ```powershell
> python -c "from app.pii import scrub_text; print(scrub_text('req-3f9a1c2b 2026-08-11T08:02:38.174127Z latency_ms=2651 cost=0.002364'))"
> ```
>
> Output phải **giống hệt input**. Nếu correlation ID, timestamp hay số đo bị biến thành `[REDACTED_...]`, dashboard của VT3 và cuộc điều tra của VT4 sẽ hỏng. Ví dụ `\b\d{7,}\b` là pattern tồi vì nó nuốt cả `latency_ms`.
>
> Riêng `tax_code_vn` ở trên khá tham: nó bắt mọi số 10 chữ số. Nếu nhóm bạn có log nào chứa số 10 chữ số hợp lệ (timestamp epoch millis chẳng hạn) thì **bỏ dòng đó đi**. Ít pattern mà đúng hơn là nhiều pattern mà sai.

Test lại đầy đủ:

```powershell
python -m pytest tests/test_pii.py -q
python -c "from app.pii import scrub_text; print(scrub_text('Hộ chiếu B1234567, nhà tôi ở số nhà 12 đường Láng, quận Đống Đa, Hà Nội'))"
```

---

## Bước 1.5 — Chạy lại và đạt 100/100

> [!CAUTION]
> **`data/logs.jsonl` là file ghi nối đuôi (append-only). Không xoá nó thì bạn không bao giờ quá 70/100.**
>
> [scripts/validate_logs.py:47](scripts/validate_logs.py#L47) cộng `missing_required` cho **mọi** record có `service == "api"` mà thiếu `correlation_id` — kể cả 20 dòng cũ sinh ra từ lúc chưa sửa code. Chúng nằm đó vĩnh viễn → dòng `- [FAILED] Missing required fields` không bao giờ tắt → mất cứng 30 điểm.
>
> Đã chụp ảnh baseline ở [mục 0.3](#03-checkpoint-0--lấy-baseline-trước-khi-sửa-bất-kỳ-dòng-nào) chưa? Nếu rồi thì xoá.

```powershell
# 1. Xoá log cũ (đã có ảnh baseline)
Remove-Item data\logs.jsonl

# 2. Khởi động lại API ở Terminal 1 (Ctrl+C rồi chạy lại)
uvicorn app.main:app --reload --env-file .env

# 3. Terminal 2
python scripts/load_test.py
python scripts/validate_logs.py
```

Output phải là:

```text
--- Lab Verification Results ---
Total log records analyzed: 21
Records with missing required fields: 0
Records with missing enrichment (context): 0
Unique correlation IDs found: 10
Potential PII leaks detected: 0

--- Grading Scorecard (Estimates) ---
+ [PASSED] Basic JSON schema
+ [PASSED] Correlation ID propagation
+ [PASSED] Log enrichment
+ [PASSED] PII scrubbing

Estimated Score: 100/100
```

Tự kiểm tra thêm bằng chính dữ liệu vừa sinh:

```powershell
python -c "import json,re; rs=[json.loads(l) for l in open('data/logs.jsonl',encoding='utf-8')]; api=[r for r in rs if r.get('service')=='api']; print('api records:', len(api)); print('co du correlation_id:', all('correlation_id' in r for r in api)); print('dung format req-8hex:', all(re.fullmatch(r'req-[0-9a-f]{8}', r['correlation_id']) for r in api)); print('co du enrichment:', all({'user_id_hash','session_id','feature','model','env'} <= r.keys() for r in api))"
```

Kỳ vọng: `api records: 20` / ba dòng còn lại đều `True`.

Cuối cùng chạy toàn bộ test — **không được gãy cái nào**:

```powershell
python -m pytest -q     # ky vong: 23 passed (22 goc + 1 test scrub_event ban vua them)
```

## Evidence VT1 phải nộp

| File | Cách chụp |
|---|---|
| `00-baseline-validate-logs.png` | Đã chụp ở Checkpoint 0 (30/100) |
| `01-validate-logs-final.png` | Output 100/100 ở trên |
| `02-log-correlation-id.png` | Mở `data/logs.jsonl`, Ctrl+F một `req-xxxxxxxx`, chụp **2 dòng** `request_received` và `response_sent` cùng ID → chứng minh ID xuyên suốt request |
| `03-log-pii-redacted.png` | Dòng log của `u01` có `[REDACTED_EMAIL]`, `u05` có `[REDACTED_PHONE_VN]`, `u09` có `[REDACTED_CREDIT_CARD]` |

Điền vào `submission/REPORT.md` mục 2 và 3.

## Vấn đáp — VT1 sẽ bị hỏi gì

Lấy từ [docs/mock-debug-qa.md](docs/mock-debug-qa.md):

**"Correlation ID khác trace ID như thế nào?"**
Correlation ID do **chính app mình** sinh ở middleware, sống trong `data/logs.jsonl`, format `req-<8 hex>`, và trả về client qua header `x-request-id`. Trace ID do **Langfuse** sinh, sống trong hệ thống tracing, mang cấu trúc span cha-con. Chúng là hai không gian ID khác nhau; trong lab này chúng được nối gián tiếp qua `user_id_hash` và `session_id` — hai trường có mặt ở cả log lẫn trace ([app/agent.py:46-49](app/agent.py#L46-L49)).

**"PII cần được scrub trước hay sau khi render JSON?"**
Trước. Cụ thể là trước `JsonlFileProcessor` chứ không chỉ trước `JSONRenderer`, vì `JsonlFileProcessor` tự render và tự ghi file bên trong nó. Scrub sau khi ghi file là đã muộn — dữ liệu đã nằm trên đĩa.

**"Vì sao `validate_logs.py` đạt 100 chưa đồng nghĩa lab đạt 100 điểm?"**
Vì script chỉ kiểm 4 thứ kỹ thuật trên file log (schema, số lượng correlation ID, enrichment, regex PII). Nó không kiểm được: trace có thật hay không, prompt version có đúng không, dashboard có dùng đúng dữ liệu không, report có bằng chứng không. [RUBRIC.md](RUBRIC.md) ghi rõ 60 điểm nhóm + 40 điểm cá nhân, và chính script cũng ghi *"Điểm do script in ra không phải điểm cuối của rubric này"*.

**"Vì sao không dùng UUID đầy đủ làm correlation ID?"**
Vì detector CCCD của validator là `\b\d{12}\b`, mà nhóm cuối của UUID chuẩn dài đúng 12 ký tự — khi toàn số sẽ bị nhận nhầm là PII (đo được 0,5% mỗi ID, ~10% mỗi lượt load test). `req-<8 hex>` tối đa 8 chữ số nên miễn nhiễm.

---

# Phần 2 — Vai trò 2: Tracing & Prompt Version

> **Mục tiêu:** ≥10 trace trên Langfuse có `prompt_source: "langfuse"`, 2 prompt version có label, 1 lần rollback có ảnh.
> **Đặc thù vai trò này: gần như không phải viết code.**

## 2.0. Đọc trước: code đã xong sẵn

Khác với VT1, [app/tracing.py](app/tracing.py) và [app/prompt_management.py](app/prompt_management.py) **đã hoàn chỉnh và được test khoá** (`tests/test_tracing_adapter.py`, `tests/test_prompt_management.py`, `tests/test_agent_prompt_trace.py`). Việc của bạn là **cấu hình + thao tác trên Langfuse UI + thu bằng chứng**.

Hiểu 3 điểm sau là đủ để trả lời vấn đáp:

1. **`tracing_enabled()`** ([app/tracing.py:34-37](app/tracing.py#L34-L37)) chỉ trả `True` khi có **cả hai** key `LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY`. Thiếu một cái là tắt.
2. **`resolve_prompt()`** ([app/prompt_management.py:30-89](app/prompt_management.py#L30-L89)) có 3 nhánh và ghi nhãn trung thực vào `prompt_source`:

   | `prompt_source` | Nghĩa là | Cách sửa |
   |---|---|---|
   | `local` | Chưa bật tracing (thiếu key) → không hề gọi Langfuse | Điền key vào `.env`, restart |
   | `local-fallback` | Đã bật tracing nhưng **fetch prompt lỗi** — sai name/label/host, prompt chưa publish, hoặc timeout 2s | Xem bảng chẩn đoán ở [2.6](#26-bảng-chẩn-đoán) |
   | `langfuse` | ✅ Lấy được prompt managed thật | Đây là mục tiêu |

   > App **cố tình không giả vờ** đã lấy được prompt managed khi thực ra là fallback ([app/prompt_management.py:52-60](app/prompt_management.py#L52-L60)). Đừng sửa để ghi giả version — [docs/GUIDE.md](docs/GUIDE.md) cấm thẳng điều này.

3. **`@observe(as_type="generation", capture_input=False, capture_output=False)`** ([app/agent.py:29](app/agent.py#L29)): decorator này biến `LabAgent.run` thành một generation span. Hai cờ `capture_input=False` / `capture_output=False` là **thiết kế PII-safe có chủ đích** — Langfuse không nuốt câu hỏi thô của người dùng; thay vào đó [app/agent.py:61](app/agent.py#L61) chỉ gửi `summarize_text(message)` đã được scrub. Đây là câu trả lời vấn đáp rất được điểm.

## 2.1. Điền key và bật tracing

Xin Lab Coach 3 giá trị, điền vào `.env` (**file này đã trong `.gitignore`, tuyệt đối không commit**):

```dotenv
APP_ENV=dev
APP_NAME=day13-observability-lab
LOG_LEVEL=INFO
LOG_PATH=data/logs.jsonl
AUDIT_LOG_PATH=data/audit.jsonl
LANGFUSE_PUBLIC_KEY=pk-lf-........
LANGFUSE_SECRET_KEY=sk-lf-........
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PROMPT_NAME=day13-chat
LANGFUSE_PROMPT_LABEL=production
```

> [!IMPORTANT]
> **Restart uvicorn sau mỗi lần sửa `.env`.** Cờ `--env-file .env` chỉ nạp lúc khởi động process; `--reload` chỉ theo dõi file `.py`, **không** nạp lại `.env`.

Kiểm chứng:

```powershell
curl.exe http://127.0.0.1:8000/health
```

Kỳ vọng: `"tracing_enabled":true`. Nếu vẫn `false` → key chưa vào được `os.environ`, kiểm tra lại `.env` và restart.

## 2.2. Tạo prompt `day13-chat` version 1

Trên Langfuse UI (`LANGFUSE_HOST`) → **Prompts** → **New prompt**:

- **Name:** `day13-chat` (phải khớp `LANGFUSE_PROMPT_NAME`)
- **Type:** `text` (bắt buộc — [app/prompt_management.py:46](app/prompt_management.py#L46) truyền `type="text"`)
- **Prompt:** giữ **đúng ba biến**, không đổi tên biến:

```text
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```

- **Labels:** `baseline` **và** `production`

> [!WARNING]
> Ba biến `feature`, `docs`, `message` là hợp đồng cứng — [app/prompt_management.py:63-67](app/prompt_management.py#L63-L67) gọi `managed_prompt.compile(feature=..., docs=..., message=...)`. Đổi tên biến hoặc bỏ bớt là `compile()` ném lỗi → rơi về `local-fallback` và bạn mất bằng chứng.

## 2.3. Sinh ≥10 trace

```powershell
python scripts/load_test.py          # 10 request = 10 trace
python scripts/load_test.py          # chạy lượt 2 cho dư (tổng 20)
```

Trên Langfuse → **Tracing** → **Traces**. Mở một trace bất kỳ, kiểm tra **Metadata**:

```json
{
  "prompt_name": "day13-chat",
  "prompt_label": "production",
  "prompt_version": "1",
  "prompt_source": "langfuse"
}
```

> [!CAUTION]
> Nếu `prompt_source` là `local` hoặc `local-fallback` thì **bằng chứng không được tính**. `prompt_version` lúc đó là `"local-v1"` — con số giả. Sửa xong mới chụp ảnh.

Cấu trúc trace để chụp waterfall: trace gốc mang `user_id` (đã hash), `session_id`, `tags = ["lab", <feature>, "claude-sonnet-4-5"]`; bên trong là generation `run` với `usage_details` (prompt/completion tokens), `cost_details` và link tới prompt managed.

**Chụp:** `04-langfuse-trace-list.png` (danh sách ≥10 trace, nhìn rõ số lượng) và `05-langfuse-trace-waterfall.png` (1 trace mở rộng).

## 2.4. Tạo version 2 và chứng minh trace ăn đúng version

1. Trên UI, mở `day13-chat` → **New version**. Sửa **nhỏ** về format (theo [docs/PROMPT_VERSIONING.md](docs/PROMPT_VERSIONING.md): *"không chấm prompt nào hay hơn"*), giữ nguyên ba biến:

```text
Feature={{feature}}
Docs={{docs}}
Question={{message}}
Answer in at most 3 sentences.
```

2. Gắn label `candidate` cho version 2.

3. Đổi `.env`: `LANGFUSE_PROMPT_LABEL=candidate` → **restart uvicorn**.

> [!IMPORTANT]
> [app/prompt_management.py:48](app/prompt_management.py#L48) đặt `cache_ttl_seconds=60`. Sau khi restart thì cache trống nên request đầu tiên đã lấy đúng label mới. Nhưng nếu bạn đổi label **trên UI** mà không restart, phải **chờ ít nhất 60 giây** thì app mới thấy. Đây là nguyên nhân số 1 khiến nhóm tưởng rollback không ăn.

4. Chạy **cùng một input** với cả hai label để so sánh công bằng:

```powershell
curl.exe -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"user_id\":\"vt2-demo\",\"session_id\":\"prompt-version-demo\",\"feature\":\"qa\",\"message\":\"What is your refund policy?\"}"
```

5. Trên Langfuse lọc theo `session_id = prompt-version-demo`, mở 2 trace, ghi lại **2 trace ID**. Kiểm tra `prompt_version` khác nhau (`"1"` vs `"2"`) và `prompt_label` khác nhau (`baseline`/`production` vs `candidate`).

**Chụp:** `06-prompt-two-versions.png`, `07-trace-prompt-baseline.png`, `08-trace-prompt-candidate.png`.

## 2.5. Đổi label và rollback

Đây là phần được chấm điểm nhất — [RUBRIC.md](RUBRIC.md) đòi *"bằng chứng rollback"*.

```text
Bước 1: Chụp ảnh TRƯỚC   → production đang ở version 1
Bước 2: Trên UI, gỡ label "production" khỏi v1, gắn sang v2
Bước 3: Đặt lại LANGFUSE_PROMPT_LABEL=production trong .env, restart, gửi 1 request
        → trace mới phải hiện prompt_version = "2"
Bước 4: ROLLBACK — gỡ "production" khỏi v2, gắn lại cho v1
Bước 5: Restart, gửi 1 request nữa → trace phải quay về prompt_version = "1"
Bước 6: Chụp ảnh SAU     → production đã về version 1
```

**Chụp:** `09-prompt-rollback.png` (ghép ảnh trước + sau). Ghi cả 2 trace ID của bước 3 và bước 5 vào report — đó mới là bằng chứng rollback *thực sự có tác dụng*, chứ không phải chỉ là ảnh giao diện.

Cuối cùng nhớ trả `.env` về `LANGFUSE_PROMPT_LABEL=production` và restart, để VT4 chạy challenge trên cấu hình chuẩn.

## 2.6. Bảng chẩn đoán

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| `/health` → `tracing_enabled: false` | Thiếu 1 trong 2 key, hoặc chưa restart | Điền đủ `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY`, restart uvicorn |
| `prompt_source: "local"` | `tracing_enabled()` = False → app không gọi Langfuse | Như trên |
| `prompt_source: "local-fallback"`, `fetch_error: "LangfuseFallback"` | Kết nối được nhưng **không tìm thấy** prompt với name+label đó | Kiểm tra prompt name đúng `day13-chat`, label đã gắn và đã publish, đúng project |
| `prompt_source: "local-fallback"`, `fetch_error: "TimeoutError"` | Quá 2 giây ([app/prompt_management.py:49](app/prompt_management.py#L49)) | Kiểm tra mạng / `LANGFUSE_HOST`; nếu chạy Docker local, chờ container `langfuse-web` sẵn sàng |
| Không thấy trace nào trên UI | Sai host hoặc sai project | Đối chiếu `LANGFUSE_HOST` với URL trên trình duyệt |
| Đổi label trên UI mà app không đổi | Cache prompt 60s | Chờ 60s hoặc restart uvicorn |

## 2.7. (Tuỳ chọn) Nối `correlation_id` vào trace

Muốn VT4 nhảy từ trace sang log bằng đúng correlation ID thay vì qua `session_id`, thêm 1 dòng vào [app/agent.py](app/agent.py):

```python
# đầu file
from structlog.contextvars import get_contextvars

# trong LabAgent.run, phần update_current_generation
        langfuse_client.update_current_generation(
            model=self.model,
            metadata={
                "doc_count": len(docs),
                "query_preview": summarize_text(message),
                "prompt_name": prompt.name,
                "prompt_label": prompt.label,
                "prompt_version": prompt.version,
                "prompt_source": prompt.source,
                "prompt_fetch_error": prompt.fetch_error,
                "correlation_id": get_contextvars().get("correlation_id"),   # <-- thêm
            },
            ...
        )
```

> [!CAUTION]
> **Chỉ được thêm vào `update_current_generation`, TUYỆT ĐỐI không thêm vào `update_current_trace`.**
> [tests/test_agent_prompt_trace.py:52-57](tests/test_agent_prompt_trace.py#L52-L57) so sánh trace metadata bằng `==` với đúng 4 khoá → thêm khoá thứ 5 là **test đỏ ngay**. Trong khi generation metadata chỉ được kiểm theo từng khoá (`metadata["prompt_version"] == "3"`) → thêm khoá vào đây là an toàn.
>
> Chạy `python -m pytest -q` để xác nhận trước khi commit.

Việc này **không bắt buộc**: cầu nối trace ↔ log đã có sẵn qua `user_id_hash` + `session_id` (xem [Bước 4.4](#bước-44--logs-chứng-minh-root-cause)).

## 2.8. Kế hoạch B: không xin được key Langfuse

Vẫn làm trọn vẹn VT1, VT3, VT4 — app chạy bình thường bằng prompt local. Bạn mất khoảng 10 điểm A1 phần trace/prompt. Trong `submission/REPORT.md` mục 4 ghi thẳng: *"Không truy cập được Langfuse trong buổi lab, trace metadata ghi `prompt_source=local`; phần prompt versioning chưa có bằng chứng."*

**Trung thực mất 10 điểm. Làm giả ảnh vi phạm [RULES.md](RULES.md) và mất cả bài.**

## Vấn đáp — VT2

**"Tại sao trace không chứa câu hỏi gốc của người dùng?"**
Vì `@observe` được cấu hình `capture_input=False, capture_output=False` ([app/agent.py:29](app/agent.py#L29)). Thay vào đó chỉ gửi `summarize_text(message)` — đã qua regex redaction và cắt còn 80 ký tự. Đây là nguyên tắc PII-safe by design: hệ thống quan sát không được trở thành nơi rò rỉ dữ liệu.

**"`prompt_source=local-fallback` nghĩa là gì và vì sao app không tự ghi version giả?"**
Nghĩa là tracing đã bật nhưng lấy prompt managed thất bại, app dùng template local. Nếu app ghi bừa `version=1` thì mọi kết luận sau đó (trace này dùng prompt nào) đều sai — quan sát sai còn tệ hơn không quan sát. Nên nó ghi rõ `local-v1` + `fetch_error` để người đọc biết dữ liệu này không đáng tin.

**"Rollback prompt cần bằng chứng gì mới đủ?"**
Không phải ảnh giao diện. Phải là **trace ID trước và sau**: một trace ghi `prompt_version: "2"` khi production trỏ v2, một trace ghi `prompt_version: "1"` sau khi rollback. Ảnh UI chỉ chứng minh bạn bấm nút; trace chứng minh hệ thống thật sự đổi hành vi.

---

# Phần 3 — Vai trò 3: Dashboard, SLO & Alert

> **Mục tiêu:** `validate_dashboard.py` báo `HỢP LỆ: 6/6 panel`, dashboard runtime 6 panel có threshold, `config/alert_rules.yaml` + `docs/alerts.md` điền xong.

## Bước 3.1 — Lấy điểm validator ngay lập tức (2 phút)

```powershell
python scripts/validate_dashboard.py
```

Output: `HỢP LỆ: 6/6 panel có trong dashboard contract.` → **Chụp ngay** thành `10-validate-dashboard.png`.

> [!IMPORTANT]
> **`config/dashboard.yaml` đã hợp lệ sẵn — ĐỪNG SỬA.** File này đang bị `tests/test_dashboard_validator.py` khoá (test đọc chính file repo và assert `6/6 panel`). [docs/DASHBOARD_SETUP.md](docs/DASHBOARD_SETUP.md) nói rõ: *"không tự đổi contract chỉ để ảnh dashboard đẹp hơn"*.
>
> Việc thật của bạn là ba thứ **khác**: dựng dashboard runtime, điền `config/alert_rules.yaml` (đang toàn chữ `TODO`), điền `docs/alerts.md` (đang trống).

Đọc hợp đồng bạn phải tuân theo ([config/dashboard.yaml](config/dashboard.yaml)):

| Panel id | Title | Nguồn event.field | Aggregation | Đơn vị | Threshold |
|---|---|---|---|---|---|
| `latency` | Latency percentiles | `response_sent.latency_ms` | p50, p95, p99 | ms | p95 **≤ 3000** |
| `traffic` | Request traffic | `request_received` | count, rate_per_minute | requests_per_minute | rate **≥ 1** |
| `errors` | Error rate and breakdown | `request_failed` / `request_received`, `error_type` | error_rate_pct, count_by_value | percent | ≤ **2** |
| `cost` | Cost over time | `response_sent.cost_usd` | sum_by_minute, total | usd | total ≤ **2.5** |
| `tokens` | Input and output tokens | `response_sent.tokens_in/out` | sum_by_field | tokens | ≤ **50000** |
| `quality` | Quality proxy | `response_sent.quality_score` | mean | score_0_to_1 | mean ≥ **0.75** |

Cộng thêm: `time_range_minutes: 60`, `refresh_seconds: 30`.

## Bước 3.2 — Cài Streamlit

```powershell
.\.venv\Scripts\Activate.ps1
pip install streamlit
pip freeze | Select-String "^streamlit=="
```

Lệnh cuối in ra dòng pin đúng version vừa cài, ví dụ `streamlit==1.50.0`. **Copy đúng dòng đó** thêm vào cuối [requirements.txt](requirements.txt):

```text
streamlit==<dán version thật vừa in ra>
```

> [!NOTE]
> Đừng đoán số version. Streamlit kéo theo `pandas`, `numpy`, `altair` nên bạn **không cần** cài thêm gì cho phần biểu đồ.

## Bước 3.3 — Code dashboard

Tạo thư mục `dashboard/` và file **`dashboard/app_dashboard.py`**:

```python
"""Dashboard Day 13 — đọc data/logs.jsonl, hiển thị 6 panel theo config/dashboard.yaml.

Nguyên tắc: mọi tiêu đề, đơn vị và threshold đều ĐỌC TỪ contract, không hard-code.
Nhờ vậy dashboard không thể lệch khỏi config/dashboard.yaml.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Tái sử dụng đúng công thức percentile của app để số trên dashboard
# khớp với số ở endpoint /metrics.
from app.metrics import percentile

CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"

st.set_page_config(page_title="Day 13 AI Observability", layout="wide")


# ---------------------------------------------------------------- contract

def load_contract() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]


def panel(contract: dict, panel_id: str) -> dict:
    return next(p for p in contract["panels"] if p["id"] == panel_id)


def check(spec: dict, value: float) -> tuple[str, str]:
    """So giá trị đo được với threshold trong contract. Trả (icon, mô tả threshold)."""
    th = spec["threshold"]
    op, limit = th["operator"], th["value"]
    ok = value <= limit if op == "lte" else value >= limit
    symbol = "<=" if op == "lte" else ">="
    return ("OK" if ok else "VUOT NGUONG",
            f"{th['aggregation']} {symbol} {limit} {spec['unit']}")


# ---------------------------------------------------------------- dữ liệu

def load_records(window_minutes: int) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    records: list[dict] = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            parsed = datetime.fromisoformat(str(rec["ts"]).replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if parsed >= cutoff:
            rec["_ts"] = parsed
            records.append(rec)
    return records


def by_minute(records: list[dict], field: str | None = None) -> pd.DataFrame:
    """Gom theo từng phút. field=None nghĩa là đếm số bản ghi."""
    if not records:
        return pd.DataFrame({"value": []})
    rows = [
        {"minute": r["_ts"].replace(second=0, microsecond=0),
         "value": 1 if field is None else r.get(field, 0)}
        for r in records
    ]
    return pd.DataFrame(rows).groupby("minute")["value"].sum().to_frame("value")


def with_threshold(df: pd.DataFrame, label: str, limit: float) -> pd.DataFrame:
    """Thêm cột hằng số để Streamlit vẽ SLO line cùng biểu đồ."""
    if df.empty:
        return df
    out = df.copy()
    out[label] = limit
    return out


# ---------------------------------------------------------------- panels

def render() -> None:
    contract = load_contract()
    window = contract["time_range_minutes"]
    records = load_records(window)

    received = [r for r in records if r.get("event") == "request_received"]
    sent = [r for r in records if r.get("event") == "response_sent"]
    failed = [r for r in records if r.get("event") == "request_failed"]

    st.title(contract["title"])
    st.caption(
        f"Nguon: data/logs.jsonl | Time range: {window} phut | "
        f"Refresh: {contract['refresh_seconds']}s | "
        f"Cap nhat: {datetime.now().strftime('%H:%M:%S')} | "
        f"{len(records)} ban ghi trong cua so"
    )

    if not records:
        st.warning("Chua co du lieu trong 60 phut gan nhat. Chay: python scripts/load_test.py")
        return

    # ---- Panel 1: latency ------------------------------------------------
    spec = panel(contract, "latency")
    st.subheader(f"1. {spec['title']} [{spec['unit']}]")
    latencies = [r["latency_ms"] for r in sent if "latency_ms" in r]
    p50, p95, p99 = (percentile(latencies, p) for p in (50, 95, 99))
    status, rule = check(spec, p95)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P50", f"{p50:.0f} ms")
    c2.metric("P95", f"{p95:.0f} ms", delta=f"{p95 - spec['threshold']['value']:+.0f} vs SLO")
    c3.metric("P99", f"{p99:.0f} ms")
    c4.metric("Threshold", status, help=rule)
    st.caption(f"SLO: {rule}")
    if latencies:
        df = pd.DataFrame({"latency_ms": latencies,
                           "SLO p95 = 3000 ms": spec["threshold"]["value"]},
                          index=[r["_ts"] for r in sent if "latency_ms" in r])
        st.line_chart(df)

    # ---- Panel 2: traffic ------------------------------------------------
    spec = panel(contract, "traffic")
    st.subheader(f"2. {spec['title']} [{spec['unit']}]")
    traffic = by_minute(received)
    # rate_per_minute = trung binh so request trong cac phut CO du lieu
    rate = float(traffic["value"].mean()) if not traffic.empty else 0.0
    status, rule = check(spec, rate)
    c1, c2, c3 = st.columns(3)
    c1.metric("Tong request", len(received))
    c2.metric("Rate", f"{rate:.1f} req/min")
    c3.metric("Threshold", status, help=rule)
    st.caption(f"SLO: {rule}")
    st.bar_chart(with_threshold(traffic, "min 1 req/min", spec["threshold"]["value"]))

    # ---- Panel 3: errors -------------------------------------------------
    spec = panel(contract, "errors")
    st.subheader(f"3. {spec['title']} [{spec['unit']}]")
    error_rate = (len(failed) / len(received) * 100) if received else 0.0
    status, rule = check(spec, error_rate)
    c1, c2, c3 = st.columns(3)
    c1.metric("Error rate", f"{error_rate:.2f} %")
    c2.metric("So request loi", len(failed))
    c3.metric("Threshold", status, help=rule)
    st.caption(f"SLO: {rule}")
    breakdown = Counter(r.get("error_type", "unknown") for r in failed)
    if breakdown:
        st.bar_chart(pd.DataFrame({"count": breakdown.values()}, index=list(breakdown)))
    else:
        st.success("Khong co loi trong cua so nay.")

    # ---- Panel 4: cost ---------------------------------------------------
    spec = panel(contract, "cost")
    st.subheader(f"4. {spec['title']} [{spec['unit']}]")
    total_cost = sum(r.get("cost_usd", 0.0) for r in sent)
    status, rule = check(spec, total_cost)
    c1, c2, c3 = st.columns(3)
    c1.metric("Tong cost", f"${total_cost:.4f}")
    c2.metric("Trung binh/request", f"${total_cost / len(sent):.6f}" if sent else "$0")
    c3.metric("Threshold", status, help=rule)
    st.caption(f"SLO: {rule}")
    st.bar_chart(by_minute(sent, "cost_usd"))

    # ---- Panel 5: tokens -------------------------------------------------
    spec = panel(contract, "tokens")
    st.subheader(f"5. {spec['title']} [{spec['unit']}]")
    tokens_in = sum(r.get("tokens_in", 0) for r in sent)
    tokens_out = sum(r.get("tokens_out", 0) for r in sent)
    status, rule = check(spec, max(tokens_in, tokens_out))
    c1, c2, c3 = st.columns(3)
    c1.metric("Tokens in", f"{tokens_in:,}")
    c2.metric("Tokens out", f"{tokens_out:,}")
    c3.metric("Threshold", status, help=rule)
    st.caption(f"SLO: {rule}")
    st.bar_chart(pd.DataFrame({"tokens": [tokens_in, tokens_out]}, index=["tokens_in", "tokens_out"]))

    # ---- Panel 6: quality ------------------------------------------------
    spec = panel(contract, "quality")
    st.subheader(f"6. {spec['title']} [{spec['unit']}]")
    scores = [r["quality_score"] for r in sent if "quality_score" in r]
    mean_quality = sum(scores) / len(scores) if scores else 0.0
    status, rule = check(spec, mean_quality)
    c1, c2, c3 = st.columns(3)
    c1.metric("Quality trung binh", f"{mean_quality:.3f}")
    c2.metric("So mau", len(scores))
    c3.metric("Threshold", status, help=rule)
    st.caption(f"SLO: {rule}")
    if scores:
        df = pd.DataFrame({"quality_score": scores,
                           "SLO mean >= 0.75": spec["threshold"]["value"]},
                          index=[r["_ts"] for r in sent if "quality_score" in r])
        st.line_chart(df)


# Auto-refresh theo đúng refresh_seconds trong contract (Streamlit >= 1.37).
# Neu ban Streamlit cu hon khong co st.fragment, bo decorator va bam nut Rerun (phim R).
_refresh = load_contract()["refresh_seconds"]
render_auto = st.fragment(run_every=_refresh)(render)
render_auto()
```

Chạy:

```powershell
streamlit run dashboard/app_dashboard.py
```

Mở `http://localhost:8501`. Nếu chưa có dữ liệu, chạy `python scripts/load_test.py --concurrency 5` ở terminal khác.

### Vì sao code viết như vậy

| Lựa chọn | Lý do |
|---|---|
| Đọc threshold/title/unit từ `config/dashboard.yaml` | Contract là nguồn chân lý duy nhất. Dashboard không thể lệch khỏi thứ validator kiểm. Sửa YAML là dashboard tự đổi theo. |
| `from app.metrics import percentile` | Tái sử dụng đúng hàm ở [app/metrics.py:31](app/metrics.py#L31) → số P95 trên dashboard **khớp tuyệt đối** với `/metrics`. Tự viết `numpy.percentile` sẽ ra số khác (thuật toán nội suy khác) và giám khảo sẽ hỏi tại sao lệch. |
| Lọc theo `time_range_minutes` | `data/logs.jsonl` ghi nối đuôi mãi mãi. Không lọc thì panel trộn dữ liệu hôm qua vào, và traffic rate sẽ sai. |
| Có cột hằng số cho SLO line | [docs/dashboard-spec.md](docs/dashboard-spec.md) bắt buộc *"có threshold hoặc SLO line"* và ảnh chụp phải nhìn thấy nó. |
| `rate_per_minute` = trung bình các phút **có dữ liệu** | Chia cho cả 60 phút thì 10 request ra 0,17 req/min → luôn báo đỏ dù hệ thống khoẻ. Cách này phản ánh đúng nhịp thật khi có tải. Ghi cách tính này vào report. |

## Bước 3.4 — Điền `config/alert_rules.yaml`

Thay toàn bộ [config/alert_rules.yaml](config/alert_rules.yaml):

```yaml
alerts:
  - name: HighLatencyP95
    severity: P2
    condition: 'p95(response_sent.latency_ms) trong cua so 5m > 3000 ms, duy tri 10m lien tuc'
    duration: 10m
    type: symptom-based
    sli: latency_p95_ms
    user_impact: 'Nguoi dung cho qua 3 giay moi nhan duoc cau tra loi; phien hoi dap bi dut mach.'
    owner: <ten-thanh-vien-VT3>
    runbook: docs/alerts.md#alert-1

  - name: HighErrorRate
    severity: P1
    condition: 'count(request_failed) / count(request_received) trong cua so 5m > 2%, duy tri 5m'
    duration: 5m
    type: symptom-based
    sli: error_rate_pct
    user_impact: 'Request that bai, nguoi dung nhan HTTP 500 va khong co cau tra loi nao.'
    owner: <ten-thanh-vien-VT4>
    runbook: docs/alerts.md#alert-2

  - name: CostBudgetBurn
    severity: P3
    condition: 'sum(response_sent.cost_usd) trong 24h > 2.5 USD, duy tri 30m'
    duration: 30m
    type: symptom-based
    sli: daily_cost_usd
    user_impact: 'Chua anh huong truc tiep, nhung het ngan sach se dan toi ngat dich vu.'
    owner: <ten-thanh-vien-VT2>
    runbook: docs/alerts.md#alert-3
```

> [!NOTE]
> Ba nguyên tắc [docs/alerts.md](docs/alerts.md) đòi hỏi, giám khảo sẽ soi:
> 1. **Symptom-based, không implementation-based.** Alert đúng: "P95 > 3000ms" (người dùng cảm nhận được). Alert sai: "`mock_rag.retrieve` chậm" (tên hàm nội bộ — đổi tên hàm là alert vô nghĩa).
> 2. **Phải có `duration`.** Không có duration thì một request chậm lẻ tẻ cũng bắn alert → alert fatigue → không ai đọc nữa.
> 3. **Phải có `owner`.** Alert không có người chịu trách nhiệm là alert không ai xử lý. Điền tên thật của thành viên.
>
> Giữ nguyên đường dẫn `runbook: docs/alerts.md#alert-N` — anchor này khớp với heading `## Alert N` trong file runbook.

## Bước 3.5 — Điền `docs/alerts.md`

Điền cả 3 mục. Mẫu cho Alert 1 (làm tương tự cho 2 và 3):

```markdown
## Alert 1

- Tên: HighLatencyP95
- Severity: P2
- SLI/SLO liên quan: latency_p95_ms — mục tiêu P95 <= 3000 ms, đạt 99.5% thời gian trong cửa sổ 28 ngày (config/slo.yaml)
- Điều kiện và thời gian duy trì: P95 của response_sent.latency_ms trong cửa sổ trượt 5 phút vượt 3000 ms và duy trì liên tục 10 phút
- Ảnh hưởng tới người dùng: người dùng chờ trên 3 giây cho mỗi câu trả lời; với hội thoại nhiều lượt, trải nghiệm bị đứt mạch và tỉ lệ bỏ ngang tăng
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Latency, xác định thời điểm P95 bắt đầu tăng và so với panel Traffic — nếu traffic không tăng thì không phải quá tải
  2. Mở Langfuse, lọc trace trong khung giờ đó, xem waterfall để tìm span chiếm nhiều thời gian nhất (retrieval hay generation)
  3. Lấy session_id/user_id_hash của trace chậm, tìm trong data/logs.jsonl để lấy correlation_id và đọc toàn bộ log của request đó
- Mitigation tạm thời: tắt incident đang bật (`python scripts/inject_incident.py --scenario <ten> --disable`); nếu là sự cố thật thì đặt timeout cho retrieval và trả lời fallback không kèm tài liệu
- Owner: <tên thành viên VT3>
```

## Bước 3.6 — Rà `config/slo.yaml`

File [config/slo.yaml](config/slo.yaml) có dòng `note: Replace with your group's target`. Thay bằng lý do chọn thật của nhóm:

```yaml
service: day13-observability-lab
window: 28d
slis:
  latency_p95_ms:
    objective: 3000
    target: 99.5
    note: Khop threshold panel latency trong config/dashboard.yaml; 3000ms la nguong nguoi dung con chap nhan duoc cho mot cau tra loi AI.
  error_rate_pct:
    objective: 2
    target: 99.0
    note: Duoi 2% loi thi nguoi dung con retry duoc; tren nguong nay coi nhu dich vu khong dung duoc.
  daily_cost_usd:
    objective: 2.5
    target: 100.0
    note: Ngan sach cung cua lab; vuot la phai dung, khong co ngoai le.
  quality_score_avg:
    objective: 0.75
    target: 95.0
    note: Quality proxy tinh bang heuristic trong app/agent.py, chi dung de phat hien tut hang, khong phai diem chat luong tuyet doi.
```

## Bước 3.7 — Kiểm chứng runtime (dashboard phải phản ứng thật)

```powershell
# 1. Baseline sạch
python scripts/load_test.py --concurrency 5
#    -> mo dashboard, CHUP 11-dashboard-baseline.png

# 2. Bật incident practice
python scripts/inject_incident.py --scenario rag_slow

# 3. Cùng input, cùng concurrency
python scripts/load_test.py --concurrency 5
#    -> dashboard tu refresh sau 30s, CHUP 12-dashboard-incident.png

# 4. Tắt
python scripts/inject_incident.py --scenario rag_slow --disable
```

> [!WARNING]
> **`rag_slow` sẽ KHÔNG làm P95 vượt qua SLO line 3000 ms. Đây là kết quả đúng, đừng cố "sửa" cho nó vượt.**
>
> Số đo thật trên repo này: [app/mock_rag.py:18](app/mock_rag.py#L18) sleep 2,5 s + [app/mock_llm.py:28](app/mock_llm.py#L28) sleep 0,15 s → `latency_ms` = **2650–2655 ms**, P95 = **2655 ms**. Baseline (không incident) chỉ ~150–160 ms.
>
> Vậy 2655 < 3000 → panel latency vẫn "OK". Nhưng nó **vượt `latency_threshold_ms: 2000`** mà [config/challenge.json](config/challenge.json) quy định, và **tăng ~17 lần** so với baseline.
>
> **Cách viết caption trung thực cho ảnh 12:**
> > *"P95 tăng từ 152 ms (baseline) lên 2655 ms sau khi bật `rag_slow` — gấp 17,5 lần và vượt ngưỡng 2000 ms của challenge, tuy chưa chạm SLO line 3000 ms của dashboard. Chênh lệch giữa hai ngưỡng cho thấy SLO 3000 ms quá lỏng so với hành vi thật của hệ thống; nhóm đề xuất siết xuống 2000 ms."*
>
> Nhận xét cuối đó chính là thứ ăn điểm ở mục A2 "preventive measure" — nhìn ra SLO đặt sai. Nhóm nào cố ép biểu đồ vượt 3000 sẽ phải làm giả dữ liệu, và mất cả bài theo [RULES.md](RULES.md).

Muốn có thêm một panel thật sự báo đỏ, dùng `cost_spike` (nhân 4 lần token output, [app/mock_llm.py:31-32](app/mock_llm.py#L31-L32)) hoặc `tool_fail` (error rate vọt lên 100%, vượt xa ngưỡng 2%):

```powershell
python scripts/inject_incident.py --scenario tool_fail
python scripts/load_test.py --concurrency 5
python scripts/inject_incident.py --scenario tool_fail --disable
```

## Evidence VT3

`10-validate-dashboard.png`, `11-dashboard-baseline.png`, `12-dashboard-incident.png` — ảnh dashboard **phải nhìn rõ**: tên từng panel, time range 60 phút, đơn vị, và dòng threshold/SLO. Ảnh cắt cúp mất threshold không được tính ([docs/DASHBOARD_SETUP.md](docs/DASHBOARD_SETUP.md)).

Điền `submission/REPORT.md` mục 5.

## Vấn đáp — VT3

**"Vì sao chỉ nhìn average latency có thể bỏ sót vấn đề?"**
Vì trung bình bị số đông kéo về. Nếu 95 request nhanh 150 ms và 5 request chậm 2650 ms, trung bình chỉ ~275 ms — trông vẫn "khoẻ", trong khi 5% người dùng đang chờ 2,6 giây. Percentile P95/P99 mô tả đúng trải nghiệm ở phần đuôi. Đó là lý do contract yêu cầu P50/P95/P99 chứ không phải mean.

**"Một alert tốt cần condition, duration, severity và owner như thế nào?"**
Condition phải dựa trên triệu chứng người dùng cảm nhận được (P95 > 3000ms), không dựa trên tên hàm nội bộ. Duration để lọc nhiễu — một spike 10 giây không đáng đánh thức ai; 10 phút liên tục thì có. Severity quyết định gọi ai lúc mấy giờ (P1 gọi ngay, P3 chờ giờ hành chính). Owner là người chịu trách nhiệm cụ thể — alert không có owner là alert không ai xử lý.

**"Khi cost tăng nhưng traffic không tăng, bạn kiểm tra những trường nào?"**
Đầu tiên là `tokens_out` — vì giá output đắt gấp 5 lần input ($15 vs $3 mỗi triệu token, [app/agent.py:93-96](app/agent.py#L93-L96)). Nếu `tokens_out` tăng đột biến trong khi `tokens_in` không đổi thì nguyên nhân nằm ở phía sinh câu trả lời (đúng như incident `cost_spike` nhân 4 lần output). Tiếp theo kiểm `model` (có ai đổi model không) và `prompt_version` (prompt mới có làm câu trả lời dài ra không). Cả ba trường này đều có sẵn trong log và trace metadata.

---

# Phần 4 — Vai trò 4: Incident, Report & Demo

> **Mục tiêu:** chứng minh root cause bằng chuỗi Metrics → Traces → Logs, viết `submission/REPORT.md`, dẫn demo 5 phút.
> **Bạn cầm 30/60 điểm nhóm (A2 10đ + A3 20đ). Bạn cũng là người tổng hợp báo cáo cho cả nhóm.**

## Bước 4.0 — Đọc challenge đã release

[config/challenge.json](config/challenge.json) **đã được Lab Coach release** (commit `5ba6472`):

```text
challenge_id          : day13-k4-observability-v1
cohort                : K4
incident              : rag_slow
seed                  : 1304
affected_feature      : monitoring
latency_threshold_ms  : 2000        <-- nguong de ket luan, KHONG phai 3000 cua dashboard
queries               : 5 cau, user k4-u01..k4-u05
```

Thứ tự chạy là **tất định** (`random.Random(1304).shuffle`, [app/challenge.py:100-103](app/challenge.py#L100-L103)) — đã chạy thử và xác nhận:

| # | user_id | session_id | message |
|---|---|---|---|
| 1 | `k4-u02` | `k4-challenge-s02` | How should an engineer investigate tail latency? |
| 2 | `k4-u01` | `k4-challenge-s01` | Explain why metrics traces and logs work together. |
| 3 | `k4-u05` | `k4-challenge-s05` | Describe how to prove a slow span is the root cause. |
| 4 | `k4-u03` | `k4-challenge-s03` | Summarize the observability workflow for an AI API. |
| 5 | `k4-u04` | `k4-challenge-s04` | Which signal should be checked after latency increases? |

Biết trước thứ tự để đối chiếu log, **không phải để đoán trước kết luận**.

> [!CAUTION]
> [RULES.md](RULES.md) cấm *"tự tạo, sửa hoặc thay thế `config/challenge.json`"*. Đừng đụng vào file này, kể cả sửa format. `git status` phải sạch với nó.

**Trước 2:30, luyện tập** với practice (luôn được phép, không tính điểm):

```powershell
python scripts/inject_incident.py --scenario rag_slow
python scripts/load_test.py --concurrency 5
python scripts/inject_incident.py --scenario rag_slow --disable
```

## Bước 4.1 — Chạy challenge chính thức

```powershell
# 0. Lay baseline sach de co so sanh. Ghi lai con so nay!
curl.exe http://127.0.0.1:8000/metrics

# 1. Bat incident chinh thuc (KHONG truyen --scenario, de script tu doc challenge.json)
python scripts/inject_incident.py

# 2. Chay input chinh thuc
python scripts/load_test.py --challenge --concurrency 5
```

> [!IMPORTANT]
> **Chụp lại output terminal của bước 2 → `16-challenge-loadtest-output.png`.** Đây là bằng chứng mà dashboard **không thể** cho bạn, và nó là điểm ăn tiền nhất của cuộc điều tra. Xem [Bước 4.5](#bước-45--phát-hiện-nâng-cao-latency_ms-đang-nói-dối-bạn).

Output kỳ vọng có dạng:

```text
Challenge: day13-k4-observability-v1 | Cohort: K4
[200] req-a1b2c3d4 | monitoring | 2658.3ms
[200] req-e5f6a7b8 | monitoring | 5310.1ms
[200] req-c9d0e1f2 | monitoring | 7962.7ms
[200] req-3a4b5c6d | monitoring | 10615.2ms
[200] req-7e8f9a0b | monitoring | 13267.8ms
```

## Bước 4.2 — Metrics: xác định triệu chứng

```powershell
curl.exe http://127.0.0.1:8000/metrics
```

So với baseline, và mở dashboard của VT3. Ghi lại **có số**:

| Chỉ số | Baseline | Khi incident | Kết luận |
|---|---:|---:|---|
| `latency_p50` | ~152 ms | ~2651 ms | tăng ~17× |
| `latency_p95` | ~160 ms | ~2655 ms | **vượt ngưỡng challenge 2000 ms**, chưa chạm SLO 3000 ms |
| `error_breakdown` | `{}` | `{}` | **không có lỗi** — đây là manh mối quan trọng |
| `total_cost_usd` | không đổi | không đổi | không phải vấn đề token/cost |
| `quality_avg` | không đổi | không đổi | không phải vấn đề chất lượng |
| `traffic` | — | +5 | tải không hề tăng |

**Đọc bảng này ra kết luận:** latency tăng mạnh nhưng error rate = 0, cost không đổi, traffic không tăng → **không phải quá tải, không phải lỗi, không phải đổi model**. Đây là một thành phần trong đường xử lý đang chậm đi. Metrics chỉ nói được tới đây — nó cho biết *có chuyện gì đó* và *lúc nào*, không cho biết *ở đâu*.

**Chụp:** `13-challenge-metrics.png`. Ghi lại **mốc thời gian** của các request (từ `ts` trong log) để lát nữa khoanh vùng trên Langfuse.

## Bước 4.3 — Traces: khoanh vùng span bất thường

Trên Langfuse:

1. Lọc theo khung giờ vừa ghi, hoặc lọc theo `session_id` bắt đầu bằng `k4-challenge-s`.
2. Mở một trace, xem **waterfall**.
3. Trace có generation `run` tổng ~2650 ms. So sánh thời gian các bước bên trong: `retrieve()` chiếm ~2500 ms, phần gọi LLM chỉ ~150 ms.

**Kết luận từ tầng trace:** thời gian bị nuốt ở bước **retrieval**, không phải ở bước generation. Đây là bước thu hẹp từ "hệ thống chậm" xuống "khối retrieval chậm".

**Chụp:** `14-challenge-trace.png` — waterfall nhìn rõ span nào dài. Ghi lại **trace ID**.

> [!NOTE]
> Nếu nhóm không có Langfuse (kế hoạch B của VT2), vẫn kết luận được bằng cách so `latency_ms` trong log với thời gian sleep của từng thành phần, nhưng bằng chứng yếu hơn và A2 sẽ bị trừ. Ghi rõ hạn chế đó trong report thay vì im lặng.

## Bước 4.4 — Logs: chứng minh root cause

Trace ID của Langfuse **không** xuất hiện trong `data/logs.jsonl`. Cầu nối là hai trường có mặt ở **cả hai** phía:

- Trace Langfuse mang `user_id` = `hash_user_id(user_id)` và `session_id` ([app/agent.py:46-49](app/agent.py#L46-L49)).
- Log JSON mang `user_id_hash` và `session_id` (do VT1 bind ở [app/main.py](app/main.py)).

Chúng là **cùng một giá trị**. Quy trình:

```powershell
# 1. Tu trace lay session_id, vi du k4-challenge-s02.
#    Tim tat ca log cua phien do:
python -c "import json; [print(json.dumps(r,ensure_ascii=False)) for r in (json.loads(l) for l in open('data/logs.jsonl',encoding='utf-8')) if r.get('session_id')=='k4-challenge-s02']"

# 2. Lay correlation_id trong ket qua tren, gom toan bo log cua dung request do:
python -c "import json,sys; cid=sys.argv[1]; [print(json.dumps(r,ensure_ascii=False)) for r in (json.loads(l) for l in open('data/logs.jsonl',encoding='utf-8')) if r.get('correlation_id')==cid]" req-a1b2c3d4
```

Bạn sẽ thấy **đúng 2 dòng** cùng `correlation_id`:

```json
{"correlation_id":"req-a1b2c3d4","user_id_hash":"...","session_id":"k4-challenge-s02","feature":"monitoring","model":"claude-sonnet-4-5","env":"dev","service":"api","payload":{"message_preview":"How should an engineer investigate tail latency?"},"event":"request_received","level":"info","ts":"..."}
{"correlation_id":"req-a1b2c3d4","user_id_hash":"...","session_id":"k4-challenge-s02","feature":"monitoring","model":"claude-sonnet-4-5","env":"dev","service":"api","latency_ms":2658,"tokens_in":31,"tokens_out":143,"cost_usd":0.002238,"quality_score":0.9,"payload":{"answer_preview":"..."},"event":"response_sent","level":"info","ts":"..."}
```

Và quan trọng nhất — dòng `service: "control"` ngay trước loạt request:

```json
{"service":"control","payload":{"name":"rag_slow"},"event":"incident_enabled","level":"warning","ts":"..."}
```

**Đây là bằng chứng khoá:** log ghi lại đúng thời điểm `rag_slow` được bật, và mọi request sau mốc đó đều có `latency_ms` ~2650 trong khi trước đó ~150.

**Chụp:** `15-challenge-logs.png` — cả dòng `incident_enabled` lẫn cặp log cùng correlation ID.

**Root cause chốt tại [app/mock_rag.py:14-18](app/mock_rag.py#L14-L18):**

```python
def retrieve(message: str) -> list[str]:
    if STATE["tool_fail"]:
        raise RuntimeError("Vector store timeout")
    if STATE["rag_slow"]:
        time.sleep(2.5)          # <-- 2.5 giay bi chen vao moi lan retrieval
```

Cờ `STATE["rag_slow"]` bị bật qua `POST /incidents/rag_slow/enable` ([app/main.py:93-101](app/main.py#L93-L101)) — chính là log `incident_enabled` bạn vừa tìm thấy.

## Bước 4.5 — Phát hiện nâng cao: `latency_ms` đang nói dối bạn

Đây là phần làm báo cáo của bạn hơn hẳn các nhóm khác.

**Quan sát:** trong log, cả 5 request đều ghi `latency_ms` ≈ 2650. Nhưng output client-side của `load_test.py` lại là 2,6 s / 5,3 s / 8,0 s / 10,6 s / 13,3 s — người dùng cuối cùng chờ **13 giây**, gấp 5 lần con số hệ thống tự báo.

**Giải thích:** [app/main.py:46](app/main.py#L46) khai báo `async def chat(...)` nhưng bên trong gọi `agent.run()` là hàm **đồng bộ** có `time.sleep()`. Trong asyncio, `time.sleep` **chặn cả event loop** — không request nào khác được xử lý trong 2,5 giây đó. 5 request đồng thời bị xếp hàng nối đuôi. Nhưng [app/agent.py:31](app/agent.py#L31) bấm giờ từ **bên trong** `run()`, nên nó chỉ đo phần việc của chính nó và **không nhìn thấy thời gian chờ hàng đợi**.

Đã kiểm chứng bằng thí nghiệm độc lập (5 request đồng thời, server sleep 0,5 s):

```text
req    client wall (ms)    latency_ms in body
0                   509                   500
1                  1010                   500
2                  1512                   500
3                  2013                   500
4                  2514                   500
```

Tổng 2522 ms — nếu thật sự song song thì phải ~500 ms. Xếp hàng hoàn toàn, và `latency_ms` bên trong che giấu toàn bộ.

**Vì sao điều này quan trọng:** dashboard của bạn chỉ vẽ `latency_ms` từ log, nên nó **không bao giờ** cho thấy 13 giây kia. Nếu chỉ tin dashboard, bạn sẽ báo cáo "chậm 2,6 s" trong khi người dùng chịu 13 s. Đây là ví dụ sống của việc **instrumentation đo sai chỗ**.

Đưa vào report như một phát hiện riêng, kèm bảng số client-side vs `latency_ms`.

## Bước 4.6 — Fix action và preventive measure

| Loại | Đề xuất | Lý do |
|---|---|---|
| **Fix ngay** | Tắt cờ: `python scripts/inject_incident.py --disable` | Khôi phục dịch vụ trước, điều tra sau |
| **Fix code** | Đặt timeout cho retrieval (ví dụ 500 ms) và trả lời fallback không kèm tài liệu khi quá hạn | Một thành phần phụ không được phép quyết định latency của cả request |
| **Fix code** | Bọc `agent.run()` bằng `run_in_threadpool` (hoặc đổi `/chat` thành `def` thường để FastAPI tự đẩy sang threadpool) | Chặn hiệu ứng xếp hàng ở [4.5](#bước-45--phát-hiện-nâng-cao-latency_ms-đang-nói-dối-bạn): một retrieval chậm không được làm nghẽn toàn bộ API |
| **Phòng ngừa — đo lường** | Bấm giờ ở **middleware** (`x-response-time-ms`, VT1 đã làm) và đưa số đó vào dashboard bên cạnh `latency_ms` | Số hiện tại không đo được thời gian chờ hàng đợi |
| **Phòng ngừa — đo lường** | Tách span riêng cho `retrieve()` và `generate()` với thời lượng ghi vào log | Hiện phải suy luận từ waterfall; có số trong log thì alert được thẳng vào retrieval |
| **Phòng ngừa — alert** | Bật `HighLatencyP95` với duration 10 phút ([config/alert_rules.yaml](config/alert_rules.yaml)) | Không có alert thì lần sau vẫn phải chờ người dùng phàn nàn |
| **Phòng ngừa — SLO** | Siết `latency_p95_ms` từ 3000 xuống 2000 ms trong [config/slo.yaml](config/slo.yaml) | Sự cố này làm P95 lên 2655 ms mà SLO 3000 vẫn báo xanh — SLO đang quá lỏng, không phát hiện được sự cố thật |

Sau khi xong, **tắt incident**:

```powershell
python scripts/inject_incident.py --disable
curl.exe http://127.0.0.1:8000/health     # xac nhan tat ca incidents deu false
```

## Bước 4.7 — Viết `submission/REPORT.md`

Điền cả 7 mục. Mục 6 là mục ăn 10 điểm A2 — viết theo mẫu này, thay số thật của nhóm:

```markdown
## 6. Điều tra challenge

- Challenge ID: day13-k4-observability-v1 (cohort K4, seed 1304, affected_feature: monitoring)

- Triệu chứng từ metrics:
  Sau khi chạy `python scripts/load_test.py --challenge --concurrency 5` lúc HH:MM,
  `/metrics` cho latency_p95 = 2655 ms so với baseline 160 ms (tăng 16,6 lần), vượt
  ngưỡng latency_threshold_ms = 2000 ms của challenge. Đồng thời error_breakdown = {}
  (không có lỗi), total_cost_usd và quality_avg không đổi, traffic không tăng.
  => Loại trừ quá tải, lỗi hệ thống và thay đổi model. Evidence: evidence/13-challenge-metrics.png

- Trace ID liên quan: <dán trace ID thật>
  Waterfall cho thấy generation `run` tổng 2658 ms, trong đó bước retrieval chiếm
  ~2500 ms còn bước gọi LLM chỉ ~150 ms. Evidence: evidence/14-challenge-trace.png

- Log line/correlation ID liên quan: req-a1b2c3d4 (session k4-challenge-s02)
  Nối từ trace sang log bằng session_id + user_id_hash — hai trường có mặt ở cả trace
  Langfuse (app/agent.py:46-49) lẫn log JSON. Log `incident_enabled` với
  payload.name = "rag_slow" ghi đúng thời điểm sự cố bắt đầu; mọi request sau mốc đó
  có latency_ms ~2650 trong khi trước đó ~150. Evidence: evidence/15-challenge-logs.png

- Root cause:
  app/mock_rag.py:17-18 — `if STATE["rag_slow"]: time.sleep(2.5)` chèn 2,5 giây vào mỗi
  lần retrieval. Cờ được bật qua POST /incidents/rag_slow/enable.

- Phát hiện thêm — instrumentation đo sai chỗ:
  Log ghi latency_ms ~2650 cho cả 5 request, nhưng client (load_test.py) đo được
  2,6s / 5,3s / 8,0s / 10,6s / 13,3s. Nguyên nhân: /chat là `async def` nhưng gọi
  agent.run() đồng bộ có time.sleep, làm chặn event loop và xếp hàng các request;
  trong khi bộ đếm giờ nằm bên trong LabAgent.run nên không thấy thời gian chờ hàng đợi.
  Dashboard dựa trên latency_ms vì vậy báo thấp hơn thực tế 5 lần.
  Evidence: evidence/16-challenge-loadtest-output.png

- Fix action:
  1) Tắt cờ để khôi phục dịch vụ.
  2) Đặt timeout 500 ms cho retrieval kèm fallback trả lời không có tài liệu.
  3) Đẩy agent.run() sang threadpool để một retrieval chậm không làm nghẽn cả API.

- Preventive measure:
  1) Bật alert HighLatencyP95 (P95 > 3000 ms duy trì 10 phút) — config/alert_rules.yaml.
  2) Siết SLO latency_p95_ms từ 3000 xuống 2000 ms: sự cố này làm P95 lên 2655 ms mà
     SLO 3000 vẫn báo xanh, tức SLO hiện tại không phát hiện được sự cố thật.
  3) Đo latency ở middleware (x-response-time-ms) và đưa vào dashboard cạnh latency_ms
     để nhìn thấy thời gian chờ hàng đợi.
```

Mục 7 (đóng góp cá nhân) — **B2 = 20 điểm, phải khớp với Git**:

```markdown
| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Nguyễn Văn A | VT1 — middleware correlation ID, bind metadata, scrub_event, PII patterns | abc1234, def5678 | Thứ tự processor quyết định PII có bị ghi ra đĩa hay không |
| ... | ... | ... | ... |
```

Lấy SHA thật bằng: `git log --oneline --author="<email>"`.

## Bước 4.8 — Kiểm tra trước khi nộp

```powershell
python -m pytest -q                  # phai xanh het
python scripts/validate_logs.py      # >= 80/100, muc tieu 100/100
python scripts/validate_dashboard.py # "HOP LE: 6/6 panel"
git status --short
```

Rà `git status --short` theo [SUBMISSION.md](SUBMISSION.md):

- ❌ Không có `.env` (đã trong `.gitignore` — nếu nó hiện ra là `.gitignore` bị sửa, phải khôi phục)
- ❌ Không có `.venv/`, `__pycache__/`, `.pytest_cache/`
- ❌ Không có `data/logs.jsonl` (đã gitignore — log có thể chứa dữ liệu nhạy cảm)
- ❌ Không có thay đổi nào ở `config/challenge.json`
- ✅ Có `submission/REPORT.md` đã điền
- ✅ Có ảnh trong `submission/evidence/`

Quét lần cuối xem có lỡ commit key không:

```powershell
git grep -nE "pk-lf-|sk-lf-" -- ":!*.md" ; if ($LASTEXITCODE -ne 0) { "OK: khong tim thay key trong source" }
```

Rồi push và nộp repo URL + commit SHA cuối.

## Bước 4.9 — Kịch bản demo 5 phút

[RUBRIC.md](RUBRIC.md) cho A3 **20 điểm** và đòi *"thành viên giải thích được phần mình triển khai"* — nghĩa là **cả 4 người đều phải nói**.

| Phút | Ai | Nội dung | Màn hình |
|---|---|---|---|
| 0:00–0:30 | VT4 | "Hệ thống làm gì, chúng tôi đã thêm quan sát ở đâu." Chạy `/health` → `ok: true`. | Terminal |
| 0:30–1:30 | VT3 | **Metrics.** Dashboard 6 panel, chỉ vào panel Latency: baseline 152 ms → 2655 ms sau khi bật incident. Chỉ rõ SLO line và nói thẳng "chưa chạm 3000 nhưng vượt ngưỡng challenge 2000". | Dashboard |
| 1:30–2:30 | VT2 | **Traces.** Mở Langfuse, chỉ vào waterfall: retrieval 2,5 s, LLM 0,15 s. Nhân tiện chỉ prompt version metadata trên cùng trace đó. | Langfuse |
| 2:30–3:30 | VT1 | **Logs.** Từ `session_id` của trace, tìm ra `correlation_id`, chỉ 2 dòng log cùng ID, chỉ dòng `incident_enabled` đánh dấu thời điểm sự cố, và chỉ `[REDACTED_EMAIL]` chứng minh PII không lộ. | `data/logs.jsonl` |
| 3:30–4:30 | VT4 | **Root cause + phát hiện thêm.** `app/mock_rag.py:17-18`. Rồi mở output `load_test.py`: người dùng chờ 13 s trong khi hệ thống báo 2,6 s → instrumentation đo sai chỗ. | REPORT.md + terminal |
| 4:30–5:00 | VT4 | Fix action + 3 preventive measure, trong đó có đề xuất siết SLO xuống 2000 ms. | REPORT.md |

**Tập chạy trước ít nhất một lần.** Bật sẵn incident trước khi demo để dashboard đã có dữ liệu — đừng để 2,5 giây × 5 request trôi qua trong im lặng trước mặt giám khảo.

## Vấn đáp — VT4

**"Nếu error rate tăng, bạn mở metric, trace hay log trước? Vì sao?"**
Metric trước — vì nó rẻ nhất và trả lời được hai câu hỏi đầu tiên: *có thật sự bất thường không* và *bắt đầu từ lúc nào*. Trace là bước hai để thu hẹp *ở đâu trong đường xử lý*. Log là bước ba để chứng minh *tại sao*. Đi ngược lại (mở log trước) là bơi trong hàng nghìn dòng mà không biết tìm gì. Trong bài này chuỗi đó cụ thể là: metrics báo P95 2655 ms nhưng error = 0 → trace chỉ ra retrieval chiếm 2,5/2,65 s → log `incident_enabled` chứng minh cờ `rag_slow` được bật đúng mốc đó.

**"Evidence nào đủ để kết luận một span là root cause?"**
Ba lớp phải khớp nhau: (1) metric cho thấy triệu chứng và mốc thời gian, (2) trace cho thấy span đó chiếm phần lớn thời lượng chứ không phải span khác, (3) log của **đúng request đó** (cùng correlation ID) giải thích được vì sao. Chỉ có một lớp thì mới là giả thuyết. Trong bài này lớp thứ ba mạnh nhất vì log ghi cả sự kiện `incident_enabled` — nối được nguyên nhân với thời điểm.

**"Vì sao nhóm kết luận SLO 3000 ms đặt sai?"**
Vì sự cố thật đẩy P95 lên 2655 ms — tăng 17 lần so với bình thường — mà SLO 3000 ms vẫn báo xanh. Một SLO không phát hiện được sự cố nghiêm trọng nhất mà hệ thống có thể gặp là SLO vô dụng. Ngưỡng 2000 ms mà challenge dùng phản ánh đúng hơn.

---

# Phần 5 — Phụ lục

## 5.1. Bảng tra cứu nhanh

| Việc | File | Vai trò | Kiểm chứng bằng |
|---|---|---|---|
| Correlation ID | [app/middleware.py:13-30](app/middleware.py#L13-L30) | 1 | header `x-request-id` + `validate_logs.py` |
| Metadata enrichment | [app/main.py:47](app/main.py#L47) | 1 | `validate_logs.py` → `+ [PASSED] Log enrichment` |
| PII processor | [app/logging_config.py:45](app/logging_config.py#L45) | 1 | `tests/test_logging_scrub.py` |
| PII patterns | [app/pii.py:11](app/pii.py#L11) | 1 | `tests/test_pii.py` |
| Langfuse keys | `.env` | 2 | `/health` → `tracing_enabled: true` |
| Prompt v1/v2 | Langfuse UI | 2 | trace metadata `prompt_source: langfuse` |
| Dashboard runtime | `dashboard/app_dashboard.py` (mới) | 3 | ảnh 6 panel có threshold |
| Alert rules | [config/alert_rules.yaml](config/alert_rules.yaml) | 3 | đọc tay, không có script |
| Runbook | [docs/alerts.md](docs/alerts.md) | 3 | đọc tay |
| SLO | [config/slo.yaml](config/slo.yaml) | 3 | đọc tay |
| Điều tra + báo cáo | [submission/REPORT.md](submission/REPORT.md) | 4 | evidence có trace ID + log line |

## 5.2. Lỗi hay gặp

| Triệu chứng | Nguyên nhân | Cách sửa |
|---|---|---|
| `validate_logs.py` mãi không quá 70 dù code đã đúng | Log cũ thiếu `correlation_id` còn trong file (append-only) | `Remove-Item data\logs.jsonl` rồi chạy lại load test |
| `- [FAILED] PII scrubbing` mà không hiểu tại sao | Dùng `str(uuid.uuid4())` làm correlation ID, nhóm 12 số cuối bị detector `cccd` bắt (~10% mỗi lượt) | Đổi sang `f"req-{uuid.uuid4().hex[:8]}"` |
| PII vẫn nằm trong `data/logs.jsonl` | `scrub_event` đặt **sau** `JsonlFileProcessor()` | Chuyển lên trước — `JsonlFileProcessor` tự ghi file bên trong nó |
| `correlation_id` không xuất hiện trong log | Chưa gọi `bind_contextvars`, hoặc bind **sau** `await call_next()` | Bind trước `call_next` trong `dispatch` |
| `dashboard`/`latency_ms` bị thành `[REDACTED_...]` | Regex PII mới quá tham (`\b\d{7,}\b` chẳng hạn) | Thu hẹp pattern, test bằng `scrub_text` trên chuỗi log thật |
| Test `test_agent_prompt_trace` đỏ sau khi sửa `agent.py` | Thêm khoá vào `update_current_trace(metadata=...)` — test so sánh bằng `==` | Chỉ thêm vào `update_current_generation` |
| Test `test_chat_observability` đỏ | Đã refactor `JsonlFileProcessor` để giữ `LOG_PATH` trong `__init__` | Trả lại việc đọc biến global tại thời điểm gọi |
| `/health` vẫn `tracing_enabled: false` | Sửa `.env` mà không restart uvicorn (`--reload` không nạp lại `.env`) | Ctrl+C rồi chạy lại |
| `prompt_source: local-fallback` | Có key nhưng fetch lỗi | Xem [bảng chẩn đoán 2.6](#26-bảng-chẩn-đoán) |
| Đổi label trên Langfuse mà app không đổi | Cache prompt 60 giây | Chờ 60s hoặc restart |
| `python scripts/inject_incident.py` báo "chưa được Lab Coach release" | Thiếu `config/challenge.json` | Với K4 file đã có sẵn; nếu mất thì xin lại Lab Coach, **không tự tạo** |
| Terminal Windows lỗi encoding khi in tiếng Việt | Console dùng cp1258 | Các script đã gọi `configure_utf8_stdio()` ([app/cli.py](app/cli.py)); nếu vẫn lỗi, chạy `chcp 65001` |

> [!TIP]
> Dùng `python -m pytest -q` như [SETUP.md](SETUP.md) và [SUBMISSION.md](SUBMISSION.md) hướng dẫn. Dạng `-m` bảo đảm thư mục hiện tại nằm trong `sys.path`, cần cho `from scripts import validate_logs` ở [tests/test_validate_logs.py:6](tests/test_validate_logs.py#L6) — repo không có `conftest.py` lẫn `scripts/__init__.py`.

## 5.3. Checklist nộp bài

Source và config:

- [ ] 4 khối `TODO` trong `app/` đã hoàn thiện
- [ ] `config/alert_rules.yaml` không còn chữ `TODO` nào
- [ ] `docs/alerts.md` điền đủ 3 runbook
- [ ] `config/slo.yaml` đã bỏ dòng "Replace with your group's target"
- [ ] `config/dashboard.yaml` **giữ nguyên**, `config/challenge.json` **giữ nguyên**
- [ ] `dashboard/app_dashboard.py` chạy được, `requirements.txt` có streamlit đúng version

Kiểm tra tự động:

- [ ] `python -m pytest -q` → xanh hết
- [ ] `python scripts/validate_logs.py` → ≥ 80/100 (mục tiêu 100/100)
- [ ] `python scripts/validate_dashboard.py` → `HỢP LỆ: 6/6 panel`

10 evidence bắt buộc ([SUBMISSION.md](SUBMISSION.md)):

- [ ] Kết quả `validate_logs.py`
- [ ] Danh sách ≥ 10 traces
- [ ] Một trace waterfall
- [ ] Hai prompt version và trace gắn đúng version/label
- [ ] Bằng chứng đổi label hoặc rollback
- [ ] Log có correlation ID
- [ ] Bằng chứng PII đã redact
- [ ] Kết quả `validate_dashboard.py`
- [ ] Dashboard đủ 6 nhóm chỉ số
- [ ] Bằng chứng điều tra challenge (metric + trace ID + log line)

Báo cáo và Git:

- [ ] `submission/REPORT.md` điền đủ 7 mục, mọi ảnh dẫn bằng đường dẫn tương đối
- [ ] Bảng đóng góp cá nhân khớp với `git log`
- [ ] `git status --short`: không `.env`, không `.venv/`, không `data/logs.jsonl`, không key
- [ ] Đã push, có repo URL + commit SHA cuối

## 5.4. Bonus (tối đa +10 điểm)

[RUBRIC.md](RUBRIC.md) cho bonus với *"cost optimization có before/after, automation hữu ích hoặc audit log riêng"*. Ba hướng khả thi trong thời gian còn lại:

**1. Cost optimization có before/after** (dễ nhất, ~15 phút)

```powershell
python scripts/load_test.py --concurrency 5           # ghi total_cost_usd tu /metrics
python scripts/inject_incident.py --scenario cost_spike
python scripts/load_test.py --concurrency 5           # ghi lai, se cao gap ~4 lan
python scripts/inject_incident.py --scenario cost_spike --disable
```

`cost_spike` nhân 4 lần `output_tokens` ([app/mock_llm.py:31-32](app/mock_llm.py#L31-L32)). Vì output đắt gấp 5 lần input ($15 vs $3 mỗi triệu, [app/agent.py:93-96](app/agent.py#L93-L96)), tổng chi phí tăng gần 4 lần. Lập bảng before/after, chỉ ra rằng giới hạn độ dài output là đòn bẩy chi phí lớn nhất.

**2. Audit log riêng** — `.env.example` đã khai sẵn `AUDIT_LOG_PATH=data/audit.jsonl` mà chưa ai dùng, và `.gitignore` đã bỏ qua nó. Thêm một processor thứ hai chỉ ghi các sự kiện nhạy cảm (`incident_enabled`, `incident_disabled`, `request_failed`) sang file riêng với chính sách giữ lâu hơn. Đây rõ ràng là gợi ý bonus mà đề bài để lại.

**3. Automation** — script `scripts/check_all.py` chạy tuần tự pytest → validate_logs → validate_dashboard và in một bảng tổng kết pass/fail, để cả nhóm kiểm tra trước mỗi lần commit.

---

## Trả lời [docs/mock-debug-qa.md](docs/mock-debug-qa.md) — bảng tra nhanh

| # | Câu hỏi | Ai trả lời | Xem mục |
|---|---|---|---|
| 1 | Vì sao chỉ nhìn average latency có thể bỏ sót vấn đề? | VT3 | [Vấn đáp VT3](#vấn-đáp--vt3) |
| 2 | Correlation ID khác trace ID như thế nào? | VT1 | [Vấn đáp VT1](#vấn-đáp--vt1-sẽ-bị-hỏi-gì) |
| 3 | Error rate tăng thì mở metric, trace hay log trước? | VT4 | [Vấn đáp VT4](#vấn-đáp--vt4) |
| 4 | PII scrub trước hay sau khi render JSON? | VT1 | [Vấn đáp VT1](#vấn-đáp--vt1-sẽ-bị-hỏi-gì) |
| 5 | Alert tốt cần condition/duration/severity/owner thế nào? | VT3 | [Vấn đáp VT3](#vấn-đáp--vt3) |
| 6 | Cost tăng mà traffic không tăng thì kiểm tra trường nào? | VT3 | [Vấn đáp VT3](#vấn-đáp--vt3) |
| 7 | Evidence nào đủ để kết luận một span là root cause? | VT4 | [Vấn đáp VT4](#vấn-đáp--vt4) |
| 8 | Vì sao `validate_logs.py` đạt 100 chưa đồng nghĩa lab đạt 100 điểm? | VT1 | [Vấn đáp VT1](#vấn-đáp--vt1-sẽ-bị-hỏi-gì) |

Chúc nhóm làm bài tốt. Nhớ: **bằng chứng không kiểm chứng được thì không được tính** ([RULES.md](RULES.md)).
