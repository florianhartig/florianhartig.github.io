#!/usr/bin/env python3
"""Copy publisher abstracts verbatim into bibliography/publications.bib.

Abstracts are never retyped by hand or by a language model: a model writing a
long text out drifts into paraphrase (an earlier check found many such
"abstracts"). This script copies the publisher's text from the Crossref API and
only where reuse is permitted:

  * the Crossref record carries a Creative Commons licence, or
  * the publisher allows authors to reuse unmodified abstracts (Wiley:
    "Authors may re-use unmodified abstracts for any non-commercial purpose",
    authors.wiley.com licensing FAQ), or
  * the journal is known to be CC-licensed although Crossref has no licence
    (PERMITTED_JOURNALS below), or
  * it is the site owner's own journal article, published more than 12 months ago:
    § 38 Abs. 4 UrhG gives authors of publicly funded research a
    non-waivable right to make the accepted manuscript publicly available
    after 12 months for non-commercial purposes, citing the source. The
    abstract in Crossref is the published wording, which normally matches
    the accepted manuscript; this site is non-commercial and links the DOI.

Everything else is reported as "manual": paste the original from the
publisher's page into the entry's `abstract = {...}` field yourself, then run
`--check` on it.

Usage:
  python3 scripts/fetch_abstract.py KEY [KEY ...]   copy where permitted
  python3 scripts/fetch_abstract.py --licenses [KEY ...]
                                                    write `license = {...}` from
                                                    Crossref (all entries with a
                                                    DOI if no keys)
  python3 scripts/fetch_abstract.py --check [KEY ...]
                                                    compare the .bib abstracts
                                                    with Crossref (all entries
                                                    if no keys); prints no text
Then run `python3 scripts/bib2content.py`.

JATS markup becomes plain text: section titles become "Title: ", citation-number
superscripts are dropped, other super/subscripts become Unicode where possible.
"""
from __future__ import annotations

import difflib
import html
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "bibliography" / "publications.bib"

PERMITTED_PUBLISHERS = {"Wiley": "Wiley author reuse of unmodified abstracts"}
PERMITTED_JOURNALS = {"Electronic Journal of Statistics": "CC BY 4.0 (IMS / Project Euclid)"}

SUP = str.maketrans("0123456789+-−=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ⁿ")
SUB = str.maketrans("0123456789+-−=()", "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎")
CITATION_MARK = re.compile(r"^[0-9,–\-\s]+$")
# A single-digit superscript right after a short unit (m², km², cm³, s²…) is an
# exponent, not a citation mark.
UNIT_BEFORE = re.compile(r"(?<![A-Za-z])(m|km|cm|mm|µm|ha|s|g|kg|l|L)$")


def is_citation_sup(before: str, t: str) -> bool:
    if not CITATION_MARK.match(t) or t.startswith(("-", "−")):
        return False
    return not (t.isdigit() and len(t) == 1 and UNIT_BEFORE.search(before))


def crossref(doi: str, tries: int = 4) -> dict:
    """Crossref sometimes drops connections under load; retry with a pause."""
    req = urllib.request.Request(
        f"https://api.crossref.org/works/{doi}",
        headers={"User-Agent": "florianhartig.github.io abstract check"},
    )
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())["message"]
        except Exception:
            if attempt == tries - 1:
                # Some proxies break Python's TLS reads; curl usually copes.
                out = subprocess.run(["curl", "-sf", "-m", "30", req.full_url],
                                     capture_output=True, check=True).stdout
                return json.loads(out)["message"]
            time.sleep(2 * (attempt + 1))


