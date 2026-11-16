#!/usr/bin/env python3
"""Render the ktest report (report.json) as one self-contained HTML file (no external resources)."""

import html
import json

STATUS_CLASS = {"passed": "ok", "tested": "ok", "killed": "ok", "failed": "bad", "failing": "bad", "error": "bad",
                "survived": "bad", "untested": "warn", "weak": "warn", "not run": "warn", "skipped": "muted", "excluded": "muted",
                "compile error": "muted", "timeout": "warn"}

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--ok:#1f7a3a;--ok-bg:#e3f4e8;
--bad:#b42318;--bad-bg:#fde8e6;--warn:#8a5a00;--warn-bg:#fff2d6;--info:#1d4f91;--info-bg:#e5eefb;--code:#f1f1ee}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1d1d20;--fg:#ececee;--muted:#9a9aa2;--line:#2e2e33;
--ok:#6fd38c;--ok-bg:#16301f;--bad:#ff8a80;--bad-bg:#3a1a18;--warn:#f5c26b;--warn-bg:#352a12;--info:#8fb8ff;
--info-bg:#17253b;--code:#26262b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 4px}
h2{font-size:17px;margin:32px 0 10px}.sub{color:var(--muted);font-size:13px}
.banner{border-radius:10px;padding:14px 18px;margin:18px 0;font-weight:600;font-size:16px}
.banner.ok{background:var(--ok-bg);color:var(--ok)}.banner.bad{background:var(--bad-bg);color:var(--bad)}
.banner ul{margin:6px 0 0;padding-left:20px;font-weight:400;font-size:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.tile span{color:var(--muted);font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:7px 10px;border-top:1px solid var(--line);
vertical-align:top}th{font-size:12px;color:var(--muted);font-weight:600;border-top:0;background:var(--card)}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.chip{display:inline-block;border-radius:999px;padding:1px 8px;font-size:12px;font-weight:600;white-space:nowrap}
.chip.ok{background:var(--ok-bg);color:var(--ok)}.chip.bad{background:var(--bad-bg);color:var(--bad)}
.chip.warn{background:var(--warn-bg);color:var(--warn)}.chip.muted{background:var(--code);color:var(--muted)}
.chip.info{background:var(--info-bg);color:var(--info)}.chip.error{background:var(--bad-bg);color:var(--bad)}
.chip.warning{background:var(--warn-bg);color:var(--warn)}
code,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12.5px}
code{background:var(--code);padding:1px 5px;border-radius:4px}
pre{background:var(--code);padding:10px;border-radius:8px;overflow:auto;max-height:340px;white-space:pre-wrap;
word-break:break-word;margin:6px 0}
details{border-top:1px solid var(--line)}details:first-of-type{border-top:0}
summary{cursor:pointer;padding:9px 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
summary::-webkit-details-marker{display:none}summary:before{content:"\\25B8";color:var(--muted)}
details[open]>summary:before{content:"\\25BE"}.grow{flex:1;min-width:180px;font-weight:600}
.inner{padding:0 12px 12px}.bar{display:inline-block;width:70px;height:7px;background:var(--line);
border-radius:4px;overflow:hidden;vertical-align:middle;margin-right:6px}.bar i{display:block;height:100%;
background:var(--ok)}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
input,select,button{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;
background:var(--card);color:var(--fg)}input{flex:1;min-width:200px}.muted{color:var(--muted)}
.ev{color:var(--muted);font-size:12px}.scroll{overflow-x:auto}
"""

JS = """
function filt(sec){const q=(document.getElementById(sec+'-q').value||'').toLowerCase();
const s=document.getElementById(sec+'-s').value;document.querySelectorAll('[data-sec="'+sec+'"]').forEach(e=>{
const t=e.getAttribute('data-text')||'';const st=e.getAttribute('data-status')||'';
e.style.display=(t.indexOf(q)>=0&&(!s||st.split(' ').indexOf(s)>=0))?'':'none';});}
function openAll(sec,o){document.querySelectorAll('details[data-sec="'+sec+'"]').forEach(d=>d.open=o);}
"""


def e(x):
    return html.escape("" if x is None else str(x))


def chip(status, label=None):
    cls = STATUS_CLASS.get(status, status if status in ("error", "warning", "info") else "muted")
    return f'<span class="chip {cls}">{e(label or status)}</span>'


def bar(p):
    if p is None:
        return '<span class="muted">-</span>'
    return f'<span class="bar"><i style="width:{max(0.0, min(100.0, p))}%"></i></span>{p:g}%'


def pct(pair):
    if not pair:
        return None
    m, c = pair
    return round(100.0 * c / (m + c), 1) if m + c else None


def toolbar(sec, statuses, placeholder):
    opts = "".join(f'<option value="{e(s)}">{e(s)}</option>' for s in statuses)
    return (f'<div class="toolbar"><input id="{sec}-q" placeholder="{e(placeholder)}" oninput="filt(\'{sec}\')">'
            f'<select id="{sec}-s" onchange="filt(\'{sec}\')"><option value="">all</option>{opts}</select>'
            f'<button onclick="openAll(\'{sec}\',true)">Expand all</button>'
            f'<button onclick="openAll(\'{sec}\',false)">Collapse all</button></div>')


def render(r):
    s = r["summary"]
    run = r.get("run") or {}
    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>Kotlin unit test report</title><style>{CSS}</style></head><body><main>']
    out.append(f'<h1>Kotlin unit test report</h1><div class="sub">{e(r["project"])} &middot; {e(r["generated_at"])}'
               f' &middot; {e(r["generator"]["name"])} {e(r["generator"]["version"])}</div>')
    ok = r["verdict"] == "PASSED"
    reasons = "".join(f"<li>{e(x)}</li>" for x in r["verdict_reasons"])
    out.append(f'<div class="banner {"ok" if ok else "bad"}">{e(r["verdict"])}'
               f'{"<ul>" + reasons + "</ul>" if reasons else ""}</div>')

    tiles = [("Tests run", s["tests"]), ("Passed", s["passed"]), ("Failed", s["failed"] + s["errors"]),
             ("Skipped", s["skipped"]), ("Not run", s["not_run"]),
             ("Pass rate", f'{s["pass_rate"]}%' if s["pass_rate"] is not None else "-"),
             ("Classes", s["classes"]), ("Methods tested", f'{s["methods_tested"]}/{s["methods_total"]}'),
             ("Line coverage", f'{s["line_coverage"]}%' if s["line_coverage"] is not None else "-"),
             ("Branch coverage", f'{s["branch_coverage"]}%' if s["branch_coverage"] is not None else "-"),
             ("Errors / warnings", f'{s["findings"]["error"]} / {s["findings"]["warning"]}'),
             ("Duration", f'{s["duration_s"]:g} s')]
    if r.get("mutation"):
        mu = r["mutation"]["summary"]
        tiles.append(("Mutation score", f'{mu["score"]}%' if mu["score"] is not None else "-"))
    out.append('<div class="tiles">' + "".join(f'<div class="tile"><b>{e(v)}</b><span>{e(k)}</span></div>'
                                               for k, v in tiles) + "</div>")

    # findings
    fs = r["findings"]
    out.append(f'<h2>Findings ({len(fs)})</h2>')
    if fs:
        out.append(toolbar("f", ["error", "warning", "info"], "Filter findings (rule, file, text)"))
        out.append('<div class="card scroll"><table><tr><th>Severity</th><th>Rule</th><th>Finding</th>'
                   '<th>Where</th></tr>')
        for f in fs:
            where = f'{e(f.get("file") or "")}{":" + str(f["line"]) if f.get("line") else ""}'
            text = " ".join(str(f.get(k) or "") for k in ("rule", "title", "detail", "file")).lower()
            out.append(f'<tr data-sec="f" data-status="{e(f["severity"])}" data-text="{e(text)}">'
                       f'<td>{chip(f["severity"])}</td><td><code>{e(f["rule"])}</code></td>'
                       f'<td><b>{e(f["title"])}</b><br>{e(f["detail"])}</td><td><code>{where}</code></td></tr>')
        out.append("</table></div>")
    else:
        out.append('<p class="muted">No findings.</p>')

    # class-wise / method-wise
    out.append(f'<h2>Classes and methods ({len(r["classes"])} classes)</h2>')
    out.append('<p class="sub">Each production class with its methods. A method counts as tested when a test calls it '
               '(or is named after it) and passes. Coverage comes from JaCoCo/Kover when available.</p>')
    out.append(toolbar("c", ["tested", "weak", "failing", "untested", "not run", "skipped"], "Filter classes or methods"))
    out.append('<div class="card">')
    for c in r["classes"]:
        sts = " ".join(sorted({m["status"] for m in c["methods"]}))
        text = (c["name"] + " " + " ".join(m["name"] for m in c["methods"])).lower()
        lc = pct((c.get("coverage") or {}).get("LINE"))
        counts = c["counts"]
        head = (f'{chip("tested", str(counts.get("tested", 0)) + " tested")} '
                + (chip("failing", str(counts["failing"]) + " failing") + " " if counts.get("failing") else "")
                + (chip("untested", str(counts["untested"]) + " untested") + " " if counts.get("untested") else "")
                + (chip("weak", str(counts["weak"]) + " weak") + " " if counts.get("weak") else ""))
        out.append(f'<details data-sec="c" data-status="{e(sts)}" data-text="{e(text)}"><summary>'
                   f'<span class="grow">{e(c["name"])} <span class="muted">{e(c["kind"])}</span></span>{head}'
                   f'<span>{bar(lc)}</span></summary><div class="inner">'
                   f'<div class="sub"><code>{e(c["file"])}:{e(c["line"])}</code> &middot; test classes: '
                   f'{", ".join("<code>" + e(t) + "</code>" for t in c["test_classes"]) or "none"}</div>')
        if c["methods"]:
            out.append('<div class="scroll"><table><tr><th>Method</th><th>Status</th><th>Tests</th>'
                       '<th>Line cov.</th><th>Branch cov.</th></tr>')
            for m in c["methods"]:
                tests = "<br>".join(f'{chip(t["status"])} {e(t["name"])} <span class="ev">({e(t["evidence"])})</span>'
                                    for t in m["tests"]) or '<span class="muted">none</span>'
                cov = m.get("coverage") or {}
                skip = f'<br><span class="ev">{e(m["skip"])}</span>' if m.get("skip") else ""
                out.append(f'<tr><td><code>{e(m["signature"])}</code><br><span class="ev">line {e(m["line"])}</span>'
                           f'</td><td>{chip(m["status"])}{skip}</td><td>{tests}</td>'
                           f'<td class="num">{bar(pct(cov.get("LINE")))}</td>'
                           f'<td class="num">{bar(pct(cov.get("BRANCH")))}</td></tr>')
            out.append("</table></div>")
        else:
            out.append('<p class="muted">No methods (data holder or declarations only).</p>')
        out.append("</div></details>")
    out.append("</div>")

    # test results
    out.append(f'<h2>Test results ({s["tests"]} run)</h2>')
    out.append(toolbar("t", ["passed", "failed", "skipped", "not run"], "Filter tests"))
    out.append('<div class="card">')
    for tc in r["test_classes"]:
        sts = " ".join(sorted({t["status"] for t in tc["tests"]}))
        cnt = {}
        for t in tc["tests"]:
            cnt[t["status"]] = cnt.get(t["status"], 0) + 1
        chips = " ".join(chip(k, f"{v} {k}") for k, v in sorted(cnt.items()))
        text = (tc["id"] + " " + " ".join(t["name"] for t in tc["tests"])).lower()
        out.append(f'<details data-sec="t" data-status="{e(sts)}" data-text="{e(text)}"'
                   f'{" open" if "failed" in cnt else ""}><summary><span class="grow">{e(tc["id"])}</span>{chips}'
                   f'<span class="muted">{tc["time"]:.2f} s</span></summary><div class="inner">'
                   f'<div class="sub"><code>{e(tc["file"])}</code> &middot; tests: '
                   f'{", ".join("<code>" + e(x) + "</code>" for x in tc["targets"]) or "no linked class"}</div>'
                   '<div class="scroll"><table><tr><th>Test</th><th>Status</th><th>Time</th><th>Checks</th></tr>')
        for t in tc["tests"]:
            detail = ""
            if t["status"] == "failed":
                detail = (f'<div><b>{e(t.get("type"))}</b>: {e(t.get("message"))}</div>'
                          f'<details><summary>Stack trace</summary><pre>{e(t.get("details"))}</pre></details>')
                if t.get("stdout"):
                    detail += f'<details><summary>Output</summary><pre>{e(t["stdout"])}</pre></details>'
            if t.get("disabled"):
                detail += f'<div class="ev">disabled: {e(t["disabled"])}</div>'
            targets = ", ".join(f'<code>{e(x)}</code>' for x in t["targets"]) or '<span class="muted">-</span>'
            out.append(f'<tr><td>{e(t["name"])} <span class="ev">line {e(t["line"])}</span>{detail}</td>'
                       f'<td>{chip(t["status"])}</td><td class="num">{t["time"]:.3f}s</td><td>{targets}</td></tr>')
        out.append("</table></div></div></details>")
    out.append("</div>")
    if r.get("unmatched_results"):
        out.append(f'<h2>Results without a matching source test ({len(r["unmatched_results"])})</h2>'
                   '<div class="card scroll"><table><tr><th>Class</th><th>Test</th><th>Status</th></tr>')
        for u in r["unmatched_results"][:500]:
            out.append(f'<tr><td><code>{e(u["classname"])}</code></td><td>{e(u["name"])}</td>'
                       f'<td>{chip(u["status"])}</td></tr>')
        out.append("</table></div>")

    # mutation
    if r.get("mutation"):
        mu = r["mutation"]
        ms = mu["summary"]
        out.append(f'<h2>Mutation check: do the tests catch bugs?</h2><p class="sub">Small bugs were put into '
                   f'<code>{e(mu["unit"])}</code> one at a time and its tests were run. A <b>killed</b> mutant means '
                   f'a test failed (good); a <b>survived</b> mutant means no test noticed the bug. Score '
                   f'{e(ms["score"])}% ({ms["killed"]} killed, {ms["survived"]} survived, '
                   f'{ms["invalid"]} did not compile, {ms["timeout"]} timed out).</p>')
        out.append('<div class="card scroll"><table><tr><th>Result</th><th>Method</th><th>Change</th>'
                   '<th>Line</th></tr>')
        for x in mu["mutants"]:
            out.append(f'<tr><td>{chip(x["result"])}</td><td><code>{e(x["method"])}</code></td>'
                       f'<td><code>{e(x["original"])}</code> &rarr; <code>{e(x["mutated"])}</code></td>'
                       f'<td class="num">{e(x["line"])}</td></tr>')
        out.append("</table></div>")

    # run info
    out.append('<h2>Run</h2><div class="card scroll"><table>')
    rows = [("Build tool", run.get("tool")), ("Command", run.get("command")), ("Exit code", run.get("exit_code")),
            ("Duration", f'{run.get("duration_s")} s' if run.get("duration_s") is not None else None),
            ("Filters", ", ".join(run.get("filters") or []) or "none (all tests)"),
            ("Result files", len(r.get("result_files") or [])), ("Coverage files", ", ".join(r.get("coverage_files") or [])
                                                                 or "none"),
            ("Build log", run.get("log"))]
    for k, v in rows:
        if v not in (None, ""):
            out.append(f'<tr><th>{e(k)}</th><td><code>{e(v)}</code></td></tr>')
    out.append("</table></div>")
    if run.get("log_tail"):
        out.append(f'<details class="card"><summary>Build log (last lines)</summary><div class="inner"><pre>'
                   f'{e(run["log_tail"])}</pre></div></details>')
    out.append('<p class="sub">How tests are linked: a test class <code>FooTest</code> (also FooTests, FooSpec, '
               'FooIT) tests class <code>Foo</code>; a test is linked to a method when its body calls the method '
               '(calls inside mock stubbing/verification do not count) or its name contains the method name. '
               'Rules are explained in the skill\'s references/checks.md.</p>')
    out.append(f"<script>{JS}</script></main></body></html>")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(render(json.load(fh)))
