"""Render the token-optimizer summary as one self-contained HTML page (inline SVG, CSS and a few lines of JS;
no network access). Standard library only. Called by `token_optimizer.py dashboard`."""
from __future__ import annotations

import datetime as dt
import html
import json
import math

MAX_DAYS_SHOWN = 90

USAGE_SERIES = [("input", "Input", "--series-1"), ("output", "Output", "--series-2"),
                ("cache_read", "Cache read", "--series-3"), ("cache_write", "Cache write", "--series-4")]
FRESH_SERIES = [USAGE_SERIES[0], USAGE_SERIES[1], USAGE_SERIES[3]]
SKILL_ROWS_SHOWN = 25
SKILLS_PER_SESSION_SHOWN = 5
SAVED_SERIES = [("opt_saved", "Optimizer", "--series-1"), ("meter_saved", "Skills (skill-token-meter)", "--series-2")]

CSS = """
.viz-root{color-scheme:light;--surface-0:#f4f3ef;--surface-1:#fcfcfb;--text-primary:#0b0b0b;
--text-secondary:#52514e;--muted:#898781;--grid:#e1e0d9;--border:rgba(11,11,11,.10);
--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--series-4:#eda100}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;
--surface-0:#111110;--surface-1:#1a1a19;--text-primary:#f0efec;--text-secondary:#c3c2b7;--muted:#898781;
--grid:#2c2c2a;--border:rgba(255,255,255,.10);--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;
--series-4:#c98500}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;--surface-0:#111110;--surface-1:#1a1a19;
--text-primary:#f0efec;--text-secondary:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--border:rgba(255,255,255,.10);
--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--series-4:#c98500}
*{box-sizing:border-box}
body{margin:0;font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.viz-root{background:var(--surface-0);color:var(--text-primary);min-height:100vh;padding:24px}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:0 0 2px}
.sub{color:var(--text-secondary);margin:0 0 12px;font-size:13px}
.meta{color:var(--text-secondary);font-size:12px;margin-bottom:20px;word-break:break-all}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.tile .k{color:var(--text-secondary);font-size:12px}
.tile .v{font-size:24px;font-weight:600;font-variant-numeric:tabular-nums;margin-top:2px}
.tile .n{color:var(--muted);font-size:11px}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:16px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
svg{display:block;width:100%;height:auto}
svg text{fill:var(--muted);font-size:11px;font-family:inherit}
svg .lbl{fill:var(--text-secondary)}
svg .val{fill:var(--text-primary);font-variant-numeric:tabular-nums}
.gridline{stroke:var(--grid);stroke-width:1}
.axis{stroke:var(--muted);stroke-width:1}
.seg{stroke:var(--surface-1);stroke-width:1}
.hit{fill:transparent;cursor:default}
.hit:hover{fill:var(--text-primary);fill-opacity:.05}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin:8px 0 4px;color:var(--text-secondary);font-size:12px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:10px;height:10px;border-radius:2px;display:inline-block}
table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--text-secondary);font-weight:600;border-bottom:1px solid var(--grid);padding:6px 8px}
td{border-bottom:1px solid var(--grid);padding:6px 8px;vertical-align:top}
td.num,th.num{text-align:right;white-space:nowrap}
td.time{white-space:nowrap;color:var(--text-secondary)}
details{margin-top:8px}
summary{cursor:pointer;color:var(--text-secondary);font-size:12px}
.scroll{overflow-x:auto}
ul.advice{margin:6px 0 0;padding-left:18px}
ul.advice li{margin:4px 0}
.empty{color:var(--text-secondary);padding:24px 0;text-align:center}
code{font-size:12px;background:var(--surface-0);padding:1px 4px;border-radius:4px}
#tip{position:fixed;pointer-events:none;z-index:9;background:var(--surface-1);color:var(--text-primary);
border:1px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;white-space:pre;
box-shadow:0 4px 16px rgba(0,0,0,.15);display:none;font-variant-numeric:tabular-nums}
.theme{float:right;background:var(--surface-1);color:var(--text-secondary);border:1px solid var(--border);
border-radius:8px;padding:4px 10px;cursor:pointer;font:inherit;font-size:12px}
"""