def jats_to_text(a: str) -> str:
    def script(m, table, sup):
        t = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if sup and is_citation_sup(m.string[:m.start()], t):
            return ""
        return t.translate(table)

    a = re.sub(r"^\s*<jats:title>\s*(Abstract|Summary)\s*</jats:title>", "", a.strip(), flags=re.I)
    a = re.sub(r"\s+(?=<(jats:)?su[pb]>)", "", a)
    a = re.sub(r"<(jats:)?sup>(.*?)</(jats:)?sup>", lambda m: script(m, SUP, True), a, flags=re.S)
    a = re.sub(r"<(jats:)?sub>(.*?)</(jats:)?sub>", lambda m: script(m, SUB, False), a, flags=re.S)
    a = re.sub(r"<jats:title>(.*?)</jats:title>\s*",
               lambda m: re.sub(r"\s+", " ", m.group(1)).strip() + ": ", a, flags=re.S)
    # Wiley wraps acronyms in <jats:styled-content style="fixed-case"> without
    # spaces around them in the deposit ("enhance<…>DVM</…>performance"); the
    # publisher page shows them as separate words.
    a = re.sub(r"(?<=\w)(<jats:styled-content[^>]*>)", r" \1", a)
    a = re.sub(r"(</jats:styled-content>)(?=\w)(?!s\b)", r"\1 ", a)
    a = re.sub(r"</jats:p>\s*", " ", a)
    a = html.unescape(re.sub(r"<[^>]+>", "", a))
    a = re.sub(r"\s+", " ", a).strip()
    a = re.sub(r"^(Abstract|Summary)[.:]?\s+", "", a)        # label inside the text
    # Wiley appends "<Journal> <year>;<vol>:<pages>. © <year> …" and sometimes a
    # graphical abstract after it: not part of the abstract proper.
    a = re.sub(r"\s*[A-Z][A-Za-z .&]*\s\d{4};\s?\d+(\(\d+\))?:\s?\d+[–-]\d+\.\s*©.*$", "", a)
    a = re.sub(r"\s*©\s?\d{4}\b.*$", "", a)
    a = re.sub(r"\(\s+", "(", a)
    return re.sub(r"\s+([.,;:)])", r"\1", a)


