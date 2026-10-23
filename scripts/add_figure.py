#!/usr/bin/env python3
"""Add (or replace) the one figure shown on a publication page.

Only for .bib entries with a Creative Commons `license`. The image is scaled
to at most 1600 px on its longest side (macOS `sips`, JPEG quality 85),
EXIF/IPTC segments (APP1/APP13) are stripped, and the result is written to
assets/images/publications/<key>.jpg. The entry in data/figures.yaml gets the
figure label, the caption title (copied verbatim from the publisher — pass it
from a file or JSON, never retype it) and the source URL. Hugo makes the
760/1520 px WebP versions and the social card at build time.

Usage:
  python3 scripts/add_figure.py KEY IMAGE --label "Figure 2" --caption-json FILE [--source URL]
      FILE is a JSON object with at least "caption" (and optionally "label",
      "image_url"/"page_url" used as source)
  python3 scripts/add_figure.py KEY --remove
"""
from __future__ import annotations

import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_abstract as fa  # noqa: E402  (shared .bib helpers)

ROOT = fa.ROOT
FIGS = ROOT / "data" / "figures.yaml"
IMGDIR = ROOT / "assets" / "images" / "publications"
MAX_PX = 1600


def bib_license(key: str) -> str:
    text = fa.BIB.read_text(encoding="utf-8")
    for k, start, end in fa.entries(text):
        if k == key:
            span = fa.field_span(text[start:end], "license")
            return text[start:end][span[0]:span[1]].strip() if span else ""
    sys.exit(f"{key}: not in the .bib")


def strip_metadata(path: Path) -> None:
    d = path.read_bytes()
    assert d[:2] == b"\xff\xd8", "not a JPEG"
    out, i = bytearray(b"\xff\xd8"), 2
    while i < len(d):
        marker = d[i + 1]
        if marker == 0xDA:  # start of scan: copy the rest unchanged
            out += d[i:]
            break
        length = struct.unpack(">H", d[i + 2:i + 4])[0]
        if marker not in (0xE1, 0xED):  # drop APP1 (EXIF/XMP) and APP13 (IPTC)
            out += d[i:i + 2 + length]
        i += 2 + length
    path.write_bytes(bytes(out))


def load_entries() -> list[tuple[str, list[str]]]:
    """data/figures.yaml as (key, lines) blocks plus the header comment."""
    lines = FIGS.read_text(encoding="utf-8").splitlines() if FIGS.exists() else []
    blocks, header, cur = [], [], None
    for line in lines:
        m = re.match(r"^([a-z0-9]+):\s*$", line)
        if m:
            cur = (m.group(1), [])
            blocks.append(cur)
        elif cur:
            cur[1].append(line)
        else:
            header.append(line)
    return header, blocks


def save_entries(header: list[str], blocks: list) -> None:
    out = header[:]
    for key, body in sorted(blocks, key=lambda b: b[0]):
        out.append(f"{key}:")
        out.extend(body)
    fa.atomic_write(FIGS, "\n".join(out) + "\n")


def main(argv: list[str]) -> int:
    if not argv:
        sys.exit(__doc__)
    key = argv[0]
    header, blocks = load_entries()
    blocks = [b for b in blocks if b[0] != key]
    if "--remove" in argv:
        (IMGDIR / f"{key}.jpg").unlink(missing_ok=True)
        save_entries(header, blocks)
        print(f"{key}: figure removed")
        return 0

    lic = bib_license(key)
    if not lic.startswith("CC"):
        sys.exit(f"{key}: licence is {lic!r}, not Creative Commons — no figure")
    image = Path(argv[1])
    opt = lambda f: argv[argv.index(f) + 1] if f in argv else None  # noqa: E731
    info = json.loads(Path(opt("--caption-json")).read_text(encoding="utf-8"))
    caption = info["caption"].strip()
    label = opt("--label") or info.get("label")
    source = opt("--source") or info.get("page_url") or info.get("image_url")
    if not (caption and label and source):
        sys.exit("label, caption and source are required")

    IMGDIR.mkdir(parents=True, exist_ok=True)
    dest = IMGDIR / f"{key}.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        tmpout = Path(tmp) / "out.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85",
                        "-Z", str(MAX_PX), str(image), "--out", str(tmpout)],
                       check=True, capture_output=True)
        strip_metadata(tmpout)
        dest.write_bytes(tmpout.read_bytes())

    blocks.append((key, [f"  label: {json.dumps(label, ensure_ascii=False)}",
                         f"  caption: {json.dumps(caption, ensure_ascii=False)}",
                         f"  source: {json.dumps(source, ensure_ascii=False)}"]))
    save_entries(header, blocks)
    print(f"{key}: {label} → {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
