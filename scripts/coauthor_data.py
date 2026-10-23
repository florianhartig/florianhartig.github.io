"""Read and write the co-author records — one record per co-author.

Two files (research notes about people must not go into the public repo):
  - data/coauthors.yaml — public, only what the page shows: id, name, aliases,
    n, papers and, for mapped people, institution, city, country, lat, lon, x, y;
  - .claude/maintenance/coauthors.json — private (gitignored): ORCID,
    OpenAlex id, where the location comes from, notes, location_fixed, …
read() merges both; write() splits them again.

The file is shared by two scripts and may be edited by hand:
  - bib2content.py writes id, name, aliases, n, papers (from the .bib) on
    every run and keeps every other field of a record;
  - coauthor_locations.py writes orcid, openalex and the location fields,
    unless the record has `location_fixed: true` (checked by hand).

Format (kept simple so it can be read without a YAML library): top-level
scalars and lists, then `people:` with one block per person; every value is
written in JSON notation (strings in double quotes, lists in brackets), which
is also valid YAML. Hand edits must keep that notation.

  people:
    - id: "dormann-c"                  family name + first initial, accents folded
      name: "Carsten F. Dormann"       shown name (fullest spelling)
      aliases: ["Carsten Dormann"]     other spellings found in the .bib
      n: 13                            joint publications
      papers: ["dormann2026full", …]   their .bib keys, newest first
      orcid: "0000-…"                  from OpenAlex, if known
      openalex: "A…"                   OpenAlex author id
      institution / city / country / lat / lon / x / y
                                       last known location (x, y: map coordinates)
      location_basis: "…"              where the location comes from
      location_as_of: "2026-10-18"
      location_fixed: true             optional: hand-checked, scripts keep it
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "coauthors.yaml"
PRIVATE = ROOT / ".claude" / "maintenance" / "coauthors.json"
BIB_FIELDS = ("id", "name", "aliases", "n", "papers")
PUBLIC_LOC = ("institution", "city", "country", "lat", "lon", "x", "y")
PUBLIC_TOP = ("count", "located", "locations_as_of", "merge")
# Letters that NFD does not decompose (ids must stay ASCII and stable).
TRANSLIT = str.maketrans({"æ": "ae", "ø": "o", "ß": "ss", "ł": "l", "đ": "d", "þ": "th", "œ": "oe"})
HEADER = [
    "# Co-authors of Florian Hartig, one record per person (see scripts/coauthor_data.py).",
    "# id/name/aliases/n/papers: written by scripts/bib2content.py from the .bib.",
    "# institution … y: last known institution (mapped people only). Sources, notes and",
    "# ORCIDs are kept privately in .claude/maintenance/coauthors.json (not in the repo).",
    "# Values in JSON notation; hand edits must keep it.",
]


def fold(s: str) -> str:
    s = s.lower().translate(TRANSLIT)
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def make_id(family: str, initial: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", fold(family)).strip("-")
    return f"{slug}-{fold(initial)[:1]}" if initial else slug


def read() -> tuple[dict, list[dict]]:
    """(top-level fields, people): data/coauthors.yaml merged with the private file."""
    top, people = _read_public()
    if PRIVATE.exists():
        priv = json.loads(PRIVATE.read_text(encoding="utf-8"))
        top.update(priv.get("top", {}))
        for p in people:
            p.update(priv.get("people", {}).get(p["id"], {}))
    return top, people


def _read_public() -> tuple[dict, list[dict]]:
    if not PATH.exists():
        return {}, []
    top, people, cur, in_people = {}, [], None, False
    for line in PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line == "people:":
            in_people = True
            continue
        if not in_people:
            if m := re.match(r"^(\w+):\s*(.*)$", line):
                top[m.group(1)] = json.loads(m.group(2)) if m.group(2) else None
            continue
        if m := re.match(r"^  - (\w+): (.*)$", line):
            cur = {m.group(1): json.loads(m.group(2))}
            people.append(cur)
        elif cur is not None and (m := re.match(r"^    (\w+): (.*)$", line)):
            cur[m.group(1)] = json.loads(m.group(2))
    return top, people


def write(top: dict, people: list[dict]) -> None:
    import fetch_abstract  # atomic_write
    if PATH.exists() and not PRIVATE.exists():
        raise SystemExit(f"{PRIVATE} is missing — refusing to write {PATH}: the hand-checked "
                         "locations and notes would be lost. Restore it from a backup first.")
    q = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    out = HEADER[:]
    for k in PUBLIC_TOP:
        if k in top:
            out.append(f"{k}: {q(top[k])}")
    out.append("people:")
    priv_people = {}
    for p in people:
        mapped = "lat" in p
        pub = [k for k in BIB_FIELDS if k in p] + ([k for k in PUBLIC_LOC if k in p] if mapped else [])
        out.append(f"  - {pub[0]}: {q(p[pub[0]])}")
        out += [f"    {k}: {q(p[k])}" for k in pub[1:]]
        rest = {k: v for k, v in p.items() if k not in pub}
        if rest:
            priv_people[p["id"]] = rest
    PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    fetch_abstract.atomic_write(PRIVATE, json.dumps({"top": {k: v for k, v in top.items() if k not in PUBLIC_TOP},
                                                     "people": priv_people}, ensure_ascii=False, indent=1) + "\n")
    fetch_abstract.atomic_write(PATH, "\n".join(out) + "\n")
