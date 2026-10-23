#!/usr/bin/env python3
"""Keep a private reading copy of a paper's full text for writing and checking
the significance notes (saves re-downloading).

Output, gitignored, never published:
  .claude/fulltexts/<key>.md          header (source, version, licence, date,
                                      sha256) + text with section headings and
                                      figure captions, tables and boxes; the
                                      reference list is kept (in manuscripts,
                                      captions and boxes come after it)
  .claude/fulltexts/<key>/fig-*.png   figures (PMC: the published images; PDF:
                                      the embedded raster images — vector
                                      figures are not extracted)

Usage:
  python3 scripts/fulltext.py KEY --pmc PMCID   --version "published" --license "CC BY 4.0"
  python3 scripts/fulltext.py KEY --pdf PATH|URL --version "accepted manuscript" [--license …] [--source URL]
  python3 scripts/fulltext.py KEY --text FILE   --version … --source URL   (text saved from a browser)
No API key and no personal data are sent; downloads identify as this script, without contact data.
"""
from __future__ import annotations

import hashlib
import html
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_abstract as fa  # noqa: E402  (atomic_write, ROOT)

OUT = fa.ROOT / ".claude" / "fulltexts"
# An honest, contact-free identifier, not a spoofed browser.
UA = "florianhartig.github.io fulltext script"


def fetch(url: str, dest: Path, ua: str = UA) -> None:
    subprocess.run(["curl", "-sSL", "--fail", "--retry", "3", "--retry-all-errors", "-A", ua, "-o", str(dest), url], check=True)


def opt(argv: list[str], flag: str, default: str = "") -> str:
    return argv[argv.index(flag) + 1] if flag in argv else default


