"""
Emit LaTeX TikZ fragments for ep-isomorphism class representatives
(used by Prompt_extracted appendix). Run from repo root:
  python generate_ltt_appendix_tex.py
Writes: ltt_appendix_generated.tex

Do **not** hand-edit ``ltt_appendix_generated.tex``: it is overwritten every run.
Put all figure tweaks (vertex swaps, straight segments, arc strength) in **this file**
via ``class_*_manual`` flags (including ``class_five_manual`` where needed) so they persist.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Sequence

from ltt_structures import LTT, canonical_signature, iter_distinguished_ltt

# User-provided authoritative dictionary:
# Box Roman numeral <-> ep-isomorphism class number.
CLASS_TO_ROMAN: dict[int, str] = {
    1: "II",
    2: "I",
    3: "VII",
    4: "VIII",
    5: "VI",
    6: "III",
    7: "X",
    8: "XII",
    9: "IV",
    10: "IX",
    11: "XIII",
    12: "V",
    13: "XI",
    14: "XIV",
}

ORDER = ["x1", "xb1", "x2", "xb2", "x3", "xb3", "x4", "xb4", "x5", "xb5"]

# Base cluster vertex positions (same pattern as seed figure); scaled below for spacing.
_RAW_SLOT_CLUSTERS: list[list[tuple[float, float]]] = [
    [(-5.55, 1.55), (-6.7, -1.35), (-4.4, -1.35)],
    [(-0.15, 5.45), (2.65, 5.95), (5.35, 4.85)],
    [(5.45, -2.35), (9.35, -2.35), (7.55, 1.45)],
]

# Spread clusters so black detours have more room (reduces crossings with purple).
LAYOUT_SCALE = 1.2

SLOT_COORDS: list[list[tuple[float, float]]] = [
    [(LAYOUT_SCALE * x, LAYOUT_SCALE * y) for x, y in cluster]
    for cluster in _RAW_SLOT_CLUSTERS
]

# Horizontal gap from the left side of the red-adjacent purple triangle to $x_1$.
X1_LEFT_OF_TRIANGLE_GAP = 3.05 * LAYOUT_SCALE
# Fallback if red partner is not found in any triple (should not happen).
X1_FALLBACK_POS = (5.85, 1.45)

TIKZ_OPEN = r"""\resizebox{\linewidth}{!}{%
\begin{tikzpicture}[
  lbl/.style={font=\small, inner sep=1pt},
  redv/.style={circle, draw=red!70!black, line width=0.8pt, fill=red!45, minimum size=7mm},
  purpv/.style={circle, draw=violet!80!black, line width=0.8pt, fill=blue!12!purple!28, minimum size=7mm},
  purpleedge/.style={draw=violet, line width=2.8pt, line cap=round, line join=round},
  blackedge/.style={draw=black, line width=2.4pt, line cap=round},
  rededge/.style={draw=red!92!black, line width=3.2pt, line cap=round}
]
"""

TIKZ_CLOSE = r"""
\end{tikzpicture}%
}%
"""

# Black edges: cubic Bézier control offsets (perpendicular to chord), away from layout
# centroid, with different magnitudes so the five strands use different corridors.
BLACK_ROUTE_STRENGTH = [6.2, 8.0, 5.4, 9.0, 6.8]
# When multiple black edges share the same two vertices: increase separation.
PARALLEL_ROUTE_STEP = 2.2
# Gentler cubic for the red edge so it does not hug chords through purple regions.
RED_ROUTE_STRENGTH = 3.4
# Fraction of chord from A / to B where control anchors sit (TikZ cubic).
_BLACK_CTRL_T = 0.38


def _centroid_xy(pos: dict[str, tuple[float, float]]) -> tuple[float, float]:
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    n = len(xs)
    return sum(xs) / n, sum(ys) / n


def _black_bezier_controls(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    strength: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Control points for a cubic from A to B bowing away from centroid (cx, cy).
    Larger |strength| pushes the bend farther out, helping avoid purple segments.
    """
    dx, dy = bx - ax, by - ay
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return (ax, ay), (bx, by)
    ux, uy = dx / chord, dy / chord
    px, py = -uy, ux
    mx, my = (ax + bx) / 2, (ay + by) / 2
    d_plus = (mx + px - cx) ** 2 + (my + py - cy) ** 2
    d_minus = (mx - px - cx) ** 2 + (my - py - cy) ** 2
    if d_minus > d_plus:
        px, py = -px, -py
    sx, sy = px * strength, py * strength
    t = _BLACK_CTRL_T
    c1x, c1y = ax + t * dx + sx, ay + t * dy + sy
    c2x, c2y = bx - t * dx + sx, by - t * dy + sy
    return (c1x, c1y), (c2x, c2y)


