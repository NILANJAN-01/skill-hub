"""Guardrails for yt-lecture-overview: accept only YouTube video links, and only study/tech videos.

Standard library only. Two checks:

1. ``parse_youtube_url(url)``: the input must be a link to ONE YouTube video on a real YouTube host
   (look-alike hosts, playlists without a video, channels and bare text are rejected).
2. ``classify_title(title, category, keywords)``: the video's real title (read from YouTube, never
   from the user) must be about study or technology. Category and tags only add a small bonus; they
   cannot pass a video on their own.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
                 "youtube-nocookie.com", "www.youtube-nocookie.com"}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
PATH_PREFIXES = ("shorts", "embed", "live", "v", "e")


class LinkError(ValueError):
    """The input is not a usable link to a single YouTube video."""


def parse_youtube_url(url: str) -> dict:
    """Return {'video_id', 'url', 'start'} for a YouTube video link, or raise LinkError."""
    if not isinstance(url, str) or not url.strip():
        raise LinkError("give a YouTube video link, e.g. https://www.youtube.com/watch?v=<id>")
    raw = url.strip()
    if not re.match(r"^https?://", raw, re.I):
        if re.match(r"^(www\.|m\.)?(youtube\.com|youtu\.be|youtube-nocookie\.com)/", raw, re.I):
            raw = "https://" + raw
        else:
            raise LinkError(f"not a YouTube link: {url!r}. Only http(s) links to youtube.com or youtu.be are accepted")
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    if parts.username or parts.password or (parts.port not in (None, 80, 443)):
        raise LinkError("the link has a user name, password or unusual port; give a plain YouTube link")
    query = parse_qs(parts.query)
    segs = [s for s in parts.path.split("/") if s]
    vid = None
    if host in SHORT_HOSTS:
        vid = segs[0] if segs else None
    elif host in YOUTUBE_HOSTS:
        if segs[:1] == ["watch"] or not segs:
            vid = (query.get("v") or [None])[0]
            if not vid and query.get("list"):
                raise LinkError("this is a playlist link; open one video of the playlist and give its link")
        elif segs[0] in PATH_PREFIXES and len(segs) > 1:
            vid = segs[1]
        elif segs[0] in ("playlist",):
            raise LinkError("this is a playlist link; give the link of one video")
        elif segs[0] in ("channel", "c", "user") or segs[0].startswith("@"):
            raise LinkError("this is a channel link; give the link of one video")
    else:
        raise LinkError(f"{host or 'this'} is not a YouTube host; only youtube.com and youtu.be links are accepted")
    if not vid or not VIDEO_ID_RE.match(vid):
        raise LinkError("could not find a valid 11-character video id in the link")
    start = 0
    t = (query.get("t") or query.get("start") or [""])[0]
    m = re.match(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?$", t or "")
    if t and m:
        start = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
    return {"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "start": start}


# ---------------------------------------------------------------- title classification
# Weights: STUDY words say "this is teaching"; SUBJECT words name a study or tech subject;
# BLOCK words mark entertainment. A title passes at PASS_SCORE or more.
STUDY = {
    3: ["lecture", "lectures", "tutorial", "tutorials", "course", "crash course", "full course", "lesson",
        "lessons", "introduction to", "intro to", "beginner's guide", "beginners guide", "for beginners",
        "masterclass", "bootcamp", "seminar", "webinar", "workshop", "ocw", "opencourseware", "nptel", "cs50",
        "syllabus", "semester", "one shot", "study", "studying", "tech talk", "ted talk", "keynote",
        "interview preparation", "interview questions", "coding interview", "system design", "systems design",
        "system design interview", "hld", "lld", "jee", "neet", "gate exam", "upsc", "gre", "gmat"],
    2: ["explained", "explainer", "fundamentals", "basics", "concepts", "theory", "exam", "exams", "revision",
        "deep dive", "walkthrough", "lab", "conference", "high level design", "high-level design",
        "low level design", "low-level design"],
    1: ["learn", "learning", "how to", "how does", "how do", "what is", "what are", "why does", "guide",
        "class", "classes", "chapter", "module", "part", "unit", "problem", "problems", "solved", "solution",
        "solutions", "proof", "derivation", "notes", "summary", "overview"],
}
SUBJECT = [
    # computing and engineering
    "programming", "coding", "code", "software", "computer", "computing", "computer science", "algorithm",
    "algorithms", "data structure", "data structures", "python", "java", "javascript", "typescript", "c++",
    "c#", "rust", "golang", "kotlin", "swift", "sql", "database", "databases", "linux", "unix", "git",
    "docker", "kubernetes", "devops", "cloud", "aws", "azure", "gcp", "api", "apis", "web development",
    "frontend", "backend", "react", "angular", "vue", "node.js", "nodejs", "django", "flask", "spring",
    "android", "ios development", "machine learning", "deep learning", "neural network", "neural networks",
    "artificial intelligence", "ai", "llm", "llms", "transformer", "transformers", "nlp", "computer vision",
    "data science", "data analysis", "statistics", "probability", "cybersecurity", "security", "cryptography",
    "network", "networking", "operating system", "operating systems", "compiler", "compilers", "blockchain",
    "cpu", "gpu", "processor", "internet", "http", "dns", "tcp", "html", "css",
    "software architecture", "system architecture", "distributed system", "distributed systems", "microservices",
    "scalability", "load balancer", "load balancing", "caching", "sharding", "message queue", "kafka", "redis",
    "embedded", "microcontroller", "arduino", "raspberry pi", "electronics", "circuit", "circuits",
    "signal processing", "robotics", "engineering", "testing", "automation", "excel", "matlab",
    # sciences and maths
    "math", "maths", "mathematics", "algebra", "linear algebra", "calculus", "geometry", "trigonometry",
    "differential equations", "discrete math", "physics", "quantum", "mechanics", "thermodynamics",
    "electromagnetism", "chemistry", "organic chemistry", "biology", "genetics", "biochemistry", "anatomy",
    "physiology", "medicine", "neuroscience", "astronomy", "astrophysics", "geology", "ecology", "science",
    # other academic subjects
    "economics", "microeconomics", "macroeconomics", "finance", "accounting", "history", "geography",
    "philosophy", "psychology", "sociology", "political science", "law", "grammar", "vocabulary",
    "language", "literature", "english", "research", "university", "college", "school", "academic",
]
BLOCK = [
    "official music video", "music video", "official video", "official audio", "lyric", "lyrics", "song",
    "songs", "remix", "cover song", "karaoke", "trailer", "teaser", "full movie", "movie", "film scene",
    "web series", "episode recap", "prank", "pranks", "reaction", "reacts", "vlog", "mukbang", "asmr",
    "gameplay", "let's play", "lets play", "walkthrough gameplay", "speedrun", "highlights", "funny",
    "comedy", "meme", "memes", "tiktok", "shorts compilation", "compilation", "challenge", "dance",
    "unboxing", "haul", "makeup", "fashion", "gossip", "celebrity", "drama", "kdrama", "roast", "live stream chat", "giveaway",
    "trading signals", "betting", "casino",
]
BLOCK_WEIGHT = -4
SUBJECT_WEIGHT = 2
CATEGORY_BONUS = {"Education": 1, "Science & Technology": 1, "Howto & Style": 0}
PASS_SCORE = 3


def _find(terms, text):
    found = []
    for term in terms:
        pat = r"(?<![a-z0-9])" + re.escape(term.strip()) + r"(?![a-z0-9])"
        if re.search(pat, text):
            found.append(term.strip())
    return found


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("’", "'")).strip()


def classify_title(title: str, category: str = "", keywords=None) -> dict:
    """Decide whether a video is study/tech from its title.

    Returns {'allowed', 'score', 'reason', 'matched': {...}}. Category and tags add at most +2 and are
    counted only when the title itself already has a study or subject term.
    """
    t = _norm(title)
    if not t:
        return {"allowed": False, "score": 0, "reason": "the video has no title, so it cannot be checked",
                "matched": {}}
    study3, study2, study1 = _find(STUDY[3], t), _find(STUDY[2], t), _find(STUDY[1], t)
    subjects = _find(SUBJECT, t)
    blocked = _find(BLOCK, t)
    # keep only the longest of overlapping matches ("learning" inside "machine learning", etc.)
    subjects = [s for s in subjects if not any(s != o and s in o for o in subjects)]
    study1 = [s for s in study1 if not any(s in o for o in subjects + study3 + study2)]
    blocked = [s for s in blocked if not any(s != o and s in o for o in blocked)]
    score = (3 * len(study3) + 2 * len(study2) + len(study1) + SUBJECT_WEIGHT * len(subjects)
             + BLOCK_WEIGHT * len(blocked))
    bonus = 0
    if study3 or study2 or subjects:
        bonus += CATEGORY_BONUS.get((category or "").strip(), 0)
        tag_text = _norm(" ".join(keywords or []))
        if tag_text and (_find(STUDY[3], tag_text) or _find(SUBJECT, tag_text)):
            bonus += 1
    score += bonus
    allowed = score >= PASS_SCORE and bool(study3 or study2 or subjects)
    if allowed:
        reason = "the title is about study or technology"
    elif blocked:
        reason = f"the title looks like entertainment ({', '.join(blocked)}), not a study or tech video"
    elif not (study3 or study2 or subjects):
        reason = "the title has no study or technology terms"
    else:
        reason = "the title is not clearly a study or tech video (score too low)"
    return {"allowed": allowed, "score": score, "pass_score": PASS_SCORE, "reason": reason,
            "matched": {"study": study3 + study2 + study1, "subjects": subjects, "entertainment": blocked,
                        "category": category or "", "metadata_bonus": bonus}}
