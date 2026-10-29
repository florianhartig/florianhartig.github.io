#!/usr/bin/env python3
"""Maintenance check for the publication data — run before every commit.

Verification status lives OUTSIDE the .bib, in .claude/maintenance/publications.json
(gitignored): one record per .bib key with what was checked,
when, against which source, on which legal basis, and a hash of the checked
text. If an abstract or significance note changes later, its hash no longer
matches and the entry shows up as "changed since check" here.

Usage:
  python3 scripts/check_site.py                 report (exit code 1 if problems)
  python3 scripts/check_site.py --record KEY --against SOURCE --basis BASIS [--version V] [--method M]
      record that KEY's current abstract was verified verbatim against SOURCE;
      M says how (default "script diff"): "script diff" (fetch_abstract
      comparable(): markup-, dash- and quote-insensitive), "exact sha256"
      (whitespace-collapsed text identical), "sha256 letters+digits" (only
      letters and digits compared — punctuation not checked)
      (crossref | publisher page | pubmed | europepmc | pmc | arxiv) on legal
      BASIS (e.g. "CC BY 4.0", "Wiley author reuse", "§ 38(4) UrhG");
      --version: "published" (default) or e.g. "arXiv preprint" when the
      official text could not be reached
  python3 scripts/check_site.py --record-note KEY --model MODEL
      record that KEY's note has been through the full v3 procedure
      (.claude/maintenance/note-pipeline/README.md). Refused unless the full
      text (.claude/fulltexts/KEY.md), the dossier (dossiers/KEY.md), the core
      message (cores/KEY.md) and the reports reports/KEY/facts*.json and
      reader*.json exist and the note passes the lint below (rules v4). There is no separate per-note approval:
      the procedure is the rule.

Checks: licence present for every DOI; abstract recorded and unchanged since
its check; significance-note lint (numbers not found in the abstract,
time-relative reception phrases); maintenance records whose key no longer
exists; figures only for CC-licensed entries, each with its image; age,
coverage and git status of data/stats.yaml. It also prints the
current counts.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_abstract as fa  # noqa: E402  (shared .bib helpers and normaliser)

ROOT = fa.ROOT
STATUS = ROOT / ".claude" / "maintenance" / "publications.json"
FIGURES = ROOT / "data" / "figures.yaml"
FIGDIR = ROOT / "assets" / "images" / "publications"
SOURCES = {"crossref", "publisher page", "web archive", "pubmed", "europepmc", "pmc", "arxiv"}
# Reception phrases the rules ban (they go stale or count citations). Under
# the current rules, dated uses by others with a reference ("has since been used
# to …") are allowed.
STALE = re.compile(r"\b(today|to date|still being|so far|now widely|widely (?:cited|used|adopted)|"
                   r"standard reference|most cited|highly cited|citations?)\b", re.I)
PIPE = ROOT / ".claude" / "maintenance" / "note-pipeline"
FULLTEXTS = ROOT / ".claude" / "fulltexts"
RULES_VERSION = "v4"


def note_refs() -> dict:
    """data/note_refs.yaml (written by note_refs.py: one JSON object per line)."""
    path = ROOT / "data" / "note_refs.yaml"
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith('"'):
                k, v = line.split(": ", 1)
                out[json.loads(k)] = json.loads(v)
    return out


def ref_label(rec: dict, suffix: str = "") -> str:
    a = rec.get("authors") or [""]
    who = a[0] if len(a) == 1 else f"{a[0]} and {a[1]}" if len(a) == 2 else f"{a[0]} et al."
    # Crossref often spells hyphenated names with U+2010/U+2011 and apostrophes plainly; compare in ASCII.
    return particles(f"{who} {rec.get('year')}{suffix}".replace("\u2010", "-").replace("\u2011", "-").replace("\u2019", "'"))


def particles(s: str) -> str:
    """Name particles in lower case ("Van Oijen" at a sentence start = Crossref's "van Oijen")."""
    return re.sub(r"\b(Van|Von|De|Der|Den|Di|Du|La|Le) (?=[A-Z])", lambda m: m.group(1).lower() + " ", s)


def lint_note(key: str, f: dict, refs_db: dict) -> tuple[list[str], list[str]]:
    """Problems and notes for one v3 note (paragraphs, citations and references,
    numbers against the full text, banned phrases)."""
    problems, notes = [], []
    raw = f.get("significance", "")
    paras = [p for p in re.split(r"\s*\\par\b\s*", raw) if p.strip()]
    if len(paras) != 3:
        notes.append(f"{key}: note has {len(paras)} paragraph(s), rules v3 ask for 3 (background / paper / significance)")
    text = particles(" ".join(paras).replace("\u2010", "-").replace("\u2011", "-").replace("\u2019", "'"))
    if re.search(r"\\[A-Za-z]+", text):
        problems.append(f"{key}: note contains a LaTeX command other than \\par")
    refs = f.get("significance_refs", "").split()
    if len(refs) != len(set(refs)):
        problems.append(f"{key}: duplicate DOI in significance_refs")
    labels = []
    for r in refs:
        doi, _, suf = r.lower().partition("|")
        rec = refs_db.get(doi)
        if not rec:
            problems.append(f"{key}: reference {doi} not in data/note_refs.yaml — run scripts/note_refs.py")
            continue
        labels.append(ref_label(rec, suf))
    # Every listed reference cited in the text ("Label (Year)" or "(Label Year") …
    flat = re.sub(r"[()]", "", text).replace(" & ", " and ")
    for lab in labels:
        if lab not in flat:
            problems.append(f"{key}: reference \"{lab}\" listed but not cited in the text (or label/year differs)")
    # … and every author–year citation in the text listed.
    # Surnames may carry particles ("Van Kleunen", "de Vries"); the lookbehind stops a match starting mid-name.
    part = r"(?:(?:[Vv]an|[Vv]on|[Dd]e|[Dd]er|[Dd]en|[Dd]i|[Dd]u|[Ll]a|[Ll]e) )*[A-Z][\w'-]+"
    for m in re.finditer(rf"(?<![\w'-] )(?<![\w'-])({part}(?: et al\.| and {part})?) \(?((?:19|20)\d\d[a-z]?)\b", text):
        if m.group(1) in {"In", "By", "Since", "From", "Until", "Before", "After", "During", "Around", "Between"}:
            continue
        if f"{m.group(1)} {m.group(2)}" not in labels:
            problems.append(f"{key}: citation \"{m.group(1)} {m.group(2)}\" has no matching reference")
    # Numbers: against the full text (else the abstract), ignoring cited years.
    ft = FULLTEXTS / f"{key}.md"
    source = ft.read_text(encoding="utf-8") if ft.exists() else f.get("abstract", "")
    known = set(re.findall(r"\d[\d,.]*\d|\d", source)) | {re.sub(r"[a-z]$", "", l.rsplit(" ", 1)[1]) for l in labels}
    extra = [n for n in re.findall(r"\d[\d,.]*\d|\d", text) if n not in known and len(n) > 1]
    if extra:
        notes.append(f"{key}: note has numbers not in the {'full text' if ft.exists() else 'abstract'}: {', '.join(sorted(set(extra)))}")
    for m in STALE.finditer(text):
        notes.append(f"{key}: note has a banned reception phrase: \"{m.group(0)}\"")
    return problems, notes


def digest(text: str) -> str:
    return hashlib.sha256(fa.comparable(text).encode()).hexdigest()[:16]


def note_digest(f: dict) -> str:
    """Hash of a note and its reference list together (a changed
    reference must invalidate the record too)."""
    return digest(f.get("significance", "") + " || " + " ".join(f.get("significance_refs", "").split()))


def load_status() -> dict:
    return json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}


