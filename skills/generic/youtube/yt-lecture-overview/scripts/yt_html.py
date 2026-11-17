"""Render the self-contained overview.html for yt-lecture-overview. Standard library only.

The page is built for reading, in this order: what the lecture is, the summary and the points to remember,
an outline with a timeline, notes per section, key terms, a self-check quiz, what the audio tells us, and the
searchable transcript. Labels are plain words; technical audio details sit in a collapsed block.

Every value from YouTube or the notes is escaped: titles, descriptions and transcripts are untrusted text.
"""
from __future__ import annotations

import datetime
import html
import re

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def e(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def fmt_time(sec) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_length(sec) -> str:
    """Human length: '45 s', '7 min', '1 h 05 min'."""
    sec = int(round(sec or 0))
    if sec < 60:
        return f"{sec} s"
    h, m = divmod(round(sec / 60), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def nice_date(value: str) -> str:
    """'2017-10-05T08:11:25-07:00' -> '5 Oct 2017'; anything else is returned unchanged."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value or "")
    if not m:
        return value or ""
    try:
        d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return value
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def sentence(text, limit=0) -> str:
    """Capitalise, end with punctuation and optionally shorten to `limit` words (for automatic drafts)."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""
    words = text.split(" ")
    cut = limit and len(words) > limit
    if cut:
        text = " ".join(words[:limit]).rstrip(",;:")
    text = text[0].upper() + text[1:]
    if cut:
        return text + " …"
    return text if re.search(r"[.!?…:)\"']$", text) else text + "."


def pace_label(wpm: int) -> str:
    if not wpm:
        return ""
    if wpm < 110:
        return "slow"
    if wpm <= 160:
        return "normal"
    return "fast"


def watch(info, sec, label=None, cls="ts") -> str:
    sec = int(sec or 0)
    text = label or fmt_time(sec)
    return (f'<a class="{cls}" href="{e(info["url"])}&amp;t={sec}s" target="_blank" rel="noopener" '
            f'title="Watch from {fmt_time(sec)} on YouTube">{e(text)}</a>')


CSS = """
:root{color-scheme:light;--page:#f9f9f7;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#6f6d68;--line:#e1e0d9;
--axis:#c3c2b7;--link:#1c5cab;--bar:#2a78d6;--bar-hi:#5598e7;--chip:#eef3fb;--note:#fff7e6;--note-line:#e9c27a;--mark:#fde68a}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--page:#0d0d0d;--card:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--muted:#9a988f;--line:#2c2c2a;--axis:#383835;--link:#86b6ef;--bar:#3987e5;--bar-hi:#6da7ec;
--chip:#1d2633;--note:#2a2416;--note-line:#7a5f2a;--mark:#7a6420}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#9a988f;
--line:#2c2c2a;--axis:#383835;--link:#86b6ef;--bar:#3987e5;--bar-hi:#6da7ec;--chip:#1d2633;--note:#2a2416;--note-line:#7a5f2a;--mark:#7a6420}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:880px;margin:0 auto;padding:20px 16px 72px}
a{color:var(--link)}h1,h2,h3{line-height:1.3}
h1{font-size:1.65rem;margin:.15em 0 .3em}h2{font-size:1.25rem;margin:0 0 .2em}h3{font-size:1.05rem;margin:0}
.lead{color:var(--ink2);margin:.1em 0 1em;font-size:.95rem}
.muted{color:var(--muted)}.small{font-size:.85rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin:18px 0;scroll-margin-top:64px}
header.card{display:grid;grid-template-columns:220px 1fr;gap:20px;align-items:center}
header img{width:100%;border-radius:10px;aspect-ratio:16/9;object-fit:cover;background:var(--chip);display:block}
.facts{display:flex;flex-wrap:wrap;gap:6px 16px;color:var(--ink2);font-size:.92rem;margin:.2em 0 .8em}
.btn{display:inline-block;background:var(--bar);color:#fff;text-decoration:none;border-radius:8px;padding:7px 14px;font-weight:600;font-size:.92rem}
.note{background:var(--note);border:1px solid var(--note-line);border-radius:10px;padding:10px 14px;margin:12px 0;font-size:.93rem}
nav.toc{position:sticky;top:0;z-index:5;background:var(--page);border-bottom:1px solid var(--line);margin:0 -16px;padding:8px 16px;
display:flex;gap:6px;overflow-x:auto;white-space:nowrap;scrollbar-width:none}nav.toc::-webkit-scrollbar{display:none}
nav.toc a{text-decoration:none;color:var(--ink2);font-size:.88rem;padding:4px 10px;border-radius:999px;background:var(--chip)}
nav.toc a:hover{color:var(--ink)}
.summary{font-size:1.05rem;max-width:70ch}
ol.remember{padding-left:1.3em;margin:.4em 0 0}ol.remember li{margin:.35em 0;max-width:70ch}
.timeline{display:flex;gap:2px;height:30px;margin:6px 0 4px}
.timeline a{display:flex;align-items:center;justify-content:center;background:var(--bar);color:#fff;text-decoration:none;
font-size:.75rem;font-weight:600;border-radius:4px;min-width:3px;overflow:hidden}
.timeline a:hover,.timeline a:focus{background:var(--bar-hi);outline:none}
.tl-axis{display:flex;justify-content:space-between;font-size:.78rem;color:var(--muted);margin-bottom:12px}
table{border-collapse:collapse;width:100%;font-size:.95rem}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:.8rem;text-transform:uppercase;letter-spacing:.03em}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--ink2)}
.badge{display:inline-flex;align-items:center;justify-content:center;min-width:1.7em;height:1.7em;border-radius:999px;
background:var(--bar);color:#fff;font-size:.8rem;font-weight:700;margin-right:8px;padding:0 .4em}
.sec{border-top:1px solid var(--line);padding:16px 0 6px}.sec:first-of-type{border-top:0;padding-top:4px}
.sec-head{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 10px}
.sec-time{color:var(--muted);font-size:.85rem;font-variant-numeric:tabular-nums}
.sec ul{margin:.5em 0 .3em;padding-left:1.2em}.sec li{margin:.25em 0;max-width:70ch}
.ts{font-variant-numeric:tabular-nums;text-decoration:none;font-size:.85rem;background:var(--chip);border-radius:6px;padding:1px 7px;white-space:nowrap}
details>summary{cursor:pointer;color:var(--link);font-size:.9rem;margin:.3em 0}
.said{color:var(--ink2);font-size:.92rem;max-height:240px;overflow:auto;border-left:3px solid var(--line);padding-left:12px}
dl.terms{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:8px 18px;margin:0}
dl.terms dt{font-weight:600}dl.terms dd{margin:0;color:var(--ink2)}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{background:var(--chip);border-radius:999px;padding:2px 10px;font-size:.85rem}
.chip b{font-weight:600;color:var(--ink2);margin-left:4px;font-size:.78rem}
.quiz details{border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:8px 0}
.quiz summary{color:var(--ink);font-size:1rem;font-weight:600}.quiz p{margin:.4em 0 .2em;color:var(--ink2)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:8px 0 14px}
.tile{border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile b{display:block;font-size:1.25rem;line-height:1.3}.tile span{color:var(--ink2);font-size:.85rem}
.chart{position:relative;margin:4px 0 2px;padding-left:38px}
.plot{position:relative;height:120px;border-bottom:1px solid var(--axis)}
.grid{position:absolute;left:0;right:0;border-top:1px solid var(--line)}
.ylab{position:absolute;left:-38px;width:32px;text-align:right;font-size:.72rem;color:var(--muted);transform:translateY(-50%)}
.bars{position:absolute;inset:0;display:flex;align-items:flex-end;gap:2px}
.bars.dense{gap:1px}
.bars span{flex:1 1 0;min-width:1px;background:var(--bar);border-radius:4px 4px 0 0;cursor:default}
.bars span:hover,.bars span:focus{background:var(--bar-hi);outline:none}
.xaxis{position:relative;height:1.2em;font-size:.72rem;color:var(--muted);margin-top:3px}
.xaxis span{position:absolute;top:0;white-space:nowrap}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--page);font-size:.82rem;padding:6px 9px;border-radius:7px;
display:none;z-index:20;max-width:260px}
#tip b{display:block;font-size:.95rem}
#q{width:100%;padding:9px 11px;border-radius:8px;border:1px solid var(--line);background:var(--page);color:var(--ink);font-size:.95rem}
.tr p{margin:.55em 0;max-width:75ch}
footer{font-size:.8rem;color:var(--muted);text-align:center;margin-top:28px}
@media (max-width:640px){header.card{grid-template-columns:1fr}dl.terms{grid-template-columns:1fr}dl.terms dd{margin-bottom:6px}}
@media print{nav.toc,#q,#tip{display:none}.card{break-inside:avoid;border-color:#ccc}details{display:block}details>*{display:block}}
"""

JS = """
(function(){
const tip=document.getElementById('tip');
function show(el,x,y){tip.textContent='';const b=document.createElement('b');b.textContent=el.dataset.v||'';
const s=document.createElement('span');s.textContent=el.dataset.l||'';tip.append(b,s);tip.style.display='block';
const w=tip.offsetWidth;tip.style.left=Math.min(window.innerWidth-w-8,Math.max(8,x-w/2))+'px';tip.style.top=(y-tip.offsetHeight-10)+'px';}
document.querySelectorAll('[data-v]').forEach(el=>{
 el.addEventListener('pointermove',ev=>show(el,ev.clientX,ev.clientY));
 el.addEventListener('pointerleave',()=>{tip.style.display='none'});
 el.addEventListener('focus',()=>{const r=el.getBoundingClientRect();show(el,r.left+r.width/2,r.top)});
 el.addEventListener('blur',()=>{tip.style.display='none'});});
const q=document.getElementById('q'),n=document.getElementById('qn');
if(q){q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();let c=0;
 document.querySelectorAll('.tr p').forEach(p=>{const hit=!v||p.dataset.t.includes(v);p.style.display=hit?'':'none';if(hit&&v)c++;});
 n.textContent=v?(c+' paragraph'+(c===1?'':'s')+' match'):'';});}
})();
"""


def _ul(items, limit_words=0) -> str:
    items = [sentence(i, limit_words) for i in items or [] if str(i).strip()]
    return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>" if items else ""


def _section_bounds(sections, i, base, end_all):
    s = sections[i]
    start = max(float(s.get("start", 0)), base)
    end = s.get("end") or (sections[i + 1]["start"] if i + 1 < len(sections) else end_all)
    return start, max(start, min(float(end), end_all))


def audio_card(info: dict, meta: dict) -> str:
    """What the audio tells us, in plain words, with a per-minute speech chart and a collapsed tech block."""
    audio = meta.get("audio") or {}
    if not audio:
        return ""
    f, a, stt = audio.get("audio") or {}, audio.get("analysis") or {}, audio.get("speech_to_text") or {}
    wpm = meta.get("words_per_minute") or 0
    tiles = []
    if a:
        tiles.append((f'{round(100 * a.get("speech_ratio", 0))}%',
                      f'of the time someone is speaking ({fmt_length(a.get("speech_seconds", 0))} of '
                      f'{fmt_length(a.get("analysed_seconds", 0))})'))
    if wpm:
        tiles.append((f"{wpm} words per minute", f"speaking pace: {pace_label(wpm)} (lectures are usually 120–160)"))
    if a:
        longest = (a.get("pauses") or [{}])[0]
        tiles.append((str(a.get("pause_count", 0)), "pauses longer than 2 seconds" +
                      (f'; the longest is {longest.get("length")} s at {fmt_time(longest.get("start"))}'
                       if longest else "")))
    if stt:
        tiles.append((stt.get("engine", "?"), f'turned the speech into text ({stt.get("model", "")}, language '
                                              f'{stt.get("language", "?")})'))
    out = ['<section class="card" id="audio"><h2>About the audio</h2>'
           '<p class="lead">The audio track was extracted and analysed by the computer. This is what it found.</p>'
           '<div class="tiles">' + "".join(f'<div class="tile"><b>{e(v)}</b><span>{e(k)}</span></div>'
                                           for v, k in tiles) + "</div>"]
    per_min = a.get("speech_per_minute") or []
    if per_min:
        c0 = (meta.get("clip") or (0, None))[0] or 0
        bars = []
        for i, v in enumerate(per_min):
            t0, t1 = c0 + 60 * i, c0 + 60 * (i + 1)
            bars.append(f'<span tabindex="0" style="height:{max(2, round(100 * v))}%" data-v="{round(100 * v)}% speech" '
                        f'data-l="minute {i + 1} ({fmt_time(t0)}–{fmt_time(t1)})" '
                        f'aria-label="minute {i + 1}: {round(100 * v)}% speech"></span>')
        n = len(per_min)
        step = next(k for k in (1, 2, 5, 10, 15, 30, 60, 120) if n / k <= 8)   # at most ~8 labels
        ticks = "".join(f'<span style="left:{100 * i / n:.2f}%">{fmt_time(c0 + 60 * i)}</span>'
                        for i in range(0, n, step))
        rows = "".join(f'<tr><td class="num">{fmt_time(c0 + 60 * i)}</td><td class="num">{round(100 * v)}%</td></tr>'
                       for i, v in enumerate(per_min))
        out.append('<h3>How much of each minute is speech</h3>'
                   '<p class="muted small">Each bar is one minute. A low bar usually means a demo, a silent pause, '
                   'music or a question from the room. Hover over a bar, or move to it with Tab, to see its value.</p>'
                   '<div class="chart"><div class="plot">'
                   '<div class="grid" style="top:0"><span class="ylab">100%</span></div>'
                   '<div class="grid" style="top:50%"><span class="ylab">50%</span></div>'
                   '<div class="ylab" style="top:100%">0%</div>'
                   f'<div class="bars{" dense" if len(per_min) > 90 else ""}">{"".join(bars)}</div></div>'
                   f'<div class="xaxis">{ticks}</div></div>'
                   '<details><summary>Show the numbers as a table</summary><table><tr><th>Minute starting</th>'
                   f'<th>Speech</th></tr>{rows}</table></details>')
    pauses = a.get("pauses") or []
    if pauses:
        out.append('<h3 style="margin-top:14px">Longest pauses</h3><p class="muted small">A long pause often marks a '
                   'change of topic or a demo. Click a time to watch from there.</p><p>' +
                   " ".join(f'{watch(info, p["start"])} <span class="muted small">{e(p["length"])} s</span>&ensp;'
                            for p in pauses[:8]) + "</p>")
    tech = []
    if f:
        tech += [("Audio format", f'{f.get("codec") or f.get("format", "?")}, {f.get("bitrate_kbps", "?")} kbps, '
                                  f'{f.get("sample_rate", "?")} Hz, {f.get("channels", "?")} channel(s)'),
                 ("Audio downloaded", f'{round((f.get("size_bytes") or 0) / 1e6, 1)} MB ('
                                      f'{"a copy was kept" if f.get("kept") else "deleted after processing"})')]
    loud = [f"{label} {a[key]} dBFS" for label, key in (("average", "mean_dbfs"), ("peak", "peak_dbfs"),
                                                          ("background", "noise_floor_dbfs")) if a.get(key) is not None]
    if loud:
        tech.append(("Loudness", ", ".join(loud)))
    if a.get("method"):
        tech.append(("How speech was detected", a["method"]))
    if tech:
        out.append("<details><summary>Technical details</summary><table>" +
                   "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in tech) + "</table></details>")
    out.append("</section>")
    return "".join(out)


def render_html(info: dict, notes: dict, segs: list, keywords: list, meta: dict) -> str:
    from yt_lecture import paragraphs
    draft = notes.get("written_by") == "auto-draft"
    cut = 32 if draft else 0                       # automatic picks are shortened; written notes are shown whole
    sections = notes.get("sections") or []
    duration = info.get("duration") or (int(segs[-1]["end"]) if segs else 0) or 1
    c_start, c_end = meta.get("clip") or (0, None)
    base = float(c_start or 0)
    end_all = float(c_end if c_end is not None else duration)
    span = max(1.0, end_all - base)
    words = meta.get("words", 0)
    terms = [t for t in notes.get("terms") or [] if t.get("term") and t.get("meaning")]
    questions = [q for q in notes.get("review_questions") or [] if q.get("q")]
    path = (notes.get("prerequisites") or []) + (notes.get("further_study") or [])
    src = meta.get("source", "")

    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>{e(info["title"])} · lecture overview</title><style>{CSS}</style></head><body><main>']

    # 1. what this is
    facts = [info.get("channel") or "", nice_date(info.get("published", "")),
             f"{fmt_length(duration)} long", f"{words:,} words spoken"]
    if c_start or c_end is not None:
        facts.append(f"part processed: {fmt_time(base)}–{fmt_time(end_all)}")
    facts.append("text from the audio" if src.startswith("audio") else
                 "text from captions" if "caption" in src or "subtitle" in src else "text from a transcript file")
    out.append(f'<header class="card"><a href="{e(info["url"])}" target="_blank" rel="noopener">'
               f'<img src="{e(info.get("thumbnail", ""))}" alt="Video thumbnail" loading="lazy"></a><div>'
               f'<div class="muted small">Lecture overview</div><h1>{e(info["title"])}</h1>'
               f'<div class="facts">{"".join(f"<span>{e(x)}</span>" for x in facts if x)}</div>'
               f'<a class="btn" href="{e(info["url"])}" target="_blank" rel="noopener">▶ Watch on YouTube</a>'
               '</div></header>')

    if draft:
        out.append('<div class="note"><b>Automatic draft.</b> The sentences below were picked from what was said, '
                   'word for word, and have not been checked or rewritten yet. Ask your assistant to "write the '
                   'notes" for a clean summary.</div>')
    for w in meta.get("warnings") or []:
        out.append(f'<div class="note"><b>Please note:</b> {e(sentence(w))}</div>')

    # navigation (only the parts that exist)
    links = [("summary", "Summary"), ("outline", "Outline") if sections else None,
             ("notes", "Section notes") if sections else None, ("terms", "Key terms") if terms else None,
             ("quiz", "Check yourself") if questions else None, ("path", "Study path") if path else None,
             ("words", "Common words") if keywords else None, ("audio", "Audio") if meta.get("audio") else None,
             ("transcript", "Transcript")]
    out.append('<nav class="toc" aria-label="Sections of this page">' +
               "".join(f'<a href="#{k}">{v}</a>' for k, v in filter(None, links)) + "</nav>")

    # 2. summary + points to remember
    out.append('<section class="card" id="summary"><h2>Summary</h2>'
               f'<p class="summary">{e(sentence(notes.get("summary"), 60 if draft else 0) or "Not written yet.")}</p>')
    take = (notes.get("key_takeaways") or [])[:5 if draft else 8]
    if take:
        out.append('<h3 style="margin-top:12px">Remember these</h3><ol class="remember">' +
                   "".join(f"<li>{e(sentence(t, cut))}</li>" for t in take) + "</ol>")
    out.append("</section>")

    # 3. outline: one-hue timeline (order is shown by number, not colour) + table
    if sections:
        blocks, rows = [], []
        for i, s in enumerate(sections):
            start, end = _section_bounds(sections, i, base, end_all)
            width = max(0.4, 100.0 * max(1.0, end - start) / span)
            title = s.get("title", "")
            blocks.append(f'<a style="flex:0 0 calc({width:.2f}% - 2px)" href="{e(info["url"])}&amp;t={int(start)}s" '
                          f'target="_blank" rel="noopener" data-v="{i + 1}. {e(title)}" '
                          f'data-l="{fmt_time(start)}–{fmt_time(end)} · {fmt_length(end - start)}" '
                          f'aria-label="Part {i + 1}: {e(title)}, from {fmt_time(start)}">'
                          f'{i + 1 if width > 2.5 else ""}</a>')
            rows.append(f'<tr><td><span class="badge">{i + 1}</span></td><td><a href="#part-{i + 1}">{e(title)}</a>'
                        f'</td><td class="num">{watch(info, start)}</td><td class="num">{fmt_length(end - start)}</td></tr>')
        out.append('<section class="card" id="outline"><h2>Outline</h2>'
                   '<p class="lead">The lecture in order. Each block is one part, and its width shows how long it '
                   'lasts. Click a block or a time to watch that part, or a topic to read its notes.</p>'
                   f'<div class="timeline">{"".join(blocks)}</div>'
                   f'<div class="tl-axis"><span>{fmt_time(base)}</span><span>{fmt_time(end_all)}</span></div>'
                   '<table><tr><th>#</th><th>Topic</th><th>Starts</th><th>Length</th></tr>' + "".join(rows) +
                   "</table></section>")

        # 4. section notes
        body = []
        for i, s in enumerate(sections):
            start, end = _section_bounds(sections, i, base, end_all)
            said = " ".join(x["text"] for x in segs if start <= x["start"] < end)
            body.append(f'<div class="sec" id="part-{i + 1}"><div class="sec-head"><h3><span class="badge">{i + 1}</span>'
                        f'{e(s.get("title", ""))}</h3><span class="sec-time">{fmt_time(start)}–{fmt_time(end)} · '
                        f'{fmt_length(end - start)}</span>{watch(info, start, "▶ watch")}</div>'
                        f'{_ul((s.get("points") or [])[:4], cut)}' +
                        (f'<details><summary>Read what was said in this part ({len(said.split()):,} words)</summary>'
                         f'<p class="said">{e(said)}</p></details>' if said else "") + "</div>")
        out.append('<section class="card" id="notes"><h2>Section notes</h2>'
                   '<p class="lead">The main points of each part.</p>' + "".join(body) + "</section>")

    # 5. key terms, quiz, study path
    if terms:
        out.append('<section class="card" id="terms"><h2>Key terms</h2><dl class="terms">' +
                   "".join(f"<dt>{e(t['term'])}</dt><dd>{e(sentence(t['meaning']))}</dd>" for t in terms) +
                   "</dl></section>")
    if questions:
        out.append('<section class="card quiz" id="quiz"><h2>Check yourself</h2>'
                   '<p class="lead">Try to answer each question, then click it to see the answer.</p>' +
                   "".join(f"<details><summary>{i}. {e(q['q'])}</summary><p>{e(q.get('a') or 'No answer given.')}"
                           f"</p></details>" for i, q in enumerate(questions, 1)) + "</section>")
    if path:
        part = ""
        if notes.get("prerequisites"):
            part += "<h3>Good to know before watching</h3>" + _ul(notes["prerequisites"])
        if notes.get("further_study"):
            part += '<h3 style="margin-top:10px">What to study next</h3>' + _ul(notes["further_study"])
        out.append(f'<section class="card" id="path"><h2>Study path</h2>{part}</section>')

    # 6. common words: plain chips with counts (not a size-coded cloud)
    if keywords:
        chips = "".join(f'<span class="chip">{e(k["term"])}<b>×{k["count"]}</b></span>' for k in keywords[:18])
        out.append('<section class="card" id="words"><h2>Words used most</h2>'
                   '<p class="lead">How often the speaker said each word: a quick hint of what the lecture is about.</p>'
                   f'<div class="chips">{chips}</div></section>')

    # 7. audio
    out.append(audio_card(info, meta))

    # 8. transcript
    paras = [f'<p data-t="{e(txt.lower())}">{watch(info, t)} {e(txt)}</p>' for t, txt in paragraphs(segs)]
    origin = ("made from the audio by speech-to-text, so some words may be misheard" if src.startswith("audio")
              else "taken from the video's captions" if "caption" in src or "subtitle" in src
              else "taken from the transcript file")
    out.append('<section class="card" id="transcript"><h2>Full transcript</h2>'
               f'<p class="lead">Everything that was said, {e(origin)}.</p>'
               '<details><summary>Show the transcript</summary>'
               '<input id="q" type="search" placeholder="Search the transcript…" aria-label="Search the transcript">'
               '<div class="muted small" id="qn" aria-live="polite"></div><div class="tr">' + "".join(paras) +
               "</div></details></section>")

    out.append(f'<footer>Made on {e(meta.get("generated", ""))} for personal study. The video and its content '
               'belong to its creator.</footer>')
    out.append(f'<div id="tip" role="tooltip"></div></main><script>{JS}</script></body></html>')
    return "\n".join(out)
