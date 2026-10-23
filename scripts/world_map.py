#!/usr/bin/env python3
"""World land outline for the co-author map, as one SVG path.

Natural Earth 1:110m land polygons (public domain, naturalearthdata.com),
projected with the Equal Earth projection (Šavrič, Patterson & Jenny 2019,
doi:10.1080/13658816.2018.1504949) into a 1000 px wide coordinate system,
written to assets/maps/world-land.path. `project()` is shared with
coauthor_locations.py so that the points line up with the outline.

For the zoomed Europe/Germany views a finer layer is written too:
Natural Earth 1:50m land and country borders, clipped to the Europe zoom
box, to assets/maps/europe-land.path and assets/maps/europe-borders.path.

Usage: python3 scripts/world_map.py ne_110m_land.geojson [ne_50m_land.geojson ne_50m_admin_0_boundary_lines_land.geojson]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "maps" / "world-land.path"
WIDTH = 1000.0
# Equal Earth constants (Šavrič et al. 2019, eq. 2)
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def _raw(lon: float, lat: float) -> tuple[float, float]:
    lam, phi = math.radians(lon), math.radians(lat)
    theta = math.asin(M * math.sin(phi))
    t2 = theta * theta
    t6 = t2 * t2 * t2
    x = 2 * math.sqrt(3) * lam * math.cos(theta) / (3 * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = theta * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


X_MAX = _raw(180.0, 0.0)[0]  # projected half-width (unit sphere)
Y_MAX = _raw(0.0, 90.0)[1]  # projected half-height


def project(lon: float, lat: float) -> tuple[float, float]:
    """Equal Earth → SVG coordinates (0..WIDTH, 0..height), north up."""
    x, y = _raw(lon, lat)
    s = WIDTH / (2 * X_MAX)
    return (x + X_MAX) * s, (Y_MAX - y) * s


HEIGHT = 2 * Y_MAX * WIDTH / (2 * X_MAX)


CLIP = (444.0, 29.0, 616.0, 122.0)  # Europe zoom box (448 33 164 85) plus a margin


def clip_polygon(pts: list, box=CLIP) -> list:
    """Sutherland–Hodgman clipping of a projected ring to the rectangle box."""
    x0, y0, x1, y1 = box
    edges = [(lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
             (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1))]
    out = pts
    for inside, cut in edges:
        src, out = out, []
        for i, cur in enumerate(src):
            prev = src[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(cut(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cut(prev, cur))
        if not out:
            break
    return out


def inside_box(p, box=CLIP) -> bool:
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def europe_layers(land_file: str, borders_file: str) -> None:
    land = json.loads(Path(land_file).read_text(encoding="utf-8"))
    parts = []
    for feat in land["features"]:
        g = feat["geometry"]
        for poly in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
            for ring in poly:
                pts = clip_polygon([project(lon, lat) for lon, lat in ring])
                if len(pts) > 2:
                    parts.append("M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + "Z")
    (OUT.parent / "europe-land.path").write_text("".join(parts), encoding="utf-8")
    borders = json.loads(Path(borders_file).read_text(encoding="utf-8"))
    segs = []
    for feat in borders["features"]:
        g = feat["geometry"]
        for line in ([g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]):
            run = []
            for lon, lat in line:
                p = project(lon, lat)
                if inside_box(p):
                    run.append(p)
                elif run:
                    segs.append(run); run = []
            if run:
                segs.append(run)
    path = "".join("M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in s) for s in segs if len(s) > 1)
    (OUT.parent / "europe-borders.path").write_text(path, encoding="utf-8")
    for name in ("europe-land.path", "europe-borders.path"):
        print(f"wrote assets/maps/{name} ({(OUT.parent / name).stat().st_size // 1024} KB)")


def main(argv: list[str]) -> int:
    geo = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    parts = []
    for feat in geo["features"]:
        g = feat["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            for ring in poly:
                pts = [project(lon, lat) for lon, lat in ring]
                parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB), viewBox 0 0 {WIDTH:.0f} {HEIGHT:.1f}")
    if len(argv) >= 3:
        europe_layers(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
