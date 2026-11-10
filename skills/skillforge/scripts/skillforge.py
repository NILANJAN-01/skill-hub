#!/usr/bin/env python3
"""
skillforge.py - turn a technical PDF into a library of focused, AI-actionable Agent Skills,
using only open-source NLP (no LLM, no API key, runs fully offline).

    python skillforge.py progit.pdf                                   # auto: one skill per actionable section
    python skillforge.py progit.pdf --topics "rebase, hooks, merge conflicts, bisect, submodules"
    python skillforge.py progit.pdf --plan-only                       # inspect/edit plan.json first

Output (default --out generated-skills; review, then copy folders into the hub's skills/):
    generated-skills/README.md, catalog.json       catalog of every generated skill
    generated-skills/<name>/SKILL.md               the playbook (fixed section layout)
    generated-skills/<name>/references/source-text.md   cleaned source text the skill was built from

Pipeline
  1. PARSE    PyMuPDF reads fonts and layout, so it can tell headings (by size), prose,
              code blocks (monospace + indent), inline code, figure captions, page numbers and
              note/tip/warning callouts (icon + indented box) apart - exactly, not by guessing.
  2. INDEX    Every subsection becomes a "unit". scikit-learn TF-IDF (with light stemming,
              so rebase/rebasing/rebased match) indexes units for topic retrieval.
  3. PLAN     --topics: each topic retrieves its best units from the WHOLE book (e.g. "merge
              conflicts" pulls from Branching AND Advanced Merging). Without --topics: one skill
              per section that contains enough commands. Saved to <out>/.work/<pdf>/plan.json
              (editable; reused unless --replan).
  4. AUTHOR   Extractive, structured writing per skill:
                - procedures   = "lead sentence -> command(s) -> expected output" steps
                - safety rules = warning/caution callouts + risk sentences + destructive commands
                - troubleshooting = error lines in command output -> the sentence that fixes them
                - key concepts = TextRank (PageRank over TF-IDF sentence similarity)
                - keywords     = YAKE
              Every statement is copied from the source; nothing is invented.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

try:
    import numpy as np
    import pymupdf
    import yake
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError as exc:  # pragma: no cover
    sys.exit(f"Missing dependency ({exc.name}). Run: pip install -r requirements.txt")


# =========================================================================== patterns

MONO_FONT = re.compile(r"mono|courier|consol|menlo|inconsolata|code|mplus1mn|dejavusansm|"
                       r"liberationm|lucidaconsole|andale|fira ?mono|jetbrains", re.IGNORECASE)
ICON_FONT = re.compile(r"fontawesome|awesome|icons?\b|symbol|wingding|dingbat", re.IGNORECASE)
CALLOUT_GLYPHS = {0xF05A: "NOTE", 0xF129: "NOTE", 0xF0EB: "TIP", 0xF071: "WARNING",
                  0xF06A: "IMPORTANT", 0xF06D: "CAUTION", 0xF05E: "CAUTION"}
CAPTION = re.compile(r"^(?:figure|fig\.|table|listing|example)\s+\d+", re.IGNORECASE)
BULLET = re.compile(r"^\s*(?:[•◦▪‣\-*]|\d{1,2}[.)])\s+")
PROMPT = re.compile(r"^\s*(?:\$|#|>|C:\\[^>]*>|PS [^>]*>)\s+(?=\S)")
SHELL_PROMPT = re.compile(r"^\s*(?:\$|C:\\[^>]*>|PS [^>]*>)\s+\S")
SKIP_TITLE = re.compile(r"^(?:preface|foreword|contributors?|acknowledg|dedication|about the author|"
                        r"copyright|license|table of contents|contents|index|bibliography|colophon)",
                        re.IGNORECASE)
MAX_INLINE_PROCEDURES = 5
JUNK_SECTION = re.compile(r"^(?:summary|conclusion|introduction|overview|wrapping up)$", re.IGNORECASE)
META = re.compile(r"\b(this (?:book|chapter|section|edition|appendix)|the (?:book|next chapter|previous "
                  r"chapter)|in (?:this|the next|the following|the previous) (?:chapter|section)|"
                  r"by the end of|we(?:'|’)ll (?:see|cover|look|go|discuss|explore|talk)|we covered|"
                  r"you(?:'|’)ll learn|as (?:we|you) (?:saw|discussed|mentioned)|see \w[\w ]* for more|"
                  r"screenshot|figure \d|as shown in)\b", re.IGNORECASE)

RISK = re.compile(r"\b(lose|lost|losing|destroy\w*|destructive|permanent\w*|overwrit\w*|irreversib\w*|"
                  r"cannot be undone|can(?:no|’|')t (?:be )?(?:undo|undone|recover)|dangerous|careful|"
                  r"caution|beware|never|force[ds]?|rewrit\w* (?:\w+ )?history|"
                  r"discard\w*|wipe\w*|irrecoverabl\w*|unsafe)\b|^(?:do not|don(?:’|')t|avoid)\b", re.IGNORECASE)
NOT_USE = re.compile(r"^(?:do not|don(?:’|')t|never|avoid)\b|\b(?:never|avoid|should(?: not|n(?:’|')t)|"
                     r"(?:you|we) (?:do not|don(?:’|')t) (?:want|need) to)\b", re.IGNORECASE)
NARRATIVE = re.compile(r"^(?:so|next|then|now|finally|first|second|for instance|for example|let(?:’|')s|"
                       r"suppose|here|at this point|after that|this time|again|also|meanwhile|remember)\b|"
                       r"\b(you(?:’|')ll see|looks? like this|the following|as follows|in the previous|"
                       r"earlier example|go back to)\b", re.IGNORECASE)
ADVICE = re.compile(r"\b(should|recommend\w*|better|prefer\w*|instead|safe(?:ly)?|fine|avoid|never|"
                    r"always|best|make sure|be sure|good idea|bad idea|careful)\b", re.IGNORECASE)
WHEN_USE = re.compile(r"\b(if you want to|when you want to|if you need to|you can use|is useful|"
                      r"use (?:it|this) (?:to|when)|lets you|allows you to|helps you|is handy|"
                      r"comes in handy|the (?:easiest|simplest|best) way to)\b", re.IGNORECASE)
DECISION = re.compile(r"^(?:if|when|whenever|unless|in (?:that|this) case)\b[^.]{8,},|"
                      r"\b(instead of|rather than|is (?:generally )?(?:better|preferable)|prefer\w*|"
                      r"in general,|as a rule)\b", re.IGNORECASE)
CONCEPT = re.compile(r"\b(is an?|is the|are the|means|refers to|works by|under the hood|is called|"
                     r"essentially|basically|in other words)\b", re.IGNORECASE)
FIX = re.compile(r"\b(to fix|to resolve|to undo|to recover|to get (?:back|out)|to abort|abort|"
                 r"resolve[ds]?|undo|recover\w*|fix\w*|revert\w*|start over)\b", re.IGNORECASE)
ERROR_LINE = re.compile(r"^\s*(?:error|fatal|warning|hint|(?-i:CONFLICT)|Automatic merge failed|"
                        r"! \[rejected\]|![^\n]*rejected|Cannot|Could not|Unable to|failed to|"
                        r"Your branch and .* have diverged|You are in 'detached HEAD')", re.IGNORECASE)
DESTRUCTIVE = re.compile(r"(--force\b|\bpush\b.*\s-f\b|\bpush\b.*\s\+\S|reset\s+--hard|\bclean\s+-\w*f|"
                         r"checkout\s+(?:\S+\s+)?--\s|\brestore\b(?!.*--staged)|branch\s+-D\b|\brebase\b|"
                         r"filter-branch|filter-repo|commit\s+--amend|reflog\s+expire|gc\s+--prune|"
                         r"stash\s+(?:drop|clear)|\brm\s+-\w*r|update-ref\s+-d|push\s+\S+\s+:\S|"
                         r"push\s+.*--delete|\bprune\b)")
READ_ONLY = re.compile(r"^(?:\S+\s+)?(?:status|log|diff|show|branch(?:\s+-[avr]+)?$|"
                       r"remote(?:\s+-v)?$|ls-files|ls-tree|cat-file|rev-parse|describe|blame|"
                       r"reflog$|stash list|shortlog|tag$|config --list|ls|cat)\b")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,}")
STOP = set("""a about above after again all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each either else even ever few for
from further get gets got had has have having he her here him his how however i if in into is it its
itself just let like make makes many may me might more most much must my need no nor not now of off on
once one only or other our out over own per put rather really said same see seen she should since so
some such than that the their them then there these they thing things this those though through thus to
too two under until up upon us use used uses using very via want was way we well were what when where
whether which while who whom whose why will with within without would yet you your yours ll ve re""".split())


def stem(word: str) -> str:
    """Tiny suffix stemmer so rebase/rebasing/rebased/rebases all match."""
    w = word.lower()
    for suf in ("ations", "ation", "ings", "ing", "ions", "ion", "ers", "er", "ed", "es", "s", "e"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def analyzer(text: str) -> list[str]:
    out = []
    for w in WORD.findall(text):
        lw = w.lower()
        if lw in STOP:
            continue
        out.append(stem(lw))
        if "-" in lw:
            out += [stem(p) for p in lw.split("-") if len(p) > 2 and p not in STOP]
    return out


def slugify(value: str, fallback: str = "skill") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:64].strip("-") or fallback


def strip_prompt(cmd: str) -> str:
    return PROMPT.sub("", cmd).strip()


def command_key(cmd: str) -> str:
    """'$ git rebase --onto master server client' -> 'git rebase --onto'."""
    parts = [p for p in strip_prompt(cmd).split() if p != "sudo"]
    if not parts:
        return ""
    key, rest = [parts[0]], parts[1:]
    if rest and re.fullmatch(r"[a-z][a-z0-9\-]+", rest[0]):
        key.append(rest.pop(0))
    key += [p.split("=")[0] for p in rest if re.fullmatch(r"--?[A-Za-z][\w\-]*(=\S*)?", p)][:2]
    return " ".join(key)


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z`\"“(])", text)
    return [p.strip() for p in parts if p.strip()]


def good_sentence(s: str) -> bool:
    return (35 <= len(s) <= 360 and s.count(" ") >= 5 and not s[0].islower()
            and not META.search(s) and not CAPTION.match(s))


def md_cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def md_inline(s: str) -> str:
    return s.replace("`", "'").split("\n")[0]


def dedupe(items: list[str], limit: int = 999) -> list[str]:
    seen, out = set(), []
    for it in items:
        key = re.sub(r"\W+", "", it.lower())[:100]
        if key and key not in seen:
            seen.add(key)
            out.append(it)
            if len(out) >= limit:
                break
    return out


# =========================================================================== 1. parse

@dataclass
class Block:
    kind: str                  # h | p | li | code | callout
    text: str = ""
    lines: list[str] = field(default_factory=list)   # code lines
    label: str = ""            # callout kind
    page: int = 0              # 1-based


@dataclass
class Unit:
    uid: int
    path: list[str]            # heading path, e.g. [chapter, section, subsection]
    page_start: int
    page_end: int
    blocks: list[Block] = field(default_factory=list)

    @property
    def heading(self) -> str:
        return self.path[-1] if self.path else ""

    @property
    def chapter(self) -> str:
        return self.path[0] if self.path else ""

    def prose(self) -> str:
        return " ".join(b.text for b in self.blocks if b.kind in ("p", "li", "callout"))

    def commands(self) -> list[str]:
        return [l for b in self.blocks if b.kind == "code" for l in b.lines if SHELL_PROMPT.match(l)]

    def index_text(self) -> str:
        path = " ".join(self.path[1:] or self.path)
        cmds = " ".join(strip_prompt(c) for c in self.commands())
        return f"{path} {path} {path} {self.prose()} {cmds}"


def inline(spans: list[dict]) -> str:
    """Prose line with inline code spans wrapped in backticks."""
    out: list[str] = []
    for s in spans:
        t = s["text"]
        if MONO_FONT.search(s["font"]) and t.strip():
            lead, core, trail = re.match(r"^(\s*)(.*?)(\s*)$", t, re.S).groups()
            if out and out[-1].endswith("`") and not lead:
                out[-1] = out[-1][:-1] + core + "`" + trail          # merge adjacent code spans
            else:
                out.append(f"{lead}`{core}`{trail}")
        else:
            out.append(t)
    return "".join(out).strip()


def join_text(a: str, b: str) -> str:
    if not a:
        return b
    if a.endswith("-") and b[:1].isalpha():
        return a + b
    if a.endswith("`") and b.startswith("`"):
        return a[:-1] + b[1:]
    return f"{a} {b}"


class Document:
    def __init__(self, path: Path):
        self.path = path
        self.pdf = pymupdf.open(str(path))
        if self.pdf.needs_pass and not self.pdf.authenticate(""):
            sys.exit("The PDF is password-protected.")
        self.title = (self.pdf.metadata or {}).get("title") or path.stem
        self.toc = [(lvl, t.strip(), p) for lvl, t, p in self.pdf.get_toc()]
        print(f"[parse] '{self.title}': {len(self.pdf)} pages")
        self._stats()
        self.units = self._parse()
        if sum(len(u.prose()) for u in self.units) < 500:
            sys.exit("Almost no text could be extracted - the PDF is probably scanned. Run OCR first "
                     "(e.g. `ocrmypdf in.pdf out.pdf`).")
        print(f"[parse] {len(self.units)} units, "
              f"{sum(len(u.commands()) for u in self.units)} commands, "
              f"{sum(1 for u in self.units for b in u.blocks if b.kind == 'callout')} callouts")

    def _stats(self) -> None:
        """Body font size and left margin = the most common values in the document."""
        sizes, xs = Counter(), Counter()
        self.page_dicts = [page.get_text("dict", sort=True) for page in self.pdf]   # read each page once
        for d in self.page_dicts:
            for b in d["blocks"]:
                for l in b.get("lines", []):
                    for s in l["spans"]:
                        if s["text"].strip() and not MONO_FONT.search(s["font"]):
                            sizes[round(s["size"], 1)] += len(s["text"])
                    if l["spans"] and not MONO_FONT.search(l["spans"][0]["font"]):
                        xs[round(l["bbox"][0])] += 1
        self.body = sizes.most_common(1)[0][0] if sizes else 10.0
        self.left = xs.most_common(1)[0][0] if xs else 50

    @staticmethod
    def _is_bold(s: dict) -> bool:
        return bool(s["flags"] & 16) or "bold" in s["font"].lower()

    @staticmethod
    def _callout_lines(lines: list[tuple]) -> dict[int, str]:
        """Map line index -> callout kind, using icon glyphs and the indented box beside them."""
        found: dict[int, str] = {}
        for i, (bbox, spans) in enumerate(lines):
            sp = spans[0]
            if not (ICON_FONT.search(sp["font"]) and sp["text"].strip()):
                continue
            kind = CALLOUT_GLYPHS.get(ord(sp["text"].strip()[0]), "NOTE")
            ix1, iy_mid = bbox[2], (bbox[1] + bbox[3]) / 2
            cand = sorted(((j, b) for j, (b, s) in enumerate(lines)
                           if j != i and b[0] > ix1 + 5 and not ICON_FONT.search(s[0]["font"])),
                          key=lambda t: t[1][1])
            seed = [j for j, b in cand if b[1] - 25 <= iy_mid <= b[3] + 25]
            if not seed:
                continue
            x0 = lines[seed[0]][0][0]
            col = [(j, b) for j, b in cand if abs(b[0] - x0) < 4]
            pos = next(k for k, (j, _) in enumerate(col) if j == seed[0])
            keep = {col[pos][0]}
            for step in (-1, 1):                     # grow the box while lines stay close together
                k = pos
                while 0 <= k + step < len(col):
                    a, b = col[k][1], col[k + step][1]
                    gap = (b[1] - a[3]) if step == 1 else (a[1] - b[3])
                    if gap > 8:
                        break
                    k += step
                    keep.add(col[k][0])
            for j in keep:
                found[j] = kind
        return found

    def _parse(self) -> list[Unit]:
        stack: list[tuple[float, str]] = []          # (font size, heading text)
        units: list[Unit] = []
        cur: Unit | None = None

        def new_unit(page: int) -> Unit:
            u = Unit(len(units), [t for _, t in stack], page, page)
            units.append(u)
            return u

        for pno, page in enumerate(self.pdf, 1):
            height = page.rect.height
            lines = []
            for b_i, b in enumerate(self.page_dicts[pno - 1]["blocks"]):
                for l in b.get("lines", []):
                    spans = [s for s in l["spans"] if s["text"].strip()]
                    if spans:
                        lines.append((l["bbox"], spans, b_i))
            callouts = self._callout_lines([(bb, sp) for bb, sp, _ in lines])
            prev = None                                # (kind, block index) of the previous line
            for i, (bbox, spans, b_i) in enumerate(lines):
                first = spans[0]
                raw = "".join(s["text"] for s in spans).strip()
                size = round(max(s["size"] for s in spans), 1)
                if ICON_FONT.search(first["font"]):
                    continue
                if size < self.body - 0.6 and (raw.isdigit() or bbox[1] < height * 0.07
                                               or bbox[3] > height * 0.93):
                    continue                                       # page number / running header
                if CAPTION.match(raw) and "italic" in first["font"].lower():
                    continue
                if cur is None:
                    cur = new_unit(pno)
                cur.page_end = pno
                last = cur.blocks[-1] if cur.blocks else None

                if i in callouts:                                  # note / tip / warning box
                    text = inline(spans)
                    if last and last.kind == "callout" and last.page == pno and prev and prev[0] == "c":
                        last.text = join_text(last.text, text)
                    else:
                        cur.blocks.append(Block("callout", text, label=callouts[i], page=pno))
                    prev = ("c", b_i)
                    continue

                all_mono = all(MONO_FONT.search(s["font"]) for s in spans)
                if all_mono and (bbox[0] > self.left + 4 or abs(size - self.body) > 0.3):
                    text = "".join(s["text"] for s in spans).rstrip()
                    if last and last.kind == "code" and prev and prev[0] == "code":
                        last.lines.append(text)
                    else:
                        cur.blocks.append(Block("code", lines=[text], page=pno))
                    prev = ("code", b_i)
                    continue

                all_bold = all(self._is_bold(s) for s in spans) and not all_mono
                if all_bold and size > self.body + 0.5 and len(raw) < 120:   # real heading
                    while stack and stack[-1][0] <= size:
                        stack.pop()
                    stack.append((size, raw))
                    cur = new_unit(pno)
                    prev = ("h", b_i)
                    continue
                if all_bold and len(raw) < 70 and not raw.endswith((".", ":", ",")):  # run-in heading
                    cur.blocks.append(Block("h", raw, page=pno))
                    prev = ("minor", b_i)
                    continue

                text = inline(spans)
                if BULLET.match(text):
                    cur.blocks.append(Block("li", BULLET.sub("", text), page=pno))
                elif last and last.kind in ("p", "li") and prev == ("p", b_i):
                    last.text = join_text(last.text, text)
                elif (last and last.kind == "p" and last.text and last.text[-1] not in ".:!?”\""
                      and (text[:1].islower() or text[:1] in "`(<\"“—-")):
                    last.text = join_text(last.text, text)         # paragraph split by page/figure
                else:
                    cur.blocks.append(Block("p", text, page=pno))
                prev = ("p", b_i)

        title = (self.title or "").strip().lower()
        kept = [u for u in units if u.blocks and u.path and not SKIP_TITLE.match(u.chapter)
                and u.chapter.strip().lower() != title]
        for n, u in enumerate(kept):          # uid == list position (plan.json stores these ids)
            u.uid = n
        return kept


# =========================================================================== 2. index

class Index:
    def __init__(self, units: list[Unit]):
        self.units = units
        self.vec = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True, max_df=0.6)
        self.X = self.vec.fit_transform([u.index_text() for u in units])
        self.path_stems = [set(analyzer(" ".join(u.path[1:] or u.path))) for u in units]
        self.cmd_stems = [set(analyzer(" ".join(strip_prompt(c) for c in u.commands()))) for u in units]

    def search(self, query: str) -> list[tuple[float, int]]:
        q_stems = set(analyzer(query))
        if not q_stems:
            return []
        sims = (self.X @ self.vec.transform([query]).T).toarray().ravel()
        scored = []
        for i in range(len(self.units)):
            s = float(sims[i])
            s += 0.35 * len(q_stems & self.path_stems[i]) / len(q_stems)
            s += 0.15 * len(q_stems & self.cmd_stems[i]) / len(q_stems)
            scored.append((s, i))
        return sorted(scored, reverse=True)


# =========================================================================== 3. plan

def domain_word(doc: Document, prefix: str | None) -> str:
    if prefix:
        return slugify(prefix)
    words = Counter(w.lower() for _, t, _ in doc.toc for w in WORD.findall(t) if w.lower() not in STOP)
    return slugify(words.most_common(1)[0][0]) if words else "doc"


def skill_name(domain: str, title: str) -> str:
    slug = slugify(title)
    return slug if slug == domain or slug.startswith(domain + "-") else f"{domain}-{slug}"[:64].strip("-")


def plan_topics(doc: Document, index: Index, topics: list[str], domain: str) -> list[dict]:
    skills = []
    for topic in topics:
        ranked = [(s, i) for s, i in index.search(topic) if doc.units[i].prose() or doc.units[i].commands()]
        if not ranked or ranked[0][0] < 0.1:
            print(f"[plan] '{topic}': nothing relevant found - skipped")
            continue
        top = ranked[0][0]
        chosen = [i for s, i in ranked if s >= max(0.45 * top, 0.12)][:25]
        q = set(analyzer(topic))                 # a section whose title covers the topic: take it whole
        for u in doc.units:
            if len(u.path) >= 2 and q <= set(analyzer(u.path[1])) and u.uid not in chosen:
                chosen.append(u.uid)
        skills.append({"name": skill_name(domain, topic), "title": topic.strip().title(),
                       "query": topic, "units": sorted(set(chosen))})
    return skills


def plan_auto(doc: Document, index: Index, domain: str, min_commands: int, max_skills: int) -> list[dict]:
    groups: dict[tuple, list[int]] = defaultdict(list)
    for u in doc.units:
        groups[tuple(u.path[:2])].append(u.uid)
    cands = []
    for key, uids in groups.items():
        # actionability = shell commands + script/config listings + inline code mentions / 4
        # (descriptive reference sections such as "Git Hooks" are mostly inline `names`)
        n_cmd = sum(len(doc.units[i].commands())
                    + sum(1 for b in doc.units[i].blocks if b.kind == "code"
                          and not any(SHELL_PROMPT.match(l) for l in b.lines))
                    + doc.units[i].prose().count("`") // 8
                    for i in uids)
        if not JUNK_SECTION.match(key[-1].strip()) and n_cmd >= min_commands:
            cands.append((n_cmd, key, uids))
    cands.sort(key=lambda c: -c[0])
    cands = sorted(cands[:max_skills], key=lambda c: c[2][0])        # back to document order
    titles = Counter(k[-1].lower() for _, k, _ in cands)
    skills, used = [], set()
    for _, key, uids in cands:
        title = key[-1]
        name = skill_name(domain, title if titles[title.lower()] == 1 else f"{key[0]} {title}")
        while name in used:
            name += "-2"
        used.add(name)
        skills.append({"name": name, "title": title, "query": title, "units": sorted(uids)})
    return skills


# =========================================================================== 4. author

def textrank(sentences: list[str], n: int, focus: set[str] | None = None) -> list[str]:
    """Top-n central sentences (original order). Sentences mentioning the focus stems and
    phrased as definitions are boosted, so the summary stays on topic."""
    if len(sentences) <= n:
        return sentences
    try:
        X = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True).fit_transform(sentences)
    except ValueError:
        return sentences[:n]
    sim = (X @ X.T).toarray()
    np.fill_diagonal(sim, 0.0)
    ranks = pagerank(sim)
    if focus:
        for i, s in enumerate(sentences):
            ranks[i] *= (1.0 + 0.8 * bool(focus & set(analyzer(s)))) * (1.0 + 0.4 * bool(CONCEPT.search(s)))
    best = sorted(range(len(sentences)), key=lambda i: -ranks[i])[:n]
    return [sentences[i] for i in sorted(best)]


def pagerank(weights: np.ndarray, d: float = 0.85, iters: int = 100) -> np.ndarray:
    """Weighted PageRank by power iteration (same result as networkx.pagerank, much faster)."""
    n = len(weights)
    out = weights.sum(axis=1, keepdims=True)
    trans = np.divide(weights, out, out=np.full_like(weights, 1.0 / n), where=out > 0)
    r = np.full(n, 1.0 / n)
    for _ in range(iters):
        nxt = (1 - d) / n + d * (r @ trans)
        if np.abs(nxt - r).sum() < 1e-8:
            break
        r = nxt
    return r


def keyphrases(text: str, domain: str, n: int = 8) -> list[str]:
    try:
        kws = yake.KeywordExtractor(lan="en", n=3, top=n * 3, dedupLim=0.7).extract_keywords(text[:60000])
    except Exception:
        return []
    out: list[str] = []
    for kw, _ in kws:
        k = kw.strip().lower()
        if k == domain or len(k) < 4 or any(k in o or o in k for o in out):
            continue
        if " " not in k and sum(" " in o for o in out) < 3 and len(out) < n // 2:
            continue                                  # prefer multi-word phrases over generic words
        out.append(k)
        if len(out) >= n:
            break
    return out


def code_lang(lines: list[str]) -> str:
    joined = "\n".join(lines)
    if any(SHELL_PROMPT.match(l) for l in lines) or re.search(r"^#!/bin/(ba)?sh", joined, re.M):
        return "bash"
    if re.search(r"^#!.*ruby|^\s*puts\b|^\s*end\s*$", joined, re.M):
        return "ruby"
    if re.search(r"^#!.*python|^\s*def \w+\(.*\):", joined, re.M):
        return "python"
    if re.search(r"^\s*\[[\w \".-]+\]\s*$", joined, re.M):
        return "ini"
    return "text"


def split_commands(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Code block -> [(command, output_lines)]; a non-shell block returns [("", lines)]."""
    if not any(SHELL_PROMPT.match(l) for l in lines):
        return [("", lines)]
    out: list[tuple[str, list[str]]] = []
    for l in lines:
        if SHELL_PROMPT.match(l):
            out.append((strip_prompt(l), []))
        elif out:
            if out[-1][0].endswith("\\") and not out[-1][1]:
                out[-1] = (out[-1][0] + "\n" + l.strip(), [])          # continued command line
            else:
                out[-1][1].append(l)
    return out