def save_status(status: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    fa.atomic_write(STATUS, json.dumps(dict(sorted(status.items())), ensure_ascii=False, indent=1) + "\n")


def bib_entries() -> dict:
    text = fa.BIB.read_text(encoding="utf-8")
    out = {}
    for key, start, end in fa.entries(text):
        body = text[start:end]
        fields = {}
        for name in ("doi", "abstract", "significance", "significance_refs", "license", "abstract_kind", "preprint", "journal", "year"):
            span = fa.field_span(body, name)
            if span:
                fields[name] = body[span[0]:span[1]].strip()
        out[key] = fields
    return out


def arg(argv: list[str], flag: str, default: str | None = None) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv: list[str]) -> int:
    entries, status = bib_entries(), load_status()
    today = date.today().isoformat()

    if "--record" in argv:
        key, against, basis = arg(argv, "--record"), arg(argv, "--against"), arg(argv, "--basis")
        if key not in entries or "abstract" not in entries[key]:
            sys.exit(f"{key}: no such entry or no abstract in the .bib")
        if against not in SOURCES or not basis:
            sys.exit(f"--against must be one of {sorted(SOURCES)}; --basis is required")
        status.setdefault(key, {})["abstract"] = {
            "checked": today, "against": against, "basis": basis,
            "version": arg(argv, "--version", "published"),
            "method": arg(argv, "--method", "script diff"),
            "hash": digest(entries[key]["abstract"]),
        }
        save_status(status)
        print(f"{key}: abstract recorded")
        return 0
    if "--record-note" in argv:
        key, model = arg(argv, "--record-note"), arg(argv, "--model")
        if key not in entries or "significance" not in entries[key]:
            sys.exit(f"{key}: no such entry or no significance note")
        if not model:
            sys.exit("--model is required (a model ID)")
        ft = FULLTEXTS / f"{key}.md"
        dossier = PIPE / "dossiers" / f"{key}.md"
        core = PIPE / "cores" / f"{key}.md"
        # Rules v4: core message (stage 1), reader check (stage 2) and fact check (stage 3) are required; the field
        # check is optional.
        reports = {r: sorted((PIPE / "reports" / key).glob(f"{r}*.json")) for r in ("facts", "field", "reader")}
        # Reduced procedure: an abstract-only source needs no dossier and no reader check.
        abstract_only = ft.exists() and re.search(r"^version: abstract", ft.read_text(encoding="utf-8"), re.M)
        # Reduced procedure: no dossier for papers from this or last year (too
        # recent for documented uptake; background comes from the paper itself).
        recent = int(entries[key].get("year", "0")[:4] or 0) >= date.today().year - 1
        need = (ft, core) if abstract_only or recent else (ft, dossier, core)
        missing = [str(p.relative_to(ROOT)) for p in need if not p.exists()] + \
                  [f"reports/{key}/{r}*.json" for r, found in reports.items()
                   if not found and r != "field" and not (abstract_only and r == "reader")]
        if missing:
            sys.exit(f"{key}: not recorded — missing {', '.join(missing)}")
        probs, _ = lint_note(key, entries[key], note_refs())
        if probs:
            sys.exit(f"{key}: not recorded — " + "; ".join(probs))
        head = ft.read_text(encoding="utf-8").split("---", 2)[1]
        meta = dict(re.findall(r"^(\w+): (.*)$", head, re.M))
        status.setdefault(key, {})["significance"] = {
            "written": today, "rules": RULES_VERSION, "model": model,
            "based_on": "fulltext", "fulltext_version": meta.get("version", "unknown"),
            "fulltext_source": meta.get("source", ""), "fulltext_sha256": meta.get("sha256", ""),
            "dossier": str(dossier.relative_to(ROOT)) if dossier.exists() else None, "core": str(core.relative_to(ROOT)),
            "reports": [str(p.relative_to(ROOT)) for ps in reports.values() for p in ps],
            "hash": note_digest(entries[key])}
        save_status(status)
        print(f"{key}: note recorded (rules {RULES_VERSION})")
        return 0

    problems, notes, pending = [], [], []
    refs_db = note_refs()
    # Fields the parser would silently drop (e.g. a missing comma after the
    # previous field).
    import bib2content
    bibtext = fa.BIB.read_text(encoding="utf-8")
    for key, start, end in fa.entries(bibtext):
        body = bibtext[start:end]
        declared = re.findall(r"^\s*([a-z_]+)\s*=\s*\{", body, re.M)
        _, parsed = bib2content.parse_fields(body)
        lost = [d for d in declared if d not in parsed]
        if lost:
            problems.append(f"{key}: field(s) {', '.join(lost)} not parsed — missing comma before them?")
    for key, f in entries.items():
        rec = status.get(key, {})
        if f.get("doi") and not f.get("license"):
            problems.append(f"{key}: DOI but no `license`")
        if "abstract" in f:
            a = rec.get("abstract")
            if not a:
                problems.append(f"{key}: abstract not verified")
            elif a.get("hash") != digest(f["abstract"]):
                problems.append(f"{key}: abstract changed since its check on {a.get('checked')}")
            elif a.get("version", "published") != "published" and not a["version"].startswith("preprint v"):
                notes.append(f"{key}: abstract is the {a['version']} — replace with the official text when reachable")
        sig = f.get("significance", "")
        if sig:
            s = rec.get("significance")
            if s and s.get("rules") == RULES_VERSION and s.get("hash") != note_digest(f):
                problems.append(f"{key}: note or its references changed since it was recorded — re-run the checks")
            elif not s or s.get("rules") != RULES_VERSION:
                pending.append(key)
            if "\\par" in sig or f.get("significance_refs"):     # v3 notes only; old ones are replaced anyway
                p_, n_ = lint_note(key, f, refs_db)
                problems += p_
                notes += n_
    for key in status:
        if key not in entries:
            problems.append(f"{key}: maintenance record for a key that is no longer in the .bib")

    # Figures (data/figures.yaml + assets/images/publications/, via add_figure.py):
    # only for CC-licensed entries, every entry with its image and vice versa.
    figs = set(re.findall(r"^([a-z0-9]+):\s*$", FIGURES.read_text(encoding="utf-8"), re.M)) if FIGURES.exists() else set()
    images = {f.stem for f in FIGDIR.glob("*.jpg")} if FIGDIR.exists() else set()
    for key in sorted(figs):
        if key not in entries:
            problems.append(f"{key}: figure for a key that is not in the .bib")
        elif not entries[key].get("license", "").startswith("CC"):
            problems.append(f"{key}: figure shown, but the licence is not Creative Commons")
        if key not in images:
            problems.append(f"{key}: figure entry without image file")
    for key in sorted(images - figs):
        problems.append(f"{key}: image in assets/images/publications without a figures.yaml entry")

    # Citation figures (data/stats.yaml, written by citation_stats.R): age,
    # coverage, histories, and whether git tracks the file (the CI build only
    # sees committed files).
    import subprocess
    stats = ROOT / "data" / "stats.yaml"
    if not stats.exists():
        problems.append("data/stats.yaml is missing — the site would show no citation figures")
    else:
        st = stats.read_text(encoding="utf-8")
        m = re.search(r"^as_of:\s*['\"]?(\d{4}-\d{2}-\d{2})", st, re.M)
        if m:
            age = (date.today() - date.fromisoformat(m.group(1))).days
            (notes if age <= 45 else problems).append(f"data/stats.yaml is {age} days old (as_of {m.group(1)})")
        hist = re.findall(r"history_as_of:\s*['\"]?(\d{4}-\d{2}-\d{2})", st)
        papers = set(re.findall(r"^  ([a-z0-9]+):\s*$", st.split("\npapers:", 1)[-1].split("\nsoftware:", 1)[0], re.M))
        if hist:
            notes.append(f"per-paper citation histories: {len(hist)}, oldest {min(hist)}")
        missing = sorted(k for k in entries if k not in papers and entries[k].get("doi"))
        if missing:
            notes.append(f"{len(missing)} .bib entries with DOI have no stats record (new papers?): {', '.join(missing[:8])}{' …' if len(missing) > 8 else ''}")
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "data/stats.yaml"], cwd=ROOT,
                                 capture_output=True).returncode == 0
        if not tracked:
            notes.append("data/stats.yaml is not tracked by git — commit it, or the deployed site has no citation figures")
    # Data files the build needs: untracked ones are missing on the live site
    # (a missing note_refs.yaml would drop every reference list).
    for rel in ("data/note_refs.yaml", "data/figures.yaml", "data/coauthors.yaml"):
        if (ROOT / rel).exists() and subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT,
                                                    capture_output=True).returncode != 0:
            problems.append(f"{rel} is not tracked by git — add it before committing, or the live site lacks it")

    with_abstract = sum("abstract" in f for f in entries.values())
    verified = sum(1 for k, f in entries.items() if "abstract" in f and status.get(k, {}).get("abstract", {}).get("hash") == digest(f["abstract"]))
    done = sum(1 for k, f in entries.items() if "significance" in f and status.get(k, {}).get("significance", {}).get("rules") == RULES_VERSION and status[k]["significance"].get("hash") == note_digest(f))
    cc = sum(f.get("license", "").startswith("CC") for f in entries.values())
    print(f"entries {len(entries)} · with DOI {sum('doi' in f for f in entries.values())} · "
          f"preprint links {sum('preprint' in f for f in entries.values())} · CC-licensed {cc}")
    print(f"abstracts {with_abstract} · verified and unchanged {verified} · "
          f"opening paragraphs {sum(f.get('abstract_kind') == 'opening' for f in entries.values())}")
    print(f"figures {len(figs)} of {cc} CC-licensed entries")
    print(f"significance notes {sum('significance' in f for f in entries.values())} · through the {RULES_VERSION} procedure and unchanged {done} · pending {len(pending)}")
    for p in problems:
        print("PROBLEM", p)
    for n in notes:
        print("note   ", n)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
