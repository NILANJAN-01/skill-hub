"""Render the self-contained overview.html for yt-lecture-overview. Standard library only.

Every value from YouTube or the notes is escaped: titles, descriptions and transcripts are untrusted text.
"""
from __future__ import annotations

import html

PALETTE = ["#2563eb", "#0d9488", "#d97706", "#7c3aed", "#db2777", "#059669", "#dc2626", "#4f46e5",
           "#0891b2", "#65a30d", "#c2410c", "#9333ea"]


def e(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def fmt_time(sec) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def ts_link(info, sec, label=None) -> str:
    sec = int(sec or 0)
    return (f'<a class="ts" href="{e(info["url"])}&amp;t={sec}s" target="_blank" rel="noopener">'
            f'{e(label or fmt_time(sec))}</a>')


CSS = """
:root{--bg:#f7f8fa;--card:#fff;--ink:#14171f;--muted:#5b6475;--line:#e3e6ec;--accent:#2563eb;--soft:#eef3ff;--warn:#fff7e6;--warnline:#f5c46b}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b23;--ink:#e8ebf1;--muted:#9aa3b5;--line:#2a303c;--accent:#7aa2ff;--soft:#1c2433;--warn:#2b2414;--warnline:#8a6a2a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.7rem;line-height:1.25;margin:.2em 0}h2{font-size:1.2rem;margin:0 0 .6em}h3{font-size:1.02rem;margin:.2em 0}
a{color:var(--accent)}.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:16px 0}
header.card{display:grid;grid-template-columns:240px 1fr;gap:20px;align-items:start}
header img{width:100%;border-radius:10px;aspect-ratio:16/9;object-fit:cover;background:var(--soft)}
@media (max-width:640px){header.card{grid-template-columns:1fr}}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.chip{background:var(--soft);border-radius:999px;padding:2px 10px;font-size:.82rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
.stat{background:var(--soft);border-radius:10px;padding:10px 12px}.stat b{display:block;font-size:1.3rem}.stat span{font-size:.8rem;color:var(--muted)}
.banner{background:var(--warn);border:1px solid var(--warnline);border-radius:10px;padding:10px 14px;font-size:.92rem}
.timeline{display:flex;height:34px;border-radius:8px;overflow:hidden;border:1px solid var(--line)}
.timeline a{display:block;color:#fff;text-decoration:none;font-size:.72rem;padding:8px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:6px}
.legend{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:4px 16px;margin-top:10px;font-size:.88rem}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}
.map{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;position:relative}
.hub{grid-column:1/-1;justify-self:center;background:var(--accent);color:#fff;border-radius:12px;padding:10px 18px;font-weight:600;text-align:center;max-width:640px}
.node{border:1px solid var(--line);border-top:5px solid var(--c);border-radius:10px;padding:10px 12px;background:var(--card)}
.node ul{margin:.3em 0 0;padding-left:1.1em;font-size:.88rem}
.cloud{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline}.cloud span{line-height:1.2}
.sec{border-left:4px solid var(--c);padding:4px 0 4px 14px;margin:14px 0}.sec ul{margin:.3em 0}
details summary{cursor:pointer;color:var(--accent)}details .excerpt{font-size:.9rem;color:var(--muted);max-height:260px;overflow:auto}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.ts{font-variant-numeric:tabular-nums;text-decoration:none;font-size:.85rem;background:var(--soft);border-radius:6px;padding:0 6px;margin-right:6px}
#q{width:100%;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);margin-bottom:10px}
.tr p{margin:.3em 0}.tr mark{background:#fde68a;color:#111}
.bars{display:flex;align-items:flex-end;gap:2px;height:110px;border-bottom:1px solid var(--line);padding-top:6px}
.bars .bar{flex:1 1 0;min-width:2px;background:var(--accent);border-radius:3px 3px 0 0;opacity:.85}
.bars .bar:hover{opacity:1}.axis{display:flex;justify-content:space-between;font-size:.75rem;color:var(--muted)}
.small{font-size:.82rem}
footer{font-size:.8rem;color:var(--muted);text-align:center;margin-top:30px}
@media print{details{display:block}details>*{display:block}#q{display:none}.card{break-inside:avoid}}
"""

JS = """
const q=document.getElementById('q');if(q){q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();
document.querySelectorAll('.tr p').forEach(p=>{const t=p.dataset.t;p.style.display=!v||t.includes(v)?'':'none'});});}
"""


def _short(text, limit=160) -> str:
    text = str(text)
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _list(items) -> str:
    items = [i for i in items or [] if str(i).strip()]
    return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>" if items else ""


def audio_card(info: dict, meta: dict) -> str:
    """Facts about the extracted audio, a speech-activity chart per minute and the longest pauses."""
    audio = meta.get("audio") or {}
    if not audio:
        return ""
    f, a, stt = audio.get("audio") or {}, audio.get("analysis") or {}, audio.get("speech_to_text") or {}
    facts = []
    if f:
        facts += [(f.get("codec") or f.get("format") or "?", "audio codec"),
                  (f'{f.get("bitrate_kbps", "?")} kbps', "bitrate"),
                  (f'{round((f.get("size_bytes") or 0) / 1e6, 1)} MB', "audio extracted")]
    if stt:
        facts += [(f'{stt.get("engine", "?")}', f'speech to text ({stt.get("model", "")})'),
                  (str(stt.get("language", "?")), "spoken language")]
    if a:
        facts += [(f'{round(100 * a.get("speech_ratio", 0))}%', "of the time someone speaks"),
                  (str(a.get("pause_count", 0)), "pauses of 2 s or more"),
                  (f'{a.get("longest_pause", 0)} s', "longest pause")]
    html_out = ['<section class="card"><h2>Audio analysis</h2><div class="stats">' +
                "".join(f'<div class="stat"><b>{e(v)}</b><span>{e(k)}</span></div>' for v, k in facts) + "</div>"]
    per_min = a.get("speech_per_minute") or []
    if per_min:
        c_start = (meta.get("clip") or (0, None))[0] or 0
        bars = "".join(
            f'<a class="bar" href="{e(info["url"])}&amp;t={int(c_start + 60 * i)}s" target="_blank" rel="noopener" '
            f'title="{fmt_time(c_start + 60 * i)}: speech {round(100 * v)}%" style="height:{max(3, round(100 * v))}%"></a>'
            for i, v in enumerate(per_min))
        html_out.append('<h3>Speech activity per minute</h3><div class="bars">' + bars + "</div>"
                        f'<div class="axis"><span>{fmt_time(c_start)}</span>'
                        f'<span>{fmt_time(c_start + 60 * len(per_min))}</span></div>'
                        '<p class="muted small">Bar height = share of the minute with speech. Low bars are demos, '
                        'silence, music or questions from the room. Estimated from loudness.</p>')
    pauses = a.get("pauses") or []
    if pauses:
        html_out.append("<h3>Longest pauses</h3><p>" + " ".join(
            f'{ts_link(info, p["start"])}<span class="muted small">{p["length"]} s</span>&nbsp; ' for p in pauses[:8])
            + "</p>")
    html_out.append("</section>")
    return "".join(html_out)


def render_html(info: dict, notes: dict, segs: list, keywords: list, meta: dict) -> str:
    sections = notes.get("sections") or []
    duration = info.get("duration") or (int(segs[-1]["end"]) if segs else 0) or 1
    c_start, c_end = meta.get("clip") or (0, None)
    base = float(c_start or 0)
    span = max(1.0, float(c_end if c_end is not None else duration) - base)
    words = meta.get("words", 0)
    out = [f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           f"<title>{e(info['title'])} - lecture overview</title><style>{CSS}</style></head><body><main>"]

    # header
    chips = "".join(f'<span class="chip">{e(k)}</span>' for k in (info.get("keywords") or [])[:10])
    out.append(f'<header class="card"><a href="{e(info["url"])}" target="_blank" rel="noopener">'
               f'<img src="{e(info.get("thumbnail", ""))}" alt="Video thumbnail" loading="lazy"></a><div>'
               f'<div class="muted">Lecture overview</div><h1>{e(info["title"])}</h1>'
               f'<div class="muted">{e(info.get("channel") or "")}'
               f'{" · published " + e(info["published"][:10]) if info.get("published") else ""}'
               f'{" · " + e(info["category"]) if info.get("category") else ""}</div>'
               f'<div class="chips">{chips}</div>'
               f'<a href="{e(info["url"])}" target="_blank" rel="noopener">Watch on YouTube</a></div></header>')

    if notes.get("written_by") == "auto-draft":
        out.append('<div class="banner"><b>Automatic draft.</b> The summary and points below are sentences picked '
                   'from the transcript by a script; they have not been reviewed or rewritten yet.</div>')

    for w in meta.get("warnings") or []:
        out.append(f'<div class="banner"><b>Note.</b> {e(w)}</div>')

    # stats
    src = meta.get("source", "")
    src_label = "audio → text" if src.startswith("audio") else (src.split(" (")[0].split(":")[0] or "-")
    stats = [(fmt_time(duration), "length"), (str(len(sections)), "sections"), (f"{words:,}", "words spoken"),
             (f"{max(1, round(words / 230))} min", "to read the transcript"), (src_label, "transcript source")]
    if meta.get("words_per_minute"):
        stats.append((f'{meta["words_per_minute"]}', "words per minute"))
    if c_start or c_end is not None:
        stats.append((f"{fmt_time(base)}–{fmt_time(base + span)}", "part processed"))
    out.append('<section class="card"><h2>At a glance</h2><div class="stats">' +
               "".join(f'<div class="stat"><b>{e(v)}</b><span>{e(k)}</span></div>' for v, k in stats) +
               "</div></section>")

    # summary + takeaways
    out.append(f'<section class="card"><h2>Summary</h2><p>{e(notes.get("summary") or "Not written yet.")}</p>')
    if notes.get("key_takeaways"):
        out.append("<h3>Key takeaways</h3>" + _list(notes["key_takeaways"]))
    out.append("</section>")

    out.append(audio_card(info, meta))

    # visual timeline
    if sections:
        bars, legend = [], []
        for i, s in enumerate(sections):
            color = PALETTE[i % len(PALETTE)]
            end = s.get("end") or (sections[i + 1]["start"] if i + 1 < len(sections) else duration)
            width = max(0.6, 100.0 * max(1, min(end, base + span) - max(s.get("start", 0), base)) / span)
            label = f'{fmt_time(s.get("start"))} {s.get("title", "")}'
            bars.append(f'<a style="flex:0 0 {width:.2f}%;background:{color}" title="{e(label)}" '
                        f'href="{e(info["url"])}&amp;t={int(s.get("start", 0))}s" target="_blank" rel="noopener">'
                        f'{i + 1}</a>')
            legend.append(f'<div><i style="background:{color}"></i>{i + 1}. {ts_link(info, s.get("start"))}'
                          f'{e(s.get("title", ""))}</div>')
        out.append('<section class="card"><h2>Timeline</h2><div class="timeline">' + "".join(bars) +
                   '</div><div class="legend">' + "".join(legend) + "</div></section>")

        # topic map
        nodes = "".join(f'<div class="node" style="--c:{PALETTE[i % len(PALETTE)]}"><h3>{i + 1}. {e(s.get("title", ""))}'
                        f'</h3>{_list([_short(p) for p in (s.get("points") or [])[:3]])}</div>' for i, s in enumerate(sections))
        out.append(f'<section class="card"><h2>Topic map</h2><div class="map"><div class="hub">{e(info["title"])}'
                   f"</div>{nodes}</div></section>")

    # keyword cloud
    if keywords:
        top = max(k["count"] for k in keywords) or 1
        cloud = "".join(f'<span style="font-size:{0.8 + 1.3 * k["count"] / top:.2f}rem;'
                        f'color:{PALETTE[i % len(PALETTE)]}" title="said {k["count"]} times">{e(k["term"])}</span>'
                        for i, k in enumerate(keywords))
        out.append(f'<section class="card"><h2>Most-used words</h2><div class="cloud">{cloud}</div></section>')

    # section notes
    if sections:
        body = []
        for i, s in enumerate(sections):
            start, end = s.get("start", 0), s.get("end") or duration
            excerpt = " ".join(x["text"] for x in segs if start <= x["start"] < end)
            body.append(f'<div class="sec" style="--c:{PALETTE[i % len(PALETTE)]}"><h3>{ts_link(info, start)}'
                        f'{e(s.get("title", ""))}</h3>{_list(s.get("points"))}'
                        f'<details><summary>What was said ({len(excerpt.split())} words)</summary>'
                        f'<p class="excerpt">{e(excerpt)}</p></details></div>')
        out.append('<section class="card"><h2>Section notes</h2>' + "".join(body) + "</section>")

    # glossary, prerequisites, further study, questions
    terms = [t for t in notes.get("terms") or [] if t.get("term")]
    if any(t.get("meaning") for t in terms):  # a draft without meanings adds nothing over the word cloud
        rows = "".join(f"<tr><th>{e(t['term'])}</th><td>{e(t.get('meaning') or '')}</td></tr>" for t in terms)
        out.append(f'<section class="card"><h2>Key terms</h2><table>{rows}</table></section>')
    extra = ""
    if notes.get("prerequisites"):
        extra += "<h3>Know before watching</h3>" + _list(notes["prerequisites"])
    if notes.get("further_study"):
        extra += "<h3>Study next</h3>" + _list(notes["further_study"])
    if extra:
        out.append(f'<section class="card"><h2>Study path</h2>{extra}</section>')
    if notes.get("review_questions"):
        qa = "".join(f"<details><summary>{i}. {e(q.get('q', ''))}</summary><p>{e(q.get('a', ''))}</p></details>"
                     for i, q in enumerate(notes["review_questions"], 1))
        out.append(f'<section class="card"><h2>Check yourself</h2>{qa}</section>')

    # transcript
    from yt_lecture import paragraphs
    paras = [f'<p data-t="{e(txt.lower())}">{ts_link(info, t)}{e(txt)}</p>' for t, txt in paragraphs(segs)]
    out.append('<section class="card"><details><summary><b>Full transcript</b> '
               f'<span class="muted">({e(meta.get("source", ""))})</span></summary>'
               '<input id="q" type="search" placeholder="Search the transcript"><div class="tr">' +
               "".join(paras) + "</div></details></section>")

    out.append(f'<footer>Made with yt-lecture-overview on {e(meta.get("generated", ""))} from the video\'s '
               f'{"captions" if "caption" in meta.get("source", "") or "subtitle" in meta.get("source", "") else "transcript"}. '
               'For study use; the video belongs to its creator.</footer>')
    out.append(f"</main><script>{JS}</script></body></html>")
    return "\n".join(out)

