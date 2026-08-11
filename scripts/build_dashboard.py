"""Generate a static HTML dashboard from data/logs.jsonl.

Reads the same six panels defined in config/dashboard.yaml (latency, traffic,
errors, cost, tokens, quality) and renders them as a self-contained HTML file
at dashboard/index.html that can be opened in a browser and screenshotted for
submission evidence. Re-run this script any time data/logs.jsonl changes.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
OUT_PATH = REPO_ROOT / "dashboard" / "index.html"
WINDOW_MINUTES = 60
REFRESH_SECONDS = 30

THRESHOLDS = {
    "latency_p95_ms": 3000,
    "traffic_rate_per_min": 1,
    "error_rate_pct": 2,
    "cost_total_usd": 2.5,
    "tokens_per_field": 50000,
    "quality_avg": 0.75,
}

# dataviz skill reference palette (references/palette.md) — validated, unchanged.
SEQ_BLUE = {150: "#b7d3f6", 250: "#86b6ef", 450: "#2a78d6", 650: "#104281"}
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[idx])


def minute_bucket(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def build_metrics(events: list[dict]) -> dict:
    timestamped = [(parse_ts(e["ts"]), e) for e in events if isinstance(e.get("ts"), str)]
    now = datetime.now(timezone.utc)
    if not timestamped:
        window_end = now
        window_start = now - timedelta(minutes=WINDOW_MINUTES)
        windowed: list[tuple[datetime, dict]] = []
    else:
        window_end = max(t for t, _ in timestamped)
        window_start = window_end - timedelta(minutes=WINDOW_MINUTES)
        windowed = [(t, e) for t, e in timestamped if t >= window_start]

    received = [(t, e) for t, e in windowed if e.get("event") == "request_received"]
    sent = [(t, e) for t, e in windowed if e.get("event") == "response_sent"]
    failed = [(t, e) for t, e in windowed if e.get("event") == "request_failed"]

    latencies = [e["latency_ms"] for _, e in sent if isinstance(e.get("latency_ms"), (int, float))]
    costs = [e["cost_usd"] for _, e in sent if isinstance(e.get("cost_usd"), (int, float))]
    tokens_in = [e["tokens_in"] for _, e in sent if isinstance(e.get("tokens_in"), (int, float))]
    tokens_out = [e["tokens_out"] for _, e in sent if isinstance(e.get("tokens_out"), (int, float))]
    quality = [e["quality_score"] for _, e in sent if isinstance(e.get("quality_score"), (int, float))]
    error_breakdown = Counter(e.get("error_type") or "unknown" for _, e in failed)

    cost_by_min: dict[datetime, float] = defaultdict(float)
    for t, e in sent:
        if isinstance(e.get("cost_usd"), (int, float)):
            cost_by_min[minute_bucket(t)] += e["cost_usd"]

    traffic_by_min: dict[datetime, int] = defaultdict(int)
    for t, _e in received:
        traffic_by_min[minute_bucket(t)] += 1

    window_minutes_actual = max(1.0, (window_end - window_start).total_seconds() / 60)

    return {
        "window_start": window_start,
        "window_end": window_end,
        "latency_p50": percentile(latencies, 50),
        "latency_p95": percentile(latencies, 95),
        "latency_p99": percentile(latencies, 99),
        "traffic_total": len(received),
        "traffic_rate_per_min": round(len(received) / window_minutes_actual, 2),
        "traffic_series": sorted(traffic_by_min.items()),
        "error_rate_pct": round((len(failed) / len(received) * 100) if received else 0.0, 2),
        "error_breakdown": error_breakdown,
        "cost_total": round(sum(costs), 4),
        "cost_series": sorted(cost_by_min.items()),
        "tokens_in_total": sum(tokens_in),
        "tokens_out_total": sum(tokens_out),
        "quality_avg": round(statistics.mean(quality), 4) if quality else 0.0,
        "received_total": len(received),
        "sent_total": len(sent),
        "failed_total": len(failed),
    }


def rounded_top_bar(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    if h <= 0:
        return ""
    r = max(0.0, min(r, w / 2, h))
    return (
        f"M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} "
        f"Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"L{x + w - r:.1f},{y:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"L{x + w:.1f},{y + h:.1f} Z"
    )


def fmt_value(value: float, unit: str) -> str:
    if unit == "usd":
        return f"${value:,.4f}"
    if unit in ("ms",):
        return f"{value:,.0f} ms"
    if unit == "percent":
        return f"{value:,.2f}%"
    if unit == "score_0_to_1":
        return f"{value:.2f}"
    if unit == "tokens":
        return f"{value:,.0f}"
    return f"{value:,.0f}"


def status_badge(passed: bool, threshold_label: str) -> str:
    color = STATUS_GOOD if passed else STATUS_CRITICAL
    text = "PASS" if passed else "FAIL"
    return (
        f'<span class="badge" style="color:{color};border-color:{color}">'
        f'<span class="dot" style="background:{color}"></span>{text} · {threshold_label}</span>'
    )


def stat_tile(label: str, value: str, sub: str = "", badge: str = "") -> str:
    return (
        '<div class="tile">'
        f'<div class="tile-label">{label}</div>'
        f'<div class="tile-value">{value}</div>'
        f'<div class="tile-sub">{sub}</div>'
        f'{badge}'
        "</div>"
    )


def category_bar_chart(
    bars: list[tuple[str, float, str]],
    unit: str,
    threshold: float | None = None,
    threshold_label: str = "",
    height: int = 200,
) -> str:
    width = 560
    pad_left, pad_right, pad_top, pad_bottom = 56, 20, 24, 34
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    values = [v for _, v, _ in bars] + ([threshold] if threshold else [])
    y_max = max(values) * 1.2 if values and max(values) > 0 else 1.0

    def y(v: float) -> float:
        return pad_top + plot_h - (v / y_max * plot_h)

    n = max(1, len(bars))
    slot_w = plot_w / n
    bar_w = min(48, slot_w * 0.5)

    svg = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for i in range(4):
        gy = pad_top + plot_h * i / 3
        gv = y_max * (1 - i / 3)
        svg.append(f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" class="grid"/>')
        svg.append(f'<text x="{pad_left - 8}" y="{gy + 4:.1f}" class="axis-label" text-anchor="end">{fmt_value(gv, unit)}</text>')

    if threshold is not None:
        ty = y(threshold)
        svg.append(f'<line x1="{pad_left}" y1="{ty:.1f}" x2="{width - pad_right}" y2="{ty:.1f}" class="threshold"/>')
        svg.append(f'<text x="{width - pad_right}" y="{ty - 4:.1f}" class="threshold-label" text-anchor="end">{threshold_label}</text>')

    for i, (label, value, color) in enumerate(bars):
        cx = pad_left + slot_w * i + slot_w / 2
        bx = cx - bar_w / 2
        by = y(value)
        bh = pad_top + plot_h - by
        svg.append(f'<path d="{rounded_top_bar(bx, by, bar_w, bh)}" fill="{color}"><title>{label}: {fmt_value(value, unit)}</title></path>')
        svg.append(f'<text x="{cx:.1f}" y="{by - 8:.1f}" class="value-label" text-anchor="middle">{fmt_value(value, unit)}</text>')
        svg.append(f'<text x="{cx:.1f}" y="{height - pad_bottom + 18:.1f}" class="axis-label" text-anchor="middle">{label}</text>')

    svg.append(f'<line x1="{pad_left}" y1="{pad_top + plot_h:.1f}" x2="{width - pad_right}" y2="{pad_top + plot_h:.1f}" class="baseline"/>')
    svg.append("</svg>")
    return "".join(svg)


def time_bar_chart(
    series: list[tuple[datetime, float]],
    unit: str,
    threshold: float | None = None,
    threshold_label: str = "",
    height: int = 200,
    color: str = SEQ_BLUE[450],
) -> str:
    width = 560
    pad_left, pad_right, pad_top, pad_bottom = 56, 20, 24, 34
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    if not series:
        return (
            f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">'
            f'<text x="{width/2}" y="{height/2}" class="axis-label" text-anchor="middle">Không có dữ liệu trong cửa sổ 60 phút</text>'
            "</svg>"
        )

    values = [v for _, v in series] + ([threshold] if threshold else [])
    y_max = max(values) * 1.2 if values and max(values) > 0 else 1.0

    def y(v: float) -> float:
        return pad_top + plot_h - (v / y_max * plot_h)

    n = len(series)
    slot_w = plot_w / n
    bar_w = min(28, slot_w * 0.6)
    label_stride = max(1, n // 8)

    svg = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for i in range(4):
        gy = pad_top + plot_h * i / 3
        gv = y_max * (1 - i / 3)
        svg.append(f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" class="grid"/>')
        svg.append(f'<text x="{pad_left - 8}" y="{gy + 4:.1f}" class="axis-label" text-anchor="end">{fmt_value(gv, unit)}</text>')

    if threshold is not None:
        ty = y(threshold)
        svg.append(f'<line x1="{pad_left}" y1="{ty:.1f}" x2="{width - pad_right}" y2="{ty:.1f}" class="threshold"/>')
        svg.append(f'<text x="{width - pad_right}" y="{ty - 4:.1f}" class="threshold-label" text-anchor="end">{threshold_label}</text>')

    for i, (t, value) in enumerate(series):
        cx = pad_left + slot_w * i + slot_w / 2
        bx = cx - bar_w / 2
        by = y(value)
        bh = pad_top + plot_h - by
        svg.append(f'<path d="{rounded_top_bar(bx, by, bar_w, bh)}" fill="{color}"><title>{t.strftime("%H:%M")}: {fmt_value(value, unit)}</title></path>')
        if i % label_stride == 0:
            svg.append(f'<text x="{cx:.1f}" y="{height - pad_bottom + 18:.1f}" class="axis-label" text-anchor="middle">{t.strftime("%H:%M")}</text>')

    svg.append(f'<line x1="{pad_left}" y1="{pad_top + plot_h:.1f}" x2="{width - pad_right}" y2="{pad_top + plot_h:.1f}" class="baseline"/>')
    svg.append("</svg>")
    return "".join(svg)


def horizontal_breakdown_chart(counter: Counter, height_per_row: int = 32) -> str:
    width = 560
    pad_left, pad_right, pad_top = 140, 60, 16
    if not counter:
        return (
            f'<svg viewBox="0 0 {width} 80" class="chart" role="img">'
            f'<text x="{width/2}" y="40" class="axis-label" text-anchor="middle">Không có lỗi trong cửa sổ 60 phút</text>'
            "</svg>"
        )
    items = counter.most_common(8)
    other = sum(v for _, v in counter.most_common()[8:])
    if other:
        items.append(("Other", other))
    max_v = max(v for _, v in items)
    height = pad_top + len(items) * height_per_row + 12
    plot_w = width - pad_left - pad_right

    svg = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for i, (name, count) in enumerate(items):
        y = pad_top + i * height_per_row
        bar_h = 18
        bar_w = (count / max_v) * plot_w if max_v else 0
        color = CATEGORICAL[i % len(CATEGORICAL)]
        svg.append(f'<text x="{pad_left - 10}" y="{y + bar_h/2 + 4:.1f}" class="axis-label" text-anchor="end">{name}</text>')
        svg.append(f'<path d="{rounded_top_bar(pad_left, y, max(bar_w, 2), bar_h)}" fill="{color}"><title>{name}: {count}</title></path>')
        svg.append(f'<text x="{pad_left + bar_w + 8:.1f}" y="{y + bar_h/2 + 4:.1f}" class="value-label">{count}</text>')
    svg.append("</svg>")
    return "".join(svg)


def meter_svg(value: float, threshold: float, passed: bool) -> str:
    width, height = 560, 90
    pad = 24
    track_w = width - pad * 2
    fill_color = STATUS_GOOD if passed else STATUS_CRITICAL
    fill_w = max(0.0, min(1.0, value)) * track_w
    tick_x = pad + max(0.0, min(1.0, threshold)) * track_w
    return f'''<svg viewBox="0 0 {width} {height}" class="chart" role="img">
  <rect x="{pad}" y="30" width="{track_w}" height="18" rx="9" fill="{SEQ_BLUE[150]}"/>
  <rect x="{pad}" y="30" width="{fill_w:.1f}" height="18" rx="9" fill="{fill_color}"><title>Quality avg: {value:.2f}</title></rect>
  <line x1="{tick_x:.1f}" y1="24" x2="{tick_x:.1f}" y2="54" class="threshold"/>
  <text x="{tick_x:.1f}" y="18" class="threshold-label" text-anchor="middle">SLO ≥ {threshold:.2f}</text>
  <text x="{pad}" y="70" class="axis-label">0.0</text>
  <text x="{width - pad}" y="70" class="axis-label" text-anchor="end">1.0</text>
</svg>'''


def render_html(m: dict) -> str:
    lat_p95_pass = m["latency_p95"] <= THRESHOLDS["latency_p95_ms"]
    err_pass = m["error_rate_pct"] <= THRESHOLDS["error_rate_pct"]
    cost_pass = m["cost_total"] <= THRESHOLDS["cost_total_usd"]
    tok_in_pass = m["tokens_in_total"] <= THRESHOLDS["tokens_per_field"]
    tok_out_pass = m["tokens_out_total"] <= THRESHOLDS["tokens_per_field"]
    quality_pass = m["quality_avg"] >= THRESHOLDS["quality_avg"]

    latency_chart = category_bar_chart(
        [
            ("P50", m["latency_p50"], SEQ_BLUE[250]),
            ("P95", m["latency_p95"], SEQ_BLUE[450]),
            ("P99", m["latency_p99"], SEQ_BLUE[650]),
        ],
        unit="ms",
        threshold=THRESHOLDS["latency_p95_ms"],
        threshold_label=f'SLO P95 ≤ {THRESHOLDS["latency_p95_ms"]:,} ms',
    )
    traffic_chart = time_bar_chart(
        m["traffic_series"], unit="requests_per_minute",
        threshold=THRESHOLDS["traffic_rate_per_min"], threshold_label="SLO ≥ 1 req/min",
    )
    cost_chart = time_bar_chart(
        m["cost_series"], unit="usd", color=SEQ_BLUE[450],
        threshold=None, threshold_label="",
    )
    errors_chart = horizontal_breakdown_chart(m["error_breakdown"])
    tokens_chart = category_bar_chart(
        [
            ("tokens_in", m["tokens_in_total"], CATEGORICAL[0]),
            ("tokens_out", m["tokens_out_total"], CATEGORICAL[1]),
        ],
        unit="tokens",
        threshold=THRESHOLDS["tokens_per_field"],
        threshold_label=f'SLO ≤ {THRESHOLDS["tokens_per_field"]:,} tokens',
    )
    quality_chart = meter_svg(m["quality_avg"], THRESHOLDS["quality_avg"], quality_pass)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    window_label = (
        f'{m["window_start"].strftime("%Y-%m-%d %H:%M")} → {m["window_end"].strftime("%H:%M")} UTC'
        if m["received_total"] or m["sent_total"] else "không có dữ liệu"
    )

    return f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Day 13 AI Observability Dashboard</title>
<style>
  :root {{
    --surface-1: {SURFACE};
    --page: #f9f9f7;
    --text-primary: {INK_PRIMARY};
    --text-secondary: {INK_SECONDARY};
    --text-muted: {INK_MUTED};
    --grid: {GRID};
    --border: rgba(11,11,11,0.10);
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --surface-1: #1a1a19;
      --page: #0d0d0d;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted: #898781;
      --grid: #2c2c2a;
      --border: rgba(255,255,255,0.10);
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px; background: var(--page); color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  header {{ margin-bottom: 20px; }}
  h1 {{ margin: 0 0 4px; font-size: 22px; }}
  .meta {{ color: var(--text-secondary); font-size: 13px; }}
  .meta span {{ color: var(--text-muted); }}
  .grid-panels {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(560px, 1fr)); gap: 16px;
  }}
  .panel {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px 16px 12px;
  }}
  .panel-header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }}
  .panel-title {{ font-size: 15px; font-weight: 600; }}
  .panel-unit {{ font-size: 12px; color: var(--text-muted); }}
  .tiles {{ display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }}
  .tile {{ flex: 1; min-width: 110px; }}
  .tile-label {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .02em; }}
  .tile-value {{ font-size: 22px; font-weight: 600; }}
  .tile-sub {{ font-size: 11px; color: var(--text-secondary); }}
  .badge {{
    display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600;
    border: 1px solid; border-radius: 999px; padding: 2px 8px; margin-top: 4px;
  }}
  .badge .dot {{ width: 6px; height: 6px; border-radius: 50%; }}
  .chart {{ width: 100%; height: auto; display: block; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .baseline {{ stroke: var(--text-muted); stroke-width: 1; }}
  .axis-label {{ fill: var(--text-muted); font-size: 10px; }}
  .value-label {{ fill: var(--text-secondary); font-size: 10px; font-weight: 600; }}
  .threshold {{ stroke: {STATUS_CRITICAL}; stroke-width: 1.5; stroke-dasharray: 4 3; }}
  .threshold-label {{ fill: {STATUS_CRITICAL}; font-size: 10px; font-weight: 600; }}
  footer {{ margin-top: 20px; font-size: 12px; color: var(--text-muted); }}
</style>
</head>
<body>
<header>
  <h1>Day 13 AI Observability — Dashboard</h1>
  <div class="meta">
    Time range: <span>{window_label}</span> (last {WINDOW_MINUTES} min) ·
    Refresh contract: <span>{REFRESH_SECONDS}s</span> (regenerate: <code>python scripts/build_dashboard.py</code>) ·
    Generated: <span>{generated}</span> · Source: <span>data/logs.jsonl</span>
  </div>
</header>
<div class="grid-panels">

  <section class="panel">
    <div class="panel-header"><div class="panel-title">1. Latency percentiles</div><div class="panel-unit">ms</div></div>
    {latency_chart}
    {status_badge(lat_p95_pass, f'P95 {fmt_value(m["latency_p95"], "ms")} vs ≤{THRESHOLDS["latency_p95_ms"]:,} ms')}
  </section>

  <section class="panel">
    <div class="panel-header"><div class="panel-title">2. Request traffic</div><div class="panel-unit">requests/min</div></div>
    <div class="tiles">
      {stat_tile("Total requests", f'{m["traffic_total"]:,}')}
      {stat_tile("Rate", f'{m["traffic_rate_per_min"]:.2f}/min')}
    </div>
    {traffic_chart}
  </section>

  <section class="panel">
    <div class="panel-header"><div class="panel-title">3. Error rate and breakdown</div><div class="panel-unit">percent</div></div>
    <div class="tiles">
      {stat_tile("Error rate", f'{m["error_rate_pct"]:.2f}%', f'{m["failed_total"]} failed / {m["received_total"]} received', status_badge(err_pass, f'≤{THRESHOLDS["error_rate_pct"]}%'))}
    </div>
    {errors_chart}
  </section>

  <section class="panel">
    <div class="panel-header"><div class="panel-title">4. Cost over time</div><div class="panel-unit">usd</div></div>
    <div class="tiles">
      {stat_tile("Total cost", fmt_value(m["cost_total"], "usd"), "", status_badge(cost_pass, f'≤${THRESHOLDS["cost_total_usd"]}'))}
    </div>
    {cost_chart}
  </section>

  <section class="panel">
    <div class="panel-header"><div class="panel-title">5. Input and output tokens</div><div class="panel-unit">tokens</div></div>
    {tokens_chart}
    <div class="tiles">
      {status_badge(tok_in_pass, "tokens_in ≤ 50,000")}
      {status_badge(tok_out_pass, "tokens_out ≤ 50,000")}
    </div>
  </section>

  <section class="panel">
    <div class="panel-header"><div class="panel-title">6. Quality proxy</div><div class="panel-unit">score 0–1</div></div>
    <div class="tiles">
      {stat_tile("Mean quality_score", f'{m["quality_avg"]:.2f}', "", status_badge(quality_pass, f'≥{THRESHOLDS["quality_avg"]}'))}
    </div>
    {quality_chart}
  </section>

</div>
<footer>
  Contract: config/dashboard.yaml · SLO: config/slo.yaml · Validator: <code>python scripts/validate_dashboard.py</code>
</footer>
</body>
</html>
'''


def main() -> int:
    configure_utf8_stdio()
    events = load_events(LOG_PATH)
    metrics = build_metrics(events)
    html = render_html(metrics)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Đã tạo dashboard: {OUT_PATH} ({len(events)} log record, cửa sổ {WINDOW_MINUTES} phút)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