JS = """
(function(){var tip=document.getElementById('tip');
document.addEventListener('mousemove',function(e){var t=e.target.closest?e.target.closest('[data-tip]'):null;
if(!t){tip.style.display='none';return;}tip.textContent=t.getAttribute('data-tip');tip.style.display='block';
var x=e.clientX+14,y=e.clientY+14,w=tip.offsetWidth,h=tip.offsetHeight;
if(x+w>innerWidth-8)x=e.clientX-w-14;if(y+h>innerHeight-8)y=e.clientY-h-14;
tip.style.left=x+'px';tip.style.top=y+'px';});
var b=document.getElementById('theme');if(b)b.addEventListener('click',function(){var r=document.documentElement;
var dark=r.getAttribute('data-theme')==='dark'||(!r.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);
r.setAttribute('data-theme',dark?'light':'dark');});})();
"""


def esc(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def fmt(n) -> str:
    n = int(n or 0)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(n) >= div:
            v = n / div
            return f"{v:.1f}{suf}" if abs(v) < 100 else f"{v:.0f}{suf}"
    return str(n)


def full(n) -> str:
    return f"{int(n or 0):,}"


def when(iso) -> str:
    return esc((iso or "")[:16].replace("T", " "))


def nice_max(v: float) -> float:
    if v <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def day_range(days: dict) -> list:
    if not days:
        return []
    keys = sorted(k for k in days if len(k) == 10)
    if not keys:
        return []
    start = dt.date.fromisoformat(keys[0])
    end = dt.date.fromisoformat(keys[-1])
    span = (end - start).days
    if span >= MAX_DAYS_SHOWN:
        start = end - dt.timedelta(days=MAX_DAYS_SHOWN - 1)
        span = MAX_DAYS_SHOWN - 1
    return [(start + dt.timedelta(days=i)).isoformat() for i in range(span + 1)]


def legend(series) -> str:
    items = "".join(f'<span><i style="background:var({var})"></i>{esc(label)}</span>' for _, label, var in series)
    return f'<div class="legend">{items}</div>'


def stacked_bars(day_keys: list, data: dict, series, label: str) -> str:
    """Stacked daily bars with one hover target per day that lists every series."""
    W, H, ml, mr, mt, mb = 760, 240, 52, 10, 10, 26
    pw, ph = W - ml - mr, H - mt - mb
    totals = [sum(int(data.get(d, {}).get(k, 0)) for k, _, _ in series) for d in day_keys]
    ymax = nice_max(max(totals) if totals else 0)
    n = max(1, len(day_keys))
    bw = pw / n
    bar = max(2.0, min(26.0, bw * 0.72))
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">']
    for i in range(5):
        v = ymax * i / 4
        y = mt + ph - ph * i / 4
        out.append(f'<line class="gridline" x1="{ml}" x2="{W - mr}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text x="{ml - 6}" y="{y + 4:.1f}" text-anchor="end">{fmt(v)}</text>')
    step = max(1, math.ceil(n / 8))
    for i, d in enumerate(day_keys):
        x0 = ml + i * bw + (bw - bar) / 2
        base = mt + ph
        tip = [d]
        for key, name, var in series:
            v = int(data.get(d, {}).get(key, 0))
            tip.append(f"{name}: {full(v)}")
            if v <= 0:
                continue
            h = ph * v / ymax
            base -= h
            out.append(f'<rect class="seg" x="{x0:.1f}" y="{base:.1f}" width="{bar:.1f}" height="{h:.1f}" '
                       f'rx="1.5" style="fill:var({var})"/>')
        tip.append(f"Total: {full(totals[i])}")
        out.append(f'<rect class="hit" x="{ml + i * bw:.1f}" y="{mt}" width="{bw:.1f}" height="{ph}" '
                   f'data-tip="{esc(chr(10).join(tip))}"/>')
        if i % step == 0 or i == n - 1 and n <= 8:
            out.append(f'<text x="{ml + i * bw + bw / 2:.1f}" y="{H - 8}" text-anchor="middle">{esc(d[5:])}</text>')
    out.append(f'<line class="axis" x1="{ml}" x2="{W - mr}" y1="{mt + ph}" y2="{mt + ph}"/></svg>')
    return "".join(out)


def hbars(rows, label: str, tip_fn) -> str:
    """Horizontal bars, one series: name on the left, value at the end of the bar."""
    if not rows:
        return '<p class="empty">No data yet.</p>'
    W, row_h, ml, mr = 760, 26, 190, 70
    H = row_h * len(rows) + 8
    vmax = max(v for _, v, _ in rows) or 1
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">']
    for i, (name, v, extra) in enumerate(rows):
        y = 4 + i * row_h
        w = max(2.0, (W - ml - mr) * v / vmax)
        short = name if len(name) <= 28 else name[:27] + "..."
        out.append(f'<text class="lbl" x="{ml - 8}" y="{y + 16}" text-anchor="end">{esc(short)}</text>')
        out.append(f'<rect x="{ml}" y="{y + 5}" width="{w:.1f}" height="14" rx="2" style="fill:var(--series-1)"/>')
        out.append(f'<text class="val" x="{ml + w + 6:.1f}" y="{y + 16}">{esc(fmt(v))}</text>')
        out.append(f'<rect class="hit" x="0" y="{y}" width="{W}" height="{row_h}" data-tip="{esc(tip_fn(name, v, extra))}"/>')
    out.append("</svg>")
    return "".join(out)


def table(headers, rows, num_cols=()) -> str:
    th = "".join(f'<th class="{"num" if i in num_cols else ""}">{esc(h)}</th>' for i, h in enumerate(headers))
    body = []
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            cls = "num" if i in num_cols else ("time" if isinstance(c, tuple) else "")
            val = c[0] if isinstance(c, tuple) else esc(c)
            cells.append(f'<td class="{cls}">{val}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def tile(k, v, note="") -> str:
    return f'<div class="tile"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div><div class="n">{esc(note)}</div></div>'


def describe(e: dict) -> tuple:
    """(type, skill or tool, tokens, saved, note) for one activity row."""
    kind = e.get("kind")
    if kind == "usage":
        ranked = sorted((e.get("skills") or {}).items(), key=lambda kv: -int(kv[1]))
        skills = ", ".join(f"{k} x{v}" for k, v in ranked[:SKILLS_PER_SESSION_SHOWN])
        if len(ranked) > SKILLS_PER_SESSION_SHOWN:
            skills += f" +{len(ranked) - SKILLS_PER_SESSION_SHOWN} more"
        models = ", ".join((e.get("models") or {}).keys())
        note = e.get("task") or models
        return "session" if not str(e.get("id", "")).startswith("manual") else "manual", skills or "-", \
            full(e.get("total")), "", note
    if kind == "guard":
        return "read guard", e.get("skill") or "", full(e.get("before")), "", e.get("source") or ""
    if kind == "optimize":
        return f"optimize: {e.get('tool')}", e.get("skill") or "", full(e.get("before")), full(e.get("saved")), \
            e.get("source") or e.get("note") or ""
    return f"skill saving ({e.get('method') or 'estimate'})", e.get("skill") or "", full(e.get("total")), \
        full(e.get("saved")), e.get("note") or ""


def render(s: dict, title: str = "Token usage dashboard", generated: str = "", sources=(), days=None) -> str:
    t = s["totals"]
    prompt_side = t["input"] + t["cache_read"] + t["cache_write"]
    cache_share = f"{t['cache_read'] / prompt_side:.0%}" if prompt_side else "-"
    saved_total = t["opt_saved"] + t["meter_saved"]
    period = f"{when(s['first'])} to {when(s['last'])}" if s["first"] else "no data yet"
    if days:
        period += f" (last {days:g} days)"
    skills_used = [r for r in s["skills"] if r["uses"] or r["opt_runs"] or r["meter_uses"]]

    parts = [f'<button class="theme" id="theme" type="button">Light / dark</button><h1>{esc(title)}</h1>',
             f'<p class="sub">Period: {period}. Generated {when(generated)}.</p>',
             f'<div class="meta">Data: {esc(", ".join(sources))}. Token counts from session logs are as the agent '
             f'recorded them; optimizer and skill savings are estimates (chars / 4).</div>']

    parts.append('<div class="tiles">' + "".join([
        tile("Tokens used", fmt(t["total"]), f"{full(t['total'])} in {t['sessions']} sessions"),
        tile("Output tokens", fmt(t["output"]), "usually the most expensive kind"),
        tile("Cache reads", cache_share, "share of prompt tokens"),
        tile("Tool calls", fmt(t["tool_calls"]), f"{full(t['messages'])} model replies"),
        tile("Tokens saved", fmt(saved_total), f"optimizer {fmt(t['opt_saved'])}, skills {fmt(t['meter_saved'])}"),
        tile("Skills used", str(len(skills_used)), f"{t['opt_runs']} optimizer runs, "
             f"{t.get('guarded_reads', 0)} big reads redirected"),
    ]) + "</div>")

    day_keys = day_range(s["days"])
    if not day_keys:
        parts.append('<div class="card"><p class="empty">No data yet. Run <code>token_optimizer.py import '
                     '--auto</code> or an optimizer command, then rebuild this page.</p></div>')
    else:
        trimmed = len([k for k in s["days"] if len(k) == 10]) and day_keys[0] > min(s["days"])
        note = f" Showing the last {MAX_DAYS_SHOWN} days." if trimmed else ""
        usage_rows = [[d] + [full(s["days"].get(d, {}).get(k, 0)) for k, _, _ in USAGE_SERIES]
                      + [full(s["days"].get(d, {}).get("total", 0))] for d in reversed(day_keys) if d in s["days"]]
        parts.append('<div class="card"><h2>Tokens used per day</h2>'
                     f'<p class="sub">Input, output and cache tokens from imported sessions and manual entries.{note}</p>'
                     + legend(USAGE_SERIES) + stacked_bars(day_keys, s["days"], USAGE_SERIES, "Tokens used per day")
                     + '<details><summary>Show as table</summary>'
                     + table(["Day", "Input", "Output", "Cache read", "Cache write", "Total"], usage_rows,
                             (1, 2, 3, 4, 5)) + "</details></div>")
        parts.append('<div class="card"><h2>Fresh tokens per day (without cache reads)</h2>'
                     '<p class="sub">Cache reads are billed far below normal input, so this is where most of the cost '
                     'is. Same colours as above.</p>' + legend(FRESH_SERIES)
                     + stacked_bars(day_keys, s["days"], FRESH_SERIES, "Fresh tokens per day") + "</div>")
        saved_rows = [[d, full(s["days"][d]["opt_saved"]), full(s["days"][d]["meter_saved"])]
                      for d in reversed(day_keys) if d in s["days"]
                      and (s["days"][d]["opt_saved"] or s["days"][d]["meter_saved"])]
        parts.append('<div class="card"><h2>Tokens saved per day</h2>'
                     '<p class="sub">Optimizer runs (before minus after) and savings recorded by skill-token-meter.</p>'
                     + legend(SAVED_SERIES) + stacked_bars(day_keys, s["days"], SAVED_SERIES, "Tokens saved per day")
                     + '<details><summary>Show as table</summary>'
                     + table(["Day", "Optimizer", "Skills"], saved_rows, (1, 2)) + "</details></div>")

    # Skills
    top = sorted(skills_used, key=lambda r: -(r["uses"] + r["opt_runs"] + r["meter_uses"]))[:15]
    bars = hbars([(r["skill"], r["uses"] + r["opt_runs"] + r["meter_uses"], r) for r in top], "Skill uses",
                 lambda name, v, r: f"{name}\nUses: {v}\nSessions: {r['sessions']}\nLast used: "
                                    f"{(r['last'] or '')[:16].replace('T', ' ')}")
    skill_rows = [[r["skill"], r["uses"], r["sessions"], fmt(r["tokens"]), r["opt_runs"], fmt(r["opt_saved"]),
                   fmt(r["meter_saved"]), (when(r["first"]),), (when(r["last"]),)] for r in skills_used]
    skill_head = ["Skill", "Calls", "Sessions", "Session tokens", "Optimizer runs", "Optimizer saved",
                  "Meter saved", "First used", "Last used"]
    nums = (1, 2, 3, 4, 5, 6)
    skill_table = table(skill_head, skill_rows[:SKILL_ROWS_SHOWN], nums)
    if len(skill_rows) > SKILL_ROWS_SHOWN:
        skill_table += (f'<details><summary>Show {len(skill_rows) - SKILL_ROWS_SHOWN} more skills</summary>'
                        + table(skill_head, skill_rows[SKILL_ROWS_SHOWN:], nums) + "</details>")
    parts.append('<div class="card"><h2>How skills are used</h2>'
                 '<p class="sub">Uses = tool calls that loaded a skill or ran its scripts, plus optimizer runs and '
                 'skill-token-meter entries. Tokens = all tokens of the session-days that used it.</p>' + bars
                 + skill_table + "</div>")

    # Optimizer and models
    tool_rows = [[r["tool"], r["runs"], full(r["before"]), full(r["after"]), full(r["saved"]), f"{r['percent']}%"]
                 for r in s["tools"]]
    model_rows = [[m, full(c)] for m, c in list(s["models"].items())[:10]]
    agent_rows = [[a, fmt(c)] for a, c in s["agents"].items()]
    parts.append('<div class="grid2"><div class="card"><h2>Optimizer tools</h2>'
                 '<p class="sub">Estimated tokens before and after each kind of reduction.</p>'
                 + (table(["Tool", "Runs", "Before", "After", "Saved", "Saved %"], tool_rows, (1, 2, 3, 4, 5))
                    if tool_rows else '<p class="empty">No optimizer runs yet.</p>')
                 + '</div><div class="card"><h2>Models and agents</h2><p class="sub">Replies per model, tokens per agent.</p>'
                 + (table(["Model", "Replies"], model_rows, (1,)) if model_rows else "")
                 + (table(["Agent", "Tokens"], agent_rows, (1,)) if agent_rows else "")
                 + ("" if model_rows or agent_rows else '<p class="empty">No sessions imported yet.</p>')
                 + "</div></div>")

    parts.append('<div class="card"><h2>Advice from your data</h2><ul class="advice">'
                 + "".join(f"<li>{esc(a)}</li>" for a in s["advice"]) + "</ul></div>")

    recent = []
    for e in s["recent"]:
        kind, who, tokens, saved, note = describe(e)
        recent.append([(when(e.get("time")),), kind, who, e.get("agent", ""), tokens, saved, str(note)[:120]])
    parts.append('<div class="card"><h2>Recent activity</h2><p class="sub">Newest first, with timestamps (last 50).</p>'
                 + (table(["Time", "Type", "Skill / skills", "Agent", "Tokens", "Saved", "Note"], recent, (4, 5))
                    if recent else '<p class="empty">Nothing recorded yet.</p>') + "</div>")

    data_json = json.dumps({"totals": t, "days": s["days"]}, default=str).replace("</", "<\\/")
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head>"
            f"<body><div class=\"viz-root\"><div class=\"wrap\">{''.join(parts)}</div><div id=\"tip\"></div></div>"
            f"<script type=\"application/json\" id=\"data\">{data_json}</script><script>{JS}</script></body></html>\n")
