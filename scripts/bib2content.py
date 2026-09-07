#!/usr/bin/env python3
"""Generate content/publications/*.md from bibliography/publications.bib.

This replaces the BibTeX import that the HugoBlox academic-cv theme would have
provided, and keeps the same workflow the handoff asked for: export a fresh
.bib from Google Scholar / ORCID / Scopus over the seed file, re-run this, get
an up-to-date publication list.

    python3 scripts/bib2content.py

Generated files are overwritten on every run and the whole output directory is
cleared first, so deletions in the .bib propagate. Do not hand-edit the
generated markdown; edit the .bib instead.

An optional `abstract = {...}` field becomes a real "## Abstract" section in
the page body, a front-matter field (so schema.html can put the full text into
the page's JSON-LD `abstract` property), and the source for a separately
truncated meta description (see `meta_description()` — search engines cut
descriptions at ~155-160 chars anyway, so the full text there would be dead
weight). JATS/XML tags (as raw Crossref API responses wrap abstracts in
`<jats:p>...</jats:p>`) are stripped automatically.

An optional `significance = {...}` field is a short, hand-written "why it
matters" note — never sourced from an API, always written by whoever is
maintaining this file, in plain language for a non-specialist reader. Renders
under the abstract (or as the sole body content, and the meta description, if
there is no abstract).

Deliberately dependency-free (no bibtexparser) so it runs on a bare Python 3
with no network access.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "bibliography" / "publications.bib"
OUT = ROOT / "content" / "publications"

# The generated files live alongside the hand-written _index.md, so the output
# directory is cleaned selectively rather than wholesale.
KEEP = {"_index.md"}

# LaTeX escapes that actually occur in exported .bib files. Applied longest-key
# first so that e.g. {\"u} wins over a bare " match.
LATEX = {
    r"{\"a}": "ä", r"{\"o}": "ö", r"{\"u}": "ü",
    r"{\"A}": "Ä", r"{\"O}": "Ö", r"{\"U}": "Ü",
    r"{\"i}": "ï", r"{\"e}": "ë", r"{\"E}": "Ë",
    r"{\'a}": "á", r"{\'e}": "é", r"{\'i}": "í", r"{\'o}": "ó", r"{\'u}": "ú",
    r"{\'c}": "ć", r"{\'n}": "ń", r"{\'s}": "ś", r"{\'z}": "ź",
    r"{\'A}": "Á", r"{\'E}": "É", r"{\'I}": "Í", r"{\'O}": "Ó", r"{\'U}": "Ú",
    r"{\`a}": "à", r"{\`e}": "è", r"{\`i}": "ì", r"{\`o}": "ò", r"{\`u}": "ù",
    r"{\^a}": "â", r"{\^e}": "ê", r"{\^i}": "î", r"{\^o}": "ô", r"{\^u}": "û",
    r"{\~n}": "ñ", r"{\~a}": "ã", r"{\~o}": "õ",
    r"{\c c}": "ç", r"{\c{c}}": "ç",
    r"{\v s}": "š", r"{\v{s}}": "š", r"{\v c}": "č", r"{\v{c}}": "č",
    r"{\v C}": "Č", r"{\v{C}}": "Č", r"{\v S}": "Š", r"{\v{S}}": "Š",
    r"{\o}": "ø", r"{\O}": "Ø", r"{\aa}": "å", r"{\AA}": "Å",
    r"{\ss}": "ß", r"{\ae}": "æ", r"{\l}": "ł", r"{\L}": "Ł",
    r"\&": "&", r"\%": "%", r"\_": "_", r"\$": "$", r"\#": "#",
    "---": "—", "--": "–",
    "``": "“", "''": "”",
}


def strip_comments(text: str) -> str:
    """Drop whole-line BibTeX comments (a leading %)."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("%")
    )


def detex(value: str) -> str:
    for key in sorted(LATEX, key=len, reverse=True):
        value = value.replace(key, LATEX[key])
    # Remaining braces are BibTeX capitalisation guards, not content.
    value = value.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", value).strip()