def comparable(t: str) -> str:
    """Dash-, quote- and markup-insensitive form for --check. Whitespace is
    collapsed, not removed, so words glued together are caught."""
    t = re.sub(r"\s+(?=<(jats:)?sup>)", "", t)
    t = re.sub(r"<(jats:)?sup>([0-9,–\-\s]+)</(jats:)?sup>",
               lambda m: "" if is_citation_sup(m.string[:m.start()], m.group(2).strip()) else m.group(2).strip(), t)
    t = re.sub(r"(?<=\w)(<jats:styled-content[^>]*>)", r" \1", t)
    t = re.sub(r"(</jats:styled-content>)(?=\w)(?!s\b)", r"\1 ", t)
    t = re.sub(r"\s+(?=<(jats:)?su[pb]>)", "", t)
    t = re.sub(r"</?(jats:)?(title|p|sec)\b[^>]*>", " ", t)   # block tags separate words
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"^\s*(a\s*bstract|summary)\b[.:]?", "", t.strip(), flags=re.I)
    # the same trailers jats_to_text drops (Wiley citation/copyright line)
    t = re.sub(r"\s*[A-Z][A-Za-z .&]*\s\d{4};\s?\d+(\(\d+\))?:\s?\d+[–-]\d+\.\s*©.*$", "", t, flags=re.S)
    t = re.sub(r"\s*©\s?\d{4}\b.*$", "", t, flags=re.S)
    t = re.sub(r"[‐-―−]|--", "-", t)
    t = re.sub(r"[‘’“”\"'`:{}\\]", "", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*([.,;()\[\]/-])\s*", r"\1", t)  # spacing around punctuation is markup noise
    return t.strip().lower()


def entries(text: str):
    for m in re.finditer(r"@\w+\{([^,\s]+),", text):
        end = text.index("\n}", m.start())
        yield m.group(1), m.start(), end


def field_span(body: str, name: str):
    m = re.search(r"\n(\s*)" + name + r"\s*=\s*\{", body)
    if not m:
        return None
    i, depth = m.end(), 1
    while depth:
        depth += {"{": 1, "}": -1}.get(body[i], 0)
        i += 1
    return m.end(), i - 1, m.group(1)


def permission(rec: dict) -> str | None:
    for lic in rec.get("license", []):
        if "creativecommons.org" in lic.get("URL", ""):
            return lic["URL"]
    publisher = rec.get("publisher", "")
    for name, why in PERMITTED_PUBLISHERS.items():
        if publisher.startswith(name):
            return why
    journal = (rec.get("container-title") or [""])[0]
    if journal in PERMITTED_JOURNALS:
        return PERMITTED_JOURNALS[journal]
    parts = (rec.get("published") or rec.get("issued") or {}).get("date-parts", [[None]])[0]
    if rec.get("type") == "journal-article" and parts and parts[0]:
        y, m, d = (parts + [1, 1])[:3]
        if (date.today() - date(y, m or 1, d or 1)).days > 365:
            return "§ 38 Abs. 4 UrhG (author's secondary publication right, > 12 months)"
    return None


def atomic_write(path: Path, text: str) -> None:
    """Write via a temporary file and rename, so a crash never leaves a half
    file. The temp file lives in the gitignored .claude/maintenance/tmp/ (same
    volume; no scratch files in the public repo folder)."""
    import os
    import tempfile
    tmpdir = ROOT / ".claude" / "maintenance" / "tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=tmpdir, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def license_label(rec: dict) -> str:
    """Short licence label for the .bib: "CC BY 4.0" etc. for Creative Commons
    licences in the Crossref record, else the publisher's terms. A CC licence
    deposited only for the accepted manuscript ("am") does not count."""
    for lic in rec.get("license", []):
        if lic.get("content-version") not in (None, "vor", "unspecified"):
            continue
        m = re.search(r"creativecommons\.org/licenses/([a-z-]+)/([0-9.]+)", lic.get("URL", ""))
        if m:
            return f"CC {m.group(1).upper()} {m.group(2)}"
    journal = (rec.get("container-title") or [""])[0]
    if journal in PERMITTED_JOURNALS:
        return PERMITTED_JOURNALS[journal].split(" (")[0]
    return "publisher (subscription)"


def set_field(body: str, name: str, value: str) -> str:
    span = field_span(body, name)
    if span:
        return body[:span[0]] + value + body[span[1]:]
    return body.rstrip().rstrip(",") + f",\n  {name} = {{{value}}},"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    licenses = "--licenses" in argv
    keys = [a for a in argv if not a.startswith("--")]
    text = BIB.read_text(encoding="utf-8")
    todo = [(k, s, e) for k, s, e in entries(text) if not keys or k in keys]
    if keys and len(todo) != len(set(keys)):
        print("unknown key(s):", sorted(set(keys) - {k for k, _, _ in todo}))
    for key, start, end in reversed(todo):
        body = text[start:end]
        doi_span = field_span(body, "doi")
        if not doi_span:
            print(f"{key}: no DOI — manual")
            continue
        doi = body[doi_span[0]:doi_span[1]].strip()
        try:
            rec = crossref(doi)
        except Exception as err:  # network, 404, ...
            print(f"{key}: Crossref lookup failed ({err})")
            continue
        if licenses:
            new, span = license_label(rec), field_span(body, "license")
            cur = body[span[0]:span[1]].strip() if span else ""
            # Never downgrade a CC licence because Crossref lacks a record (e.g.
            # hartig2015dale, CC BY 4.0 per eScholarship): report it instead.
            if cur.startswith("CC") and not new.startswith("CC"):
                print(f"{key}: kept {cur!r} (Crossref says {new!r}) — check the publisher page")
                continue
            text = text[:start] + set_field(body, "license", new) + text[end:]
            print(f"{key}: {new}")
            continue
        source = rec.get("abstract")
        span = field_span(body, "abstract")
        if check:
            if not source:
                print(f"{key}: no Crossref abstract — check against the publisher page")
            elif not span:
                print(f"{key}: no abstract in .bib")
            else:
                a, b = comparable(body[span[0]:span[1]]), comparable(source)
                ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
                print(f"{key}: {'OK' if a == b else f'DIFFERS (similarity {ratio:.3f})'}")
            continue
        why = permission(rec)
        if not why:
            print(f"{key}: reuse not permitted automatically — paste it yourself: https://doi.org/{doi}")
            continue
        if not source:
            print(f"{key}: permitted ({why}) but Crossref has no abstract — copy from https://doi.org/{doi}")
            continue
        abstract = jats_to_text(source)
        if re.search(r"[{}\\]", abstract):
            print(f"{key}: abstract contains braces/backslashes — manual")
            continue
        if span:
            body = body[:span[0]] + abstract + body[span[1]:]
        else:
            body = body.rstrip().rstrip(",") + f",\n  abstract = {{{abstract}}},"
        text = text[:start] + body + text[end:]
        print(f"{key}: copied ({why})")
    if not check:
        atomic_write(BIB, text)
        if licenses:
            print("licences written; run scripts/bib2content.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
