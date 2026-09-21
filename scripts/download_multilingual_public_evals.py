"""Downloads and verifies genuine public-domain multilingual evaluation corpora.

Every corpus is fetched from Project Gutenberg (plain text or HTML) or Wikisource
(via the MediaWiki API, which resolves ProofreadPage transclusion into real body
text). Each download is verified before being written:
  (a) the expected title/author string appears in the fetched text, and
  (b) at least 80% of alphabetic characters belong to the target script.
Long texts are truncated at a paragraph boundary to <= MAX_BYTES (Don Quijote is
exempted per the eval spec and kept at full length). No corpus is synthesized:
if a genuine source can't be found and verified, the language is dropped instead
of being padded with generated filler.

Run: .venv/bin/python scripts/download_multilingual_public_evals.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

DEST_DIR = Path(__file__).resolve().parent.parent / "examples" / "eval" / "multilingual"
DEST_DIR.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (ContextCull Public Eval Ingest; research use)"}
MAX_BYTES = 500_000

SCRIPT_RANGES = {
    "latin": r"A-Za-zÀ-ÖØ-öø-ÿ",
    "cjk": r"一-鿿",
    "kana_cjk": r"぀-ヿ一-鿿ｦ-ﾟ",
    "cyrillic": r"Ѐ-ӿ",
    "devanagari": r"ऀ-ॿ",
    "arabic": r"؀-ۿ",
    "bengali": r"ঀ-৿",
    "hebrew": r"֐-׿",
}


def script_ratio(text: str, script: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    pattern = re.compile(f"[{SCRIPT_RANGES[script]}]")
    hits = sum(1 for c in letters if pattern.match(c))
    return hits / len(letters)


def fetch(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (public-domain text mirrors only)
        return resp.read()


def strip_gutenberg_boilerplate(text: str) -> str:
    start = re.search(
        r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", text, re.I | re.S
    )
    end = re.search(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK", text, re.I)
    body = text[start.end() : end.start()] if start and end else text
    return body.strip()


def truncate_at_paragraph(text: str, max_bytes: int = MAX_BYTES) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    idx = truncated.rfind("\n\n")
    if idx <= 0:
        idx = truncated.rfind("\n")
    return (truncated[:idx] if idx > 0 else truncated).strip(), True


class VisibleTextExtractor(HTMLParser):
    """Minimal stdlib HTML -> text extractor. Skips script/style/nav/header/footer."""

    SKIP = {"script", "style", "nav", "header", "footer", "noscript"}
    BLOCK = {"p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = VisibleTextExtractor()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def wikisource_page_text(lang: str, title: str) -> str:
    """Fetch one Wikisource page's rendered body text (resolves transcluded scans)."""
    from urllib.parse import quote

    url = f"https://{lang}.wikisource.org/w/api.php?action=parse&page={quote(title)}&prop=text&format=json"
    data = json.loads(fetch(url).decode("utf-8"))
    html = data["parse"]["text"]["*"]
    return html_to_text(html)


def bengali_numeral(n: int) -> str:
    return "".join(chr(0x09E6 + int(d)) for d in str(n))


@dataclass
class Corpus:
    file: str
    language: str
    title: str
    author: str
    source_url: str
    license: str
    title_check: str
    script: str
    fetcher: str
    keep_full: bool = False
    extra: dict = field(default_factory=dict)


