"""nlp_lite.py - the text statistics skillforge needs, in pure Python (standard library only).

    Tfidf     same weights as scikit-learn's TfidfVectorizer(analyzer=..., sublinear_tf=..., max_df=...)
              with its defaults (smooth idf, L2-normalised rows). Rows are sparse dicts {term_id: weight}.
    dot       dot product of two sparse rows.
    pagerank  weighted PageRank by power iteration over a sparse similarity matrix.
    yake      YAKE keyword extraction (Campos et al., 2020), following the reference implementation's
              features (casing, position, frequency, relatedness, spread) and its Levenshtein dedup.
"""
from __future__ import annotations

import math
import re
import string
from collections import Counter, defaultdict
from statistics import median

__all__ = ["Tfidf", "dot", "pagerank", "yake"]


# =========================================================================== TF-IDF

class Tfidf:
    """TF-IDF with scikit-learn's formulas: tf = 1 + ln(count) when sublinear, idf = ln((1+n)/(1+df)) + 1,
    terms in more than max_df of the documents dropped, rows scaled to unit length."""

    def __init__(self, analyzer, sublinear_tf=False, max_df=1.0):
        self.analyzer = analyzer
        self.sublinear_tf = sublinear_tf
        self.max_df = max_df
        self.vocab = {}
        self.idf = []

    def fit_transform(self, docs):
        tokenized = [self.analyzer(d) for d in docs]
        df = Counter()
        for toks in tokenized:
            df.update(set(toks))
        if not df:
            raise ValueError("empty vocabulary; perhaps the documents only contain stop words")
        n = len(tokenized)
        limit = self.max_df if isinstance(self.max_df, int) and not isinstance(self.max_df, bool) else self.max_df * n
        terms = sorted(t for t, c in df.items() if c <= limit)
        if not terms:
            raise ValueError("After pruning, no terms remain. Try a lower min_df or a higher max_df.")
        self.vocab = {t: i for i, t in enumerate(terms)}
        self.idf = [math.log((1.0 + n) / (1.0 + df[t])) + 1.0 for t in terms]
        return [self._row(toks) for toks in tokenized]

    def transform(self, docs):
        return [self._row(self.analyzer(d)) for d in docs]

    @property
    def n_features(self):
        return len(self.vocab)

    def _row(self, toks):
        vocab, idf = self.vocab, self.idf
        counts = Counter(t for t in toks if t in vocab)
        row = {}
        for t, c in counts.items():
            i = vocab[t]
            tf = 1.0 + math.log(c) if self.sublinear_tf else float(c)
            row[i] = tf * idf[i]
        norm = math.sqrt(sum(v * v for v in row.values()))
        if norm > 0:
            row = {k: v / norm for k, v in row.items()}
        return row


def dot(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b[k] for k, v in a.items() if k in b)


def similarity_matrix(rows):
    """Sparse rows -> {i: {j: dot(rows[i], rows[j])}} for i != j with a non-zero product."""
    postings = defaultdict(list)
    for i, row in enumerate(rows):
        for t, w in row.items():
            postings[t].append((i, w))
    sim = defaultdict(lambda: defaultdict(float))
    for plist in postings.values():
        for a in range(len(plist)):
            i, wi = plist[a]
            for b in range(a + 1, len(plist)):
                j, wj = plist[b]
                p = wi * wj
                sim[i][j] += p
                sim[j][i] += p
    return sim


def pagerank(sim, n, d=0.85, iters=100):
    """Weighted PageRank by power iteration. sim: {i: {j: weight}}; rows without weight jump anywhere."""
    if n == 0:
        return []
    out = [sum(sim[i].values()) if i in sim else 0.0 for i in range(n)]
    trans = {i: [(j, w / out[i]) for j, w in sim[i].items()] for i in range(n) if out[i] > 0}
    dangling = [i for i in range(n) if out[i] <= 0]
    r = [1.0 / n] * n
    base = (1.0 - d) / n
    for _ in range(iters):
        nxt = [0.0] * n
        for i, edges in trans.items():
            ri = r[i]
            for j, p in edges:
                nxt[j] += ri * p
        jump = sum(r[i] for i in dangling) / n
        nxt = [base + d * (v + jump) for v in nxt]
        if sum(abs(a - b) for a, b in zip(nxt, r)) < 1e-8:
            break
        r = nxt
    return r


# =========================================================================== YAKE