def page_ranges(units: list[Unit]) -> str:
    merged: list[list[int]] = []
    for a, b in sorted((u.page_start, u.page_end) for u in units):
        if merged and a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in merged)


class Author:
    def __init__(self, doc: Document, plan: dict, index: Index):
        self.doc, self.plan, self.domain = doc, plan, plan["domain"]
        # related skills = cosine similarity between the skills' summed unit vectors
        vecs = []
        for sk in plan["skills"]:
            rows = [i for i in sk["units"] if i < len(doc.units)]
            v = np.asarray(index.X[rows].sum(axis=0)).ravel() if rows else np.zeros(index.X.shape[1])
            vecs.append(v / (np.linalg.norm(v) or 1.0))
        sim = np.array(vecs) @ np.array(vecs).T if vecs else np.zeros((0, 0))
        self.related = {sk["name"]: [plan["skills"][b] for b in np.argsort(-sim[a])
                                     if b != a and sim[a][b] > 0.12][:4]
                        for a, sk in enumerate(plan["skills"])}

    def write(self, sk: dict, out: Path) -> list[str]:
        units = [self.doc.units[i] for i in sk["units"] if i < len(self.doc.units)]
        sentences = dedupe([s for u in units for b in u.blocks if b.kind in ("p", "li")
                            for s in split_sentences(b.text) if good_sentence(s)])
        callouts = [b for u in units for b in u.blocks if b.kind == "callout"]
        all_cmds = [strip_prompt(c) for u in units for c in u.commands()]
        pages, title = page_ranges(units), sk["title"]

        focus = set(analyzer(f"{sk.get('query', '')} {title}")) - set(analyzer(self.domain))
        on_topic = lambda s: bool(focus & set(analyzer(s))) if focus else True
        statements = [s for s in sentences if not s.endswith(":") and not NARRATIVE.search(s)]

        concepts = textrank(statements, 8, focus)
        overview = next((s for s in concepts if CONCEPT.search(s) and on_topic(s) and len(s) <= 220
                         and not s.startswith("If")),
                        next((s for s in concepts if on_topic(s)), concepts[0] if concepts else ""))
        when_not_all = [s for s in statements if NOT_USE.search(s) and on_topic(s)]
        concepts = [s for s in concepts if s != overview and s not in when_not_all]
        when_use = dedupe([s for s in statements if WHEN_USE.search(s) and on_topic(s)], 5)
        when_not = dedupe([s for s in statements if NOT_USE.search(s) and on_topic(s)], 5)
        decisions = dedupe([s for s in statements if DECISION.search(s) and ADVICE.search(s)
                            and s not in when_not], 8)
        risks = [s for s in dedupe([s for s in statements if RISK.search(s)], 12)
                 if s not in when_not and s not in decisions][:6]
        destructive = dedupe([c.split("\n")[0] for c in all_cmds if DESTRUCTIVE.search(c)], 12)
        errors = self.troubleshooting(units)
        cmd_ref = self.command_reference(units, sentences)
        full = [(u, p) for u in units if (p := self.procedure(u, on_topic))]
        procedures = [p for _, p in full]
        kws = keyphrases(" ".join(sentences), self.domain)
        related = self.related.get(sk["name"], [])
        key_counts = Counter(command_key(c) for c in all_cmds if command_key(c))
        top_keys = sorted(key_counts, key=lambda k: (not on_topic(k), -key_counts[k]))[:6]
        description = self.description(title, overview, kws, top_keys, errors)

        L: list[str] = [f"# {title}", "", overview or f"Playbook for {title.lower()}.", "",
                        f"_Built from \"{self.doc.title}\" (pages {pages}) by extraction: statements below "
                        f"are quoted from the source. Full cleaned source: "
                        f"[references/source-text.md](references/source-text.md) - read it when a step "
                        f"needs more context._", ""]

        L += ["## When to use", "",
              f"- The user asks about **{title.lower()}**" + (f" ({', '.join(kws[:5])})." if kws else ".")]
        L += [f"- The user wants to run or understand `{k}`." for k in top_keys[:4]]
        L += [f"- The user sees an error like `{md_inline(e)}`." for e, _ in errors[:3]]
        L += [f"- {s}" for s in when_use] + [""]

        if when_not or related:
            L += ["## When NOT to use", "", *[f"- {s}" for s in when_not]]
            L += [f"- For {r['title'].lower()}, use the `{r['name']}` skill instead." for r in related[:3]]
            L += [""]

        if concepts:
            L += ["## Key concepts", "", *[f"- {s}" for s in concepts], ""]

        L += ["## Safety rules for the agent", "",
              "- Inspect the current state before changing anything" +
              (" (`git status`, current branch, uncommitted work, whether commits were already pushed)"
               if self.domain == "git" else "") + " and tell the user what you are about to do."]
        if destructive:
            L += ["- These commands can rewrite history or discard work. Ask the user to confirm first and "
                  "create a safety net (backup branch, stash or copy) before running them:"]
            L += [f"  - `{md_inline(c)}`" for c in destructive]
        L += [f"- **{c.label.title()} (from source):** {c.text}" for c in callouts
              if c.label in ("WARNING", "CAUTION", "IMPORTANT") or RISK.search(c.text)]
        L += [f"- {s}" for s in risks] + [""]

        extra_procs: list[list[str]] = []
        if procedures:
            # keep the most on-topic procedures inline, move the rest to references/procedures.md
            ranked = sorted(range(len(procedures)), key=lambda i: -(
                3 * on_topic(procedures[i][0]) + sum(on_topic(l) for l in procedures[i] if l.startswith("   git"))))
            inline_ids = set(ranked[:MAX_INLINE_PROCEDURES])
            L += ["## Procedures", ""]
            for i, p in enumerate(procedures):
                if i in inline_ids:
                    short = self.procedure(full[i][0], on_topic, compact=True)
                    L += short + [""]
                    if short != p:
                        extra_procs.append(p)                # full version goes to references
                else:
                    extra_procs.append(p)
            if extra_procs:
                L += ["More procedures in [references/procedures.md](references/procedures.md):", ""]
                L += [f"- {p[0][4:]}" for p in extra_procs] + [""]

        if cmd_ref:
            L += ["## Command reference", "", "| Command | What it does (from source) | Example |", "|---|---|---|"]
            L += [f"| `{md_cell(k)}` | {md_cell(e) or '-'} | `{md_cell(x)}` |" for k, e, x in cmd_ref] + [""]

        if decisions:
            L += ["## Decision guide", "", *[f"- {s}" for s in decisions], ""]

        tips = [c for c in callouts if c.label in ("NOTE", "TIP") and not RISK.search(c.text)]
        if errors or tips:
            L += ["## Troubleshooting", ""]
            if errors:
                L += ["| Symptom / message | What the source says next |", "|---|---|"]
                L += [f"| `{md_cell(e)}` | {md_cell(f)} |" for e, f in errors] + [""]
            L += [f"- **{c.label.title()}:** {c.text}" for c in tips[:8]] + [""]

        example = [] if procedures else self.example(units)      # transcripts live in source-text.md
        if example:
            L += ["## Examples", "", *example]

        L += ["## Related skills", ""]
        L += [f"- `{r['name']}` - {r['title']}" for r in related] or ["- (none in this library)"]
        L += ["", "## Source", "", f"\"{self.doc.title}\", pages {pages}. Sections: "
              + "; ".join(dedupe([" > ".join(u.path[1:] or u.path) for u in units], 30)) + "."]

        skill_dir = out / sk["name"]
        (skill_dir / "references").mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {sk['name']}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n"
            + "\n".join(L).rstrip() + "\n", encoding="utf-8")
        (skill_dir / "references" / "source-text.md").write_text(self.source_text(units, title), encoding="utf-8")
        procs_md = skill_dir / "references" / "procedures.md"
        if extra_procs:
            body = "\n".join(l for p in extra_procs for l in p + [""]).rstrip()
            procs_md.write_text(f"# More procedures: {title}\n\n{body}\n", encoding="utf-8")
        elif procs_md.exists():
            procs_md.unlink()
        return validate(skill_dir / "SKILL.md")

    def description(self, title, overview, kws, keys, errors) -> str:
        parts = [f"{title} playbook extracted from \"{self.doc.title}\"."]
        if overview:
            parts.append(overview if len(overview) < 260 else overview[:257].rsplit(" ", 1)[0] + "...")
        use = f"Use when the user asks about {title.lower()}"
        if kws:
            use += f", {', '.join(kws[:6])}"
        if keys:
            use += f"; or mentions {', '.join(keys[:6])}"
        if errors:
            use += f"; or hits errors like \"{errors[0][0][:80]}\""
        parts.append(use + ".")
        return " ".join(" ".join(parts).replace("`", "").split())[:1024]

    def procedure(self, u: Unit, on_topic=lambda s: True, compact: bool = False) -> list[str] | None:
        max_steps, max_listing = (6, 15) if compact else (12, 40)
        steps, lead, mutated = [], "", False
        verify, fail = None, None
        for b in u.blocks:
            if b.kind in ("p", "li"):
                sents = [s for s in split_sentences(b.text) if not META.search(s)]
                lead = sents[-1] if sents else lead
                if fail is None:
                    fail = next((s for s in sents if FIX.search(s) and good_sentence(s)), None)
                continue
            if b.kind != "code":
                continue
            pairs = split_commands(b.lines)
            if not pairs[0][0]:                                     # script / config listing
                if len(b.lines) <= 40:
                    steps.append((lead, None, b.lines, code_lang(b.lines)))
                lead = ""
                continue
            cmds = [c for c, _ in pairs]
            output = [l for _, o in pairs for l in o]
            if mutated and all(READ_ONLY.match(c) for c in cmds):
                verify = (cmds[0], output[:6])
            elif not all(READ_ONLY.match(c) for c in cmds):
                mutated = True
            steps.append((lead, cmds, output[:4], "bash"))
            lead = ""
        if not steps:
            return None
        unit_sents = [s for b in u.blocks if b.kind == "p" for s in split_sentences(b.text)
                      if good_sentence(s) and not NARRATIVE.search(s) and not s.endswith(":")]
        topical = [s for s in unit_sents if on_topic(s)]
        goal = next((s for s in topical if WHEN_USE.search(s) or CONCEPT.search(s)),
                    topical[0] if topical else None)
        L = [f"### {u.heading}", "", f"**Goal:** {goal or u.heading}", "", "**Steps:**", ""]
        for n, (lead, cmds, extra, lang) in enumerate(steps[:max_steps], 1):
            L.append(f"{n}. {lead or 'Run:'}")
            if cmds is None:
                L += [f"   ```{lang}", *[f"   {l}" for l in extra[:max_listing]],
                      *(["   # ... (full listing in references)"] if len(extra) > max_listing else []), "   ```"]
                continue
            L += ["   ```bash", *[f"   {line}" for c in cmds for line in c.split("\n")], "   ```"]
            if extra:
                L += ["   Expected output (excerpt):", "   ```text", *[f"   {l}" for l in extra], "   ```"]
        if len(steps) > max_steps:
            where = "references/procedures.md" if compact else "references/source-text.md"
            L.append(f"\n_{len(steps) - max_steps} more step(s) in {where}._")
        if verify:
            L += ["", f"**Verify:** run `{verify[0]}`" + (" - expect something like:" if verify[1] else "")]
            if verify[1]:
                L += ["```text", *verify[1], "```"]
        if fail:
            L += ["", f"**If it fails:** {fail}"]
        return L

    def command_reference(self, units: list[Unit], sentences: list[str]) -> list[tuple[str, str, str]]:
        examples: dict[str, list[str]] = defaultdict(list)
        leads: dict[str, str] = {}
        for u in units:
            lead = ""
            for b in u.blocks:
                if b.kind in ("p", "li"):
                    s = split_sentences(b.text)
                    lead = s[-1] if s else lead
                elif b.kind == "code":
                    for c, _ in split_commands(b.lines):
                        if c:
                            k = command_key(c)
                            examples[k].append(c.split("\n")[0])
                            leads.setdefault(k, lead)
        generic = {"cd", "ls", "cat", "echo", "vim", "vi", "mkdir", "touch", "rm", "mv", "cp", "nano",
                   "emacs", "find", "tree", "head", "tail", "less", "wc"}
        rows = []
        for k, ex in sorted(examples.items(), key=lambda kv: -len(kv[1])):
            if not k or k.split()[0] in generic:
                continue
            needle = k.lower()
            expl = min((s for s in sentences if needle in s.lower().replace("`", "")),
                       key=lambda s: (not (WHEN_USE.search(s) or CONCEPT.search(s)), len(s)), default="")
            rows.append((k, (expl or leads.get(k, "")).rstrip(":"), min(ex, key=len)))
            if len(rows) >= 20:
                break
        return rows

    def troubleshooting(self, units: list[Unit]) -> list[tuple[str, str]]:
        rows, seen = [], set()
        for u in units:
            for k, b in enumerate(u.blocks):
                if b.kind != "code":
                    continue
                errs = [l.strip() for _, o in split_commands(b.lines) for l in o if ERROR_LINE.match(l)]
                if not errs:
                    continue
                key = re.sub(r"[0-9a-f]{7,}|\W+", "", errs[0].lower())[:60]
                if key in seen:
                    continue
                seen.add(key)
                after = next((x for x in u.blocks[k + 1:] if x.kind in ("p", "li")), None)
                sents = split_sentences(after.text) if after else []
                fix = next((s for s in sents if FIX.search(s)), sents[0] if sents else "")
                rows.append((errs[0][:120], fix or "See references/source-text.md for this section."))
        return rows[:10]

    def example(self, units: list[Unit]) -> list[str]:
        best = max(units, key=lambda u: len(u.commands()), default=None)
        if not best or len(best.commands()) < 3:
            return []
        L = [f"**Scenario: {best.heading}** (pages {best.page_start}-{best.page_end})", ""]
        shown = 0
        for b in best.blocks:
            if shown >= 4:
                break
            if b.kind == "p":
                s = [x for x in split_sentences(b.text) if not META.search(x)]
                if s:
                    L += [" ".join(s[:2]), ""]
            elif b.kind == "code":
                L += ["```console", *b.lines[:25], *(["..."] if len(b.lines) > 25 else []), "```", ""]
                shown += 1
        return L

    def source_text(self, units: list[Unit], title: str) -> str:
        L = [f"# Source text: {title}", "", f"_Cleaned extract from \"{self.doc.title}\"._", ""]
        for u in units:
            L += [f"## {' > '.join(u.path[1:] or u.path)} (pages {u.page_start}-{u.page_end})", ""]
            for b in u.blocks:
                if b.kind == "h":
                    L += [f"### {b.text}", ""]
                elif b.kind == "p":
                    L += [b.text, ""]
                elif b.kind == "li":
                    L += [f"- {b.text}"]
                elif b.kind == "callout":
                    L += ["", f"> **{b.label}:** {b.text}", ""]
                elif b.kind == "code":
                    lang = code_lang(b.lines)
                    L += ["", f"```{'console' if lang == 'bash' else lang}", *b.lines, "```", ""]
        return "\n".join(L).rstrip() + "\n"


