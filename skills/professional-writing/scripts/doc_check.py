#!/usr/bin/env python3
"""Check a professional document (blog post, CV/resume, technical doc) and report concrete problems.

    python doc_check.py FILE [--type blog|cv|doc] [--job JOB.txt] [--json]

FILE is .md, .txt or .docx (PDF: export to text or .docx first). --type is guessed from the text when
omitted. With --type cv and --job, also reports which keywords of the job post the CV covers or misses.
Standard library only (Python 3.8+). Exit code is always 0 unless the file cannot be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

WPM = 200  # reading speed used for "reading time"

FILLER = ["very", "really", "just", "basically", "actually", "simply", "quite", "literally", "obviously",
          "in order to", "a lot of", "leverage", "utilize", "synergy", "best-in-class", "cutting-edge",
          "state-of-the-art", "game-changer", "think outside the box", "go-getter", "hard-working",
          "team player", "results-driven", "detail-oriented", "responsible for", "worked on", "helped with"]

ACTION_VERBS = set("""
achieved automated built created cut delivered designed developed drove eliminated established executed
improved implemented increased integrated introduced launched led managed migrated mentored optimized
owned reduced refactored released replaced resolved scaled shipped simplified streamlined supported
tested trained wrote analysed analyzed architected authored coordinated debugged deployed diagnosed
documented enabled expanded identified initiated maintained measured modernized monitored organized
planned presented prototyped researched reviewed standardized strengthened upgraded validated verified
""".split())

CV_SECTIONS = {
    "summary": r"summary|profile|objective|about",
    "experience": r"experience|employment|work history|career",
    "education": r"education|academic|qualification",
    "skills": r"skills|technologies|tech stack|tools|competenc",
    "projects": r"projects|portfolio|open.?source",
    "certifications": r"certifi|courses|training|awards",
}

STOPWORDS = set("""
a about above after again all also am an and any are as at be because been before being below between both but
by can could did do does doing down during each few for from further had has have having he her here hers him his
how i if in into is it its just me more most my no nor not now of off on once only or other our out over own same
she should so some such than that the their them then there these they this those through to too under until up
very was we were what when where which while who whom why will with would you your
experience experienced work working years year role team teams candidate ability able strong skills skill
looking join company position job responsibilities requirements required preferred plus including etc must
need needs using use used good great new will best well within across related relevant
""".split())

TECH_PHRASES = ["ci/cd", "c++", "c#", ".net", "node.js", "rest api", "unit test", "test automation",
                "machine learning", "code review", "problem solving", "agile", "scrum"]


# ----------------------------------------------------------------------------- reading
def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
        out = []
        for p in paragraphs:
            text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
            text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                    .replace("&quot;", '"').replace("&apos;", "'"))
            if "<w:numPr>" in p and text.strip():
                text = "- " + text
            out.append(text)
        return "\n".join(out)
    if suffix == ".pdf":
        raise SystemExit("PDF is not read directly. Export it to .docx or .txt first (or paste the text into a file).")
    return path.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------------- text helpers
def strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)          # fenced code
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", text, flags=re.M)
    return re.sub(r"[*_>|]", " ", text)


def words_of(text: str) -> list:
    return re.findall(r"[A-Za-z][A-Za-z'’+#.-]*", text)


def sentences_of(text: str) -> list:
    flat = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", flat)
    return [p.strip() for p in parts if len(words_of(p)) >= 2]


def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def flesch(words: list, n_sentences: int) -> float:
    if not words or not n_sentences:
        return 0.0
    syl = sum(syllables(w) for w in words)
    return round(206.835 - 1.015 * (len(words) / n_sentences) - 84.6 * (syl / len(words)), 1)


PASSIVE = re.compile(r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b", re.I)


def guess_type(text: str) -> str:
    low = text.lower()
    hits = sum(1 for pat in CV_SECTIONS.values() if re.search(r"^\s*#*\s*(?:" + pat + r")\b", low, re.M))
    has_contact = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text))
    if hits >= 3 and has_contact:
        return "cv"
    if re.search(r"^\s*#\s+\S", text, re.M) and len(words_of(text)) > 500:
        return "blog"
    return "doc"


# ----------------------------------------------------------------------------- checks
class Report:
    def __init__(self) -> None:
        self.findings = []   # (severity, message)
        self.stats = {}

    def add(self, severity: str, msg: str) -> None:
        self.findings.append({"severity": severity, "message": msg})


def check_prose(text: str, rep: Report) -> None:
    plain = strip_markdown(text)
    words = words_of(plain)
    sents = sentences_of(plain)
    n = len(words)
    avg = round(n / len(sents), 1) if sents else 0
    rep.stats.update({"words": n, "sentences": len(sents), "avg_sentence_words": avg,
                      "reading_minutes": round(n / WPM, 1), "flesch_reading_ease": flesch(words, len(sents))})
    long_ones = [s for s in sents if len(words_of(s)) > 35]
    if long_ones:
        rep.add("warn", f"{len(long_ones)} sentence(s) over 35 words. Split them. First: \"{long_ones[0][:110]}...\"")
    if avg > 24:
        rep.add("warn", f"Average sentence is {avg} words; aim for 15-20.")
    passive = PASSIVE.findall(plain)
    if len(sents) and len(passive) / len(sents) > 0.2:
        rep.add("info", f"Possible passive voice in about {len(passive)} places (e.g. \"{passive[0]}\"). Prefer active verbs.")
    low = plain.lower()
    found = {}
    for f in FILLER:
        c = len(re.findall(r"\b" + re.escape(f) + r"\b", low))
        if c:
            found[f] = c
    if found:
        top = ", ".join(f"{k} x{v}" for k, v in sorted(found.items(), key=lambda kv: -kv[1])[:8])
        rep.add("info", f"Filler or cliche phrases: {top}.")
    starts = [w.split()[0].lower() for w in (s for s in sents) if w.split()]
    run = 1
    for i in range(1, len(starts)):
        run = run + 1 if starts[i] == starts[i - 1] else 1
        if run >= 3:
            rep.add("info", f"Three sentences in a row start with \"{starts[i]}\". Vary the openings.")
            break
    paras = [p for p in re.split(r"\n\s*\n", text) if len(words_of(strip_markdown(p))) > 0]
    big = [p for p in paras if len(words_of(strip_markdown(p))) > 150 and not p.lstrip().startswith("```")]
    if big:
        rep.add("info", f"{len(big)} paragraph(s) over 150 words. Break them up.")
    rep.stats["paragraphs"] = len(paras)


def check_blog(text: str, rep: Report) -> None:
    n = rep.stats["words"]
    heads = re.findall(r"^#{1,6}\s+(.+)$", text, re.M)
    h1 = re.findall(r"^#\s+(.+)$", text, re.M)
    rep.stats.update({"headings": len(heads), "code_blocks": text.count("```") // 2,
                      "links": len(re.findall(r"\]\(https?://", text))})
    if not h1:
        rep.add("warn", "No title (a single '# Title' line).")
    elif len(h1[0]) > 70:
        rep.add("info", f"Title is {len(h1[0])} characters; keep it under about 65 for search results.")
    if len(h1) > 1:
        rep.add("warn", "More than one H1 title. Use one H1 and H2/H3 for sections.")
    if n < 600:
        rep.add("info", f"Only {n} words. Most useful how-to or comparison posts are 800-2000 words.")
    elif n > 2800:
        rep.add("info", f"{n} words is long; consider splitting into a series.")
    if n > 600 and len(heads) < 4:
        rep.add("warn", "Fewer than 3 section headings for a post this long. Readers skim by headings.")
    first = strip_markdown(text.split("\n\n", 2)[1] if "\n\n" in text else text)
    if len(words_of(first)) > 90:
        rep.add("info", "The opening paragraph is long. State the problem and what the reader gets in 2-4 sentences.")
    if not re.search(r"^#{2,3}\s+.*(conclusion|summary|takeaway|next steps|wrap|verdict|recommend)", text, re.I | re.M):
        rep.add("info", "No conclusion / takeaways / next-steps heading.")
    if not rep.stats["links"]:
        rep.add("info", "No external links. Link to official docs and sources for every tool or claim.")
    if re.search(r"\b(best|fastest|easiest|ultimate|perfect)\b", text, re.I):
        rep.add("info", "Superlatives found (best, fastest...). Back each with a measurement or soften it.")
    if re.search(r"\b(v?\d+\.\d+(\.\d+)?)\b", text) and not re.search(r"(as of|tested (with|on)|version)", text, re.I):
        rep.add("info", "Versions are mentioned but no 'tested with / as of <date>'. Tool posts age quickly; state when it was checked.")


def check_cv(text: str, rep: Report, job: str | None) -> None:
    low = text.lower()
    n = rep.stats["words"]
    present = {k: bool(re.search(r"^\s*#*\s*\**(?:" + pat + r")", low, re.M)) for k, pat in CV_SECTIONS.items()}
    rep.stats["sections_found"] = [k for k, v in present.items() if v]
    for key in ("experience", "education", "skills"):
        if not present[key]:
            rep.add("warn", f"No '{key}' section heading found.")
    if not present["summary"]:
        rep.add("info", "No summary/profile section. Add 2-3 lines tailored to the target role.")
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    phone = re.search(r"(?:\+?\d[\d ()-]{8,}\d)", text)
    if not email:
        rep.add("warn", "No email address found.")
    if not phone:
        rep.add("info", "No phone number found.")
    if not re.search(r"linkedin\.com|github\.com|gitlab\.com", low):
        rep.add("info", "No LinkedIn / GitHub link.")
    if re.search(r"date of birth|dob\b|marital status|passport no|photograph", low):
        rep.add("warn", "Personal data that most employers do not need (date of birth, marital status, passport...). Consider removing it.")
    if n < 150:
        rep.add("warn", f"Only {n} words; the CV looks thin.")
    elif n > 950:
        rep.add("warn", f"{n} words is more than two pages for most people. Cut older or minor items.")
    bullets = [re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s+", "", ln).strip()
               for ln in text.splitlines() if re.match(r"^\s*(?:[-*+•]|\d+[.)])\s+\S", ln)]
    rep.stats["bullets"] = len(bullets)
    if bullets:
        weak = [b for b in bullets if words_of(b) and words_of(b)[0].lower() not in ACTION_VERBS]
        with_nums = [b for b in bullets if re.search(r"\d", b)]
        long_b = [b for b in bullets if len(words_of(b)) > 30]
        pct = round(100 * len(with_nums) / len(bullets))
        rep.stats["bullets_with_numbers_pct"] = pct
        if len(weak) / len(bullets) > 0.4:
            ex = weak[0][:90]
            rep.add("warn", f"{len(weak)} of {len(bullets)} bullets do not start with a strong action verb (e.g. \"{ex}\"). "
                            "Start with built, cut, led, automated, migrated...")
        if pct < 30:
            rep.add("warn", f"Only {pct}% of bullets contain a number. Add scale or results: %, time saved, counts, users, devices.")
        if long_b:
            rep.add("info", f"{len(long_b)} bullet(s) over 30 words. One line or two is enough.")
        dup = {b.split()[0].lower() for b in bullets if b.split()}
        firsts = [b.split()[0].lower() for b in bullets if b.split()]
        if firsts and max(firsts.count(w) for w in dup) > max(3, len(firsts) // 3):
            rep.add("info", "Many bullets start with the same word. Vary the verbs.")
    else:
        rep.add("warn", "No bullet points found. Use short bullets for achievements under each role.")
    if re.search(r"\b(i|my|me)\b", re.sub(r"https?://\S+", "", low)) and len(re.findall(r"\b(i|my|me)\b", low)) >= 2:
        rep.add("info", "First-person words (I, my). CVs normally drop them (\"Built...\" not \"I built...\").")
    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    if not years:
        rep.add("warn", "No dates found. Give months/years for each role and education.")
    if re.search(r"responsible for|duties included|worked on", low):
        rep.add("info", "\"Responsible for / duties included / worked on\" describe tasks, not results. State what changed because of you.")
    if job:
        job_match(text, job, rep)


def keywords_of(text: str, top: int = 40) -> list:
    low = text.lower()
    found = [p for p in TECH_PHRASES if p in low]
    freq = {}
    for w in re.findall(r"[a-z][a-z0-9+#.]*[a-z0-9+#]|[a-z]", low):
        w = w.strip(".")
        if len(w) < 3 or w in STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = [w for w, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))]
    out = list(dict.fromkeys(found + ranked))
    return out[:top]


def job_match(cv: str, job: str, rep: Report) -> None:
    cv_low = cv.lower()
    kws = keywords_of(job)
    hit = [k for k in kws if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", cv_low)]
    miss = [k for k in kws if k not in hit]
    pct = round(100 * len(hit) / len(kws)) if kws else 0
    rep.stats["job_keywords"] = len(kws)
    rep.stats["job_keyword_coverage_pct"] = pct
    rep.stats["job_keywords_missing"] = miss
    rep.stats["job_keywords_covered"] = hit
    if miss:
        rep.add("info", f"Job keywords not in the CV ({len(miss)}): {', '.join(miss[:20])}. "
                        "Add only the ones that are true for you, using the job post's wording.")


# ----------------------------------------------------------------------------- main
def run(path: Path, doc_type: str | None, job_path: Path | None) -> dict:
    text = read_text(path)
    if not text.strip():
        raise SystemExit(f"{path} has no text.")
    rep = Report()
    kind = doc_type or guess_type(text)
    check_prose(text, rep)
    if kind == "blog":
        check_blog(text, rep)
    elif kind == "cv":
        check_cv(text, rep, read_text(job_path) if job_path else None)
    rep.stats["type"] = kind
    return {"file": str(path), "type": kind, "stats": rep.stats, "findings": rep.findings}


def render(result: dict) -> str:
    s = result["stats"]
    lines = [f"File: {result['file']}", f"Type: {result['type']}",
             f"Words: {s['words']}  Sentences: {s['sentences']}  Avg sentence: {s['avg_sentence_words']} words  "
             f"Reading time: {s['reading_minutes']} min  Flesch ease: {s['flesch_reading_ease']}"]
    extra = {k: v for k, v in s.items() if k not in
             ("words", "sentences", "avg_sentence_words", "reading_minutes", "flesch_reading_ease", "type",
              "job_keywords_missing", "job_keywords_covered")}
    if extra:
        lines.append("  ".join(f"{k}: {v}" for k, v in extra.items()))
    lines.append("")
    order = {"warn": 0, "info": 1}
    items = sorted(result["findings"], key=lambda f: order.get(f["severity"], 2))
    if not items:
        lines.append("No problems found by the automatic checks. Still read it aloud once.")
    for f in items:
        lines.append(f"[{f['severity'].upper()}] {f['message']}")
    lines += ["", "These checks are heuristics. Use them to find places to look, not as a verdict."]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path)
    ap.add_argument("--type", choices=["blog", "cv", "doc"], help="document type (guessed if omitted)")
    ap.add_argument("--job", type=Path, help="job post text file, to compare keywords with a CV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = ap.parse_args()
    try:
        result = run(args.file, args.type, args.job)
    except (OSError, zipfile.BadZipFile, KeyError) as e:
        sys.exit(f"Cannot read {args.file}: {e}")
    print(json.dumps(result, indent=2) if args.json else render(result))


if __name__ == "__main__":
    main()
