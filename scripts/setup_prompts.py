"""
Script tạo Prompt Versioning trên Langfuse cho Day 13 Lab.
Chạy: .venv/bin/python scripts/setup_prompts.py

Làm gì:
  1. Kết nối Langfuse bằng keys trong .env
  2. Tạo prompt day13-chat Version 1 → label: baseline, production
  3. Tạo prompt day13-chat Version 2 → label: candidate
  4. In ra Trace IDs để điền vào REPORT.md
"""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Kiểm tra keys ────────────────────────────────────────────────────────────
public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
prompt_name = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")

if not public_key or not secret_key:
    print("❌ Chưa có LANGFUSE_PUBLIC_KEY hoặc LANGFUSE_SECRET_KEY trong .env")
    sys.exit(1)

print(f"✅ Kết nối tới: {host}")
print(f"✅ Prompt name: {prompt_name}\n")

# ── Kết nối Langfuse ─────────────────────────────────────────────────────────
from langfuse import Langfuse

langfuse = Langfuse(
    public_key=public_key,
    secret_key=secret_key,
    host=host,
)

# ── Nội dung Prompt V1 (Baseline) ────────────────────────────────────────────
PROMPT_V1 = """\
Bạn là trợ lý AI hỗ trợ tính năng {{feature}}.

Dựa vào tài liệu tham khảo sau để trả lời:
{{docs}}

Câu hỏi của người dùng: {{message}}

Hãy trả lời đầy đủ, chính xác và hữu ích.\
"""

# ── Nội dung Prompt V2 (Candidate) ───────────────────────────────────────────
PROMPT_V2 = """\
Bạn là trợ lý AI hỗ trợ tính năng {{feature}}.

Tài liệu tham khảo:
{{docs}}

Câu hỏi: {{message}}

Hãy trả lời ngắn gọn, súc tích trong tối đa 3 câu.\
"""

# ── Tạo Prompt V1 ─────────────────────────────────────────────────────────────
print("📝 Tạo Prompt Version 1 (baseline + production)...")
try:
    prompt_v1 = langfuse.create_prompt(
        name=prompt_name,
        prompt=PROMPT_V1,
        labels=["baseline", "production"],
        config={"temperature": 0.7},
    )
    print(f"   ✅ Version {prompt_v1.version} tạo thành công")
    print(f"   Labels: baseline, production")
except Exception as e:
    print(f"   ⚠️  V1 có thể đã tồn tại hoặc lỗi: {e}")
    print("   → Tiếp tục tạo V2...\n")

# ── Tạo Prompt V2 ─────────────────────────────────────────────────────────────
print("\n📝 Tạo Prompt Version 2 (candidate)...")
try:
    prompt_v2 = langfuse.create_prompt(
        name=prompt_name,
        prompt=PROMPT_V2,
        labels=["candidate"],
        config={"temperature": 0.5},
    )
    print(f"   ✅ Version {prompt_v2.version} tạo thành công")
    print(f"   Labels: candidate")
except Exception as e:
    print(f"   ❌ Lỗi tạo V2: {e}")
    sys.exit(1)

# ── Xác minh ─────────────────────────────────────────────────────────────────
print("\n🔍 Xác minh danh sách prompts trên Langfuse...")
try:
    prompts = langfuse.client.prompts.list(name=prompt_name)
    print(f"   Tổng số versions: {len(prompts.data)}")
    for p in prompts.data:
        labels_str = ", ".join(p.labels) if p.labels else "(no label)"
        print(f"   - Version {p.version}: labels=[{labels_str}]")
except Exception as e:
    print(f"   ⚠️  Không list được prompts: {e}")

# ── Hướng dẫn tiếp theo ───────────────────────────────────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ XONG! Prompt đã được tạo trên Langfuse.

📌 Bước tiếp theo:
   1. Chạy API:    .venv/bin/uvicorn app.main:app --reload --env-file .env
   2. Chạy test:   .venv/bin/python scripts/load_test.py
   3. Mở Langfuse → Traces → xem trace ID và prompt_version trong metadata
   4. Chụp ảnh màn hình → lưu vào submission/evidence/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

langfuse.flush()