def _black_bezier_controls_arc_left(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    strength: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Cubic controls bowing to the left (toward decreasing $x$) from segment $AB$."""
    dx, dy = bx - ax, by - ay
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return (ax, ay), (bx, by)
    ux, uy = dx / chord, dy / chord
    px, py = -uy, ux
    # Among $\pm$(px,py), pick the perpendicular whose $x$-component is non-positive when possible.
    if px > 0:
        px, py = -px, -py
    sx, sy = px * strength, py * strength
    t = _BLACK_CTRL_T
    c1x, c1y = ax + t * dx + sx, ay + t * dy + sy
    c2x, c2y = bx - t * dx + sx, by - t * dy + sy
    return (c1x, c1y), (c2x, c2y)


# Class~1: left-arch strength for $x_5$–$\bar x_5$ only (half of the earlier bend — still curved).
CLASS1_LEFT_ARC_STRENGTH_BASE = 8.5
CLASS1_LEFT_ARC_STRENGTH_X5_XB5 = CLASS1_LEFT_ARC_STRENGTH_BASE * 0.5
# Class 1: after appendix vertex swaps, nudge $x_3$ somewhat down and slightly to the left.
CLASS1_SHIFT_X3_X = -0.28
CLASS1_LOWER_X3_Y = -0.42
CLASS1_SHIFT_XB2_X = 0.30
CLASS1_RAISE_XB2_Y = 0.36
CLASS1_LOWER_X2_Y = -0.36
CLASS1_SHIFT_XB5_X = -0.30
CLASS1_RAISE_XB5_Y = 0.36

# Class 2: ``x_4``--$\bar x_4$ uses half the usual outward-route strength (milder arch).
CLASS2_X4_XB4_STRENGTH_FACTOR = 0.5
# Class 2: after the $\bar x_2$/$\bar x_5$ swap, nudge $\bar x_2$ left and $x_2$ down.
CLASS2_SHIFT_XB2_X = -0.40
CLASS2_SHIFT_X2_X = 0.00
CLASS2_LOWER_X2_Y = -0.62
CLASS2_LOWER_X1_Y = -0.36

# Class 3: ``x_5``--$\bar x_5$ uses half the usual outward-route strength (milder arch).
CLASS3_X5_XB5_STRENGTH_FACTOR = 0.5
# Class 3: nudge $x_1$, $x_2$, and $x_4$ for the appendix layout.
CLASS3_SHIFT_X1_X = 0.30
CLASS3_LOWER_X1_Y = -0.45
CLASS3_SHIFT_X2_X = 0.30
CLASS3_LOWER_X2_Y = -0.45
CLASS3_SHIFT_X4_X = -0.30
CLASS3_LOWER_X4_Y = -0.45
# Class 4: keep the half-strength for ``x_5``--$\bar x_5$.
CLASS4_X5_XB5_STRENGTH_FACTOR = CLASS3_X5_XB5_STRENGTH_FACTOR

# Class 4: ``x_4``--$\bar x_4$ slightly stronger outward bulge than the default strand.
CLASS4_X4_XB4_STRENGTH_FACTOR = 1.28
CLASS4_LEFT_ARC_STRENGTH_X3_XB3 = 2.2
CLASS4_SHIFT_X4_X = 0.60
CLASS4_LOWER_X4_Y = -0.66
CLASS4_SHIFT_XB4_X = 0.36
CLASS4_RAISE_XB4_Y = 0.36
CLASS4_SHIFT_XB1_X = 0.30
CLASS4_LOWER_XB1_Y = -0.34
CLASS4_RAISE_XB2_Y = 0.34
CLASS4_X1_LEVEL_BETWEEN_X2_AND_XB5_FRACTION = 0.55

# Class 5: ``x_4``--$\bar x_4$ stronger outward bulge than the default strand (after vertex swaps).
CLASS5_X4_XB4_STRENGTH_FACTOR = 1.24
# Class 5: ``x_5``--$\bar x_5$ at half default bulge.
CLASS5_X5_XB5_STRENGTH_FACTOR = 0.5
# Class 5: after $x_3$/$x_4$ and $\bar x_2$/$\bar x_4$ swaps, nudge vertices for appendix layout.
CLASS5_LOWER_X1_Y = -0.40
CLASS5_LOWER_X2_Y = -0.40
CLASS5_SHIFT_XB1_X = 0.26
CLASS5_SHIFT_XB2_X = 0.26
CLASS5_RAISE_XB4_Y = 0.36
CLASS5_SHIFT_XB3_X = -0.34
CLASS5_RAISE_XB3_Y = 0.78
CLASS5_SHIFT_X3_X = -0.42
CLASS5_LOWER_X3_Y = -0.62

# Class 6: ``x_1``--$\bar x_1$ milder outward bulge than the default strand.
CLASS6_X1_XB1_STRENGTH_FACTOR = 0.58
CLASS6_X4_XB4_STRENGTH_FACTOR = 0.5
CLASS6_SHIFT_X2_X = -0.22
CLASS6_RAISE_X2_Y = 0.48
CLASS6_SHIFT_XB2_X = -0.26
CLASS6_LOWER_XB2_Y = -0.60
CLASS6_SHIFT_X5_X = -0.42
CLASS6_LOWER_X5_Y = -0.78
CLASS6_RIGHT_SHIFT_DISTANCE_FRACTION = 1.0 / 3.0
CLASS6_RAISE_XB3_Y = 0.36
CLASS6_X3_ABOVE_XB1_GAP = 3.40

# Class 7: ``x_4``--$\bar x_4$ and ``x_1``--$\bar x_1$ milder outward bulges than default.
CLASS7_X4_XB4_STRENGTH_FACTOR = 0.55
CLASS7_X1_XB1_STRENGTH_FACTOR = CLASS6_X1_XB1_STRENGTH_FACTOR
CLASS7_SHIFT_X2_X = -0.30
CLASS7_RAISE_X2_Y = 0.34
CLASS7_SHIFT_XB3_X = -0.24
CLASS7_LOWER_XB3_Y = -0.74
CLASS7_SHIFT_XB5_X = -0.34
CLASS7_LOWER_XB5_Y = -0.86

# Class 8: ``x_4``--$\bar x_4$, ``x_5``--$\bar x_5$, and ``x_1``--$\bar x_1$ milder outward bulges than default.
CLASS8_X4_XB4_STRENGTH_FACTOR = 0.32
CLASS8_X5_XB5_STRENGTH_FACTOR = 2.0 / 3.0
CLASS8_X1_XB1_STRENGTH_FACTOR = CLASS6_X1_XB1_STRENGTH_FACTOR
CLASS8_SHIFT_X2_X = -0.22
CLASS8_RAISE_X2_Y = 0.36
CLASS8_SHIFT_XB2_X = -0.22
CLASS8_LOWER_XB2_Y = -0.22
CLASS8_LOWER_XB4_Y = -1.60

# Class 9: ``x_2``--$\bar x_2$ and ``x_4``--$\bar x_4$ milder outward bulges than default.
CLASS9_X2_XB2_STRENGTH_FACTOR = 0.42
CLASS9_X4_XB4_STRENGTH_FACTOR = 0.48
# Appendix Class 9: nudge $x_5$ and $\bar x_5$ upward (same TikZ units as ``pos``).
CLASS9_RAISE_X5_PAIR_Y = 0.55
CLASS9_LOWER_X1_Y = -0.36
CLASS9_LOWER_X2_Y = -0.36
CLASS9_SHIFT_X3_X = -0.34
CLASS9_LOWER_X3_Y = -0.50
CLASS9_RAISE_XB5_Y = 0.34

# Class 10: ``x_2``--$\bar x_2$ at $1/2$ default bulge; ``x_4``--$\bar x_4$ at $1/2$; ``x_5``--$\bar x_5$ straight.
CLASS10_X2_XB2_STRENGTH_FACTOR = 0.5
CLASS10_X4_XB4_STRENGTH_FACTOR = 0.5
CLASS10_SHIFT_X3_X = -0.48
CLASS10_LOWER_X3_Y = -0.68
CLASS10_RAISE_XB3_Y = 0.82
CLASS10_SHIFT_XB3_X = 0.54
CLASS10_SHIFT_XB5_X = 0.30
CLASS10_LOWER_X2_Y = -0.36
CLASS10_LOWER_X1_Y = -0.36

# Class 11: $x_2$--$\bar x_2$ and $x_4$--$\bar x_4$ at $1/4$ default bulge; $x_5$--$\bar x_5$ at $1/2$.
CLASS11_X2_XB2_STRENGTH_FACTOR = 0.25
CLASS11_X4_XB4_STRENGTH_FACTOR = 0.25
CLASS11_X5_XB5_STRENGTH_FACTOR = 0.5
CLASS11_SHIFT_XB3_X = -0.42
CLASS11_RAISE_XB3_Y = 0.82
CLASS11_SHIFT_X3_X = -0.26
CLASS11_LOWER_X3_Y = -0.34

# Class 12: custom black-edge and vertex nudges for appendix layout.
CLASS12_X3_XB3_STRENGTH_FACTOR = 0.25
CLASS12_X4_XB4_STRENGTH_FACTOR = 0.5
CLASS12_LOWER_X2_Y = -0.40
CLASS12_SHIFT_X5_X = 0.24
CLASS12_RAISE_X5_Y = 0.26
CLASS12_SHIFT_XB5_X = -0.24
CLASS12_RAISE_XB5_Y = 0.40

# Class 13: custom black-edge strengths and vertex nudges for appendix layout.
CLASS13_X3_XB3_STRENGTH_FACTOR = 0.5
CLASS13_X4_XB4_STRENGTH_FACTOR = 0.25
CLASS13_LOWER_X1_Y = -0.40
CLASS13_X1_BELOW_X2_GAP = 0.90
CLASS13_SHIFT_XB3_X = -0.34
CLASS13_LOWER_XB3_Y = -0.56

# Class 14: custom black-edge strengths and vertex nudges for appendix layout.
CLASS14_X3_XB3_STRENGTH_FACTOR = 0.5
CLASS14_X4_XB4_STRENGTH_FACTOR = 0.25
CLASS14_X5_XB5_STRENGTH_FACTOR = 0.5
CLASS14_LOWER_X1_Y = -0.40
CLASS14_LOWER_X2_Y = -0.40
CLASS14_SHIFT_XB3_X = -0.28
CLASS14_LOWER_XB3_Y = -0.48


def _default_black_strands(g: LTT) -> list[tuple[str, str]]:
    """One entry per black edge in `g` (frozenset has no duplicate pairs)."""
    return [(e[0], e[1]) for e in sorted(g.black_edges)]


def _append_black_edge_draws(
    lines: list[str],
    pos: dict[str, tuple[float, float]],
    strands: Sequence[tuple[str, str]],
    *,
    class_one_manual: bool = False,
    class_two_manual: bool = False,
    class_three_manual: bool = False,
    class_four_manual: bool = False,
    class_five_manual: bool = False,
    class_six_manual: bool = False,
    class_seven_manual: bool = False,
    class_eight_manual: bool = False,
    class_nine_manual: bool = False,
    class_ten_manual: bool = False,
    class_eleven_manual: bool = False,
    class_twelve_manual: bool = False,
    class_thirteen_manual: bool = False,
    class_fourteen_manual: bool = False,
) -> None:
    """Draw black edges as cubics bowed away from the figure centroid to reduce crossings."""
    gcx, gcy = _centroid_xy(pos)
    pair_counts = Counter(tuple(sorted((a, b))) for a, b in strands)
    parallel_slot: dict[tuple[str, str], int] = defaultdict(int)
    singleton_idx = 0

    ordered = sorted(
        strands, key=lambda ab: (ORDER.index(ab[0]), ORDER.index(ab[1]))
    )
    for a, b in ordered:
        key = tuple(sorted((a, b)))
        k = parallel_slot[key]
        parallel_slot[key] += 1
        n_parallel = pair_counts[key]

        na, nb = tikz_node_name(a), tikz_node_name(b)
        ax, ay = pos[a]
        bx, by = pos[b]

        if class_one_manual and n_parallel == 1:
            if key in {
                ("x1", "xb1"),
                ("x2", "xb2"),
                ("x3", "xb3"),
            }:
                lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
                continue
            if key == ("x5", "xb5"):
                (c1x, c1y), (c2x, c2y) = _black_bezier_controls_arc_left(
                    ax, ay, bx, by, CLASS1_LEFT_ARC_STRENGTH_X5_XB5
                )
                lines.append(
                    rf"\draw[blackedge] ({na}) "
                    rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
                )
                continue

        if class_two_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x2", "xb2"),
            ("x5", "xb5"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_two_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS2_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_three_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x2", "xb2"),
            ("x4", "xb4"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_three_manual and n_parallel == 1 and key == ("x5", "xb5"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS3_X5_XB5_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_four_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x2", "xb2"),
            ("x4", "xb4"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_four_manual and n_parallel == 1 and key == ("x3", "xb3"):
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls_arc_left(
                ax, ay, bx, by, CLASS4_LEFT_ARC_STRENGTH_X3_XB3
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_five_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x2", "xb2"),
            ("x3", "xb3"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_five_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS5_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_five_manual and n_parallel == 1 and key == ("x5", "xb5"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS5_X5_XB5_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_six_manual and n_parallel == 1 and key in {
            ("x2", "xb2"),
            ("x3", "xb3"),
            ("x5", "xb5"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_six_manual and n_parallel == 1 and key == ("x1", "xb1"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS6_X1_XB1_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_six_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS6_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_seven_manual and n_parallel == 1 and key in {
            ("x3", "xb3"),
            ("x5", "xb5"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_seven_manual and n_parallel == 1 and key == ("x1", "xb1"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS7_X1_XB1_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_seven_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS7_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_eight_manual and n_parallel == 1 and key == ("x3", "xb3"):
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_eight_manual and n_parallel == 1 and key == ("x1", "xb1"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS8_X1_XB1_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_eight_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS8_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_eight_manual and n_parallel == 1 and key == ("x5", "xb5"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS8_X5_XB5_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_nine_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x3", "xb3"),
            ("x5", "xb5"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_nine_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS9_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_nine_manual and n_parallel == 1 and key == ("x2", "xb2"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS9_X2_XB2_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_ten_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x3", "xb3"),
            ("x5", "xb5"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_ten_manual and n_parallel == 1 and key == ("x2", "xb2"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS10_X2_XB2_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_ten_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS10_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_eleven_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x3", "xb3"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_eleven_manual and n_parallel == 1 and key == ("x2", "xb2"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS11_X2_XB2_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_eleven_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS11_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_eleven_manual and n_parallel == 1 and key == ("x5", "xb5"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS11_X5_XB5_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_twelve_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x2", "xb2"),
            ("x5", "xb5"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_twelve_manual and n_parallel == 1 and key == ("x3", "xb3"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS12_X3_XB3_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_twelve_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS12_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_thirteen_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x5", "xb5"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_thirteen_manual and n_parallel == 1 and key == ("x3", "xb3"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS13_X3_XB3_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_thirteen_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS13_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_fourteen_manual and n_parallel == 1 and key in {
            ("x1", "xb1"),
            ("x2", "xb2"),
        }:
            lines.append(rf"\draw[blackedge] ({na}) -- ({nb});")
            continue

        if class_fourteen_manual and n_parallel == 1 and key == ("x3", "xb3"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS14_X3_XB3_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_fourteen_manual and n_parallel == 1 and key == ("x4", "xb4"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS14_X4_XB4_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_fourteen_manual and n_parallel == 1 and key == ("x5", "xb5"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS14_X5_XB5_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if class_four_manual and n_parallel == 1 and key == ("x5", "xb5"):
            strength = (
                BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
                * CLASS4_X5_XB5_STRENGTH_FACTOR
            )
            singleton_idx += 1
            (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
                ax, ay, bx, by, gcx, gcy, strength
            )
            lines.append(
                rf"\draw[blackedge] ({na}) "
                rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
            )
            continue

        if n_parallel > 1:
            strength = (
                BLACK_ROUTE_STRENGTH[k % len(BLACK_ROUTE_STRENGTH)]
                + k * PARALLEL_ROUTE_STEP
            )
        else:
            strength = BLACK_ROUTE_STRENGTH[singleton_idx % len(BLACK_ROUTE_STRENGTH)]
            singleton_idx += 1

        (c1x, c1y), (c2x, c2y) = _black_bezier_controls(
            ax, ay, bx, by, gcx, gcy, strength
        )
        lines.append(
            rf"\draw[blackedge] ({na}) "
            rf".. controls ({c1x:.2f},{c1y:.2f}) and ({c2x:.2f},{c2y:.2f}) .. ({nb});"
        )


def lab_order(l: str) -> int:
    return ORDER.index(l)


def latex_label(code: str) -> str:
    if code.startswith("xb"):
        return rf"$\bar{{x}}_{{{code[2:]}}}$"
    if code.startswith("x"):
        return rf"$x_{{{code[1:]}}}$"
    raise ValueError(code)


def tikz_node_name(lab: str) -> str:
    return "n" + lab.replace("xb", "b")


def _position_x1_left_of_red_triangle(
    pos: dict[str, tuple[float, float]],
    triples: list[frozenset[str]],
    g: LTT,
) -> None:
    """Place $x_1$ just left of the purple triangle containing the red-edge partner."""
    rv = g.red_vertex
    a, b = g.red_edge
    partner = b if a == rv else a
    for tri in triples:
        if partner not in tri:
            continue
        pts = [pos[v] for v in tri]
        min_x = min(p[0] for p in pts)
        _, y_partner = pos[partner]
        pos["x1"] = (min_x - X1_LEFT_OF_TRIANGLE_GAP, y_partner)
        return
    pos["x1"] = X1_FALLBACK_POS


def triple_partition(g: LTT) -> list[frozenset[str]]:
    pool = {"xb1", "x2", "xb2", "x3", "xb3", "x4", "xb4", "x5", "xb5"}
    pe = set(g.purple_edges)

    def has(u: str, v: str) -> bool:
        return tuple(sorted((u, v))) in pe

    remaining = set(pool)
    triples: list[frozenset[str]] = []
    while remaining:
        v = min(remaining, key=lab_order)
        partners = sorted([u for u in remaining if u != v and has(v, u)], key=lab_order)
        assert len(partners) == 2, (v, partners, remaining)
        tri = frozenset({v, partners[0], partners[1]})
        triples.append(tri)
        remaining -= tri
    triples.sort(key=lambda T: min(lab_order(x) for x in T))
    return triples


def tikz_picture_for_graph(
    g: LTT,
    *,
    black_strands: Sequence[tuple[str, str]] | None = None,
    class_one_manual: bool = False,
    class_two_manual: bool = False,
    class_three_manual: bool = False,
    class_four_manual: bool = False,
    class_five_manual: bool = False,
    class_six_manual: bool = False,
    class_seven_manual: bool = False,
    class_eight_manual: bool = False,
    class_nine_manual: bool = False,
    class_ten_manual: bool = False,
    class_eleven_manual: bool = False,
    class_twelve_manual: bool = False,
    class_thirteen_manual: bool = False,
    class_fourteen_manual: bool = False,
    straight_red_edge: bool = False,
) -> str:
    """Emit TikZ for `g`.

    Pass `black_strands` with repeated (a,b) pairs if several black edges join the same
    vertices; those parallels are drawn with alternating bulge direction and increasing
    looseness. When omitted, strands are taken from `g.black_edges` (no duplicates).

    ``class_one_manual``: layout tweaks for appendix Class~1 only (swap $x_5\leftrightarrow$
    $\bar x_2$, swap $\bar x_3\leftrightarrow\bar x_5$, swap $x_3\leftrightarrow x_4$; shift $x_3$
    somewhat down and slightly to the left; place $L_2$ and $L_3$ at the centroids of the second and third purple triples;
    straight $x_1$--$\bar x_1$, $x_2$--$\bar x_2$, and $x_3$--$\bar x_3$, left-arched $x_5$--$\bar x_5$).

    ``class_two_manual``: appendix Class~2 only; swap $\bar x_2\leftrightarrow\bar x_5$
    positions; shift $\bar x_2$ somewhat to the left and $x_2$ somewhat down; place $L_2$ and $L_3$ at the centroids of the second and
    third purple triples; straight black edges $x_1$--$\bar x_1$, $x_2$--$\bar x_2$, and $x_5$--$\bar x_5$; $x_4$--$\bar x_4$
    uses half the usual cubic bulge strength.

    ``class_three_manual``: appendix Class~3 only; shift $x_1$ and $x_2$ somewhat down and slightly
    to the right and shift $x_4$ somewhat down and slightly to the left; place $L_2$ and $L_3$ at the
    centroids of the second and third purple triples; straight black edges $x_1$--$\bar x_1$,
    $x_2$--$\bar x_2$, and $x_4$--$\bar x_4$; $x_5$--$\bar x_5$ uses half the usual cubic bulge
    strength.

    Red edge $(x_1,x_2)$ is drawn straight when any ``class_*_manual`` flag is set (Classes 1--4)
    or when ``straight_red_edge`` is true (appendix Classes 5--14).

    ``class_four_manual``: appendix Class~4 only; swap $x_2\leftrightarrow x_4$, $\bar x_1\leftrightarrow\bar x_4$, and
    $\bar x_2\leftrightarrow\bar x_5$ positions; place $\bar x_4$ directly above $\bar x_1$ and move $\bar x_3$ to halfway
    between their vertical levels; place $x_1$ directly below $x_3$ with vertical level between $x_2$ and $\bar x_5$;
    straight black edges $x_1$--$\bar x_1$, $x_2$--$\bar x_2$, $x_3$--$\bar x_3$,
    and $x_4$--$\bar x_4$; $x_5$--$\bar x_5$ uses half the usual cubic bulge (same as Class~3).

    ``class_five_manual``: appendix Class~5 only; swap $x_3\leftrightarrow x_4$ and
    $\bar x_2\leftrightarrow\bar x_4$ positions; shift $x_3$ somewhat down and slightly to the left and $\bar x_3$
    somewhat further up and slightly to the left; shift $x_1$ and $x_2$ somewhat down; place $L_2$ and $L_3$ at the centroids
    of the second and third purple triples;
    straight black $x_1$--$\bar x_1$, $x_2$--$\bar x_2$, and $x_3$--$\bar x_3$; $x_4$--$\bar x_4$ uses a larger cubic
    bulge than the default strand; $x_5$--$\bar x_5$ uses two thirds of the default cubic bulge.

    ``class_six_manual``: appendix Class~6 only; swap $\bar x_1\leftrightarrow x_3$ positions;
    straight black $x_3$--$\bar x_3$ and $x_5$--$\bar x_5$; $x_1$--$\bar x_1$ uses a milder cubic bulge than the default strand.

    ``class_seven_manual``: appendix Class~7 only; swap $\bar x_1\leftrightarrow x_3$ and
    $\bar x_2\leftrightarrow\bar x_3$ positions; straight black $x_3$--$\bar x_3$ and $x_5$--$\bar x_5$; $x_1$--$\bar x_1$ and $x_4$--$\bar x_4$ use milder cubic bulges than the default strand.

    ``class_eight_manual``: appendix Class~8 only; swap $\bar x_1\leftrightarrow x_3$ positions;
    straight black $x_3$--$\bar x_3$; $x_1$--$\bar x_1$, $x_4$--$\bar x_4$, and $x_5$--$\bar x_5$ use milder cubic bulges than the default strand.

    ``class_nine_manual``: appendix Class~9 only; swap $\bar x_3\leftrightarrow\bar x_5$ positions; raise
    $x_5$ and $\bar x_5$ slightly; place $L_3$ at the centroid of the third purple triple; straight black
    $x_1$--$\bar x_1$, $x_3$--$\bar x_3$, and $x_5$--$\bar x_5$; $x_2$--$\bar x_2$ and $x_4$--$\bar x_4$ use milder
    cubic bulges than the default strand.

    ``class_ten_manual``: appendix Class~10 only; swap $\bar x_3\leftrightarrow\bar x_5$ positions and offset
    $\bar x_3$ slightly up and to the right; swap $x_4\leftrightarrow x_5$ positions; shift $x_3$ somewhat down and slightly to
    the left; place $L_2$ and $L_3$ at the centroids of the second and third purple triples; straight black $x_1$--$\bar x_1$,
    $x_3$--$\bar x_3$, and $x_5$--$\bar x_5$; $x_2$--$\bar x_2$ and $x_4$--$\bar x_4$ use half the default cubic bulge strength.

    ``class_eleven_manual``: appendix Class~11 only; shift $x_3$ slightly down and to the left and $\bar x_3$ further up and
    to the left; place $L_2$ and $L_3$ at the centroids of the second and third purple triples; straight black $x_1$--$\bar x_1$
    and $x_3$--$\bar x_3$; $x_2$--$\bar x_2$ and $x_4$--$\bar x_4$ use one quarter of the default cubic bulge strength;
    $x_5$--$\bar x_5$ uses half the default cubic bulge strength.

    ``class_twelve_manual``: appendix Class~12 only; swap $\bar x_2\leftrightarrow\bar x_5$ positions; shift $x_2$ somewhat down,
    shift $x_5$ slightly up/right, and shift $\bar x_5$ somewhat up/slightly left; place $L_2$ and $L_3$ at the centroids of
    the second and third purple triples; straight black $x_1$--$\bar x_1$, $x_2$--$\bar x_2$, and $x_5$--$\bar x_5$;
    $x_3$--$\bar x_3$ uses one quarter of the default cubic bulge strength.

    ``class_thirteen_manual``: appendix Class~13 only; shift $x_1$ somewhat down and shift $\bar x_3$ somewhat down/left; place
    $L_2$ and $L_3$ at the centroids of the second and third purple triples; straight black $x_1$--$\bar x_1$ and $x_5$--$\bar x_5$;
    $x_3$--$\bar x_3$ uses half the default cubic bulge strength; $x_4$--$\bar x_4$ uses one quarter of the default cubic bulge strength.

    ``class_fourteen_manual``: appendix Class~14 only; swap $\bar x_1\leftrightarrow\bar x_4$ positions;
    and shift $\bar x_3$ somewhat down/slightly left; place $L_2$ and $L_3$ at the centroids of the second and third purple triples;
    straight black $x_1$--$\bar x_1$ and $x_2$--$\bar x_2$; $x_3$--$\bar x_3$ and $x_5$--$\bar x_5$ use half the default cubic
    bulge strength; $x_4$--$\bar x_4$ uses one quarter of the default cubic bulge strength.
    """
    triples = triple_partition(g)
    lines: list[str] = [TIKZ_OPEN]

    pos: dict[str, tuple[float, float]] = {}

    for ci, tri in enumerate(triples):
        verts = sorted(tri, key=lab_order)
        slots = SLOT_COORDS[ci]
        for vi, lab in enumerate(verts):
            pos[lab] = slots[vi]

    _position_x1_left_of_red_triangle(pos, triples, g)

    if class_one_manual:
        pos["x5"], pos["xb2"] = pos["xb2"], pos["x5"]
        pos["xb3"], pos["xb5"] = pos["xb5"], pos["xb3"]
        pos["x3"], pos["x4"] = pos["x4"], pos["x3"]
        oxb2x, oxb2y = pos["xb2"]
        pos["xb2"] = (
            oxb2x + CLASS1_SHIFT_XB2_X,
            oxb2y + CLASS1_RAISE_XB2_Y,
        )
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x,
            ox2y + CLASS1_LOWER_X2_Y,
        )
        oxb5x, oxb5y = pos["xb5"]
        pos["xb5"] = (
            oxb5x + CLASS1_SHIFT_XB5_X,
            oxb5y + CLASS1_RAISE_XB5_Y,
        )
        ox3x, ox3y = pos["x3"]
        pos["x3"] = (
            ox3x + CLASS1_SHIFT_X3_X,
            ox3y + CLASS1_LOWER_X3_Y,
        )

    if class_two_manual:
        pos["xb2"], pos["xb5"] = pos["xb5"], pos["xb2"]
        ox1x, ox1y = pos["x1"]
        pos["x1"] = (
            ox1x,
            ox1y + CLASS2_LOWER_X1_Y,
        )
        oxb2x, oxb2y = pos["xb2"]
        pos["xb2"] = (
            oxb2x + CLASS2_SHIFT_XB2_X,
            oxb2y,
        )
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x + CLASS2_SHIFT_X2_X,
            ox2y + CLASS2_LOWER_X2_Y,
        )

    if class_three_manual:
        ox1x, ox1y = pos["x1"]
        pos["x1"] = (
            ox1x + CLASS3_SHIFT_X1_X,
            ox1y + CLASS3_LOWER_X1_Y,
        )
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x + CLASS3_SHIFT_X2_X,
            ox2y + CLASS3_LOWER_X2_Y,
        )
        ox4x, ox4y = pos["x4"]
        pos["x4"] = (
            ox4x + CLASS3_SHIFT_X4_X,
            ox4y + CLASS3_LOWER_X4_Y,
        )

    if class_four_manual:
        pos["x2"], pos["x4"] = pos["x4"], pos["x2"]
        pos["xb1"], pos["xb4"] = pos["xb4"], pos["xb1"]
        pos["xb2"], pos["xb5"] = pos["xb5"], pos["xb2"]
        ox4x, ox4y = pos["x4"]
        pos["x4"] = (
            ox4x + CLASS4_SHIFT_X4_X,
            ox4y + CLASS4_LOWER_X4_Y,
        )
        oxb4x, oxb4y = pos["xb4"]
        pos["xb4"] = (
            oxb4x + CLASS4_SHIFT_XB4_X,
            oxb4y + CLASS4_RAISE_XB4_Y,
        )
        oxb1x, oxb1y = pos["xb1"]
        pos["xb1"] = (
            oxb1x + CLASS4_SHIFT_XB1_X,
            oxb1y + CLASS4_LOWER_XB1_Y,
        )
        _, oxb4y = pos["xb4"]
        pos["xb4"] = (
            pos["xb1"][0],
            oxb4y,
        )
        oxb3x, _ = pos["xb3"]
        xb1y = pos["xb1"][1]
        xb4y = pos["xb4"][1]
        pos["xb3"] = (
            oxb3x,
            (xb1y + xb4y) / 2.0,
        )
        oxb2x, oxb2y = pos["xb2"]
        pos["xb2"] = (
            oxb2x,
            oxb2y + CLASS4_RAISE_XB2_Y,
        )
        x3x, _ = pos["x3"]
        _, x2y = pos["x2"]
        _, xb5y = pos["xb5"]
        x1y = x2y + (xb5y - x2y) * CLASS4_X1_LEVEL_BETWEEN_X2_AND_XB5_FRACTION
        pos["x1"] = (
            x3x,
            x1y,
        )

    if class_five_manual:
        pos["x3"], pos["x4"] = pos["x4"], pos["x3"]
        pos["xb2"], pos["xb4"] = pos["xb4"], pos["xb2"]
        ox1x, ox1y = pos["x1"]
        pos["x1"] = (
            ox1x,
            ox1y + CLASS5_LOWER_X1_Y,
        )
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x,
            ox2y + CLASS5_LOWER_X2_Y,
        )
        oxb1x, oxb1y = pos["xb1"]
        pos["xb1"] = (
            oxb1x + CLASS5_SHIFT_XB1_X,
            oxb1y,
        )
        oxb2x, oxb2y = pos["xb2"]
        pos["xb2"] = (
            oxb2x + CLASS5_SHIFT_XB2_X,
            oxb2y,
        )
        oxb4x, oxb4y = pos["xb4"]
        pos["xb4"] = (
            oxb4x,
            oxb4y + CLASS5_RAISE_XB4_Y,
        )
        ox3x, ox3y = pos["x3"]
        pos["x3"] = (
            ox3x + CLASS5_SHIFT_X3_X,
            ox3y + CLASS5_LOWER_X3_Y,
        )
        oxb3x, oxb3y = pos["xb3"]
        pos["xb3"] = (
            oxb3x + CLASS5_SHIFT_XB3_X,
            oxb3y + CLASS5_RAISE_XB3_Y,
        )

    if class_six_manual:
        pos["xb1"], pos["x3"] = pos["x3"], pos["xb1"]
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x + CLASS6_SHIFT_X2_X,
            ox2y + CLASS6_RAISE_X2_Y,
        )
        oxb2x, oxb2y = pos["xb2"]
        pos["xb2"] = (
            oxb2x + CLASS6_SHIFT_XB2_X,
            oxb2y + CLASS6_LOWER_XB2_Y,
        )
        oxb3x, oxb3y = pos["xb3"]
        pos["xb3"] = (
            oxb3x,
            oxb3y + CLASS6_RAISE_XB3_Y,
        )
        ox5x, ox5y = pos["x5"]
        pos["x5"] = (
            ox5x + CLASS6_SHIFT_X5_X,
            ox5y + CLASS6_LOWER_X5_Y,
        )
        d_nb1_nb3 = math.dist(pos["xb1"], pos["xb3"])
        right_shift = d_nb1_nb3 * CLASS6_RIGHT_SHIFT_DISTANCE_FRACTION
        for _lab in ("x1", "x2", "x3", "xb1"):
            lx, ly = pos[_lab]
            pos[_lab] = (lx + right_shift, ly)
        xb3x, xb3y = pos["xb3"]
        xb5x, xb5y = pos["xb5"]
        # Place nb5 directly above nb3.
        pos["xb5"] = (
            xb3x,
            xb5y,
        )
        xb4x, _ = pos["xb4"]
        # Place nb4 halfway (vertically) between nb3 and nb5.
        pos["xb4"] = (
            xb4x,
            (pos["xb3"][1] + pos["xb5"][1]) / 2.0,
        )
        x5x, x5y = pos["x5"]
        xb2x, _ = pos["xb2"]
        # Place nb2 at the same vertical level as nx5.
        pos["xb2"] = (
            xb2x,
            x5y,
        )
        x3x, x3y = pos["x3"]
        xb2x_new, xb2y_new = pos["xb2"]
        # Place nx3 directly below nb2 (aligned x; keep it below in y).
        pos["x3"] = (
            xb2x_new,
            min(x3y, xb2y_new - 0.24),
        )
        x2x, _ = pos["x2"]
        # Place nx2 halfway (vertically) between nb1 and nx3.
        x2_target_y = (pos["xb1"][1] + pos["x3"][1]) / 2.0
        pos["x2"] = (
            x2x,
            x2_target_y,
        )
        x1x, _ = pos["x1"]
        old_x2x = x2x
        old_x1_to_x2 = abs(old_x2x - x1x)
        # Place nx1 directly left of nx2 (same y, preserve horizontal separation).
        pos["x1"] = (
            pos["x2"][0] - max(old_x1_to_x2, 0.24),
            pos["x2"][1],
        )

    if class_seven_manual:
        pos["xb1"], pos["x3"] = pos["x3"], pos["xb1"]
        pos["xb2"], pos["xb3"] = pos["xb3"], pos["xb2"]
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x + CLASS7_SHIFT_X2_X,
            ox2y + CLASS7_RAISE_X2_Y,
        )
        oxb3x, oxb3y = pos["xb3"]
        pos["xb3"] = (
            oxb3x + CLASS7_SHIFT_XB3_X,
            oxb3y + CLASS7_LOWER_XB3_Y,
        )
        oxb5x, oxb5y = pos["xb5"]
        pos["xb5"] = (
            oxb5x + CLASS7_SHIFT_XB5_X,
            oxb5y + CLASS7_LOWER_XB5_Y,
        )

    if class_eight_manual:
        pos["xb1"], pos["x3"] = pos["x3"], pos["xb1"]
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x + CLASS8_SHIFT_X2_X,
            ox2y + CLASS8_RAISE_X2_Y,
        )
        oxb2x, oxb2y = pos["xb2"]
        pos["xb2"] = (
            oxb2x + CLASS8_SHIFT_XB2_X,
            oxb2y + CLASS8_LOWER_XB2_Y,
        )
        x4x, x4y = pos["x4"]
        oxb4x, _ = pos["xb4"]
        pos["xb4"] = (
            x4x,
            x4y + CLASS8_LOWER_XB4_Y,
        )

    if class_nine_manual:
        pos["xb3"], pos["xb5"] = pos["xb5"], pos["xb3"]
        ox1x, ox1y = pos["x1"]
        pos["x1"] = (
            ox1x,
            ox1y + CLASS9_LOWER_X1_Y,
        )
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x,
            ox2y + CLASS9_LOWER_X2_Y,
        )
        ox3x, ox3y = pos["x3"]
        pos["x3"] = (
            ox3x + CLASS9_SHIFT_X3_X,
            ox3y + CLASS9_LOWER_X3_Y,
        )
        for _x5_lab in ("x5", "xb5"):
            ox, oy = pos[_x5_lab]
            pos[_x5_lab] = (ox, oy + CLASS9_RAISE_X5_PAIR_Y)
        oxb5x, oxb5y = pos["xb5"]
        pos["xb5"] = (
            oxb5x,
            oxb5y + CLASS9_RAISE_XB5_Y,
        )

    if class_ten_manual:
        pos["xb3"], pos["xb5"] = pos["xb5"], pos["xb3"]
        ox1x, ox1y = pos["x1"]
        pos["x1"] = (
            ox1x,
            ox1y + CLASS10_LOWER_X1_Y,
        )
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x,
            ox2y + CLASS10_LOWER_X2_Y,
        )
        oxb3x, oxb3y = pos["xb3"]
        pos["xb3"] = (
            oxb3x + CLASS10_SHIFT_XB3_X,
            oxb3y + CLASS10_RAISE_XB3_Y,
        )
        oxb5x, oxb5y = pos["xb5"]
        pos["xb5"] = (
            oxb5x + CLASS10_SHIFT_XB5_X,
            oxb5y,
        )
        pos["x4"], pos["x5"] = pos["x5"], pos["x4"]
        ox3x, ox3y = pos["x3"]
        pos["x3"] = (
            ox3x + CLASS10_SHIFT_X3_X,
            ox3y + CLASS10_LOWER_X3_Y,
        )

    if class_eleven_manual:
        ox3x, ox3y = pos["x3"]
        pos["x3"] = (
            ox3x + CLASS11_SHIFT_X3_X,
            ox3y + CLASS11_LOWER_X3_Y,
        )
        oxb3x, oxb3y = pos["xb3"]
        pos["xb3"] = (
            oxb3x + CLASS11_SHIFT_XB3_X,
            oxb3y + CLASS11_RAISE_XB3_Y,
        )

    if class_twelve_manual:
        pos["xb2"], pos["xb5"] = pos["xb5"], pos["xb2"]
        ox2x, ox2y = pos["x2"]
        pos["x2"] = (
            ox2x,
            ox2y + CLASS12_LOWER_X2_Y,
        )
        ox5x, ox5y = pos["x5"]
        pos["x5"] = (
            ox5x + CLASS12_SHIFT_X5_X,
            ox5y + CLASS12_RAISE_X5_Y,
        )
        oxb5x, oxb5y = pos["xb5"]
        pos["xb5"] = (
            oxb5x + CLASS12_SHIFT_XB5_X,
            oxb5y + CLASS12_RAISE_XB5_Y,
        )

    if class_thirteen_manual:
        x2x, x2y = pos["x2"]
        ox1x, ox1y = pos["x1"]
        pos["x1"] = (
            x2x,
            min(ox1y + CLASS13_LOWER_X1_Y, x2y - CLASS13_X1_BELOW_X2_GAP),
        )
        oxb3x, oxb3y = pos["xb3"]
        pos["xb3"] = (
            oxb3x + CLASS13_SHIFT_XB3_X,
            oxb3y + CLASS13_LOWER_XB3_Y,
        )

    if class_fourteen_manual:
        pos["xb1"], pos["xb4"] = pos["xb4"], pos["xb1"]
        oxb3x, oxb3y = pos["xb3"]
        pos["xb3"] = (
            oxb3x + CLASS14_SHIFT_XB3_X,
            oxb3y + CLASS14_LOWER_XB3_Y,
        )
        x3x, _ = pos["x3"]
        _, xb3y_new = pos["xb3"]
        # Place x2 directly below x3 and at nb3's vertical level.
        pos["x2"] = (
            x3x,
            xb3y_new,
        )
        x2x, x2y = pos["x2"]
        _, xb5y = pos["xb5"]
        # Place x1 halfway (vertically) between x2 and nb5.
        x1_target_y = (x2y + xb5y) / 2.0
        pos["x1"] = (
            x2x,
            x1_target_y,
        )

    # Vertices (red x1 first for readability)
    rx, ry = pos["x1"]
    lines.append(
        rf"\node[redv] ({tikz_node_name('x1')}) at ({rx:.2f}, {ry:.2f}) {{{latex_label('x1')}}};"
    )
    for lab in sorted(pos.keys(), key=lab_order):
        if lab == "x1":
            continue
        x, y = pos[lab]
        lines.append(
            rf"\node[purpv] ({tikz_node_name(lab)}) at ({x:.2f}, {y:.2f}) {{{latex_label(lab)}}};"
        )

    # Purple edges (within triples)
    pe = set(g.purple_edges)
    drawn: set[tuple[str, str]] = set()

    def draw_purple(a: str, b: str) -> None:
        ka = tuple(sorted((a, b)))
        if ka not in pe:
            return
        if ka in drawn:
            return
        drawn.add(ka)
        lines.append(rf"\draw[purpleedge] ({tikz_node_name(a)}) -- ({tikz_node_name(b)});")

    for tri in triples:
        verts = sorted(tri, key=lab_order)
        for i in range(3):
            for j in range(i + 1, 3):
                draw_purple(verts[i], verts[j])

    # Black edges: fan out when several strands join the same two vertices
    strands = (
        list(black_strands) if black_strands is not None else _default_black_strands(g)
    )
    _append_black_edge_draws(
        lines,
        pos,
        strands,
        class_one_manual=class_one_manual,
        class_two_manual=class_two_manual,
        class_three_manual=class_three_manual,
        class_four_manual=class_four_manual,
        class_five_manual=class_five_manual,
        class_six_manual=class_six_manual,
        class_seven_manual=class_seven_manual,
        class_eight_manual=class_eight_manual,
        class_nine_manual=class_nine_manual,
        class_ten_manual=class_ten_manual,
        class_eleven_manual=class_eleven_manual,
        class_twelve_manual=class_twelve_manual,
        class_thirteen_manual=class_thirteen_manual,
        class_fourteen_manual=class_fourteen_manual,
    )

    # Red edge: straight $(x_1,x_2)$ for appendix Classes 1--14; cubic elsewhere.
    rv, rp = g.red_edge
    if (
        class_one_manual
        or class_two_manual
        or class_three_manual
        or class_four_manual
        or straight_red_edge
    ):
        lines.append(
            rf"\draw[rededge] ({tikz_node_name(rv)}) -- ({tikz_node_name(rp)});"
        )
    else:
        rax, ray = pos[rv]
        rbx, rby = pos[rp]
        gcx, gcy = _centroid_xy(pos)
        (rc1x, rc1y), (rc2x, rc2y) = _black_bezier_controls(
            rax, ray, rbx, rby, gcx, gcy, RED_ROUTE_STRENGTH
        )
        lines.append(
            rf"\draw[rededge] ({tikz_node_name(rv)}) "
            rf".. controls ({rc1x:.2f},{rc1y:.2f}) and ({rc2x:.2f},{rc2y:.2f}) "
            rf".. ({tikz_node_name(rp)});"
        )

    # Cluster labels L1,L2,L3 (optional visual cue) — same scale as slots
    _raw_centers = [(-5.55, -0.38), (2.55, 6.65), (7.55, -3.35)]
    cluster_centers = [
        (LAYOUT_SCALE * x, LAYOUT_SCALE * y) for x, y in _raw_centers
    ]
    for i, (cx, cy) in enumerate(cluster_centers, start=1):
        if (class_four_manual or class_six_manual) and i == 1:
            tri_l1 = triples[0]
            pts_l1 = [pos[v] for v in tri_l1]
            cx = sum(p[0] for p in pts_l1) / len(pts_l1)
            cy = sum(p[1] for p in pts_l1) / len(pts_l1)
        if (
            class_one_manual
            or class_two_manual
            or class_three_manual
            or class_four_manual
            or class_six_manual
            or class_seven_manual
            or class_eight_manual
            or class_nine_manual
            or class_five_manual
            or class_ten_manual
            or class_eleven_manual
            or class_twelve_manual
            or class_thirteen_manual
            or class_fourteen_manual
        ) and i == 2:
            tri_l2 = triples[1]
            pts_l2 = [pos[v] for v in tri_l2]
            cx = sum(p[0] for p in pts_l2) / len(pts_l2)
            cy = sum(p[1] for p in pts_l2) / len(pts_l2)
        if (
            class_one_manual
            or class_two_manual
            or class_three_manual
            or class_four_manual
            or class_six_manual
            or class_seven_manual
            or class_eight_manual
            or class_nine_manual
            or class_ten_manual
            or class_eleven_manual
            or class_five_manual
            or class_twelve_manual
            or class_thirteen_manual
            or class_fourteen_manual
        ) and i == 3:
            tri_l3 = triples[2]
            pts_l3 = [pos[v] for v in tri_l3]
            cx = sum(p[0] for p in pts_l3) / len(pts_l3)
            cy = sum(p[1] for p in pts_l3) / len(pts_l3)
        lines.append(rf"\node[lbl] at ({cx:.2f}, {cy:.2f}) {{$L_{i}$}};")

    lines.append(TIKZ_CLOSE)
    return "\n".join(lines)


def main() -> None:
    representatives: dict = {}
    members: dict = defaultdict(list)

    for idx, graph in enumerate(iter_distinguished_ltt(), start=1):
        key = canonical_signature(graph)
        members[key].append(idx)
        if key not in representatives:
            representatives[key] = graph

    keys = sorted(representatives.keys())
    out_lines: list[str] = []
    out_lines.append(
        "% Auto-generated by generate_ltt_appendix_tex.py — do not edit by hand "
        "(change generate_ltt_appendix_tex.py and re-run ``python generate_ltt_appendix_tex.py``)."
    )
    out_lines.append("")

    for class_num, k in enumerate(keys, start=1):
        g = representatives[k]
        mem = sorted(members[k])
        if len(mem) > 20:
            index_chunks = [mem[i:i + 24] for i in range(0, len(mem), 24)]
            chunk_strings = [
                ", ".join(str(m) for m in chunk) for chunk in index_chunks
            ]
            wrapped_indices = r"\\ ".join(chunk_strings)
            distinguished_line = (
                r"\noindent Distinguished indices:\\ "
                rf"$\{{{wrapped_indices}\}}$, ${len(mem)}$ total."
            )
        else:
            distinguished_line = (
                rf"\noindent Distinguished indices: "
                rf"$\{{{', '.join(str(m) for m in mem)}\}}$, ${len(mem)}$ total."
            )
        roman = CLASS_TO_ROMAN.get(class_num, str(class_num))
        out_lines.append(rf"\subsection*{{Class {class_num} ({roman})}}")
        out_lines.append(
            r"\noindent Representative of this ep-isomorphism class.\\"
        )
        out_lines.append(distinguished_line)
        out_lines.append(r"\begin{center}")
        out_lines.append(
            tikz_picture_for_graph(
                g,
                class_one_manual=(class_num == 1),
                class_two_manual=(class_num == 2),
                class_three_manual=(class_num == 3),
                class_four_manual=(class_num == 4),
                class_five_manual=(class_num == 5),
                class_six_manual=(class_num == 6),
                class_seven_manual=(class_num == 7),
                class_eight_manual=(class_num == 8),
                class_nine_manual=(class_num == 9),
                class_ten_manual=(class_num == 10),
                class_eleven_manual=(class_num == 11),
                class_twelve_manual=(class_num == 12),
                class_thirteen_manual=(class_num == 13),
                class_fourteen_manual=(class_num == 14),
                straight_red_edge=(5 <= class_num <= 14),
            )
        )
        out_lines.append(r"\end{center}")
        out_lines.append(r"\medskip")

    path = "ltt_appendix_generated.tex"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print(f"Wrote {path} ({len(keys)} figures).")


if __name__ == "__main__":
    main()