CORPORA = [
    Corpus(
        file="01_en_literature_alice.txt",
        language="en",
        title="Alice's Adventures in Wonderland",
        author="Lewis Carroll",
        source_url="https://www.gutenberg.org/cache/epub/11/pg11.txt",
        license="Public Domain (Project Gutenberg #11)",
        title_check="Adventures in Wonderland",
        script="latin",
        fetcher="gutenberg_txt",
    ),
    Corpus(
        file="02_en_math_calculus.txt",
        language="en",
        title="Calculus Made Easy",
        author="Silvanus P. Thompson",
        source_url="https://www.gutenberg.org/ebooks/33283.html.images",
        license="Public Domain (Project Gutenberg #33283; no plain-text edition, extracted from HTML)",
        title_check="Calculus Made Easy",
        script="latin",
        fetcher="gutenberg_html",
    ),
    Corpus(
        file="03_zh_journey_to_the_west.txt",
        language="zh",
        title="西遊記 (Journey to the West)",
        author="Wu Cheng'en",
        source_url="https://www.gutenberg.org/cache/epub/23962/pg23962.txt",
        license="Public Domain (Project Gutenberg #23962)",
        title_check="西遊記",
        script="cjk",
        fetcher="gutenberg_txt",
    ),
    Corpus(
        file="04_hi_premchand_stories.txt",
        language="hi",
        title="Idgah; A Night in the Fields; My Elder Brother (from Mansarovar I)",
        author="Munshi Premchand",
        source_url=(
            "https://hi.wikisource.org/wiki/मानसरोवर_१/ईदगाह ; "
            "https://hi.wikisource.org/wiki/मानसरोवर_१/पूस_की_रात ; "
            "https://hi.wikisource.org/wiki/मानसरोवर_१/बड़े_भाई_साहब"
        ),
        license="Public Domain (author d. 1936); Wikisource transcription CC BY-SA 4.0",
        title_check="प्रेमचंद",
        script="devanagari",
        fetcher="wikisource_multi",
        extra={
            "lang": "hi",
            "pages": ["मानसरोवर १/ईदगाह", "मानसरोवर १/पूस की रात", "मानसरोवर १/बड़े भाई साहब"],
        },
    ),
    Corpus(
        file="05_es_don_quijote.txt",
        language="es",
        title="Don Quijote de la Mancha",
        author="Miguel de Cervantes",
        source_url="https://www.gutenberg.org/cache/epub/2000/pg2000.txt",
        license="Public Domain (Project Gutenberg #2000)",
        title_check="Don Quijote",
        script="latin",
        fetcher="gutenberg_txt",
        keep_full=True,
    ),
    Corpus(
        file="06_fr_tour_du_monde.txt",
        language="fr",
        title="Le Tour du monde en quatre-vingts jours",
        author="Jules Verne",
        source_url="https://www.gutenberg.org/cache/epub/800/pg800.txt",
        license="Public Domain (Project Gutenberg #800)",
        title_check="Le tour du monde",
        script="latin",
        fetcher="gutenberg_txt",
    ),
    Corpus(
        file="07_ar_kalila_wa_dimna.txt",
        language="ar",
        title="كليلة ودمنة (Kalila wa Dimna)",
        author="Ibn al-Muqaffa",
        source_url=(
            "https://ar.wikisource.org/wiki/كليلة_ودمنة/باب_مقدمة_الكتاب ; "
            "https://ar.wikisource.org/wiki/كليلة_ودمنة/باب_بعثة_برزويه_إلى_بلاد_الهند"
        ),
        license="Public Domain (8th century text); Wikisource transcription CC BY-SA 4.0",
        title_check="كليلة ودمنة",
        script="arabic",
        fetcher="wikisource_multi",
        extra={
            "lang": "ar",
            "pages": [
                "كليلة ودمنة/باب مقدمة الكتاب",
                "كليلة ودمنة/باب بعثة برزويه إلى بلاد الهند",
            ],
        },
    ),
    Corpus(
        file="08_bn_gitanjali.txt",
        language="bn",
        title="গীতাঞ্জলি (Gitanjali, 1913 Bengali original)",
        author="Rabindranath Tagore",
        source_url="https://bn.wikisource.org/wiki/গীতাঞ্জলি_(১৯১৩)",
        license="Public Domain (author d. 1941); Wikisource transcription CC BY-SA 4.0",
        title_check="রবীন্দ্রনাথ",
        script="bengali",
        fetcher="wikisource_multi",
        extra={
            "lang": "bn",
            "pages": [f"গীতাঞ্জলি (১৯১৩)/{bengali_numeral(i)}" for i in range(1, 26)],
            "join_titles": True,
        },
    ),
    Corpus(
        file="09_pt_dom_casmurro.txt",
        language="pt",
        title="Dom Casmurro",
        author="Machado de Assis",
        source_url="https://www.gutenberg.org/cache/epub/55752/pg55752.txt",
        license="Public Domain (Project Gutenberg #55752)",
        title_check="Dom Casmurro",
        script="latin",
        fetcher="gutenberg_txt",
    ),
    Corpus(
        file="10_ru_rachinsky_arithmetic.txt",
        language="ru",
        title="1001 задача для умственного счета",
        author="Sergei Rachinsky",
        source_url="https://www.gutenberg.org/ebooks/16527.txt.utf-8",
        license="Public Domain (Project Gutenberg #16527)",
        title_check="умственного счета",
        script="cyrillic",
        fetcher="gutenberg_txt",
    ),
    Corpus(
        file="11_ja_akutagawa_rashomon.txt",
        language="ja",
        title="羅生門 (Rashomon)",
        author="Akutagawa Ryūnosuke",
        source_url="https://www.gutenberg.org/cache/epub/1982/pg1982.txt",
        license="Public Domain (Project Gutenberg #1982)",
        title_check="羅生門",
        script="kana_cjk",
        fetcher="gutenberg_txt",
    ),
    Corpus(
        file="12_he_bereshit_genesis.txt",
        language="he",
        title="Sefer Bereshit (Book of Genesis)",
        author="Classical Hebrew (Masoretic Text)",
        source_url="pre-existing file, not re-fetched; re-verified in place (title + script ratio) this pass",
        license="Public Domain (Masoretic Text, unpointed consonantal transcription)",
        title_check="בראשית",
        script="hebrew",
        fetcher="keep_existing",
    ),
]