def validate(skill_md: Path) -> list[str]:
    text = skill_md.read_text(encoding="utf-8")
    problems = []
    m = re.match(r"---\nname: ([a-z0-9-]+)\ndescription: (\".*\")\n---\n", text)
    if not m:
        problems.append("bad frontmatter")
    elif len(json.loads(m.group(2))) > 1024:
        problems.append("description > 1024 chars")
    if "## Procedures" not in text:
        problems.append("no procedures (no commands in these sections)")
    return problems


# =========================================================================== catalog

def write_index(plan: dict, out: Path) -> None:
    rows, catalog = [], []
    for sk in plan["skills"]:
        md = out / sk["name"] / "SKILL.md"
        if not md.exists():
            continue
        m = re.search(r'^description: (".*")$', md.read_text(encoding="utf-8"), re.MULTILINE)
        desc = json.loads(m.group(1)) if m else ""
        catalog.append({"name": sk["name"], "title": sk["title"], "description": desc,
                        "pages": sk.get("pages", ""), "sections": sk.get("sections", [])})
        short = desc if len(desc) <= 170 else desc[:167].rsplit(" ", 1)[0] + "..."
        rows.append(f"| [`{sk['name']}`]({sk['name']}/SKILL.md) | {md_cell(short)} | {sk.get('pages', '')} |")
    readme = [f"# Skill library: {plan['title']}", "",
              f"Generated from `{plan['source']}` by `skillforge.py` (offline NLP extraction). "
              f"{len(rows)} skills.", "",
              "Install: copy the skill folders into `~/.claude/skills/` (personal) or "
              "`<project>/.claude/skills/` (project). An agent loads a skill only when its description "
              "matches the task.", "",
              "| Skill | Use when | Source pages |", "|---|---|---|", *rows, ""]
    (out / "README.md").write_text("\n".join(readme), encoding="utf-8")
    (out / "catalog.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")


