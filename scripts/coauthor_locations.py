#!/usr/bin/env python3
"""Last known location (and ORCID) of every co-author, for the co-author map.

Reads and updates data/coauthors.yaml (format: scripts/coauthor_data.py).
Always the last known location. Sources, in this order,
for each co-author whose record is not `location_fixed`:

  1. OpenAlex: find the person's authorship in the OpenAlex record of the
     newest joint paper with a DOI (name match: family name + first initial,
     accents ignored), then the OpenAlex author's `last_known_institutions`;
  2. OpenAlex: the institution given on that authorship;
  3. Crossref: the affiliation text printed on the newest joint paper,
     resolved to an institution by the ROR affiliation matcher (only ROR's
     confident "chosen" match is used).
  Coordinates: OpenAlex institution `geo`, or ROR GeoNames details.

No API key and no contact parameter is sent — never add an e-mail address or
other personal data. Requests go through urllib
with a curl fallback, in small batches, because anonymous OpenAlex access
has a small daily budget and sometimes cuts responses short.

Usage: python3 scripts/coauthor_locations.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coauthor_data as cd  # noqa: E402
import fetch_abstract as fa  # noqa: E402  (shared .bib helpers)
from world_map import project  # noqa: E402

OPENALEX, CROSSREF, ROR = "https://api.openalex.org", "https://api.crossref.org", "https://api.ror.org/v2"
LOC_FIELDS = ("orcid", "openalex", "institution", "city", "country", "lat", "lon", "x", "y",
              "location_basis", "location_as_of")
UA = "florianhartig.github.io build script"


def get_json(url: str) -> dict | None:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=40) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            try:  # curl copes better with responses that urllib reads incompletely
                out = subprocess.run(["curl", "-sS", "--fail", "--retry", "2", "-A", UA, url],
                                     capture_output=True, timeout=90, check=True).stdout
                return json.loads(out)
            except Exception as e:  # noqa: BLE001
                print(f"  retry {attempt + 1}: {str(e)[:120]}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
    return None


def openalex_batch(kind: str, field: str, ids: list[str], select: str) -> dict:
    out = {}
    for i in range(0, len(ids), 20):
        q = urllib.parse.urlencode({"filter": f"{field}:" + "|".join(ids[i:i + 20]), "per-page": 50, "select": select})
        for rec in (get_json(f"{OPENALEX}/{kind}?{q}") or {}).get("results", []):
            out[rec["id"].rsplit("/", 1)[-1]] = rec
            if rec.get("doi"):
                out[rec["doi"].lower().replace("https://doi.org/", "")] = rec
        time.sleep(1)
    return out


def key_of(name: str) -> tuple[str, str]:
    parts = name.replace(".", " ").replace(",", " ").split()
    return (cd.fold(parts[-1]), cd.fold(parts[0][:1])) if parts else ("", "")


def main() -> int:
    text = fa.BIB.read_text(encoding="utf-8")
    dois = {}
    for key, start, end in fa.entries(text):
        span = fa.field_span(text[start:end], "doi")
        if span:
            dois[key] = text[start:end][span[0]:span[1]].strip().lower()
    top, people = cd.read()
    todo = [p for p in people if not p.get("location_fixed")]
    need_dois = sorted({dois[k] for p in todo for k in p["papers"] if k in dois})
    works = openalex_batch("works", "doi", need_dois, "id,doi,authorships")
    print(f"OpenAlex works: {sum(1 for d in need_dois if d in works)} of {len(need_dois)}")

    # Steps 1–2: each person's OpenAlex authorship on the newest joint paper.
    hits = {}
    for p in todo:
        want = key_of(p["name"])
        for k in p["papers"]:
            for a in (works.get(dois.get(k, "")) or {}).get("authorships", []):
                if any(n and key_of(n) == want for n in (a.get("raw_author_name"), (a.get("author") or {}).get("display_name"))):
                    hits[p["id"]] = (k, a)
                    break
            if p["id"] in hits:
                break
    aids = sorted({((a.get("author") or {}).get("id") or "").rsplit("/", 1)[-1] for _, a in hits.values()} - {""})
    authors = openalex_batch("authors", "openalex", aids, "id,orcid,last_known_institutions")
    found = {}
    for pid, (k, a) in hits.items():
        aid = ((a.get("author") or {}).get("id") or "").rsplit("/", 1)[-1]
        rec = authors.get(aid, {})
        lki = rec.get("last_known_institutions") or []
        if lki:
            inst, basis = lki[0]["id"], "OpenAlex last known institution"
        elif a.get("institutions"):
            inst, basis = a["institutions"][0]["id"], f"OpenAlex affiliation on {k}"
        else:
            inst, basis = None, None
        found[pid] = {"openalex": aid, "orcid": (rec.get("orcid") or "").replace("https://orcid.org/", ""),
                      "inst": inst.rsplit("/", 1)[-1] if inst else None, "basis": basis}
    insts = openalex_batch("institutions", "openalex", sorted({v["inst"] for v in found.values() if v["inst"]}),
                           "id,display_name,geo")

    # Step 3: Crossref affiliation text + ROR for those still without coordinates.
    crossref, ror = {}, {}
    today = date.today().isoformat()
    for p in todo:
        v = found.get(p["id"], {})
        inst = insts.get(v.get("inst") or "")
        geo = (inst or {}).get("geo") or {}
        new = {}
        if inst and geo.get("latitude") is not None:
            new = {"institution": inst["display_name"], "city": geo.get("city") or "", "country": geo.get("country") or "",
                   "lat": geo["latitude"], "lon": geo["longitude"], "location_basis": v["basis"]}
        else:
            want = key_of(p["name"])
            for k in p["papers"]:
                if k not in dois:
                    continue
                if dois[k] not in crossref:
                    crossref[dois[k]] = (get_json(f"{CROSSREF}/works/{urllib.parse.quote(dois[k])}") or {}).get("message", {})
                    time.sleep(0.3)
                auth = next((a for a in crossref[dois[k]].get("author", [])
                             if key_of(f"{a.get('given', '')} {a.get('family', '')}") == want), None)
                if not auth:
                    continue
                if not v.get("orcid") and auth.get("ORCID"):
                    v["orcid"] = auth["ORCID"].rsplit("/", 1)[-1]
                aff = "; ".join(x.get("name", "") for x in auth.get("affiliation", []) if x.get("name"))
                if not aff:
                    continue
                if aff not in ror:
                    res = get_json(f"{ROR}/organizations?affiliation={urllib.parse.quote(aff)}") or {}
                    ror[aff] = next((it["organization"] for it in res.get("items", []) if it.get("chosen")), None)
                    time.sleep(0.3)
                org = ror[aff]
                if org and org.get("locations"):
                    g = org["locations"][0]["geonames_details"]
                    name = next((n["value"] for n in org["names"] if "ror_display" in n.get("types", [])), org["names"][0]["value"])
                    new = {"institution": name, "city": g.get("name", ""), "country": g.get("country_name", ""),
                           "lat": g["lat"], "lon": g["lng"], "location_basis": f"Crossref affiliation on {k} → ROR"}
                break
        # Replace the old location only when a new one was found, so a network
        # failure never erases locations.
        if new:
            for f in LOC_FIELDS:
                p.pop(f, None)
        if v.get("orcid"):
            p["orcid"] = v["orcid"]
        if v.get("openalex"):
            p["openalex"] = v["openalex"]
        if new:
            x, y = project(new["lon"], new["lat"])
            p.update({**new, "lat": round(new["lat"], 4), "lon": round(new["lon"], 4),
                      "x": round(x, 1), "y": round(y, 1), "location_as_of": today})
    located = sum(1 for p in people if "lat" in p)
    top["located"] = located
    if any(p.get("location_as_of") == today for p in people):
        top["locations_as_of"] = today
    cd.write(top, people)
    print(f"located {located} of {len(people)} co-authors → {cd.PATH.relative_to(cd.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
