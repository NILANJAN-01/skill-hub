"""Render the self-contained overview.html for yt-lecture-overview. Standard library only.

The page is built for reading, in this order: what the lecture is, the summary and the points to remember,
an outline with a timeline, notes per section, key terms, a self-check quiz, what the audio tells us, and the
searchable transcript. Labels are plain words; technical audio details sit in a collapsed block.

A small inline script adds study aids: ticking parts as studied, scoring the quiz, highlighted transcript search,
the current part in the menu and a light/dark switch. Without scripts the page still reads in full.

Every value from YouTube or the notes is escaped: titles, descriptions and transcripts are untrusted text.
"""
from __future__ import annotations

import datetime
import html
import re
import textwrap
import zlib

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
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;background:var(--page);color:var(--ink);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 72px}
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
.layout{display:grid;grid-template-columns:196px minmax(0,1fr);gap:26px;align-items:start}
nav.toc{position:sticky;top:12px;z-index:5;display:flex;flex-direction:column;gap:2px;margin-top:18px;
max-height:calc(100vh - 24px);overflow-y:auto;scrollbar-width:thin}
.nav-group{display:flex;flex-direction:column;gap:1px;margin-bottom:12px}
.nav-h{font-size:.7rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);padding:2px 10px 4px}
nav.toc a{text-decoration:none;color:var(--ink2);font-size:.9rem;padding:5px 10px;border-radius:8px}
nav.toc a:hover{color:var(--ink);background:var(--chip)}
nav.toc a.on{color:var(--ink);background:var(--chip);font-weight:600;box-shadow:inset 3px 0 0 var(--bar)}
nav.toc .theme{align-self:flex-start;margin:4px 10px}
.group-h{display:flex;align-items:center;gap:10px;margin:30px 0 -4px;font-size:.75rem;font-weight:700;letter-spacing:.08em;
text-transform:uppercase;color:var(--muted);scroll-margin-top:64px}.group-h:first-child{margin-top:18px}
.group-h::after{content:"";flex:1;border-top:1px solid var(--line)}
.group-h span{font-weight:400;text-transform:none;letter-spacing:0;font-size:.85rem}
@media (max-width:980px){main{max-width:880px}.layout{display:block}
nav.toc{position:sticky;top:0;flex-direction:row;align-items:center;gap:6px;margin:0 -16px;padding:8px 16px;max-height:none;
background:var(--page);border-bottom:1px solid var(--line);overflow-x:auto;overflow-y:hidden;white-space:nowrap;scrollbar-width:none}
nav.toc::-webkit-scrollbar{display:none}.nav-group{display:contents}.nav-h{display:none}
nav.toc a{background:var(--chip);border-radius:999px;padding:4px 10px;font-size:.88rem}
nav.toc a.on{background:var(--bar);color:#fff;box-shadow:none;font-weight:400}nav.toc .theme{margin:0 0 0 auto;flex:none}}
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
.bars a{flex:1 1 0;min-width:1px;background:var(--bar);border-radius:4px 4px 0 0}
.bars a:hover,.bars a:focus{background:var(--bar-hi);outline:none}
.xaxis{position:relative;height:1.2em;font-size:.72rem;color:var(--muted);margin-top:3px}
.xaxis span{position:absolute;top:0;white-space:nowrap}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--page);font-size:.82rem;padding:6px 9px;border-radius:7px;
display:none;z-index:20;max-width:260px}
#tip b{display:block;font-size:.95rem}
.search{display:flex;gap:8px;align-items:center;margin:4px 0}
#q{flex:1;min-width:0;padding:9px 11px;border-radius:8px;border:1px solid var(--line);background:var(--page);color:var(--ink);font-size:.95rem}
.tr p{margin:.55em 0;max-width:75ch}
mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 1px}mark.cur{outline:2px solid var(--bar)}
.mini{font:inherit;font-size:.82rem;border:1px solid var(--line);background:var(--card);color:var(--ink2);border-radius:999px;
padding:2px 10px;cursor:pointer}.mini:hover{color:var(--ink);border-color:var(--axis)}
.mini[aria-pressed="true"]{background:var(--bar);border-color:var(--bar);color:#fff}
button.chip{font:inherit;font-size:.85rem;border:0;color:var(--ink);cursor:pointer}button.chip:hover{outline:1px solid var(--bar)}
.thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:8px 0 16px}
.thumb{display:block;aspect-ratio:16/9;border-radius:8px;border:1px solid var(--line);background:center/contain no-repeat var(--chip);
position:relative;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.thumb:hover,.thumb:focus{border-color:var(--bar);outline:none;box-shadow:0 0 0 2px var(--bar)}
.thumb .tt{position:absolute;right:6px;bottom:6px;background:rgba(0,0,0,.66);color:#fff;font-size:.72rem;border-radius:5px;
padding:1px 6px;font-variant-numeric:tabular-nums}
figure.sl{margin:0}figure.sl figcaption{font-size:.84rem;color:var(--ink2);margin-top:5px;line-height:1.4}
figcaption .sp{display:flex;align-items:center;font-size:.8rem;margin-bottom:2px}
figcaption .sp .badge{min-width:1.45em;height:1.45em;font-size:.7rem;margin-right:6px}
.strip{display:flex;gap:8px;margin:8px 0 4px;flex-wrap:wrap;align-items:center}.strip .thumb{width:132px}
dialog#lb{border:0;padding:0;background:transparent;max-width:min(1200px,96vw);width:96vw}
dialog#lb::backdrop{background:rgba(0,0,0,.82)}
.lb-img{width:100%;aspect-ratio:16/9;max-height:78vh;background:center/contain no-repeat}
.lb-bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:var(--card);color:var(--ink);border-radius:10px;
padding:8px 12px;margin-top:8px}#lb-cap{flex:1;min-width:160px;font-size:.92rem}
.hld-wrap{overflow-x:auto;margin:10px 0 6px}
.hld-svg{display:block;width:100%;height:auto;color:var(--ink2)}
.hld-text{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:4px 28px}
.hld-text dl.terms{grid-template-columns:minmax(110px,max-content) 1fr;font-size:.93rem}
.hld-svg rect{fill:var(--chip);stroke:var(--bar);stroke-width:1.5}
.hld-svg .nm{fill:var(--ink);font:600 15px system-ui,sans-serif}.hld-svg .rl{fill:var(--muted);font:12.5px system-ui,sans-serif}
.hld-svg path{fill:none;stroke:currentColor;stroke-width:1.6}.hld-svg path.back{stroke-dasharray:5 4}
.hld-svg .el{fill:var(--ink2);font:12px system-ui,sans-serif;paint-order:stroke;stroke:var(--card);stroke-width:4px;stroke-linejoin:round}
ol.flow{padding-left:1.3em}ol.flow li{margin:.25em 0}
.mystudy{margin-top:12px;font-size:.88rem;color:var(--ink2)}
.mystudy .row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.progress{flex:1;min-width:120px;height:8px;background:var(--chip);border-radius:999px;overflow:hidden}
.progress i{display:block;height:100%;width:0;background:var(--bar);transition:width .3s}
.done-box{margin-left:auto;font-size:.85rem;color:var(--ink2);display:inline-flex;gap:6px;align-items:center;cursor:pointer}
.sec.done h3{color:var(--muted)}.sec.done .badge{background:var(--muted)}
.term-at{display:inline-flex;gap:6px;align-items:center;margin-left:6px;vertical-align:middle}
.quiz-tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:6px 0}
.quiz .rate{display:flex;gap:6px;align-items:center;font-size:.85rem;color:var(--muted);margin:.3em 0 .2em}
.mk{position:absolute;top:0;bottom:0;border-left:1px dashed var(--ink2);pointer-events:none}
.mk b{position:absolute;top:-1px;left:2px;font-size:.68rem;line-height:1.3;color:var(--ink2);background:var(--card);
border-radius:3px;padding:0 3px}
footer{font-size:.8rem;color:var(--muted);text-align:center;margin-top:28px}
@media (max-width:640px){header.card{grid-template-columns:1fr}dl.terms{grid-template-columns:1fr}dl.terms dd{margin-bottom:6px}}
@media print{nav.toc,.search,#tip,.mini,.js,dialog{display:none!important}.layout{display:block}
.card{break-inside:avoid;border-color:#ccc}details{display:block}details>*{display:block}}
"""

# Raw string: the search code holds regex backslashes. Study progress and quiz scores are kept in the browser's
# localStorage under the video id; everything degrades to a plain page when scripts or storage are off.
JS = r"""
(function(){
const root=document.documentElement,main=document.querySelector('main'),KEY='yt-lecture-overview:'+(main.dataset.vid||'');
function load(k){try{return JSON.parse(localStorage.getItem(k)||'null')}catch(_){return null}}
function store(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(_){}}
const st=load(KEY)||{};st.done=st.done||{};st.quiz=st.quiz||{};
function save(){store(KEY,st)}
document.querySelectorAll('.js[hidden]').forEach(el=>{el.hidden=false});

// tooltips for the timeline and the speech chart
const tip=document.getElementById('tip');
function show(el,x,y){tip.textContent='';const b=document.createElement('b');b.textContent=el.dataset.v||'';
const s=document.createElement('span');s.textContent=el.dataset.l||'';tip.append(b,s);tip.style.display='block';
const w=tip.offsetWidth;tip.style.left=Math.min(window.innerWidth-w-8,Math.max(8,x-w/2))+'px';tip.style.top=(y-tip.offsetHeight-10)+'px';}
document.querySelectorAll('[data-v]').forEach(el=>{
 el.addEventListener('pointermove',ev=>show(el,ev.clientX,ev.clientY));
 el.addEventListener('pointerleave',()=>{tip.style.display='none'});
 el.addEventListener('focus',()=>{const r=el.getBoundingClientRect();show(el,r.left+r.width/2,r.top)});
 el.addEventListener('blur',()=>{tip.style.display='none'});});

// light / dark switch (remembered for every overview)
const tb=document.getElementById('theme'),TKEY='yt-lecture-overview:theme';
function theme(t){if(t)root.dataset.theme=t;else delete root.dataset.theme;}
theme(load(TKEY));
if(tb)tb.addEventListener('click',()=>{const dark=root.dataset.theme?root.dataset.theme==='dark':
 matchMedia('(prefers-color-scheme: dark)').matches;const t=dark?'light':'dark';theme(t);store(TKEY,t);});

// study progress: parts ticked as studied + quiz self-score
const boxes=[...document.querySelectorAll('input.studied')],qs=[...document.querySelectorAll('.quiz details[data-q]')];
function progress(){const n=boxes.filter(b=>b.checked).length,bar=document.getElementById('prog');
 const got=qs.filter(d=>st.quiz[d.dataset.q]==='y').length,tried=qs.filter(d=>st.quiz[d.dataset.q]).length;
 if(bar)bar.style.width=(boxes.length?100*n/boxes.length:0)+'%';
 const parts=[];if(boxes.length)parts.push(n+' of '+boxes.length+' parts studied');
 if(qs.length)parts.push(tried?('quiz: '+got+' of '+qs.length+' right'):'quiz not tried yet');
 const t=document.getElementById('progt');if(t)t.textContent=parts.join(' · ');
 const sc=document.getElementById('score');if(sc)sc.textContent=tried?('Score: '+got+' of '+qs.length+' right'+
  (tried<qs.length?' ('+(qs.length-tried)+' not tried)':'')):'';}
function syncBox(b){b.checked=!!st.done[b.value];b.closest('.sec').classList.toggle('done',b.checked);}
boxes.forEach(b=>{syncBox(b);b.addEventListener('change',()=>{st.done[b.value]=b.checked;syncBox(b);save();progress();});});
function syncQuiz(d){d.querySelectorAll('button[data-a]').forEach(o=>o.setAttribute('aria-pressed',st.quiz[d.dataset.q]===o.dataset.a));}
qs.forEach(d=>{syncQuiz(d);d.querySelectorAll('button[data-a]').forEach(btn=>btn.addEventListener('click',()=>{
 st.quiz[d.dataset.q]=btn.dataset.a;syncQuiz(d);save();progress();}));});
const all=document.getElementById('allq');
if(all)all.addEventListener('click',()=>{const open=all.getAttribute('aria-pressed')!=='true';qs.forEach(d=>{d.open=open});
 all.setAttribute('aria-pressed',open);all.textContent=open?'Hide all answers':'Show all answers';});
const reset=document.getElementById('reset');
if(reset)reset.addEventListener('click',()=>{if(!confirm('Clear your progress and quiz answers for this lecture?'))return;
 st.done={};st.quiz={};save();boxes.forEach(syncBox);qs.forEach(syncQuiz);progress();});
progress();

// highlight the part of the page being read in the menu
const nav=document.querySelector('nav.toc'),links=nav?[...nav.querySelectorAll('a[href^="#"]')]:[];
if(links.length&&'IntersectionObserver' in window){const seen=new Map();
 const io=new IntersectionObserver(es=>{es.forEach(en=>seen.set(en.target.id,en.isIntersecting));
  const cur=links.find(a=>seen.get(a.hash.slice(1)));if(!cur)return;
  links.forEach(a=>a.classList.toggle('on',a===cur));
  if(cur.offsetLeft<nav.scrollLeft||cur.offsetLeft+cur.offsetWidth>nav.scrollLeft+nav.clientWidth)nav.scrollLeft=cur.offsetLeft-16;
 },{rootMargin:'-70px 0px -55% 0px'});
 links.forEach(a=>{const s=document.getElementById(a.hash.slice(1));if(s)io.observe(s);});}

// slide viewer: any [data-slide] link opens it; arrows move, Esc closes. Without it, links open the video.
const lb=document.getElementById('lb'),all_s=[...document.querySelectorAll('#design a.thumb[data-slide]')];
if(lb&&lb.showModal&&all_s.length){let li=0;
 function slide(i){li=(i+all_s.length)%all_s.length;const a=all_s[li];
  lb.querySelector('.lb-img').className='lb-img im-'+a.dataset.slide;
  document.getElementById('lb-cap').textContent=a.dataset.cap||'';
  const w=document.getElementById('lb-watch');w.href=a.href;w.textContent='▶ watch from '+a.dataset.t;
  if(!lb.open)lb.showModal();}
 document.querySelectorAll('a[data-slide],button[data-slide]').forEach(a=>a.addEventListener('click',ev=>{
  if(ev.ctrlKey||ev.metaKey||ev.shiftKey)return;ev.preventDefault();
  slide(Math.max(0,all_s.findIndex(t=>t.dataset.slide===a.dataset.slide)));}));
 document.getElementById('lb-prev').addEventListener('click',()=>slide(li-1));
 document.getElementById('lb-next').addEventListener('click',()=>slide(li+1));
 document.getElementById('lb-x').addEventListener('click',()=>lb.close());
 lb.addEventListener('click',ev=>{if(ev.target===lb)lb.close();});
 lb.addEventListener('keydown',ev=>{if(ev.key==='ArrowLeft')slide(li-1);if(ev.key==='ArrowRight')slide(li+1);});}

// transcript search: highlight every match, Enter jumps to the next one
const q=document.getElementById('q'),n=document.getElementById('qn'),box=document.getElementById('trd');
const paras=[...document.querySelectorAll('.tr .tx')];let hits=[],at=-1;
function rx(v){const parts=v.split(/[\s\-]+/).filter(Boolean).map(w=>w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
 return parts.length?new RegExp(parts.join('[\\s\\-]+'),'gi'):null;}
function run(){const v=q.value.trim(),re=rx(v);hits=[];at=-1;
 paras.forEach(t=>{const raw=t.dataset.raw||(t.dataset.raw=t.textContent);t.textContent='';
  if(!re){t.append(raw);t.parentNode.hidden=false;return;}
  let m,last=0;re.lastIndex=0;
  while((m=re.exec(raw))){t.append(raw.slice(last,m.index));const k=document.createElement('mark');k.textContent=m[0];
   t.append(k);hits.push(k);last=m.index+m[0].length;}
  t.append(raw.slice(last));t.parentNode.hidden=last===0;});
 if(re&&box)box.open=true;
 n.textContent=re?(hits.length?hits.length+' match'+(hits.length===1?'':'es')+'. Press Enter to go to the next.':'No matches.'):'';}
function next(){if(!hits.length)return;if(at>=0)hits[at].classList.remove('cur');at=(at+1)%hits.length;
 hits[at].classList.add('cur');hits[at].scrollIntoView({block:'center',behavior:'smooth'});
 n.textContent='Match '+(at+1)+' of '+hits.length+'. Press Enter to go to the next.';}
if(q){q.addEventListener('input',run);q.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();next();}});
 document.querySelectorAll('[data-find]').forEach(b=>b.addEventListener('click',()=>{q.value=b.dataset.find;run();
  if(hits.length)next();else document.getElementById('transcript').scrollIntoView({behavior:'smooth'});}));
 if(q.value)run();}
})();
"""


def _norm(text) -> str:
    return " " + re.sub(r"[^0-9a-z]+", " ", str(text or "").lower()).strip() + " "


def first_mention(term, segs):
    """Start (seconds) of the first segment that says `term`, or None.

    Case, punctuation, hyphens and a plural -s/-es are ignored, a bracketed part ("gradient descent (GD)") is
    dropped, and a term split across two neighbouring segments is still found.
    """
    words = _norm(re.sub(r"\(.*?\)", " ", str(term or ""))).strip()
    if not words:
        return None
    pat = re.compile(" " + re.escape(words) + "(?:s|es)? ")
    texts = [_norm(s.get("text")) for s in segs]
    for i, t in enumerate(texts):
        if pat.search(t):
            return segs[i]["start"]
        if " " in words and i + 1 < len(texts):            # split across the boundary: must start in this segment
            m = pat.search(t + texts[i + 1].lstrip())
            if m and m.start() < len(t) - 1:
                return segs[i]["start"]
    return None


def _key(*parts) -> str:
    """Short stable id for saved progress: changes when a section or question is rewritten."""
    return format(zlib.crc32("|".join(str(p) for p in parts).encode("utf-8")), "08x")


def _short(text, limit) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def hld_layout(names: list, edges: list) -> tuple:
    """Columns for a left-to-right design diagram: each component sits one step after everything that feeds it.

    Edges that close a loop (found by a depth-first walk) are 'back' edges and do not push columns. Returns
    ({name: (layer, row)}, set of back edges).
    """
    adj = {n: [] for n in names}
    for a, b in edges:
        adj[a].append(b)
    state, back = {}, set()
    for root in names:                                   # iterative DFS: no recursion limit on big diagrams
        if state.get(root):
            continue
        stack = [(root, iter(adj[root]))]
        state[root] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                back.add((node, nxt))
            elif not state.get(nxt):
                state[nxt] = 1
                stack.append((nxt, iter(adj[nxt])))
    layer = {n: 0 for n in names}
    for _ in range(len(names)):
        moved = False
        for a, b in edges:
            if (a, b) not in back and layer[b] < layer[a] + 1:
                layer[b], moved = layer[a] + 1, True
        if not moved:
            break
    rows, pos = {}, {}
    for n in names:                                       # keep the order the components were listed in
        pos[n] = (layer[n], rows.get(layer[n], 0))
        rows[layer[n]] = rows.get(layer[n], 0) + 1
    return pos, back


def hld_svg(hld: dict) -> str:
    """The high-level design as an inline SVG: boxes for components, arrows for the flow between them."""
    comps = [c for c in hld.get("components") or [] if isinstance(c, dict) and str(c.get("name", "")).strip()]
    flow = [f for f in hld.get("flow") or [] if isinstance(f, dict) and f.get("from") and f.get("to")]
    names, roles = [], {}
    for c in comps:
        roles.setdefault(str(c["name"]).strip(), str(c.get("role") or ""))
    for n in list(roles) + [str(x).strip() for f in flow for x in (f["from"], f["to"])]:
        if n and n not in names:
            names.append(n)
    if not names or len(names) > 40:
        return ""
    edges = [(str(f["from"]).strip(), str(f["to"]).strip(), str(f.get("label") or "")) for f in flow]
    edges = [(a, b, lab) for a, b, lab in edges if a != b]
    pos, back = hld_layout(names, [(a, b) for a, b, _ in edges])
    layers = max(p[0] for p in pos.values()) + 1
    across = layers > 5                                   # a long chain reads better top to bottom
    bw, bh, pad = 168, 60, 20
    gap_main, gap_side = (64, 26) if across else (104, 24)          # room for the arrow labels

    def box(n):
        lay, row = pos[n]
        if across:
            return pad + row * (bw + gap_side), pad + lay * (bh + gap_main)
        return pad + lay * (bw + gap_main), pad + row * (bh + gap_side)
    xs = [box(n)[0] for n in names]
    ys = [box(n)[1] for n in names]
    width, height = max(xs) + bw + pad, max(ys) + bh + pad
    extra = 50 if any((a, b) in back or pos[a][0] == pos[b][0] for a, b, _ in edges) else 0
    if across:
        width += extra
    else:
        height += extra
    # shrinks to fit, but never below 80% (text stays readable); past that the diagram scrolls sideways
    parts = [f'<div class="hld-wrap"><svg class="hld-svg" viewBox="0 0 {width} {height}" '
             f'style="max-width:{width}px;min-width:{int(width * 0.75)}px" role="img" '
             f'aria-label="High-level design diagram: {len(names)} components, {len(edges)} connections">'
             '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
             'orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="currentColor" stroke="none"/></marker></defs>']
    labels = []
    for a, b, lab in edges:
        (ax, ay), (bx, by) = box(a), box(b)
        loop = (a, b) in back or pos[a][0] == pos[b][0]
        if loop and across:                              # return arrow: out of the right side, round, back in
            p0, p3 = (ax + bw, ay + bh / 2), (bx + bw, by + bh / 2)
            p1, p2 = (p0[0] + 50, p0[1]), (p3[0] + 50, p3[1])
        elif loop:                                       # return arrow below the boxes
            p0, p3 = (ax + bw / 2, ay + bh), (bx + bw / 2, by + bh)
            p1, p2 = (p0[0], p0[1] + 50), (p3[0], p3[1] + 50)
        elif across:
            p0, p3 = (ax + bw / 2, ay + bh), (bx + bw / 2, by)
            p1, p2 = (p0[0], p0[1] + gap_main / 2), (p3[0], p3[1] - gap_main / 2)
        else:
            p0, p3 = (ax + bw, ay + bh / 2), (bx, by + bh / 2)
            p1, p2 = (p0[0] + gap_main / 2, p0[1]), (p3[0] - gap_main / 2, p3[1])
        parts.append(f'<path class="{"back" if loop else "fwd"}" marker-end="url(#ah)" d="M{p0[0]:.0f},{p0[1]:.0f} '
                     f'C{p1[0]:.0f},{p1[1]:.0f} {p2[0]:.0f},{p2[1]:.0f} {p3[0]:.0f},{p3[1]:.0f}"><title>'
                     f'{e(a)} → {e(b)}{": " + e(lab) if lab else ""}</title></path>')
        if lab:                     # 60% along the arrow: arrows fanning out of one box have spread apart there
            t, u = 0.6, 0.4
            mx = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
            my = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
            labels.append(f'<text class="el" x="{mx:.0f}" y="{my - 4:.0f}" text-anchor="middle">{e(_short(lab, 20))}'
                          '</text>')
    for n in names:
        x, y = box(n)
        role = roles.get(n, "")
        cx = x + bw / 2
        if role:
            text = (f'<text class="nm" x="{cx:.0f}" y="{y + 26}" text-anchor="middle">{e(_short(n, 19))}</text>'
                    f'<text class="rl" x="{cx:.0f}" y="{y + 45}" text-anchor="middle">{e(_short(role, 25))}</text>')
        else:
            lines = textwrap.wrap(n, 18)[:2] or [n]
            if len(textwrap.wrap(n, 18)) > 2:
                lines[1] = _short(lines[1] + " …", 18)
            top = y + bh / 2 - (len(lines) - 1) * 9 + 5
            text = "".join(f'<text class="nm" x="{cx:.0f}" y="{top + i * 18:.0f}" text-anchor="middle">{e(ln)}</text>'
                           for i, ln in enumerate(lines))
        parts.append(f'<g><title>{e(n)}{": " + e(role) if role else ""}</title>'
                     f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="10"/>{text}</g>')
    return "".join(parts + labels) + "</svg></div>"


def _ul(items, limit_words=0) -> str:
    items = [sentence(i, limit_words) for i in items or [] if str(i).strip()]
    return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>" if items else ""


def _section_bounds(sections, i, base, end_all):
    s = sections[i]
    start = max(float(s.get("start", 0)), base)
    end = s.get("end") or (sections[i + 1]["start"] if i + 1 < len(sections) else end_all)
    return start, max(start, min(float(end), end_all))


def audio_card(info: dict, meta: dict, marks=()) -> str:
    """What the audio tells us, in plain words, with a per-minute speech chart and a collapsed tech block.

    `marks` is a list of (part number, start seconds): each part start is drawn on the chart as a dashed line.
    """
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
            bars.append(f'<a href="{e(info["url"])}&amp;t={int(t0)}s" target="_blank" rel="noopener" '
                        f'style="height:{max(2, round(100 * v))}%" data-v="{round(100 * v)}% speech" '
                        f'data-l="minute {i + 1} ({fmt_time(t0)}–{fmt_time(t1)}) · click to watch" '
                        f'aria-label="minute {i + 1}: {round(100 * v)}% speech; watch from {fmt_time(t0)}"></a>')
        n = len(per_min)
        step = next(k for k in (1, 2, 5, 10, 15, 30, 60, 120) if n / k <= 8)   # at most ~8 labels
        ticks = "".join(f'<span style="left:{100 * i / n:.2f}%">{fmt_time(c0 + 60 * i)}</span>'
                        for i in range(0, n, step))
        lines = "".join(f'<div class="mk" style="left:{100 * (t - c0) / (60 * n):.2f}%"><b>{num}</b></div>'
                        for num, t in marks if c0 < t < c0 + 60 * n)
        rows = "".join(f'<tr><td class="num">{fmt_time(c0 + 60 * i)}</td><td class="num">{round(100 * v)}%</td></tr>'
                       for i, v in enumerate(per_min))
        out.append('<h3>How much of each minute is speech</h3>'
                   '<p class="muted small">Each bar is one minute; click it to watch that minute. A low bar usually '
                   'means a demo, a silent pause, music or a question from the room.' +
                   (' Dashed lines mark where each part of the outline starts.' if lines else '') + '</p>'
                   '<div class="chart"><div class="plot">'
                   '<div class="grid" style="top:0"><span class="ylab">100%</span></div>'
                   '<div class="grid" style="top:50%"><span class="ylab">50%</span></div>'
                   '<div class="ylab" style="top:100%">0%</div>'
                   f'<div class="bars{" dense" if len(per_min) > 90 else ""}">{"".join(bars)}</div>{lines}</div>'
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


def slide_part(slide_start, sections, base, end_all) -> int:
    """Index of the outline part a slide belongs to (the last part starting at or before it), or -1."""
    idx = -1
    for i in range(len(sections)):
        if _section_bounds(sections, i, base, end_all)[0] <= slide_start + 0.5:
            idx = i
    return idx


def _thumb(info, s, small=False) -> str:
    cap = f'Slide {s["n"]} · {fmt_time(s["start"])}' + (f' · {s["caption"]}' if s.get("caption") else "")
    return (f'<a class="thumb im-{s["n"]}" href="{e(info["url"])}&amp;t={int(s["start"])}s" target="_blank" '
            f'rel="noopener" data-slide="{s["n"]}" data-t="{fmt_time(s["start"])}" data-cap="{e(cap)}" '
            f'aria-label="{e(cap)}" title="{e(cap)}">{"" if small else f"""<span class="tt">{fmt_time(s["start"])}</span>"""}</a>')


def design_card(info: dict, notes: dict, slides: list, sections: list, base: float, end_all: float,
                draft: bool) -> str:
    """'Design and slides': the agent's high-level design (diagram + text) and the captured slides by part."""
    hld = notes.get("hld") if isinstance(notes.get("hld"), dict) else {}
    comps = [c for c in hld.get("components") or [] if isinstance(c, dict) and c.get("name")]
    flow = [f for f in hld.get("flow") or [] if isinstance(f, dict) and f.get("from") and f.get("to")]
    if not (hld.get("summary") or comps or flow or slides):
        return ""
    by_file = {s["file"]: s for s in slides}
    out = ['<section class="card" id="design"><h2>Design and slides</h2>'
           '<p class="lead">The big picture: how the ideas of the lecture fit together, and the slides shown while '
           'presenting.</p>']
    if hld.get("summary") or comps or flow:
        out.append('<h3>High-level design</h3>')
        if hld.get("summary"):
            out.append(f'<p class="summary">{e(sentence(hld["summary"]))}</p>')
        out.append(hld_svg(hld))
        text = ""
        if comps:
            items = []
            for c in comps:
                s = by_file.get(str(c.get("slide") or ""))
                see = (f' <button type="button" class="js mini" hidden data-slide="{s["n"]}">see slide {s["n"]}'
                       '</button>' if s else "")
                items.append(f"<dt>{e(c['name'])}</dt><dd>{e(sentence(c.get('role') or ''))}{see}</dd>")
            text += '<div><h3 style="margin-top:10px">Components</h3><dl class="terms">' + "".join(items) + "</dl></div>"
        if flow:
            text += ('<div><h3 style="margin-top:10px">How it flows</h3><ol class="flow">' +
                     "".join(f"<li><b>{e(f['from'])}</b> → <b>{e(f['to'])}</b>"
                             f"{': ' + e(f['label']) if f.get('label') else ''}</li>" for f in flow) + "</ol></div>")
        if text:
            out.append(f'<div class="hld-text">{text}</div>')
    elif slides and draft:
        out.append('<div class="note">Ask your assistant to "write the notes": it can read these slides and draw '
                   'the lecture\'s high-level design here.</div>')
    if slides:
        out.append(f'<h3 style="margin-top:14px">Slides ({len(slides)})</h3><p class="muted small">Captured while the '
                   'lecture was presented: one image per slide, taken once the slide was complete. Click a slide to '
                   'enlarge it; use the arrow keys to move between slides.</p>')
        figs = []
        for s in slides:                   # one dense grid; each caption names the outline part it belongs to
            idx = slide_part(s["start"], sections, base, end_all)
            part = (f'<span class="sp"><span class="badge">{idx + 1}</span><a href="#part-{idx + 1}">'
                    f'{e(_short(sections[idx].get("title", ""), 40))}</a></span>' if idx >= 0 else "")
            figs.append(f'<figure class="sl">{_thumb(info, s)}<figcaption>{part}'
                        f'{e(s["caption"]) if s.get("caption") else ""}</figcaption></figure>')
        out.append('<div class="thumbs">' + "".join(figs) + "</div>")
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
    slides = [dict(s, n=i) for i, s in enumerate(meta.get("slides") or [], 1) if s.get("data")]

    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<link rel="icon" href="data:,">'
           f'<title>{e(info["title"])} · lecture overview</title><style>{CSS}</style></head><body>'
           f'<main data-vid="{e(info.get("video_id", ""))}">']

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
               f'<a class="btn" href="{e(info["url"])}" target="_blank" rel="noopener">▶ Watch on YouTube</a>' +
               ('<div class="js mystudy" hidden><div class="row"><b>Your progress</b><div class="progress" '
                'aria-hidden="true"><i id="prog"></i></div><button type="button" class="mini" id="reset">Start '
                'over</button></div><div id="progt" aria-live="polite"></div></div>' if sections or questions else '') +
               '</div></header>')

    if draft:
        out.append('<div class="note"><b>Automatic draft.</b> The sentences below were picked from what was said, '
                   'word for word, and have not been checked or rewritten yet. Ask your assistant to "write the '
                   'notes" for a clean summary.</div>')
    for w in meta.get("warnings") or []:
        out.append(f'<div class="note"><b>Please note:</b> {e(sentence(w))}</div>')

    # navigation: three groups (learn, practise, reference), only the parts that exist
    design = design_card(info, notes, slides, sections, base, end_all, draft)
    groups = [("Learn", [("summary", "Summary"), ("outline", "Outline") if sections else None,
                         ("design", "Design and slides") if design else None,
                         ("notes", "Section notes") if sections else None]),
              ("Practise", [("terms", "Key terms") if terms else None, ("quiz", "Check yourself") if questions else None,
                            ("path", "Study path") if path else None]),
              ("Reference", [("words", "Common words") if keywords else None,
                             ("audio", "Audio") if meta.get("audio") else None, ("transcript", "Transcript")])]
    nav = "".join(f'<div class="nav-group"><span class="nav-h">{g}</span>' +
                  "".join(f'<a href="#{k}">{v}</a>' for k, v in filter(None, items)) + "</div>"
                  for g, items in groups if any(items))
    out.append('<div class="layout"><nav class="toc" aria-label="Sections of this page">' + nav +
               '<button type="button" class="js mini theme" id="theme" hidden title="Switch between light and dark" '
               'aria-label="Switch between light and dark">◐ Theme</button></nav><div class="content">'
               '<p class="group-h" id="learn">Learn <span>what the lecture teaches</span></p>')

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

    # 3b. high-level design and the captured slides
    out.append(design)

    # 4. section notes, each with the slides shown in that part
    def _strip(i):
        mine = [s for s in slides if slide_part(s["start"], sections, base, end_all) == i]
        if not mine:
            return ""
        more = (f'<a class="small" href="#design">+{len(mine) - 6} more slides</a>' if len(mine) > 6 else "")
        return '<div class="strip">' + "".join(_thumb(info, s, small=True) for s in mine[:6]) + more + "</div>"

    if sections:
        body = []
        for i, s in enumerate(sections):
            start, end = _section_bounds(sections, i, base, end_all)
            said = " ".join(x["text"] for x in segs if start <= x["start"] < end)
            body.append(f'<div class="sec" id="part-{i + 1}"><div class="sec-head"><h3><span class="badge">{i + 1}</span>'
                        f'{e(s.get("title", ""))}</h3><span class="sec-time">{fmt_time(start)}–{fmt_time(end)} · '
                        f'{fmt_length(end - start)}</span>{watch(info, start, "▶ watch")}'
                        f'<label class="js done-box" hidden><input type="checkbox" class="studied" '
                        f'value="{_key(s.get("title", ""), int(start))}"> Studied</label></div>'
                        f'{_ul((s.get("points") or [])[:4], cut)}' + _strip(i) +
                        (f'<details><summary>Read what was said in this part ({len(said.split()):,} words)</summary>'
                         f'<p class="said">{e(said)}</p></details>' if said else "") + "</div>")
        out.append('<section class="card" id="notes"><h2>Section notes</h2>'
                   '<p class="lead">The main points of each part.<span class="js" hidden> Tick a part when you have '
                   'studied it; your progress is saved in this browser.</span></p>' + "".join(body) + "</section>")

    # 5. key terms (with where each is first said), quiz, study path
    if terms or questions or path:
        out.append('<p class="group-h" id="practise">Practise <span>check what you learned</span></p>')
    if terms:
        first_said = meta.get("first_said")
        if first_said is None:
            first_said = {t["term"]: first_mention(t["term"], segs) for t in terms}
        items = []
        for t in terms:
            at = first_said.get(t["term"])
            extra = ""
            if at is not None:
                extra = (f'<span class="term-at">{watch(info, at, "first said at " + fmt_time(at))}'
                         f'<button type="button" class="js mini" hidden data-find="{e(t["term"])}">find in transcript'
                         '</button></span>')
            items.append(f"<dt>{e(t['term'])}</dt><dd>{e(sentence(t['meaning']))}{extra}</dd>")
        out.append('<section class="card" id="terms"><h2>Key terms</h2><dl class="terms">' + "".join(items) +
                   "</dl></section>")
    if questions:
        qitems = "".join(
            f'<details data-q="{_key(q["q"])}"><summary>{i}. {e(q["q"])}</summary>'
            f'<p>{e(q.get("a") or "No answer given.")}</p><div class="js rate" hidden>Did you get it right? '
            '<button type="button" class="mini" data-a="y" aria-pressed="false">Got it</button>'
            '<button type="button" class="mini" data-a="n" aria-pressed="false">Not yet</button></div></details>'
            for i, q in enumerate(questions, 1))
        out.append('<section class="card quiz" id="quiz"><h2>Check yourself</h2>'
                   '<p class="lead">Try to answer each question, then click it to see the answer.</p>'
                   '<div class="js quiz-tools" hidden><button type="button" class="mini" id="allq" '
                   'aria-pressed="false">Show all answers</button><span class="muted small" id="score" '
                   'aria-live="polite"></span></div>' + qitems + "</section>")
    if path:
        part = ""
        if notes.get("prerequisites"):
            part += "<h3>Good to know before watching</h3>" + _ul(notes["prerequisites"])
        if notes.get("further_study"):
            part += '<h3 style="margin-top:10px">What to study next</h3>' + _ul(notes["further_study"])
        out.append(f'<section class="card" id="path"><h2>Study path</h2>{part}</section>')

    # 6. common words: plain chips with counts (not a size-coded cloud)
    out.append('<p class="group-h" id="reference">Reference <span>the raw material</span></p>')
    if keywords:
        chips = "".join(f'<button type="button" class="chip" data-find="{e(k["term"])}" '
                        f'title="Find “{e(k["term"])}” in the transcript">{e(k["term"])}<b>×{k["count"]}</b></button>'
                        for k in keywords[:18])
        out.append('<section class="card" id="words"><h2>Words used most</h2>'
                   '<p class="lead">How often the speaker said each word: a quick hint of what the lecture is about.'
                   '<span class="js" hidden> Click a word to find it in the transcript.</span></p>'
                   f'<div class="chips">{chips}</div></section>')

    # 7. audio, with the outline's part starts marked on the speech chart
    marks = [(i + 1, _section_bounds(sections, i, base, end_all)[0]) for i in range(len(sections))]
    out.append(audio_card(info, meta, marks))

    # 8. transcript: the search box stays visible and opens the transcript when used
    paras = [f'<p>{watch(info, t)} <span class="tx">{e(txt)}</span></p>' for t, txt in paragraphs(segs)]
    origin = ("made from the audio by speech-to-text, so some words may be misheard" if src.startswith("audio")
              else "taken from the video's captions" if "caption" in src or "subtitle" in src
              else "taken from the transcript file")
    out.append('<section class="card" id="transcript"><h2>Full transcript</h2>'
               f'<p class="lead">Everything that was said, {e(origin)}.</p>'
               '<div class="js search" hidden><input id="q" type="search" placeholder="Search the transcript…" '
               'aria-label="Search the transcript"></div>'
               '<div class="muted small" id="qn" aria-live="polite"></div>'
               '<details id="trd"><summary>Show the transcript</summary><div class="tr">' + "".join(paras) +
               "</div></details></section>")

    out.append(f'<footer>Made on {e(meta.get("generated", ""))} for personal study. The video, its slides and its '
               'content belong to its creator.</footer></div></div>')   # closes .content and .layout
    if slides:
        out.append('<dialog id="lb" aria-label="Slide viewer"><div class="lb-img" role="img" aria-label="Slide"></div>'
                   '<div class="lb-bar"><button type="button" class="mini" id="lb-prev">← Previous</button>'
                   '<span id="lb-cap"></span><a class="ts" id="lb-watch" target="_blank" rel="noopener" href="#">'
                   '▶ watch</a><button type="button" class="mini" id="lb-next">Next →</button>'
                   '<button type="button" class="mini" id="lb-x">Close</button></div></dialog>')
        # each image is stored once, as a class, and reused by the gallery, the section strips and the viewer
        out.append("<style>" + "".join(f'.im-{s["n"]}{{background-image:url(data:image/jpeg;base64,{s["data"]})}}'
                                       for s in slides) + "</style>")
    out.append(f'<div id="tip" role="tooltip"></div></main><script>{JS}</script></body></html>')
    return "\n".join(out)
