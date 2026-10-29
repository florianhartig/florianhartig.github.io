#!/usr/bin/env python3
"""Reference data for the works cited in the significance notes.

A note that places a paper in its field cites other work in author–year form
("Gotelli et al. (2009)"); the cited works are listed by DOI in the entry's
`significance_refs = {DOI DOI|a …}` field of the .bib, separated by whitespace
(DOIs never contain whitespace but may contain ";"), in order of first mention;
`|a`, `|b`: year suffix when a note cites two works with the same author–year
label. This script fetches the metadata of every such DOI from Crossref, once,
and stores it in data/note_refs.yaml, so the site build stays offline and the
reference list shows the registered metadata rather than retyped text. The page
template fails the build if a cited DOI is missing from that file, and
check_site.py checks that every listed reference is cited in the text and vice
versa. data/note_refs.yaml must be committed with the .bib.

    python3 scripts/note_refs.py            # add missing DOIs
    python3 scripts/note_refs.py --refresh  # re-fetch all

No API key, no e-mail address and no personal data are sent.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_abstract as fa  # noqa: E402  (entries, field_span, atomic_write, ROOT)

BIB = fa.ROOT / "bibliography" / "publications.bib"
OUT = fa.ROOT / "data" / "note_refs.yaml"
UA = "florianhartig.github.io note_refs script"
TAG = re.compile(r"</?[A-Za-z][\w:.-]*(?:\s[^<>]*)?/?>")   # real tags only (as in bib2content)


def split_refs(raw: str) -> list[str]:
    raw = re.sub(r"\s*\|\s*", "|", raw)
    return [re.sub(r"^https?://(dx\.)?doi\.org/", "", r, flags=re.I) for r in raw.split()]


def cited_dois(text: str) -> list[str]:
    dois = []
    for _, start, end in fa.entries(text):
        body = text[start:end]
        span = fa.field_span(body, "significance_refs")
        if span:
            for item in split_refs(body[span[0]:span[1]]):
                doi = item.split("|")[0].lower()
                if doi and doi not in dois:
                    dois.append(doi)
    return dois


CORPORATE = {"European Food Safety Authority": "EFSA"}


def clean(s: str) -> str:
    # Some deposits glue a word to a following italic name ("on<i>Pinus").
    s = re.sub(r"(?<=\w)<(i|em|b|scp)>", r" <\1>", s or "")
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", s))).strip()


def crossref(doi: str) -> dict | None:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
    try:
        out = subprocess.run(["curl", "-sSL", "--fail", "-g", "-m", "30", "--retry", "3", "-A", UA, url],
                             capture_output=True, text=True, check=True).stdout
        m = json.loads(out)["message"]
    except (subprocess.CalledProcessError, ValueError, KeyError) as e:
        # DOIs from other registries (DataCite: arXiv, Zenodo) — CSL-JSON via doi.org content negotiation,
        # which has the same field names as Crossref's records.
        try:
            out = subprocess.run(["curl", "-sSL", "--fail", "-g", "-m", "30", "--retry", "3", "-A", UA, "-H",
                                  "Accept: application/vnd.citationstyles.csl+json",
                                  "https://doi.org/" + urllib.parse.quote(doi, safe="/")],
                                 capture_output=True, text=True, check=True).stdout
            m = json.loads(out)
            if isinstance(m.get("title"), str):
                m["title"] = [m["title"]]
            if isinstance(m.get("container-title"), str):
                m["container-title"] = [m["container-title"]]
        except (subprocess.CalledProcessError, ValueError, KeyError):
            print(f"  {doi}: Crossref and doi.org lookups failed ({e.__class__.__name__}) — not written")
            return None
    people = m.get("author") or m.get("editor") or []
    # Some records are in capitals (Biometrika 1957: "LINDLEY", "A STATISTICAL PARADOX").
    authors = [(lambda n: n.title() if n.isupper() else n)(clean(a.get("family") or a.get("name") or a.get("given") or ""))
               for a in people]
    authors = [a for a in authors if a]
    # Corporate first author (EFSA guidance documents): cite by its short name alone, as the note does.
    if authors:
        abbr = re.search(r"\(([A-Z]{2,})\)$", authors[0])
        name = re.sub(r"\s*\([A-Z]{2,}\)$", "", authors[0])
        if abbr or name in CORPORATE:
            authors = [abbr.group(1) if abbr else CORPORATE[name]]
    year = ((m.get("published-print") or m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    title = clean((m.get("title") or [""])[0])
    sub = clean((m.get("subtitle") or [""])[0])
    if sub and sub.lower() not in title.lower():
        title = f"{title}: {sub}"
    if title.isupper():
        title = title.capitalize()
    rec = {
        "authors": authors,
        "year": year,
        "title": title,
        "container": clean((m.get("container-title") or [""])[0]),
        "volume": m.get("volume", ""),
        "pages": (m.get("page") or m.get("article-number") or "").replace("-", "–"),
    }
    if not (authors and year and title):
        print(f"  {doi}: incomplete Crossref record (authors/year/title) — not written; check by hand")
        return None
    return rec


def q(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def main(argv: list[str]) -> int:
    dois = cited_dois(BIB.read_text(encoding="utf-8"))
    old = {}
    if OUT.exists() and "--refresh" not in argv:
        # The file is written by this script only: one JSON object per DOI line.
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.startswith('"'):
                k, v = line.split(": ", 1)
                old[json.loads(k)] = json.loads(v)
    data, failed = {}, []
    for d in dois:
        rec = old.get(d) or crossref(d)
        if rec:
            data[d] = rec
        else:
            failed.append(d)
    lines = ["# Generated by scripts/note_refs.py from Crossref — do not edit by hand.",
             "# Works cited in the significance notes (bib field `significance_refs`)."]
    lines += [f"{q(d)}: {q(v)}" for d, v in sorted(data.items())]
    fa.atomic_write(OUT, "\n".join(lines) + "\n")
    new = [d for d in data if d not in old]
    print(f"{len(data)} DOI(s) in {OUT.relative_to(fa.ROOT)}; fetched: {', '.join(new) or 'none'}")
    if failed:
        print(f"FAILED (the build will stop on these until fixed): {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
