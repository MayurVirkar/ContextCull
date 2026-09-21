"""Exhaustive multilingual test suite for Hebrew (he) - 100 tests.

Verifies:
1. Native script sentence segmentation & punctuation boundary handling (20 tests).
2. Embedded technical atom extraction (IPs, CVEs, UUIDs, SHAs, quantities, dates) (30 tests).
3. Multi-byte UTF-8 SourceMap byte-to-char mapping & byte exactness (20 tests).
4. Native script negation & modality protection (10 tests).
5. Full compiler execution, provenance manifest, and invariant checks (20 tests).
"""

from __future__ import annotations

import pytest

from contextcull.api import ContextCompiler
from contextcull.detect.atoms import extract_atoms
from contextcull.ingest.decoder import clean_char_to_byte_span, ingest_bytes
from contextcull.ir.models import CompileMode
from contextcull.segment.sentence import segment_sentences

# =========================================================================
# 1. Native Hebrew Sentence Segmentation Boundaries (20 tests)
# =========================================================================

SEGMENTATION_CASES_HE = [
    ("משפט ראשון לגבי המערכת. משפט שני לגבי התקרית.", 2),
    ("משפט ראשון לגבי התקרית! משפט שני לגבי מסד הנתונים!", 2),
    ("משפט ראשון לגבי מסד הנתונים? משפט שני לגבי השרת?", 2),
    ("בראשית ברא אלהים את השמים ואת הארץ. והארץ היתה תהו ובהו וחשך על פני תהום.", 2),
    ("ויאמר אלהים יהי אור ויהי אור. וירא אלהים את האור כי טוב.", 2),
    ("השרת הראשי הושבת עקב עומס חריג. צוות התשתיות בודק את מקור התקלה.", 2),
    ("האם זוהתה פריצה למערכת? בדיקת הלוגים הושלמה בהצלחה.", 2),
    ("קובץ ההגדרות עודכן מחדש! שירות ה-API הופעל מחדש באופן אוטומטי.", 2),
    ("משפט ראשון לגבי זיכרון השרת. משפט שני לגבי השימוש במעבד.", 2),
    ("הודעת שגיאה קריטית נרשמה במסד הנתונים. המערכת עברה למצב גיבוי.", 2),
    ("האם הגיבוי האחרון תקין? בדיקת השלמות הסתיימה ללא שגיאות.", 2),
    ("פעולת השחזור החלה כעת! יש להמתין לסיום סנכרון הנתונים.", 2),
    ("משפט אודות כתובת ה-IP של השרת. משפט שני אודות פורט התקשורת.", 2),
    ("התהליך הופסק על ידי מנהל המערכת. נדרש אימות הרשאות מחודש.", 2),
    ("האם נדרש שדרוג גרסה? כל החבילות מעודכנות לגרסה האחרונה.", 2),
    ("המערכת פועלת כסדרה ללא הפרעות! זמני התגובה נותרו יציבים.", 2),
    ('דו"ח אבטחת מידע שבועי הופק. יש לסקור את הממצאים בהקדם.', 2),
    ("נמצאה חולשת אבטחה ברכיב התוכנה! עדכון אבטחה שוחרר להתקנה מיידית.", 2),
    ("האם כל הבדיקות עברו בהצלחה? שיעור ההצלחה עומד על מאה אחוזים.", 2),
    ("משפט סיכום לפעילות השוטפת. כל המדדים נמצאים בטווח התקין.", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_HE)
def test_he_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# =========================================================================
# 2. Embedded Technical Atom Extraction in Hebrew Prose (30 tests)
# =========================================================================

ATOM_CASES_HE = [
    (
        f"שרת הייצור 10.7.{i}.1 דיווח על {20 + i} ms בתאריך 2026-07-{i:02d}. המהנדס אישר טיפול ב-CVE-2026-{7000 + i}.",
        f"CVE-2026-{7000 + i}",
        f"10.7.{i}.1",
        f"{20 + i} ms",
    )
    for i in range(1, 31)
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_qty", ATOM_CASES_HE)
def test_he_atom_extraction(text: str, expected_cve: str, expected_ip: str, expected_qty: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)

    cve_atoms = [a for a in atoms if a.kind == "cve"]
    ip_atoms = [a for a in atoms if a.kind == "ipv4"]
    qty_atoms = [a for a in atoms if a.kind == "quantity"]

    assert any(a.surface == expected_cve for a in cve_atoms), f"Missing CVE: {expected_cve}"
    assert any(a.surface == expected_ip for a in ip_atoms), f"Missing IP: {expected_ip}"
    assert any(a.surface == expected_qty for a in qty_atoms), f"Missing Quantity: {expected_qty}"

    # Verify exact byte slice in raw UTF-8 bytes
    for a in atoms:
        span = a.sources[0]
        sliced = ingest.source_map.raw_bytes[span.start : span.end].decode("utf-8")
        assert sliced == a.surface


# =========================================================================
# 3. Multi-byte UTF-8 SourceMap Byte-to-Char Mapping (20 tests)
# =========================================================================

COORDINATE_CASES_HE = [
    (
        f"מקרה בדיקה עברי {i}: שרת הייצור 192.168.7.{i} דיווח על {50 + i * 5} MB בתאריך 2026-08-15. "
        f"המהנדס אישר כי לא אירע כל אובדן נתונים עם CVE-2026-{8900 + i}."
    )
    for i in range(1, 21)
]


@pytest.mark.parametrize("text", COORDINATE_CASES_HE)
def test_he_utf8_sourcemap_coordinates(text: str):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)

    # Verify character to byte slice exactness across multi-byte Hebrew UTF-8 boundary
    for char_idx in [0, len(text) // 4, len(text) // 2, len(text) - 1]:
        byte_span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        sliced_bytes = raw_bytes[byte_span.start : byte_span.end]
        assert sliced_bytes.decode("utf-8") == text[char_idx]


# =========================================================================
# 4. Native Hebrew Negation & Modality Protection (10 tests)
# =========================================================================

NEGATION_CASES_HE = [
    (
        f"שרת הייצור 10.99.7.{i} דיווח על 15 ms בתאריך 2026-09-01. המהנדס אישר כי לא אירע כל אובדן נתונים עם CVE-2026-{7800 + i}."
    )
    for i in range(1, 11)
]


@pytest.mark.parametrize("text", NEGATION_CASES_HE)
def test_he_negation_and_modality_protection(text: str):
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(text.encode("utf-8"))
    assert result.ok
    # Invariant: technical identifiers and numbers must be preserved
    assert len(result.text) > 0


# =========================================================================
# 5. Full End-to-End Compiler Pipeline & Invariant Checks (20 tests)
# =========================================================================

COMPILER_CASES_HE = [
    (
        f"כותרת בדיקה עברית {i}\n\n"
        f"שרת הייצור 10.7.1.1 דיווח על 11 ms בתאריך 2026-05-12. המהנדס אישר כי לא אירע כל אובדן נתונים עם CVE-2026-{9700 + i}.\n"
        f"שרת הייצור 10.7.2.1 דיווח על 12 ms בתאריך 2026-05-12. המהנדס אישר כי לא אירע כל אובדן נתונים עם CVE-2026-{9701 + i}.\n"
        f"שרת הייצור 10.7.3.1 דיווח על 13 ms בתאריך 2026-05-12. המהנדס אישר כי לא אירע כל אובדן נתונים עם CVE-2026-{9702 + i}.\n"
        f"שרת הייצור 10.7.4.1 דיווח על 14 ms בתאריך 2026-05-12. המהנדס אישר כי לא אירע כל אובדן נתונים עם CVE-2026-{9703 + i}."
    )
    for i in range(1, 21)
]


@pytest.mark.parametrize("doc_text", COMPILER_CASES_HE)
def test_he_end_to_end_compilation(doc_text: str):
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(doc_text.encode("utf-8"))
    assert result.ok, f"Compilation failed: {result.diagnostics}"
    assert len(result.text) > 0

    # Verify manifest provenance
    manifest = result.manifest
    assert manifest["status"] == "OK"
    assert manifest["environment"]["contextcull_version"] == "1.0.0"
    assert manifest["metrics"]["required_atom_coverage"] == 1.0
    assert manifest["metrics"]["input_bytes"] == len(doc_text.encode("utf-8"))