# =========================================================================== main

def main() -> None:
    p = argparse.ArgumentParser(description="Turn a PDF into a library of focused AI Agent Skills "
                                            "(offline, open-source NLP).")
    p.add_argument("pdf", type=Path)
    p.add_argument("--out", type=Path, default=Path("generated-skills"),
                   help="output folder (default ./generated-skills)")
    p.add_argument("--topics", help='comma-separated topics, e.g. "rebase, hooks, merge conflicts"')
    p.add_argument("--max-skills", type=int, default=60, help="auto mode: max number of skills (default 60)")
    p.add_argument("--min-commands", type=int, default=3,
                   help="auto mode: a section needs at least this many commands to become a skill")
    p.add_argument("--prefix", help="skill-name prefix (default: guessed from the document, e.g. 'git')")
    p.add_argument("--only", help="comma-separated skill names from plan.json to (re)write")
    p.add_argument("--plan-only", action="store_true", help="write plan.json and stop")
    p.add_argument("--replan", action="store_true", help="ignore an existing plan.json")
    args = p.parse_args()

    if not args.pdf.is_file():
        sys.exit(f"File not found: {args.pdf}")
    doc = Document(args.pdf)
    index = Index(doc.units)
    work = args.out / ".work" / slugify(args.pdf.stem)
    work.mkdir(parents=True, exist_ok=True)
    plan_file = work / "plan.json"
    topics = [t.strip() for t in (args.topics or "").split(",") if t.strip()]

    plan = None
    if plan_file.exists() and not args.replan:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        if plan.get("topics") != topics or plan.get("units_total") != len(doc.units):
            plan = None                                     # options changed -> plan again
        else:
            print(f"[plan] reusing {plan_file} (edit it freely; --replan to rebuild)")
    if plan is None:
        domain = domain_word(doc, args.prefix)
        skills = (plan_topics(doc, index, topics, domain) if topics
                  else plan_auto(doc, index, domain, args.min_commands, args.max_skills))
        for sk in skills:
            sk["pages"] = page_ranges([doc.units[i] for i in sk["units"]])
            sk["sections"] = dedupe([" > ".join(doc.units[i].path[1:] or doc.units[i].path)
                                     for i in sk["units"]], 40)
        plan = {"source": args.pdf.name, "title": doc.title, "domain": domain, "topics": topics,
                "units_total": len(doc.units), "skills": skills}
        plan_file.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[plan] {len(skills)} skills -> {plan_file}")

    if args.plan_only:
        for sk in plan["skills"]:
            print(f"  {sk['name']:<40} pages {sk['pages']}")
        print(f"\nEdit {plan_file} (rename skills, add/remove unit ids), then rerun without --plan-only.")
        return

    only = {slugify(n) for n in args.only.split(",")} if args.only else None
    author = Author(doc, plan, index)
    written = 0
    for sk in plan["skills"]:
        if only and sk["name"] not in only:
            continue
        problems = author.write(sk, args.out)
        written += 1
        note = f"  ({'; '.join(problems)})" if problems else ""
        print(f"  {sk['name']:<40} pages {sk['pages']}{note}")
    write_index(plan, args.out)
    print(f"\nDone: {written} skill(s) -> {args.out.resolve()}\nCatalog: {args.out / 'README.md'}")


if __name__ == "__main__":
    main()