def jats_text(el: ET.Element) -> str:
    """Plain text of a JATS element; reference citations as [label] so they
    are not mistaken for numbers of the text."""
    s = ET.tostring(el, encoding="unicode")
    s = re.sub(r"<(table-wrap|fig|supplementary-material|boxed-text)\b.*?</\1>", "", s, flags=re.S)
    s = re.sub(r'<xref[^>]*ref-type="bibr"[^>]*>(.*?)</xref>', r"[\1]", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def from_pmc(pmcid: str, figdir: Path) -> str:
    pmcid = pmcid.upper().removeprefix("PMC")
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "a.xml"
        fetch(f"https://www.ebi.ac.uk/europepmc/webservices/rest/PMC{pmcid}/fullTextXML", xml)
        root = ET.parse(xml).getroot()
    out = []
    body = root.find(".//body")

    def walk(sec: ET.Element, depth: int) -> None:
        for child in sec:
            tag = child.tag
            if tag == "title" and depth:
                out.append("\n" + "#" * min(depth + 1, 4) + " " + jats_text(child) + "\n")
            elif tag == "p":
                txt = jats_text(child)
                if txt:
                    out.append(txt + "\n")
                for fig in child.iter("fig"):
                    figure(fig)
                for tw in child.iter("table-wrap"):
                    table(tw)
                for bx in child.iter("boxed-text"):
                    walk(bx, depth + 1)
            elif tag in ("sec", "boxed-text", "app", "ack"):
                walk(child, depth + 1)
            elif tag == "fig":
                figure(child)
            elif tag == "table-wrap":
                table(child)
            elif tag == "list":
                out.extend(f"- {jats_text(li)}" for li in child.findall("list-item"))
                out.append("")

    def table(tw: ET.Element) -> None:
        label = jats_text(tw.find("label")) if tw.find("label") is not None else "Table"
        cap = jats_text(tw.find("caption")) if tw.find("caption") is not None else ""
        rows = [" | ".join(jats_text(c) for c in tr) for tr in tw.iter("tr")]
        out.append(f"> **{label}.** {cap}\n>\n" + "\n".join(f"> {r}" for r in rows) + "\n")

    def figure(fig: ET.Element) -> None:
        label = jats_text(fig.find("label")) if fig.find("label") is not None else "Figure"
        cap = jats_text(fig.find("caption")) if fig.find("caption") is not None else ""
        line = f"> **{label}.** {cap}"
        g = fig.find(".//graphic")   # often inside <alternatives>
        href = g.get("{http://www.w3.org/1999/xlink}href") if g is not None else None
        if href:
            name = f"fig-{re.sub(r'[^0-9A-Za-z]+', '', label) or len(list(figdir.glob('fig-*')))}.jpg"
            try:
                figdir.mkdir(parents=True, exist_ok=True)
                fetch(f"https://pmc.ncbi.nlm.nih.gov/articles/instance/{pmcid}/bin/{href}" + ("" if "." in href else ".jpg"), figdir / name,
                      ua="Mozilla/5.0")   # PMC answers the full browser UA with an HTML page
                if (figdir / name).read_bytes()[:2] != b"\xff\xd8":
                    (figdir / name).unlink()
                    raise subprocess.CalledProcessError(1, "fetch")
                line += f"\n>\n> ![{label}]({figdir.name}/{name})"
            except subprocess.CalledProcessError:
                line += "\n>\n> (image not retrieved)"
        out.append(line + "\n")

    ab = root.find(".//article-meta/abstract")
    if ab is not None:                             # the abstract is part of the paper's text
        if ab.find("title") is None:
            out.append("## Abstract\n")
        walk(ab, 1) if ab.find("sec") is not None or ab.find("p") is not None else out.append(jats_text(ab))
    if body is not None:
        walk(body, 0)
    for part in ("back", "floats-group"):          # appendices, acknowledgements, floating figures
        el = root.find(f".//{part}")
        if el is not None:
            walk(el, 0)
    return "\n".join(out)


def from_pdf(src: str, figdir: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "a.pdf"
        if re.match(r"https?://", src):
            fetch(src, pdf)
        else:
            pdf.write_bytes(Path(src).read_bytes())
        txt = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True,
                             text=True, check=True).stdout
        figdir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdfimages", "-png", str(pdf), str(figdir / "img")], check=True)
    # Keep only figure-sized images (small ones are logos, icons, equation bits).
    for p in sorted(figdir.glob("img-*.png")):
        w, h = png_size(p)
        if min(w, h) < 250:
            p.unlink()
    if not any(figdir.iterdir()):
        figdir.rmdir()
    txt = txt.replace("\f", "\n")
    # Manuscript line numbers and page numbers stand on their own lines.
    txt = re.sub(r"(?m)^\s*\d{1,4}\s*$\n?", "", txt)
    txt = re.sub(r"(\w)-\n(\w)", r"\1\2", txt)          # rejoin hyphenated line breaks
    txt = re.sub(r"(?<![.\n:])\n(?!\n)", " ", txt)      # unwrap lines inside paragraphs
    imgs = sorted(figdir.glob("img-*.png")) if figdir.exists() else []
    if imgs:
        txt += "\n\n## Embedded images (vector figures are not extracted)\n\n" + \
               "\n".join(f"![{p.stem}]({figdir.name}/{p.name})" for p in imgs)
    return txt


def png_size(p: Path) -> tuple[int, int]:
    b = p.read_bytes()[16:24]
    return int.from_bytes(b[:4], "big"), int.from_bytes(b[4:], "big")


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        sys.exit(__doc__)
    key = argv[0]
    OUT.mkdir(parents=True, exist_ok=True)
    figdir = OUT / key
    if "--pmc" in argv:
        pmcid = opt(argv, "--pmc")
        body = from_pmc(pmcid, figdir)
        source = opt(argv, "--source", f"https://europepmc.org/article/PMC/{pmcid.upper().removeprefix('PMC')}")
    elif "--pdf" in argv:
        src = opt(argv, "--pdf")
        body = from_pdf(src, figdir)
        source = opt(argv, "--source", src)
    elif "--text" in argv:
        body = Path(opt(argv, "--text")).read_text(encoding="utf-8")
        source = opt(argv, "--source")
    else:
        sys.exit(__doc__)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    head = ["---", f"key: {key}", f"source: {source}", f"version: {opt(argv, '--version', 'unknown')}",
            f"license: {opt(argv, '--license', 'unknown')}", f"retrieved: {date.today().isoformat()}",
            f"words: {len(body.split())}", f"sha256: {hashlib.sha256(body.encode()).hexdigest()}", "---", ""]
    fa.atomic_write(OUT / f"{key}.md", "\n".join(head) + body)
    nfig = len(list(figdir.glob('*'))) if figdir.exists() else 0
    print(f"{key}: {len(body.split())} words, {nfig} figure file(s) → {(OUT / key).relative_to(fa.ROOT)}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