_STOPWORDS = set("""
a about above across after afterwards again against all almost alone along already also although always am
among amongst amoungst amount an and another any anyhow anyone anything anyway anywhere are around as at back
be became because become becomes becoming been before beforehand behind being below beside besides between
beyond bill both bottom but by call can cannot cant co con could couldnt cry de describe detail do does doing
done down due during each eg eight either eleven else elsewhere empty enough etc even ever every everyone
everything everywhere except few fifteen fify fill find fire first five for former formerly forty found four
from front full further get give go had has hasnt have having he hence her here hereafter hereby herein
hereupon hers herself him himself his how however hundred i ie if in inc indeed interest into is it its itself
just keep last latter latterly least less ltd made many may me meanwhile might mill mine more moreover most
mostly move much must my myself name namely neither never nevertheless next nine no nobody none noone nor not
nothing now nowhere of off often on once one only onto or other others otherwise our ours ourselves out over
own part per perhaps please put rather re same see seem seemed seeming seems serious several she should show
side since sincere six sixty so some somehow someone something sometime sometimes somewhere still such system
take ten than that the their them themselves then thence there thereafter thereby therefore therein thereupon
these they thick thin third this those though three through throughout thru thus to together too top toward
towards twelve twenty two un under until up upon us very via was we well were what whatever when whence
whenever where whereafter whereas whereby wherein whereupon wherever whether which while whither who whoever
whole whom whose why will with within without would yet you your yours yourself yourselves
able according actually ago ahead allow allows apart appear appreciate appropriate aside ask asking associated
available away awfully believe best better brief came cause causes certain certainly changes clearly come comes
concerning consequently consider considering contain containing contains corresponding course currently
definitely described despite did different directly don done downwards edu entirely especially et exactly
example far following follows forth furthermore gets getting given gives goes going gone got gotten greetings
happens hardly hello help hi hopefully ignored immediate inasmuch indicate indicated indicates inner insofar
instead inward isn know known knows lately later let like liked likely little look looking looks mainly maybe
mean merely nd near nearly necessary need needs new non normally novel obviously oh ok okay old ones ought
outside overall particular particularly placed plus possible presumably probably provides que quite qv really
reasonably regarding regardless regards relatively respectively right said saw say saying says second secondly
seeing seen self selves sensible sent seriously shall sub sup sure taken tell tends th thank thanks thanx
thats theirs thorough thoroughly think tried tries truly try trying twice unfortunately unless unlikely
unto use used useful uses using usually value various viz vs want wants way welcome went won wonder yes
""".split())
_EXCLUDE = set(string.punctuation)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[`]?[A-Z0-9])")
_TOKEN = re.compile(r"https?://\S+[\w/]|\w+(?:[.\-'’/@+]\w+)*|[^\w\s]")


def _tokens(sentence):
    out = []
    for w in _TOKEN.findall(sentence):
        if ("'" in w or "’" in w) and len(w) > 2:
            w = w.replace("’", "'")
            if w.lower().endswith("n't"):
                out += [w[:-3], w[-3:]]
                continue
            k = w.find("'")
            if 0 < k < len(w) - 1:
                out += [w[:k], w[k:]]
                continue
        out.append(w)
    return [w for w in out if w and not (w.startswith("'") and len(w) > 1)]


class _Term:
    __slots__ = ("key", "id", "tf", "tf_a", "tf_n", "occurs", "stopword", "H")

    def __init__(self, key, idx, stopword):
        self.key, self.id, self.stopword = key, idx, stopword
        self.tf = self.tf_a = self.tf_n = 0.0
        self.occurs = {}
        self.H = 0.0


class _Cand:
    __slots__ = ("kw", "unique", "terms", "tags", "tf", "H", "edge_stop")

    def __init__(self, items):
        self.tags = {"".join(t for t, _, _ in items)}
        self.kw = " ".join(w for _, w, _ in items)
        self.unique = self.kw.lower()
        self.terms = [term for _, _, term in items]
        self.tf = 0.0
        self.H = 1.0
        self.edge_stop = self.terms[0].stopword or self.terms[-1].stopword

    def valid(self):
        return any("u" not in t and "d" not in t for t in self.tags) and not self.edge_stop


def _tag(word, i):
    try:
        float(word.replace(",", ""))
        return "d"
    except ValueError:
        pass
    digits = sum(c.isdigit() for c in word)
    alpha = sum(c.isalpha() for c in word)
    if (digits and alpha) or (not digits and not alpha) or sum(c in _EXCLUDE for c in word) > 1:
        return "u"
    upper = sum(c.isupper() for c in word)
    if upper == len(word):
        return "a"
    if upper == 1 and len(word) > 1 and word[0].isupper() and i > 0:
        return "n"
    return "p"


def _levenshtein_ratio(a, b):
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1.0 - prev[-1] / max(len(a), len(b))


def yake(text, n=3, top=20, dedup_lim=0.9, window=1, stopwords=None):
    """[(keyphrase, score)] with the best (lowest) scores first."""
    stop = _STOPWORDS if stopwords is None else stopwords
    terms, cands = {}, {}
    out_edges = defaultdict(lambda: defaultdict(float))
    in_edges = defaultdict(lambda: defaultdict(float))
    freq_ns = Counter()

    def term(word):
        key = word.lower()
        plain_stop = key in stop
        if key.endswith("s") and len(key) > 3:
            key = key[:-1]
        if key in terms:
            return terms[key]
        bare = "".join(c for c in key if c not in _EXCLUDE)
        t = _Term(key, len(terms), plain_stop or key in stop or len(bare) < 3)
        terms[key] = t
        return t

    def add_cand(items):
        c = _Cand(items)
        old = cands.get(c.unique)
        if old is None:
            cands[c.unique] = old = c
        else:
            old.tags |= c.tags
        old.tf += 1.0

    sentences = [s for s in _SENT.split(text.replace("\n\t", " ")) if s.strip()]
    pos_text = 0
    n_sent = len(sentences)
    for sid, sentence in enumerate(sentences):
        words = _tokens(sentence)
        block = []
        for pos, word in enumerate(words):
            if all(c in _EXCLUDE for c in word):
                block = []
                continue
            tag = _tag(word, pos)
            t = term(word)
            t.occurs.setdefault(sid, []).append((pos, pos_text))
            t.tf += 1.0
            if tag == "a":
                t.tf_a += 1.0
            elif tag == "n":
                t.tf_n += 1.0
            pos_text += 1
            if tag not in ("u", "d"):
                for w in range(max(0, len(block) - window), len(block)):
                    if block[w][0] not in ("u", "d"):
                        left = block[w][2]
                        out_edges[left.id][t.id] += 1.0
                        in_edges[t.id][left.id] += 1.0
            cand = [(tag, word, t)]
            add_cand(cand)
            for w in range(len(block) - 1, max(0, len(block) - (n - 1)) - 1, -1):
                cand.append(block[w])
                freq_ns[len(cand)] += 1.0
                add_cand(cand[::-1])
            block.append((tag, word, t))
    if not terms:
        return []
    valid_tfs = [t.tf for t in terms.values() if not t.stopword]
    if not valid_tfs:
        return []
    avg = sum(valid_tfs) / len(valid_tfs)
    std = math.sqrt(sum((x - avg) ** 2 for x in valid_tfs) / len(valid_tfs))
    max_tf = max(t.tf for t in terms.values())
    for t in terms.values():
        wdr, wir = len(out_edges[t.id]), sum(out_edges[t.id].values())
        wdl, wil = len(in_edges[t.id]), sum(in_edges[t.id].values())
        pwr = wdr / wir if wir else 0.0
        pwl = wdl / wil if wil else 0.0
        wrel = (0.5 + pwl * (t.tf / max_tf)) + (0.5 + pwr * (t.tf / max_tf))
        wfreq = t.tf / (avg + std)
        wspread = len(t.occurs) / n_sent
        wcase = max(t.tf_a, t.tf_n) / (1.0 + math.log(t.tf))
        wpos = math.log(math.log(3.0 + median(list(t.occurs.keys()))))
        t.H = (wpos * wrel) / (wcase + wfreq / wrel + wspread / wrel)
    for c in cands.values():
        if not c.valid():
            continue
        sum_h, prod_h = 0.0, 1.0
        for k, tb in enumerate(c.terms):
            if not tb.stopword:
                sum_h += tb.H
                prod_h *= tb.H
            else:
                prev, nxt = c.terms[k - 1], c.terms[k + 1]
                p1 = out_edges[prev.id].get(tb.id, 0.0) / prev.tf if tb.id in out_edges[prev.id] else 0.0
                p2 = out_edges[tb.id].get(nxt.id, 0.0) / nxt.tf if nxt.id in out_edges[tb.id] else 0.0
                prob = p1 * p2
                prod_h *= 1 + (1 - prob)
                sum_h -= 1 - prob
        c.H = prod_h / ((sum_h + 1) * c.tf)
    ranked = sorted((c for c in cands.values() if c.valid()), key=lambda c: c.H)
    if dedup_lim >= 1:
        return [(c.kw, c.H) for c in ranked][:top]
    result = []
    for c in ranked:
        if all(_levenshtein_ratio(c.unique, r.unique) <= dedup_lim for r in result):
            result.append(c)
            if len(result) == top:
                break
    return [(c.kw, c.H) for c in result]