def clean_abstract(value: str) -> str:
    """Crossref abstracts often arrive as JATS XML (`<jats:p>...</jats:p>`),
    sometimes with JSON-escaped slashes (`\\/`) left over from a raw API
    response. Strip both before the text goes anywhere near YAML or Markdown.
    Nested tags (e.g. `<jats:italic>`) that border punctuation leave a stray
    space behind once stripped (" obsoletus , but" from "obsoletus</jats:italic>,
    but"); collapse that before it reaches the page."""
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\\/", "/")
    value = re.sub(r"\s+([.,;:])", r"\1", value)
    return detex(value)


def split_entries(text: str):
    """Yield (entry_type, body) for each @type{...} block, matching braces."""
    for match in re.finditer(r"@(\w+)\s*\{", text):
        start = match.end()
        depth = 1
        i = start
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        if depth:
            raise ValueError(f"unbalanced braces in entry starting at {match.start()}")
        yield match.group(1).lower(), text[start : i - 1]


def parse_fields(body: str):
    """Split an entry body into its citation key and a field dict."""
    key, _, rest = body.partition(",")
    fields = {}
    i = 0
    while i < len(rest):
        m = re.compile(r"\s*(\w+)\s*=\s*").match(rest, i)
        if not m:
            break
        name = m.group(1).lower()
        i = m.end()
        if i >= len(rest):
            break
        if rest[i] == "{":
            depth, j = 1, i + 1
            while j < len(rest) and depth:
                if rest[j] == "{":
                    depth += 1
                elif rest[j] == "}":
                    depth -= 1
                j += 1
            raw, i = rest[i + 1 : j - 1], j
        elif rest[i] == '"':
            j = rest.index('"', i + 1)
            raw, i = rest[i + 1 : j], j + 1
        else:
            j = rest.find(",", i)
            j = len(rest) if j < 0 else j
            raw, i = rest[i:j], j
        fields[name] = raw.strip()
        comma = rest.find(",", i)
        i = len(rest) if comma < 0 else comma + 1
    return key.strip(), fields


def parse_authors(raw: str):
    """Return (named_authors, display_string).

    BibTeX's `and others` is kept out of the named list — it is not a person,
    and it must not end up in the JSON-LD author array. It becomes an ellipsis
    in the display string, in the position it occupied, so that a middle-of-list
    truncation still reads correctly.
    """
    names, display = [], []
    for token in re.split(r"\s+and\s+", raw):
        token = detex(token).strip()
        if not token:
            continue
        if token.lower() == "others":
            display.append("…")
            continue
        if "," in token:
            last, _, first = token.partition(",")
            token = f"{first.strip()} {last.strip()}".strip()
        names.append(token)
        display.append(token)
    return names, ", ".join(display)


