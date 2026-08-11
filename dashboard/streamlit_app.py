"""Live Streamlit console for the team demo.

Combines the six dashboard.yaml panels with one-click incident/load-test
controls, so the team can trigger a scenario and watch metrics -> logs
react live during the checkpoint 3 / final demo, without juggling three
terminal windows. Data still comes from data/logs.jsonl (same contract as
scripts/build_dashboard.py); the API calls only drive the demo controls.

Run: streamlit run dashboard/streamlit_app.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import altair as alt
import httpx
import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_dashboard import (  # noqa: E402
    CATEGORICAL,
    LOG_PATH,
    REFRESH_SECONDS,
    SEQ_BLUE,
    STATUS_CRITICAL,
    STATUS_GOOD,
    THRESHOLDS,
    WINDOW_MINUTES,
    build_metrics,
    fmt_value,
    load_events,
)

API_BASE = "http://127.0.0.1:8000"
SAMPLE_QUERIES = REPO_ROOT / "data" / "sample_queries.jsonl"
SCENARIOS = ["rag_slow", "tool_fail", "cost_spike"]

st.set_page_config(page_title="Day 13 AI Observability", layout="wide")


def call_with_retry(fn, attempts: int = 3, delay: float = 0.6):
    """The dev server (--reload) can briefly refuse connections right after
    a request is logged to data/logs.jsonl. Retrying keeps the demo smooth
    instead of surfacing that as a broken button."""
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except httpx.HTTPError as exc:
            last_exc = exc
            time.sleep(delay)
    raise last_exc


def badge(passed: bool, label: str) -> str:
    color = STATUS_GOOD if passed else STATUS_CRITICAL
    text = "PASS" if passed else "FAIL"
    return f'<span style="color:{color};font-weight:600;font-size:0.85rem">● {text} · {label}</span>'


# ---------------------------------------------------------------------------
# Sidebar — demo controls (incident toggle + load test trigger)
# ---------------------------------------------------------------------------
st.sidebar.title("Demo controls")

try:
    health = call_with_retry(lambda: httpx.get(f"{API_BASE}/health", timeout=3).json())
    st.sidebar.success(f"API OK · tracing_enabled={health.get('tracing_enabled')}")
    incidents = health.get("incidents", {})
except Exception as exc:  # noqa: BLE001
    st.sidebar.error(f"Không gọi được API tại {API_BASE}\n{exc}")
    incidents = {}

st.sidebar.subheader("1. Bật/tắt incident practice")
scenario = st.sidebar.selectbox("Scenario", SCENARIOS)
is_active = incidents.get(scenario, False)
st.sidebar.caption(f"Trạng thái: {'🔴 đang bật' if is_active else '⚪ đang tắt'}")
c1, c2 = st.sidebar.columns(2)
if c1.button("Enable", use_container_width=True, type="primary" if not is_active else "secondary"):
    call_with_retry(lambda: httpx.post(f"{API_BASE}/incidents/{scenario}/enable", timeout=5))
    st.rerun()
if c2.button("Disable", use_container_width=True):
    call_with_retry(lambda: httpx.post(f"{API_BASE}/incidents/{scenario}/disable", timeout=5))
    st.rerun()

st.sidebar.subheader("2. Chạy load test")
concurrency = st.sidebar.slider("Concurrency", 1, 10, 5)
if st.sidebar.button("Run load test", use_container_width=True, type="primary"):
    import concurrent.futures
    payloads = [
        json.loads(line)
        for line in SAMPLE_QUERIES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    progress = st.sidebar.progress(0.0, text=f"Đang gửi {len(payloads)} request...")
    sent = 0
    with httpx.Client(timeout=30.0) as client:
        def send_req(p):
            try:
                call_with_retry(lambda p=p: client.post(f"{API_BASE}/chat", json=p))
            except Exception:
                pass
                
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(send_req, p) for p in payloads]
            for _ in concurrent.futures.as_completed(futures):
                sent += 1
                progress.progress(sent / max(1, len(payloads)))
                
    st.sidebar.success(f"Đã gửi {sent}/{len(payloads)} request (với Concurrency={concurrency})")
    time.sleep(0.5)
    st.rerun()

st.sidebar.subheader("3. Chạy Đề Thi (Challenge)")
if st.sidebar.button("Run Challenge", use_container_width=True, type="primary"):
    from app.challenge import load_challenge, ordered_queries
    import concurrent.futures
    challenge = load_challenge()
    payloads = ordered_queries(challenge)
    progress = st.sidebar.progress(0.0, text=f"Đang gửi {len(payloads)} request Đề Thi...")
    sent = 0
    with httpx.Client(timeout=30.0) as client:
        try:
            call_with_retry(lambda: client.post(f"{API_BASE}/incidents/{challenge.incident}/enable"))
        except Exception:
            pass
            
        def send_req(p):
            try:
                call_with_retry(lambda p=p: client.post(f"{API_BASE}/chat", json=p))
            except Exception:
                pass
                
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_req, p) for p in payloads]
            for _ in concurrent.futures.as_completed(futures):
                sent += 1
                progress.progress(sent / max(1, len(payloads)))
                
    st.sidebar.success(f"Đã kích hoạt {challenge.incident} và gửi {sent}/{len(payloads)} request Đề Thi (Concurrency=5)")
    time.sleep(0.5)
    st.rerun()


st.sidebar.divider()
st.sidebar.subheader("4. Cấu hình hiển thị (SLO)")
mode = st.sidebar.radio("Ngưỡng chấm điểm P95", ["Practice (3000ms)", "Challenge (2000ms)"])
if "Challenge" in mode:
    THRESHOLDS["latency_p95_ms"] = 2000
else:
    THRESHOLDS["latency_p95_ms"] = 3000

st.sidebar.divider()
st.sidebar.caption(
    "Contract: config/dashboard.yaml · SLO: config/slo.yaml · Alert: config/alert_rules.yaml\n\n"
    "Nguồn dữ liệu: data/logs.jsonl — panel bên phải tự refresh mỗi "
    f"{REFRESH_SECONDS}s theo đúng contract."
)

# ---------------------------------------------------------------------------
# Main — the six dashboard.yaml panels, auto-refreshing
# ---------------------------------------------------------------------------
st.title("Day 13 AI Observability — Live Dashboard")


@st.fragment(run_every=REFRESH_SECONDS)
def render_dashboard() -> None:
    events = load_events(LOG_PATH)
    m = build_metrics(events)

    window_label = (
        f'{m["window_start"].strftime("%Y-%m-%d %H:%M")} → {m["window_end"].strftime("%H:%M")} UTC'
        if m["received_total"] or m["sent_total"] else "không có dữ liệu"
    )
    st.caption(
        f'Time range: **{window_label}** (last {WINDOW_MINUTES} min) · '
        f'Generated {pd.Timestamp.utcnow().strftime("%H:%M:%S UTC")} · '
        f'{len(events)} log record'
    )

    lat_p95_pass = m["latency_p95"] <= THRESHOLDS["latency_p95_ms"]
    err_pass = m["error_rate_pct"] <= THRESHOLDS["error_rate_pct"]
    cost_pass = m["cost_total"] <= THRESHOLDS["cost_total_usd"]
    quality_pass = m["quality_avg"] >= THRESHOLDS["quality_avg"]

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Traffic (requests)", f'{m["traffic_total"]:,}')
    k2.metric("Latency P95", fmt_value(m["latency_p95"], "ms"))
    k3.metric("Error rate", fmt_value(m["error_rate_pct"], "percent"))
    k4.metric("Total cost", fmt_value(m["cost_total"], "usd"))
    k5.metric("Quality avg", f'{m["quality_avg"]:.2f}')

    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    with col1:
        st.markdown("**1. Latency percentiles (ms)**")
        df = pd.DataFrame(
            {
                "percentile": ["P50", "P95", "P99"],
                "value": [m["latency_p50"], m["latency_p95"], m["latency_p99"]],
            }
        )
        bars = (
            alt.Chart(df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("percentile:N", sort=None, title=None),
                y=alt.Y("value:Q", title="ms"),
                color=alt.Color(
                    "percentile:N",
                    scale=alt.Scale(domain=["P50", "P95", "P99"], range=[SEQ_BLUE[250], SEQ_BLUE[450], SEQ_BLUE[650]]),
                    legend=None,
                ),
                tooltip=["percentile", "value"],
            )
        )
        rule = alt.Chart(pd.DataFrame({"y": [THRESHOLDS["latency_p95_ms"]]})).mark_rule(
            color=STATUS_CRITICAL, strokeDash=[4, 3]
        ).encode(y="y:Q")
        st.altair_chart(bars + rule, use_container_width=True)
        st.markdown(badge(lat_p95_pass, f'P95 ≤ {THRESHOLDS["latency_p95_ms"]:,}ms'), unsafe_allow_html=True)

    with col2:
        st.markdown("**2. Request traffic (per minute)**")
        if m["traffic_series"]:
            df = pd.DataFrame(m["traffic_series"], columns=["minute", "count"])
            chart = (
                alt.Chart(df)
                .mark_bar(color=SEQ_BLUE[450], cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(x=alt.X("minute:T", title=None), y=alt.Y("count:Q", title="requests"), tooltip=["minute", "count"])
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Không có dữ liệu traffic trong cửa sổ.")
        st.caption(f'Rate: {m["traffic_rate_per_min"]:.2f} req/min (SLO ≥ {THRESHOLDS["traffic_rate_per_min"]})')

    with col3:
        st.markdown("**3. Error rate & breakdown**")
        st.markdown(badge(err_pass, f'{fmt_value(m["error_rate_pct"], "percent")} ≤ {THRESHOLDS["error_rate_pct"]}%'), unsafe_allow_html=True)
        st.caption(f'{m["failed_total"]} failed / {m["received_total"]} received')
        if m["error_breakdown"]:
            df = pd.DataFrame(m["error_breakdown"].items(), columns=["error_type", "count"])
            chart = (
                alt.Chart(df)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    y=alt.Y("error_type:N", sort="-x", title=None),
                    x=alt.X("count:Q", title="count"),
                    color=alt.Color("error_type:N", scale=alt.Scale(range=CATEGORICAL), legend=None),
                    tooltip=["error_type", "count"],
                )
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.success("Không có lỗi trong cửa sổ 60 phút.")

    with col4:
        st.markdown("**4. Cost over time (USD)**")
        st.markdown(badge(cost_pass, f'total {fmt_value(m["cost_total"], "usd")} ≤ ${THRESHOLDS["cost_total_usd"]}'), unsafe_allow_html=True)
        if m["cost_series"]:
            df = pd.DataFrame(m["cost_series"], columns=["minute", "cost_usd"])
            chart = (
                alt.Chart(df)
                .mark_bar(color=SEQ_BLUE[450], cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(x=alt.X("minute:T", title=None), y=alt.Y("cost_usd:Q", title="usd"), tooltip=["minute", "cost_usd"])
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Không có dữ liệu cost trong cửa sổ.")

    with col5:
        st.markdown("**5. Input / output tokens**")
        df = pd.DataFrame(
            {
                "field": ["tokens_in", "tokens_out"],
                "value": [m["tokens_in_total"], m["tokens_out_total"]],
            }
        )
        bars = (
            alt.Chart(df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("field:N", sort=None, title=None),
                y=alt.Y("value:Q", title="tokens"),
                color=alt.Color("field:N", scale=alt.Scale(domain=["tokens_in", "tokens_out"], range=CATEGORICAL[:2]), legend=None),
                tooltip=["field", "value"],
            )
        )
        rule = alt.Chart(pd.DataFrame({"y": [THRESHOLDS["tokens_per_field"]]})).mark_rule(
            color=STATUS_CRITICAL, strokeDash=[4, 3]
        ).encode(y="y:Q")
        st.altair_chart(bars + rule, use_container_width=True)

    with col6:
        st.markdown("**6. Quality proxy (mean quality_score)**")
        df = pd.DataFrame({"metric": ["quality"], "value": [m["quality_avg"]], "max": [1.0]})
        track = alt.Chart(df).mark_bar(color=SEQ_BLUE[150], height=24).encode(
            x=alt.X("max:Q", title=None, scale=alt.Scale(domain=[0, 1])), y=alt.Y("metric:N", title=None)
        )
        fill_color = STATUS_GOOD if quality_pass else STATUS_CRITICAL
        fill = alt.Chart(df).mark_bar(color=fill_color, height=24).encode(
            x=alt.X("value:Q", scale=alt.Scale(domain=[0, 1])), y=alt.Y("metric:N", title=None), tooltip=["value"]
        )
        tick = alt.Chart(pd.DataFrame({"x": [THRESHOLDS["quality_avg"]]})).mark_rule(
            color=STATUS_CRITICAL, strokeDash=[4, 3]
        ).encode(x="x:Q")
        st.altair_chart((track + fill + tick).properties(height=70), use_container_width=True)
        st.markdown(badge(quality_pass, f'{m["quality_avg"]:.2f} ≥ {THRESHOLDS["quality_avg"]}'), unsafe_allow_html=True)

    st.divider()
    st.markdown("**Recent logs** — dùng để nối Metrics → Traces → Logs khi demo (khớp `correlation_id` với trace trên Langfuse)")
    recent = events[-20:][::-1]
    rows = []
    for e in recent:
        rows.append(
            {
                "ts": e.get("ts"),
                "event": e.get("event"),
                "correlation_id": e.get("correlation_id", ""),
                "feature": e.get("feature", ""),
                "latency_ms": e.get("latency_ms", ""),
                "error_type": e.get("error_type", ""),
                "quality_score": e.get("quality_score", ""),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


render_dashboard()