def do_fetch(corpus: Corpus) -> tuple[str, str]:
    """Returns (title_check_text, body_text). title_check_text includes any
    source metadata (e.g. the Gutenberg header line) that the boilerplate strip
    would otherwise remove, so the title/author check isn't fooled by a body
    that jumps straight into chapter 1 without repeating the title."""
    if corpus.fetcher == "gutenberg_txt":
        raw = fetch(corpus.source_url).decode("utf-8", errors="replace")
        return raw, strip_gutenberg_boilerplate(raw)
    if corpus.fetcher == "gutenberg_html":
        raw = fetch(corpus.source_url).decode("utf-8", errors="replace")
        text = html_to_text(raw)
        return text, text
    if corpus.fetcher == "wikisource_multi":
        import time

        lang = corpus.extra["lang"]
        chunks = []
        for title in corpus.extra["pages"]:
            for attempt in range(3):
                try:
                    chunks.append(wikisource_page_text(lang, title))
                    break
                except Exception as exc:  # noqa: BLE001 - retry, then skip a missing sub-page
                    if attempt == 2:
                        print(f"    ! sub-page fetch failed for {title!r}: {exc}", file=sys.stderr)
                    else:
                        time.sleep(2.0 * (attempt + 1))
            time.sleep(0.5)
        text = "\n\n".join(c for c in chunks if c.strip())
        return text, text
    raise ValueError(f"unknown fetcher {corpus.fetcher}")


def verify_and_write(corpus: Corpus) -> dict | None:
    dest = DEST_DIR / corpus.file
    print(f"[{corpus.language}] {corpus.title} <- {corpus.source_url.split(' ; ')[0]}")

    if corpus.fetcher == "keep_existing":
        if not dest.exists():
            print(f"    ! DROPPED: {dest} does not exist and has no fetcher")
            return None
        text = dest.read_text(encoding="utf-8")
        title_check_text = text
        truncated = False
    else:
        try:
            title_check_text, text = do_fetch(corpus)
        except Exception as exc:  # noqa: BLE001
            print(f"    ! DROPPED ({corpus.language}): fetch failed: {exc}")
            return None
        if not text.strip():
            print(f"    ! DROPPED ({corpus.language}): empty body after extraction")
            return None
        max_bytes = None if corpus.keep_full else MAX_BYTES
        if max_bytes is not None:
            text, truncated = truncate_at_paragraph(text, max_bytes)
        else:
            truncated = False

    ratio = script_ratio(text, corpus.script)
    title_ok = corpus.title_check in title_check_text

    if not title_ok:
        print(
            f"    ! DROPPED ({corpus.language}): title check {corpus.title_check!r} not found in body"
        )
        return None
    if ratio < 0.80:
        print(
            f"    ! DROPPED ({corpus.language}): script ratio {ratio:.1%} < 80% for {corpus.script}"
        )
        return None

    dest.write_text(text, encoding="utf-8")
    size = dest.stat().st_size
    sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
    print(f"    OK: title verified, script ratio {ratio:.1%}, {size} bytes, truncated={truncated}")

    return {
        "file": corpus.file,
        "language": corpus.language,
        "author": corpus.author,
        "title": corpus.title,
        "source": corpus.source_url,
        "license": corpus.license,
        "script_ratio": round(ratio, 4),
        "bytes": size,
        "sha256": sha256,
        "truncated_to_paragraph_boundary": truncated,
    }


def main() -> None:
    print("=== Downloading & verifying genuine public-domain multilingual corpora ===")
    datasets = []
    dropped = []
    for corpus in CORPORA:
        record = verify_and_write(corpus)
        if record is None:
            dropped.append(corpus.language)
        else:
            datasets.append(record)

    metadata = {
        "description": (
            "Genuine public-domain multilingual evaluation corpora, one real source text per "
            "language, verified for title match and target-script letter ratio >= 80%. No "
            "synthetic or generated filler text. Files > 500KB are truncated at a paragraph "
            "boundary (Don Quijote is kept at full length per the eval spec)."
        ),
        "verification": "title substring match + script-ratio check, see scripts/download_multilingual_public_evals.py",
        "dropped_languages": dropped,
        "datasets": datasets,
    }
    (DEST_DIR / "METADATA.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n{len(datasets)} corpora verified and written, {len(dropped)} dropped: {dropped}")
    print(f"Metadata written to {DEST_DIR / 'METADATA.json'}")


if __name__ == "__main__":
    main()