def yaml_quote(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def meta_description(value: str, limit: int = 155) -> str:
    """Search engines truncate meta descriptions at ~155-160 chars anyway, so
    a full abstract or significance note is mostly dead weight there — cut at
    a word boundary and mark the cut, rather than dumping the whole text in."""
    value = value.strip()
    if len(value) <= limit:
        return value
    truncated = value[:limit]
    cut = truncated.rfind(" ")
    if cut > 0:
        truncated = truncated[:cut]
    return truncated.rstrip(",.;:—–- ") + "…"


def main() -> int:
    if not BIB.exists():
        print(f"error: {BIB} not found", file=sys.stderr)
        return 1

    text = strip_comments(BIB.read_text(encoding="utf-8"))

    OUT.mkdir(parents=True, exist_ok=True)
    for path in OUT.iterdir():
        if path.name in KEEP:
            continue
        shutil.rmtree(path) if path.is_dir() else path.unlink()

    count = 0
    # `weight` preserves the .bib's own ordering. Every entry in a year shares
    # the same date, so date sorting alone leaves within-year order undefined —
    # the templates sort ByWeight and group on the `year` param instead.
    for weight, (entry_type, body) in enumerate(split_entries(text), start=1):
        key, fields = parse_fields(body)
        title = detex(fields.get("title", "")) or key
        year = re.sub(r"\D", "", fields.get("year", ""))[:4]
        names, display = parse_authors(fields.get("author", ""))

        lines = [
            "---",
            "# Generated by scripts/bib2content.py — edit the .bib, not this file.",
            f"title: {yaml_quote(title)}",
            f"date: {year or '1970'}-01-01",
            f"year: {yaml_quote(year)}",
            f"weight: {weight}",
            f"slug: {yaml_quote(key)}",
        ]
        # `featured = {true}` in the .bib promotes an entry to the homepage's
        # selected-publications block. Emitted unquoted so Hugo sees a boolean.
        if fields.get("featured", "").strip().lower() in {"true", "yes", "1"}:
            lines.append("featured: true")
        if names:
            lines.append("authors:")
            lines += [f"  - {yaml_quote(n)}" for n in names]
            lines.append(f"authors_display: {yaml_quote(display)}")
        for bib_field, fm_field in (
            ("journal", "journal"),
            ("booktitle", "journal"),
            ("volume", "volume"),
            ("number", "issue"),
            ("pages", "pages"),
            ("publisher", "publisher"),
            ("doi", "doi"),
            # Not `url`: that is a reserved Hugo front-matter key and would
            # rewrite the page's own permalink to the publisher's domain.
            ("url", "publisher_url"),
            ("preprint", "preprint"),
            ("note", "note"),
        ):
            value = fields.get(bib_field)
            if value and not any(l.startswith(f"{fm_field}:") for l in lines):
                lines.append(f"{fm_field}: {yaml_quote(detex(value))}")

        # A paper whose `journal`/`booktitle` IS a preprint server's own name
        # (arXiv, bioRxiv, medRxiv, EcoEvoRxiv, "PeerJ Preprints", ...) has
        # never been journal-published — computed from that one field so it
        # can't drift out of sync: the moment an entry's journal is updated to
        # the real venue (as happened for barth2026efficiency, once its
        # bioRxiv preprint was accepted by New Phytologist), it stops being
        # flagged automatically, with no second field to remember to update.
        journal_value = fields.get("journal") or fields.get("booktitle") or ""
        if re.search(r"rxiv|preprint", journal_value, re.IGNORECASE):
            lines.append("is_preprint: true")

        # `abstract` renders as real body content ("## Abstract") — not just
        # SEO plumbing. It is kept in full there; the meta description below
        # is a separately truncated summary, not this text dumped whole. It is
        # also emitted as a front-matter field so schema.html can put the full
        # text into the page's JSON-LD `abstract` property.
        abstract = fields.get("abstract")
        if abstract:
            abstract = clean_abstract(abstract)
            lines.append(f"abstract: {yaml_quote(abstract)}")

        # `significance` is a short, plain-language "why it matters" note,
        # written by hand (not sourced from Crossref) for every entry —
        # renders under the abstract as its own section. For the entries with
        # no abstract, it is also the basis for the meta description, since it
        # is still unique per-page text rather than the site-wide fallback.
        significance = fields.get("significance")
        if significance:
            significance = clean_abstract(significance)
            lines.append(f"significance: {yaml_quote(significance)}")

        # Meta description is a short, truncated summary — not the full
        # abstract/significance text, which search engines cut at ~155-160
        # chars anyway. Prefers `significance`: it's paper-specific from the
        # first word, whereas an abstract's opening is usually generic
        # scene-setting that identifies nothing once cut at 155 chars (e.g.
        # "Understanding the origins of biodiversity has been an aspiration
        # since the days of early naturalists…"). Falls back to the abstract
        # only for the handful of entries predating the significance field.
        description_source = significance or abstract
        if description_source:
            lines.append(f"description: {yaml_quote(meta_description(description_source))}")

        lines.append(f"entry_type: {yaml_quote(entry_type)}")
        lines.append("---")
        if abstract:
            lines += ["", "## Abstract", "", abstract]
        lines.append("")

        (OUT / f"{key}.md").write_text("\n".join(lines), encoding="utf-8")
        count += 1

    print(f"wrote {count} publication page(s) to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
