"""
Run Section 1 algorithm (Steps 1--7) from Prompt_extracted and write Appendix C
(``preaut_appendix_generated.tex``).

Usage:
    python generate_preaut_appendix_tex.py
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from math import cos, pi, sin
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ltt_structures import (
    LTT,
    canonical_signature,
    generate_distinguished_ltt,
    graph_signature,
    purple_neighbor_pair_ordered,
    seed_ltt_structure,
    terminal_ga_step2,
    terminal_gb_step2,
)

Label = str
EdgeColor = str  # "none" | "purple" | "black" | "red"


def tikz_braced_font(font_decl: str) -> str:
    """
    TikZ ``font=`` values must be braced (e.g. ``font={\\\\Large}``).  Bare ``font=\\\\Large``
    inside ``\\\\begin{tikzpicture}[...]`` breaks PGF parsing; errors often show at the next ``}``.
    """
    return "{" + font_decl + "}"


# AUT visual sizing.  These fractions control *printed* size in the PDF (the arguments to
# ``\\resizebox``).  ``MANUAL_LAYOUT_FIGURE_SCALE`` only spreads TikZ coordinates; a uniform
# ``\\resizebox`` to a fixed ``\\linewidth``/``\\textheight`` cancels that, so always bump these
# when you want a visibly larger diagram.
AUT_DIAGRAM_DISPLAY_SCALE = 1.25
AUT_COMPONENT_DEFAULT_WIDTH = 0.95
AUT_COMPONENT_SCC1_WIDTH = 0.095
OMITTED_COMPONENT_DEFAULT_WIDTH = min(1.0, 0.95 * AUT_DIAGRAM_DISPLAY_SCALE)
OMITTED_COMPONENT_SCC1_WIDTH = min(1.0, 0.45 * AUT_DIAGRAM_DISPLAY_SCALE)
AUT_COMPONENT_MAX_HEIGHT = min(0.68, 0.52 * AUT_DIAGRAM_DISPLAY_SCALE)
# When SCC_1 is the full 14-box component, scale it to (nearly) one text page.
AUT_SCC1_FULL_PAGE_HEIGHT = min(0.96, 0.88 * AUT_DIAGRAM_DISPLAY_SCALE)
# After height scaling, shrink only if wider than this fraction of \\linewidth.
AUT_SCC1_FULL_PAGE_MAX_WIDTH_FRAC = 1.0
# Box-collapsed preAUT (14 boxes): target width after resize (cap at full line width).
AUT_BOX_COLLAPSED_RESIZE_WIDTH_FRAC = min(1.0, 0.98 * AUT_DIAGRAM_DISPLAY_SCALE)
LOOP_SIDE_BY_CLASS: Dict[int, str] = {
    1: "above",   # II
    2: "above",   # I
    3: "right",   # VII
    4: "right",   # VIII
    5: "above",   # VI
    6: "above",   # III
    7: "right",   # X
    8: "above",   # XII
    9: "right",   # IV
    10: "right",  # IX
    11: "right",  # XIII
    12: "left",   # V
    13: "left",   # XI
    14: "left",   # XIV
}

# Manual 14-box grid (design units). Applied: x *= column squeeze, then (x,y) *= global scale.
_MANUAL_BOX_POS_BASE: Dict[int, Tuple[float, float]] = {
    2: (0.0, 18.0),  # I
    1: (-8.0, 15.0),  # II
    6: (8.0, 15.0),  # III
    12: (-8.0, 12.0),  # V
    9: (8.0, 12.0),  # IV
    3: (-8.0, 9.0),  # VII
    4: (8.0, 9.0),  # VIII
    5: (-8.0, 6.0),  # VI
    7: (8.0, 6.0),  # X
    13: (-10.0, 1.5),  # XI
    8: (0.0, -1.125),  # XII
    10: (10.0, 1.5),  # IX
    14: (-8.0, -3.75),  # XIV
    11: (8.0, -3.75),  # XIII
}
# Distance between left/right columns: 25% smaller than base.
MANUAL_LAYOUT_COLUMN_X_FRAC = 0.75
# Spacing of nodes in manual layouts (does not set PDF size; see ``AUT_*`` resize fractions).
MANUAL_LAYOUT_FIGURE_SCALE = 1.3 * 1.2 * 1.25

# TikZ node circles and fonts (relative to edge span after ``\\resizebox``).  Was ~\\scriptsize /
# \\small on ~9--10mm discs; scaled ~2× for readability.
TIKZ_NODE_TEXT_SCALE = 2.0
_NTS = TIKZ_NODE_TEXT_SCALE
AUT_NODE_MIN_MM = 9.0 * _NTS
AUT_NODE_MIN_MM_BOXCOLLAPSE = 10.0 * _NTS
AUT_OUTNODE_MIN_MM = 8.5 * _NTS
AUT_NODE_INNER_SEP_PT = 1.4 * _NTS
AUT_NODE_INNER_SEP_BOXCOLLAPSE_PT = 1.6 * _NTS
AUT_OUTNODE_INNER_SEP_PT = 1.2 * _NTS
AUT_EDGE_LINE_PT = 0.85 * _NTS
AUT_LOOP_CUSTOM_MIN_MM = 9.0 * _NTS
UGV_MIN_MM = 9.0 * _NTS
UGV_INNER_SEP_PT = 1.0 * _NTS
UGEDGE_LINE_PT = 1.1 * _NTS
TIKZ_AUT_NODE_FONT_CMD = r"\Large"
TIKZ_AUT_EDGE_LABEL_FONT_CMD = r"\LARGE"
TIKZ_AUT_CAPTION_FONT_CMD = r"\Large"
TIKZ_UGV_FONT_CMD = r"\Large"
TIKZ_AUTLBL_STYLE = (
    "font="
    + tikz_braced_font(TIKZ_AUT_EDGE_LABEL_FONT_CMD)
    + ", transform shape, text=blue!60, fill=white, "
    + f"inner sep={1.6 * _NTS:.1f}pt"
)
TIKZ_AUTLBL_PERM_STYLE = (
    "font="
    + tikz_braced_font(TIKZ_AUT_EDGE_LABEL_FONT_CMD)
    + ", transform shape, text=green!50!black, fill=white, "
    + f"inner sep={1.6 * _NTS:.1f}pt"
)

MANUAL_BOX_POS: Dict[int, Tuple[float, float]] = {
    k: (
        MANUAL_LAYOUT_FIGURE_SCALE * MANUAL_LAYOUT_COLUMN_X_FRAC * x,
        MANUAL_LAYOUT_FIGURE_SCALE * y,
    )
    for k, (x, y) in _MANUAL_BOX_POS_BASE.items()
}


def latex_collapsed_edge_count_label(n: int) -> str:
    """TikZ math for ``n`` parallel preAUT edges of one kind (Step~2 or permutation)."""
    word = "edge" if n == 1 else "edges"
    return rf"{n}\,\mathrm{{{word}}}"


def _latex_aut_single_self_loop(
    class_idx: int,
    node_name: str,
    label_text: str,
    *,
    edge_style: str,
    lbl_style: str,
    geom_slot: int,
) -> str:
    """
    One colored self-loop. ``geom_slot`` separates a second loop (Step~2 vs permutation) visually.
    """
    _mm = AUT_LOOP_CUSTOM_MIN_MM + 3.5 * geom_slot
    if class_idx == 12:
        out_a, in_a = (58, 28) if geom_slot == 0 else (52, 34)
        return (
            rf"\draw[{edge_style}] ({node_name}) to[out={out_a},in={in_a},min distance={_mm:g}mm,looseness=11] "
            rf"node[{lbl_style}] {{$ {label_text} $}} ({node_name});"
            + "\n"
        )
    if class_idx == 5:
        out_a, in_a = (148, 118) if geom_slot == 0 else (142, 124)
        return (
            rf"\draw[{edge_style}] ({node_name}) to[out={out_a},in={in_a},min distance={_mm:g}mm,looseness=11] "
            rf"node[{lbl_style}] {{$ {label_text} $}} ({node_name});"
            + "\n"
        )
    # IV (9), IX (10), XIII (11): rotate the Step~2 (blue) ``loop right`` self-loop 45° CCW
    # (bisector ~0° → ~45°). Green permutations at IV/IX/XIII use explicit angles below.
    if class_idx in (9, 10, 11) and edge_style == "autedge":
        return (
            rf"\draw[{edge_style}] ({node_name}) to[out=68,in=22,min distance={_mm:g}mm,looseness=11] "
            rf"node[{lbl_style}] {{$ {label_text} $}} ({node_name});"
            + "\n"
        )
    # IV (9), IX (10): permutation (green) self-loop: ``loop right`` + 135° CCW + 180° CCW
    # (bisector ~315°; tangents are prior ``out=165,in=105`` rotated 180° around the node).
    if class_idx in (9, 10) and edge_style == "autedgeperm":
        return (
            rf"\draw[{edge_style}] ({node_name}) to[out=345,in=285,min distance={_mm:g}mm,looseness=11] "
            rf"node[{lbl_style}] {{$ {label_text} $}} ({node_name});"
            + "\n"
        )
    # XIII (11): permutation (green) ``loop right`` + 135° CCW + 180° CCW (bisector ~315°).
    if class_idx == 11 and edge_style == "autedgeperm":
        return (
            rf"\draw[{edge_style}] ({node_name}) to[out=345,in=285,min distance={_mm:g}mm,looseness=11] "
            rf"node[{lbl_style}] {{$ {label_text} $}} ({node_name});"
            + "\n"
        )
    loop_side = LOOP_SIDE_BY_CLASS.get(class_idx, "above")
    if geom_slot == 1:
        alt = {"above": "right", "right": "left", "left": "above", "below": "right"}
        loop_side = alt.get(loop_side, "right")
    return (
        rf"\draw[{edge_style}] ({node_name}) to[loop {loop_side}] node[{lbl_style}] {{$ {label_text} $}} ({node_name});"
        + "\n"
    )


def latex_aut_self_loop_collapsed(class_idx: int, node_name: str, n_step2: int, n_perm: int) -> str:
    """
    TikZ self-loop(s) at ``node_name``: blue for Step~2 edge counts, green for permutation counts.
    """
    parts: List[str] = []
    slot = 0
    if n_step2 > 0:
        parts.append(
            _latex_aut_single_self_loop(
                class_idx,
                node_name,
                latex_collapsed_edge_count_label(n_step2),
                edge_style="autedge",
                lbl_style="autlbl",
                geom_slot=slot,
            )
        )
        slot += 1
    if n_perm > 0:
        parts.append(
            _latex_aut_single_self_loop(
                class_idx,
                node_name,
                latex_collapsed_edge_count_label(n_perm),
                edge_style="autedgeperm",
                lbl_style="autlblperm",
                geom_slot=slot,
            )
        )
    return "".join(parts)


# User-provided authoritative dictionary:
# Box Roman numeral <-> ep-isomorphism class number.
CLASS_TO_ROMAN: Dict[int, str] = {
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


def roman_for_class(class_num: int) -> str:
    return CLASS_TO_ROMAN.get(class_num, str(class_num))


def latex_roman_for_class(class_num: int) -> str:
    return rf"\mathrm{{{roman_for_class(class_num)}}}"


def latex_math_vertex(lb: Label) -> str:
    if lb.startswith("xb"):
        return "\\bar{x}_{" + lb[2:] + "}"
    if lb.startswith("x"):
        return "x_{" + lb[1:] + "}"
    raise ValueError(f"unknown label {lb!r}")


def latex_step2_label(label: str) -> str:
    out = label
    for i in range(1, 6):
        out = out.replace(f"xb{i}", f"\\bar{{x}}_{{{i}}}")
    for i in range(1, 6):
        out = out.replace(f"x{i}", f"x_{{{i}}}")
    return out


def latex_edge_set(edges: Sequence[Tuple[Label, Label]]) -> str:
    pieces: List[str] = []
    for a, b in sorted(edges):
        pieces.append(rf"\{{{latex_math_vertex(a)},\,{latex_math_vertex(b)}\}}")
    return ",\; ".join(pieces)


def edge_sort_key(e: Tuple[Label, Label]) -> Tuple[Label, Label]:
    return (e[0], e[1])


def latex_edge_list_inline(edges: Sequence[Tuple[Label, Label]]) -> str:
    pieces: List[str] = []
    for a, b in sorted(edges, key=edge_sort_key):
        pieces.append(rf"\{{{latex_math_vertex(a)},\,{latex_math_vertex(b)}\}}")
    return ",\; ".join(pieces)


def purple_partition_edge_rows(edges: Sequence[Tuple[Label, Label]]) -> List[List[Tuple[Label, Label]]]:
    sorted_edges = sorted(edges, key=edge_sort_key)
    vertices = sorted({v for a, b in sorted_edges for v in (a, b)})
    adj = {v: set() for v in vertices}
    for a, b in sorted_edges:
        adj[a].add(b)
        adj[b].add(a)

    seen: set[Label] = set()
    components: List[List[Label]] = []
    for v in vertices:
        if v in seen:
            continue
        stack = [v]
        comp: List[Label] = []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.append(cur)
            for nb in sorted(adj[cur]):
                if nb not in seen:
                    stack.append(nb)
        components.append(sorted(comp))

    components.sort(key=lambda comp: min(comp))
    rows: List[List[Tuple[Label, Label]]] = []
    for comp in components:
        comp_set = set(comp)
        row = [e for e in sorted_edges if e[0] in comp_set and e[1] in comp_set]
        if row:
            rows.append(row)
    return rows


def latex_purple_partition_lines(edges: Sequence[Tuple[Label, Label]]) -> str:
    rows = purple_partition_edge_rows(edges)
    lines: List[str] = []
    for idx, row in enumerate(rows, start=1):
        row_tex = ",\; ".join(
            rf"\{{{latex_math_vertex(a)},\,{latex_math_vertex(b)}\}}"
            for a, b in row
        )
        lines.append(rf"$P_{{{idx}}}: {row_tex}$")
    return "\\\\\n".join(lines)


def latex_edge_set_with_last_five_new_line(edges: Sequence[Tuple[Label, Label]]) -> str:
    pieces: List[str] = []
    for a, b in sorted(edges):
        pieces.append(rf"\{{{latex_math_vertex(a)},\,{latex_math_vertex(b)}\}}")

    if len(pieces) <= 5:
        return ",\; ".join(pieces)

    first_line = ",\; ".join(pieces[:-5])
    second_line = ",\; ".join(pieces[-5:])
    return rf"\begin{{aligned}}[t] {first_line},\\ {second_line} \end{{aligned}}"


def latex_node_name(name: str) -> str:
    if name == "G":
        return "G"
    if name.startswith("G") and name[1:].isdigit():
        return rf"G_{{{name[1:]}}}"
    return name


def preaut_dict_node_sort_key(name: str) -> Tuple[int, str]:
    """``G`` first, then ``G1``, ``G2``, … by numeric index (not lexicographic on strings)."""
    if name == "G":
        return (0, name)
    if name.startswith("G") and name[1:].isdigit():
        return (int(name[1:]), name)
    return (999, name)


def latex_state_name(name: str) -> str:
    if name.startswith("B") and name[1:].isdigit():
        class_num = int(name[1:])
        return rf"\mathrm{{Class}}_{{{class_num}}}\,({latex_roman_for_class(class_num)})"
    return latex_node_name(name)


def edge_key(a: Label, b: Label) -> Tuple[Label, Label]:
    return (a, b) if a < b else (b, a)


def graph_vertex_color(g: LTT, v: Label) -> str:
    return "red" if v == g.red_vertex else "purple"


def graph_edge_color(g: LTT, a: Label, b: Label) -> EdgeColor:
    e = edge_key(a, b)
    if e == g.red_edge:
        return "red"
    if e in g.purple_edges:
        return "purple"
    if e in g.black_edges:
        return "black"
    return "none"


def vertex_profile(g: LTT, v: Label) -> Tuple:
    labels = g.labels
    deg = {"red": 0, "purple": 0, "black": 0, "none": 0}
    for w in labels:
        if w == v:
            continue
        deg[graph_edge_color(g, v, w)] += 1
    return (
        graph_vertex_color(g, v),
        deg["red"],
        deg["purple"],
        deg["black"],
        deg["none"],
    )


def find_ep_isomorphism(source: LTT, target: LTT) -> Optional[Dict[Label, Label]]:
    """
    Ep-isomorphism per Prompt_extracted Definition:
    - vertex colors preserved (red vs purple)
    - edge colors preserved (red/purple/black/non-edge)
    """
    s_labels = list(source.labels)
    t_labels = list(target.labels)
    if len(s_labels) != len(t_labels):
        return None

    s_profiles = {v: vertex_profile(source, v) for v in s_labels}
    t_profiles = {v: vertex_profile(target, v) for v in t_labels}

    # Candidate targets with matching local profile.
    candidates: Dict[Label, List[Label]] = {}
    for sv in s_labels:
        cand = [tv for tv in t_labels if s_profiles[sv] == t_profiles[tv]]
        if not cand:
            return None
        candidates[sv] = cand

    # Backtracking map source->target.
    assigned: Dict[Label, Label] = {}
    used_targets: set[Label] = set()

    def order_unassigned() -> Label:
        remaining = [v for v in s_labels if v not in assigned]
        # Most constrained first.
        remaining.sort(key=lambda v: (len([t for t in candidates[v] if t not in used_targets]), v))
        return remaining[0]

    def compatible(sv: Label, tv: Label) -> bool:
        if tv in used_targets:
            return False
        if s_profiles[sv] != t_profiles[tv]:
            return False
        for su, tu in assigned.items():
            if graph_edge_color(source, sv, su) != graph_edge_color(target, tv, tu):
                return False
        return True

    def dfs() -> bool:
        if len(assigned) == len(s_labels):
            return True
        sv = order_unassigned()
        for tv in candidates[sv]:
            if not compatible(sv, tv):
                continue
            assigned[sv] = tv
            used_targets.add(tv)
            if dfs():
                return True
            used_targets.remove(tv)
            del assigned[sv]
        return False

    if not dfs():
        return None
    return assigned


def is_admissible_ltt(g: LTT, distinguished: Sequence[LTT]) -> bool:
    # Prompt definition: admissible iff ep-isomorphic to some distinguished admissible ltt.
    for d in distinguished:
        if find_ep_isomorphism(g, d) is not None:
            return True
    return False


def x_images_notation(mapping: Dict[Label, Label]) -> str:
    parts: List[str] = []
    for i in range(1, 6):
        src = f"x{i}"
        dst = mapping[src]
        parts.append(rf"{latex_math_vertex(src)} \mapsto {latex_math_vertex(dst)}")
    return r",\; ".join(parts)


def pltt_order_key(g: LTT) -> Tuple:
    # Prompt allows any fixed order on PLTT. Use deterministic exact labeled order.
    return graph_signature(g)


@dataclass
class Node:
    name: str
    graph: LTT
    box_id: int


@dataclass
class PreAutEdge:
    src: str
    dst: str
    label: str
    kind: str  # "step2" | "permutation" | "box" (collapsed aggregate)


def step2_terminals_full(g: LTT, distinguished: Sequence[LTT]) -> List[Tuple[str, str, LTT]]:
    d_r = g.red_vertex
    ra, rb = g.red_edge
    d_p = rb if d_r == ra else ra
    d1, d2 = purple_neighbor_pair_ordered(g, d_p)

    raw: List[Tuple[str, str, LTT]] = []
    for j, d_j in enumerate((d1, d2), start=1):
        ga = terminal_ga_step2(g, d_r, d_j)
        gb = terminal_gb_step2(g, d_r, d_j)
        raw.append((f"G_{j};a", rf"{d_r} \to {d_j}\,{d_r}", ga))
        raw.append((f"G_{j};b", rf"{d_j} \to {d_r}\,{d_j}", gb))

    kept = [row for row in raw if is_admissible_ltt(row[2], distinguished)]
    kept.sort(key=lambda row: pltt_order_key(row[2]))
    return kept


def run_algorithm() -> Tuple[List[Node], Dict[int, List[str]], Dict[int, List[str]], List[PreAutEdge]]:
    distinguished = generate_distinguished_ltt()
    class_representatives: Dict[Tuple, LTT] = {}
    for g in distinguished:
        key = canonical_signature(g)
        if key not in class_representatives:
            class_representatives[key] = g
    ordered_keys = sorted(class_representatives.keys())

    def class_number_for_graph(g: LTT) -> int:
        for class_idx, key in enumerate(ordered_keys, start=1):
            rep = class_representatives[key]
            if find_ep_isomorphism(g, rep) is not None:
                return class_idx
        raise RuntimeError("Could not assign ep-isomorphism class number.")

    seed = seed_ltt_structure()
    seed_box_id = class_number_for_graph(seed)
    nodes: List[Node] = [Node(name="G", graph=seed, box_id=seed_box_id)]
    boxes: Dict[int, List[str]] = {seed_box_id: ["G"]}
    edges: List[PreAutEdge] = []

    levels: Dict[int, List[str]] = {1: ["G"]}
    k = 1
    node_counter = 0

    while True:
        current_names = levels.get(k, [])
        if not current_names:
            break

        next_level: List[str] = []

        for current_name in current_names:
            current_node = next(n for n in nodes if n.name == current_name)
            terminals = step2_terminals_full(current_node.graph, distinguished)

            for _, edge_label, g_prime in terminals:
                # Step 3, case (exact equality)
                exact = next((n for n in nodes if graph_signature(n.graph) == graph_signature(g_prime)), None)
                if exact is not None:
                    edges.append(
                        PreAutEdge(
                            src=current_name,
                            dst=exact.name,
                            label=edge_label,
                            kind="step2",
                        )
                    )
                    continue

                # Step 3, case (ep-isomorphic to existing graph)
                iso_target: Optional[Node] = None
                iso_map: Optional[Dict[Label, Label]] = None
                for existing in nodes:
                    m = find_ep_isomorphism(g_prime, existing.graph)
                    if m is not None:
                        iso_target = existing
                        iso_map = m
                        break

                node_counter += 1
                new_name = f"G{node_counter}"
                new_box_id = class_number_for_graph(g_prime)

                if iso_target is not None and iso_map is not None:
                    # Keep the Step 2 transition, then add the Step 3 permutation edge.
                    nodes.append(Node(name=new_name, graph=g_prime, box_id=new_box_id))
                    boxes.setdefault(new_box_id, []).append(new_name)
                    edges.append(
                        PreAutEdge(
                            src=current_name,
                            dst=new_name,
                            label=edge_label,
                            kind="step2",
                        )
                    )
                    edges.append(
                        PreAutEdge(
                            src=new_name,
                            dst=iso_target.name,
                            label=x_images_notation(iso_map),
                            kind="permutation",
                        )
                    )
                    continue

                # Step 3, remaining case: new box and next layer.
                nodes.append(Node(name=new_name, graph=g_prime, box_id=new_box_id))
                boxes.setdefault(new_box_id, []).append(new_name)
                next_level.append(new_name)
                edges.append(
                    PreAutEdge(
                        src=current_name,
                        dst=new_name,
                        label=edge_label,
                        kind="step2",
                    )
                )

        if not next_level:
            break
        next_level.sort(key=lambda nm: pltt_order_key(next(n.graph for n in nodes if n.name == nm)))
        levels[k + 1] = next_level
        k += 1

    return nodes, boxes, levels, edges


def compute_sccs(node_names: Sequence[str], edges: Sequence[PreAutEdge]) -> List[List[str]]:
    """
    Return maximal strongly connected components (SCCs) of preAUT.
    """
    adj: Dict[str, Set[str]] = {n: set() for n in node_names}
    radj: Dict[str, Set[str]] = {n: set() for n in node_names}
    for e in edges:
        adj[e.src].add(e.dst)
        radj[e.dst].add(e.src)

    visited: Set[str] = set()
    order: List[str] = []

    def dfs1(u: str) -> None:
        visited.add(u)
        for v in sorted(adj[u]):
            if v not in visited:
                dfs1(v)
        order.append(u)

    for n in sorted(node_names):
        if n not in visited:
            dfs1(n)

    visited.clear()
    sccs: List[List[str]] = []

    def dfs2(u: str, comp: List[str]) -> None:
        visited.add(u)
        comp.append(u)
        for v in sorted(radj[u]):
            if v not in visited:
                dfs2(v, comp)

    for n in reversed(order):
        if n in visited:
            continue
        comp: List[str] = []
        dfs2(n, comp)
        comp.sort()
        sccs.append(comp)

    # Deterministic order for display.
    sccs.sort(key=lambda c: (len(c), c))
    return sccs


def filter_preaut_components_with_edges(
    node_names: Sequence[str],
    edges: Sequence[PreAutEdge],
) -> Tuple[List[str], List[PreAutEdge]]:
    """
    Step 5 output filter: omit connected components with no edges.
    """
    adj_u: Dict[str, Set[str]] = {n: set() for n in node_names}
    for e in edges:
        adj_u[e.src].add(e.dst)
        adj_u[e.dst].add(e.src)

    seen: Set[str] = set()
    keep_nodes: Set[str] = set()
    for n in sorted(node_names):
        if n in seen:
            continue
        stack = [n]
        comp: List[str] = []
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            comp.append(u)
            for v in adj_u[u]:
                if v not in seen:
                    stack.append(v)

        comp_set = set(comp)
        has_edge = any((e.src in comp_set and e.dst in comp_set) for e in edges)
        if has_edge:
            keep_nodes.update(comp_set)

    keep_list = sorted(keep_nodes)
    keep_set = set(keep_list)
    keep_edges = [e for e in edges if e.src in keep_set and e.dst in keep_set]
    return keep_list, keep_edges


def weakly_connected_components(
    node_names: Sequence[str],
    edges: Sequence[PreAutEdge],
) -> List[List[str]]:
    """Undirected components of preAUT for visualization grouping."""
    adj_u: Dict[str, Set[str]] = {n: set() for n in node_names}
    for e in edges:
        adj_u[e.src].add(e.dst)
        adj_u[e.dst].add(e.src)

    seen: Set[str] = set()
    comps: List[List[str]] = []
    for n in sorted(node_names):
        if n in seen:
            continue
        stack = [n]
        comp: List[str] = []
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            comp.append(u)
            for v in sorted(adj_u[u]):
                if v not in seen:
                    stack.append(v)
        comp.sort()
        comps.append(comp)
    comps.sort(key=lambda c: (-len(c), c))
    return comps


def build_aut(
    node_names: Sequence[str],
    edges: Sequence[PreAutEdge],
) -> Tuple[List[List[str]], List[PreAutEdge], Dict[str, int]]:
    """
    Step 7: AUT is the disjoint union of maximal SCCs of preAUT.

    We omit SCC components with no internal edges.
    """
    sccs = compute_sccs(node_names, edges)
    edge_set = {(e.src, e.dst) for e in edges}
    sccs = [
        comp
        for comp in sccs
        if any((u, v) in edge_set for u in comp for v in comp)
    ]
    node_to_scc: Dict[str, int] = {}
    for idx, comp in enumerate(sccs, start=1):
        for n in comp:
            node_to_scc[n] = idx

    aut_edges = [
        e
        for e in edges
        if e.src in node_to_scc and e.dst in node_to_scc and node_to_scc[e.src] == node_to_scc[e.dst]
    ]
    return sccs, aut_edges, node_to_scc


def colored_components(g: LTT) -> List[List[Label]]:
    """Connected components of the colored subgraph (purple + red edges)."""
    labels = list(g.labels)
    adj: Dict[Label, Set[Label]] = {v: set() for v in labels}
    for a, b in g.purple_edges:
        adj[a].add(b)
        adj[b].add(a)
    ra, rb = g.red_edge
    adj[ra].add(rb)
    adj[rb].add(ra)

    seen: Set[Label] = set()
    comps: List[List[Label]] = []
    for v in sorted(labels):
        if v in seen:
            continue
        stack = [v]
        comp: List[Label] = []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.append(cur)
            for nb in sorted(adj[cur]):
                if nb not in seen:
                    stack.append(nb)
        comps.append(sorted(comp))
    return comps


def underlying_key(g: LTT) -> Tuple[Tuple[int, int], ...]:
    """
    Canonical unlabeled underlying multigraph key.
    Collapse colored components; black edges induce 5 edges on the quotient.
    """
    comps = colored_components(g)
    idx: Dict[Label, int] = {}
    for i, comp in enumerate(comps):
        for v in comp:
            idx[v] = i

    projected: List[Tuple[int, int]] = []
    for j in range(1, 6):
        a = idx[f"x{j}"]
        b = idx[f"xb{j}"]
        projected.append((a, b) if a <= b else (b, a))

    k = len(comps)
    best: Optional[Tuple[Tuple[int, int], ...]] = None
    for p in permutations(range(k)):
        remapped: List[Tuple[int, int]] = []
        for a, b in projected:
            a2, b2 = p[a], p[b]
            remapped.append((a2, b2) if a2 <= b2 else (b2, a2))
        key = tuple(sorted(remapped))
        if best is None or key < best:
            best = key
    if best is None:
        raise RuntimeError("Failed to compute underlying canonical key.")
    return best


def tikz_underlying_graph_picture(key: Tuple[Tuple[int, int], ...], class_label: str) -> str:
    """
    Draw one unlabeled underlying multigraph on 3 vertices with loops/multi-edges.
    """
    nodes = sorted({v for e in key for v in e})
    # Fixed 3-vertex layout.
    pos = {
        0: (-2.6, 0.0),
        1: (0.0, 2.7),
        2: (2.6, 0.0),
    }

    pair_counts: Dict[Tuple[int, int], int] = {}
    for e in key:
        pair_counts[e] = pair_counts.get(e, 0) + 1

    lines: List[str] = []
    lines.append("\\begin{center}")
    lines.append("\\resizebox{0.52\\linewidth}{!}{%")
    # One physical chunk: a blank line inside ``[ ... ]`` becomes ``\\par`` and ends the optional
    # argument early (runaway / error at the closing ``}`` of ``\\resizebox``).
    lines.append(
        "\\begin{tikzpicture}[\n"
        f"  ugv/.style={{circle, draw=black, fill=gray!10, minimum size={UGV_MIN_MM}mm, "
        f"inner sep={UGV_INNER_SEP_PT:.1f}pt, font={tikz_braced_font(TIKZ_UGV_FONT_CMD)}}},\n"
        f"  ugedge/.style={{line width={UGEDGE_LINE_PT:.2f}pt, line cap=round}}\n"
        "]"
    )
    for i in nodes:
        x, y = pos[i]
        lines.append(rf"\node[ugv] (u{i}) at ({x:.2f},{y:.2f}) {{$v_{{{i+1}}}$}};")

    bend_offsets = [0, 18, -18, 30, -30]
    for (a, b), count in sorted(pair_counts.items()):
        if a == b:
            # Multiple loops at this vertex.
            for k in range(count):
                if k == 0:
                    lines.append(rf"\draw[ugedge] (u{a}) to[loop above] (u{a});")
                elif k == 1:
                    lines.append(rf"\draw[ugedge] (u{a}) to[loop right] (u{a});")
                else:
                    lines.append(rf"\draw[ugedge] (u{a}) to[loop left] (u{a});")
            continue
        for k in range(count):
            bend = bend_offsets[k] if k < len(bend_offsets) else (k * 8)
            if bend == 0:
                lines.append(rf"\draw[ugedge] (u{a}) -- (u{b});")
            elif bend > 0:
                lines.append(rf"\draw[ugedge] (u{a}) to[bend left={bend}] (u{b});")
            else:
                lines.append(rf"\draw[ugedge] (u{a}) to[bend right={-bend}] (u{b});")

    lines.append(
        r"\node[font=" + tikz_braced_font(r"\small") + rf"] at (0,-2.45) {{{class_label}}};"
    )
    lines.append("\\end{tikzpicture}%")
    lines.append("}")
    lines.append("\\end{center}")
    return "\n".join(lines)


def collapsed_step2_perm_for_pair(
    a: int,
    b: int,
    box_edge_counts: Dict[Tuple[int, int], int],
    box_perm_counts: Dict[Tuple[int, int], int],
) -> Tuple[int, int]:
    tot = box_edge_counts[(a, b)]
    perm = box_perm_counts.get((a, b), 0)
    return (tot - perm, perm)


def append_collapsed_directed_edge(
    chunks: List[str],
    s_idx: int,
    d_idx: int,
    n_step2: int,
    n_perm: int,
    step2_connector: str,
    perm_connector: str,
    pos: str = "0.52",
) -> None:
    """
    Emit one or two TikZ arrows from ``n{s_idx}`` to ``n{d_idx}``.

    ``step2_connector`` / ``perm_connector`` are the path middle segments (including leading
    space if needed), e.g. ``--`` or ``to[bend left=20]``. When both kinds are positive,
    ``perm_connector`` should differ slightly from ``step2_connector`` so the curves separate.
    """
    if n_step2 > 0:
        chunks.append(
            rf"\draw[autedge] (n{s_idx}) {step2_connector} node[autlbl, pos={pos}] "
            rf"{{$ {latex_collapsed_edge_count_label(n_step2)} $}} (n{d_idx});"
            + "\n"
        )
    if n_perm > 0:
        conn = perm_connector if n_step2 > 0 else step2_connector
        chunks.append(
            rf"\draw[autedgeperm] (n{s_idx}) {conn} node[autlblperm, pos={pos}] "
            rf"{{$ {latex_collapsed_edge_count_label(n_perm)} $}} (n{d_idx});"
            + "\n"
        )


def write_appendix(path: Path) -> None:
    nodes, boxes, levels, edges = run_algorithm()
    node_by_name: Dict[str, Node] = {n.name: n for n in nodes}
    node_names_all = [n.name for n in nodes]
    kept_preaut_nodes, kept_preaut_edges = filter_preaut_components_with_edges(node_names_all, edges)
    kept_preaut_set = set(kept_preaut_nodes)

    levels = {k: [nm for nm in v if nm in kept_preaut_set] for k, v in levels.items()}
    levels = {k: v for k, v in levels.items() if v}
    boxes = {k: [nm for nm in v if nm in kept_preaut_set] for k, v in boxes.items()}
    boxes = {k: v for k, v in boxes.items() if v}

    graph_sccs, graph_aut_edges, graph_node_to_scc = build_aut(kept_preaut_nodes, kept_preaut_edges)

    # Box-collapsed preAUT: one node per box.
    box_ids = sorted(boxes.keys())
    box_edge_counts: Dict[Tuple[int, int], int] = {}
    box_perm_counts: Dict[Tuple[int, int], int] = {}
    for e in kept_preaut_edges:
        src_box = node_by_name[e.src].box_id
        dst_box = node_by_name[e.dst].box_id
        key = (src_box, dst_box)
        box_edge_counts[key] = box_edge_counts.get(key, 0) + 1
        if e.kind == "permutation":
            box_perm_counts[key] = box_perm_counts.get(key, 0) + 1
    box_nodes = [f"B{bid}" for bid in box_ids]
    box_preaut_edges: List[PreAutEdge] = [
        PreAutEdge(src=f"B{a}", dst=f"B{b}", label=str(cnt), kind="box")
        for (a, b), cnt in sorted(box_edge_counts.items())
    ]
    box_sccs, box_aut_edges, box_node_to_scc = build_aut(box_nodes, box_preaut_edges)

    # Underlying unlabeled graph classes (up to standard graph isomorphism).
    key_by_node: Dict[str, Tuple[Tuple[int, int], ...]] = {
        nm: underlying_key(node_by_name[nm].graph) for nm in kept_preaut_nodes
    }
    unique_underlying_keys = sorted(set(key_by_node.values()))
    underlying_label_by_key: Dict[Tuple[Tuple[int, int], ...], str] = {
        k: f"U_{i}" for i, k in enumerate(unique_underlying_keys, start=1)
    }

    chunks: List[str] = []
    chunks.append(
        "\\section[Output of preAUT and AUT (Section 1)]"
        "{Output of preAUT and AUT (Section~1 algorithm)}\n\n"
    )
    chunks.append(
        "\\noindent\\textit{Regenerating this appendix.} "
        "Run \\texttt{python generate\\_preaut\\_appendix\\_tex.py} from the repository root. "
        "This executes Steps~1--5 recursively from the seed until termination, checks Step~6 "
        "(ep-isomorphism-class coverage), and then computes Step~7 "
        "(AUT as the disjoint union of maximal strongly connected components).\n\n"
    )

    chunks.append("\\subsection*{Global outcome}\n")
    chunks.append(
        rf"Total nodes in preAUT (after omitting components with no edges): ${len(kept_preaut_nodes)}$. "
        rf"Total directed edges in preAUT: ${len(kept_preaut_edges)}$. "
        rf"Total boxes (ep-isomorphism classes used by Step~3): ${len(boxes)}$. "
        rf"Maximal strongly connected components kept in AUT (box-collapsed): ${len(box_sccs)}$. "
        rf"Nodes in AUT (box-collapsed): ${len(box_node_to_scc)}$. "
        rf"Directed edges in AUT (box-collapsed): ${len(box_aut_edges)}$."
        "\n\n"
    )

    chunks.append("\\subsection*{Levels $\\mathrm{GRAPHS}_{k}$}\n")
    chunks.append("\\begin{itemize}[leftmargin=*]\n")
    for lvl in sorted(levels):
        members = ", ".join(latex_node_name(nm) for nm in levels[lvl])
        chunks.append(rf"\item $\mathrm{{GRAPHS}}_{{{lvl}}}=\{{{members}\}}$." + "\n")
    chunks.append("\\end{itemize}\n\n")

    chunks.append("\\subsection*{Boxes}\\label{app:preaut-boxes}\n")
    chunks.append("\\begin{itemize}[leftmargin=*]\n")
    for box_id in sorted(boxes):
        members = ", ".join(latex_node_name(nm) for nm in boxes[box_id])
        chunks.append(
            rf"\item $\mathrm{{graphs}}_{{{box_id}}}$ "
            rf"(Class ${box_id}$, Box ${latex_roman_for_class(box_id)}$)"
            rf"$=\{{{members}\}}$."
            + "\n"
        )
    chunks.append("\\end{itemize}\n\n")

    chunks.append("\\subsection*{Directed edges of preAUT}\n")
    chunks.append("\\begin{enumerate}[leftmargin=*]\n")
    for e in kept_preaut_edges:
        src = latex_node_name(e.src)
        dst = latex_node_name(e.dst)
        if e.kind == "step2":
            chunks.append(
                rf"\item ${src} \xrightarrow{{{latex_step2_label(e.label)}}} {dst}$."
                + "\n"
            )
        else:
            chunks.append(
                rf"\item ${src} \xrightarrow{{\varphi}} {dst}$, where "
                rf"$\varphi={e.label}$."
                + "\n"
            )
    chunks.append("\\end{enumerate}\n")

    chunks.append("\n\\subsection*{Underlying graph isomorphism classes (unlabeled)}\n")
    chunks.append(
        "Collapsing each colored component (purple cliques and red edge attachment) yields an underlying multigraph. "
        "Up to standard graph isomorphism, the preAUT/AUT dictionary graphs realize the following classes.\n\n"
    )
    chunks.append("\\begin{enumerate}[leftmargin=*]\n")
    for key in unique_underlying_keys:
        ulabel = underlying_label_by_key[key]
        chunks.append(rf"\item ${ulabel}$." + "\n")
        chunks.append(tikz_underlying_graph_picture(key, rf"${ulabel}$"))
        chunks.append("\n")
    chunks.append("\\end{enumerate}\n")

    chunks.append("\n\\subsection*{Dictionary of graph labels used in preAUT/AUT}\n")
    chunks.append(
        "For each graph label used above, this table records the corresponding ltt "
        "structure data.\n\n"
    )
    chunks.append("\\begin{enumerate}[leftmargin=*]\n")
    for nm in sorted(kept_preaut_nodes, key=preaut_dict_node_sort_key):
        g = node_by_name[nm].graph
        chunks.append(rf"\item ${latex_node_name(nm)}$:" + "\n")
        chunks.append("\\begin{itemize}[leftmargin=*]\n")
        chunks.append(
            rf"\item underlying graph class $= {underlying_label_by_key[key_by_node[nm]]}$."
            + "\n"
        )
        chunks.append(rf"\item red vertex $= {latex_math_vertex(g.red_vertex)}$." + "\n")
        chunks.append(
            rf"\item red edge $= \{{{latex_math_vertex(g.red_edge[0])},\,{latex_math_vertex(g.red_edge[1])}\}}$."
            + "\n"
        )
        chunks.append(
            rf"\item purple edges ($|\mathcal{{P}}|={len(g.purple_edges)}$):\mbox{{}}\\"
            + "\n"
            + latex_purple_partition_lines(sorted(g.purple_edges))
            + ".\n"
        )
        chunks.append(
            rf"\item black edges ($|\mathcal{{B}}|={len(g.black_edges)}$): "
            rf"${latex_edge_list_inline(sorted(g.black_edges))}$."
            + "\n"
        )
        chunks.append("\\end{itemize}\n")
    chunks.append("\\end{enumerate}\n")

    chunks.append("\n\\subsection*{Visual depiction of AUT by component (box-collapsed)}\n")
    chunks.append(
        "AUT is computed from the box-collapsed preAUT (one node per box). "
        "Retained AUT components are listed sequentially. "
        "Nodes are labeled by Roman box IDs (I--XIV). "
        "Blue (Step~2) edge labels count only non-permutation arrows along that directed box pair; "
        "green labels count permutation ($\\varphi$) edges, so blue and green labels sum to the total "
        "parallel preAUT arrows between those boxes.\n\n"
    )

    for comp_idx, comp_nodes in enumerate(box_sccs, start=1):
        if comp_idx > 1:
            chunks.append("\\medskip\n")

        component_set = set(comp_nodes)
        comp_edges = [e for e in box_aut_edges if e.src in component_set and e.dst in component_set]
        comp_nodes_sorted = sorted(comp_nodes, key=lambda nm: int(nm[1:]))
        boxnum_by_node: Dict[str, int] = {nm: int(nm[1:]) for nm in comp_nodes_sorted}
        is_scc1_full_page = comp_idx == 1 and len(comp_nodes_sorted) == 14

        if is_scc1_full_page:
            chunks.append("\\clearpage\n")
        chunks.append(rf"\paragraph{{AUT component $\mathrm{{SCC}}_{{{comp_idx}}}$.}}" + "\n")

        comp_dir_metrics: Dict[Tuple[str, str], Tuple[int, int]] = {}
        for e in comp_edges:
            sa = int(e.src[1:])
            da = int(e.dst[1:])
            comp_dir_metrics[(e.src, e.dst)] = collapsed_step2_perm_for_pair(
                sa, da, box_edge_counts, box_perm_counts
            )

        # Component-local layout.
        n_nodes = len(comp_nodes_sorted)
        pos: Dict[str, Tuple[float, float]] = {}
        if {boxnum_by_node[nm] for nm in comp_nodes_sorted} == set(MANUAL_BOX_POS.keys()):
            for nm in comp_nodes_sorted:
                pos[nm] = MANUAL_BOX_POS[boxnum_by_node[nm]]
        else:
            radius = 6.2
            for i, nm in enumerate(comp_nodes_sorted):
                theta = 2.0 * pi * i / max(1, n_nodes)
                pos[nm] = (radius * cos(theta), radius * sin(theta))

        if is_scc1_full_page:
            chunks.append("\\vfill\n")
        chunks.append("\\begin{center}\n")
        if n_nodes == 1:
            chunks.append(f"\\resizebox{{{AUT_COMPONENT_SCC1_WIDTH}\\linewidth}}{{!}}{{%\n")
        elif is_scc1_full_page:
            # Scale to target height, then shrink only if too wide (never upscale).
            chunks.append("\\setbox0=\\hbox{%\n")
            chunks.append(f"\\resizebox{{!}}{{{AUT_SCC1_FULL_PAGE_HEIGHT}\\textheight}}{{%\n")
        else:
            chunks.append(f"\\resizebox{{!}}{{{AUT_COMPONENT_MAX_HEIGHT}\\textheight}}{{%\n")
        chunks.append("\\begin{tikzpicture}[\n")
        chunks.append("  >=stealth,\n")
        chunks.append(
            f"  autnode/.style={{circle, draw=black, fill=gray!10, minimum size={AUT_NODE_MIN_MM}mm, "
            f"inner sep={AUT_NODE_INNER_SEP_PT:.1f}pt, font={tikz_braced_font(TIKZ_AUT_NODE_FONT_CMD)}}},\n"
        )
        chunks.append(
            f"  autedge/.style={{->, draw=blue!60, line width={AUT_EDGE_LINE_PT:.2f}pt}},\n"
        )
        chunks.append("  autlbl/.style={" + TIKZ_AUTLBL_STYLE + "},\n")
        chunks.append(
            f"  autedgeperm/.style={{->, draw=green!55!black, line width={AUT_EDGE_LINE_PT:.2f}pt}},\n"
        )
        chunks.append("  autlblperm/.style={" + TIKZ_AUTLBL_PERM_STYLE + "}\n")
        chunks.append("]\n")

        for nm in comp_nodes_sorted:
            x, y = pos[nm]
            boxnum = boxnum_by_node[nm]
            chunks.append(
                rf"\node[autnode] (n{boxnum}) at ({x:.4f},{y:.4f}) "
                rf"{{${latex_roman_for_class(boxnum)}$}};"
                + "\n"
            )

        pair_set = set(comp_dir_metrics.keys())
        drawn_pairs: Set[Tuple[str, str]] = set()
        for (s, d) in sorted(
            comp_dir_metrics.keys(),
            key=lambda pr: (boxnum_by_node[pr[0]], boxnum_by_node[pr[1]]),
        ):
            if (s, d) in drawn_pairs:
                continue
            s_idx = boxnum_by_node[s]
            d_idx = boxnum_by_node[d]
            n2_sd, p_sd = comp_dir_metrics[(s, d)]

            if s == d:
                chunks.append(latex_aut_self_loop_collapsed(s_idx, f"n{s_idx}", n2_sd, p_sd))
                drawn_pairs.add((s, d))
                continue

            has_reverse = (d, s) in pair_set
            if has_reverse:
                n2_ds, p_ds = comp_dir_metrics[(d, s)]
                if (d, s) not in drawn_pairs:
                    if {s_idx, d_idx} == {11, 14}:
                        n2_11_14, p_11_14 = collapsed_step2_perm_for_pair(
                            11, 14, box_edge_counts, box_perm_counts
                        )
                        n2_14_11, p_14_11 = collapsed_step2_perm_for_pair(
                            14, 11, box_edge_counts, box_perm_counts
                        )
                        append_collapsed_directed_edge(
                            chunks,
                            11,
                            14,
                            n2_11_14,
                            p_11_14,
                            "to[bend left=20]",
                            "to[bend left=14]",
                        )
                        append_collapsed_directed_edge(
                            chunks,
                            14,
                            11,
                            n2_14_11,
                            p_14_11,
                            "--",
                            "to[bend left=6]",
                        )
                        drawn_pairs.add((s, d))
                        drawn_pairs.add((d, s))
                        continue
                    if {s_idx, d_idx} == {5, 7}:
                        n2_57, p_57 = collapsed_step2_perm_for_pair(
                            5, 7, box_edge_counts, box_perm_counts
                        )
                        n2_75, p_75 = collapsed_step2_perm_for_pair(
                            7, 5, box_edge_counts, box_perm_counts
                        )
                        append_collapsed_directed_edge(
                            chunks,
                            5,
                            7,
                            n2_57,
                            p_57,
                            "to[bend left=20]",
                            "to[bend left=14]",
                        )
                        append_collapsed_directed_edge(
                            chunks,
                            7,
                            5,
                            n2_75,
                            p_75,
                            "--",
                            "to[bend left=6]",
                        )
                        drawn_pairs.add((s, d))
                        drawn_pairs.add((d, s))
                        continue
                    append_collapsed_directed_edge(
                        chunks,
                        s_idx,
                        d_idx,
                        n2_sd,
                        p_sd,
                        "to[bend left=20]",
                        "to[bend left=14]",
                    )
                    append_collapsed_directed_edge(
                        chunks,
                        d_idx,
                        s_idx,
                        n2_ds,
                        p_ds,
                        "to[bend left=20]",
                        "to[bend left=14]",
                    )
                    drawn_pairs.add((s, d))
                    drawn_pairs.add((d, s))
                continue

            if (s_idx, d_idx) in {(12, 5), (5, 12)}:
                # Visibility tweak: route the V<->VI edge around the left side.
                append_collapsed_directed_edge(
                    chunks,
                    s_idx,
                    d_idx,
                    n2_sd,
                    p_sd,
                    "to[out=180,in=180,looseness=1.2]",
                    "to[out=175,in=175,looseness=1.05]",
                )
                drawn_pairs.add((s, d))
                continue
            if (s_idx, d_idx) == (11, 13):
                # XIII (lower right) -> XI (upper left): use bend_left so the arc sags downward
                # (bend_right bulges the other way for this chord in standard TikZ coords).
                append_collapsed_directed_edge(
                    chunks,
                    s_idx,
                    d_idx,
                    n2_sd,
                    p_sd,
                    "to[bend left=10]",
                    "to[bend left=6]",
                )
                drawn_pairs.add((s, d))
                continue
            if (s_idx, d_idx) == (13, 11):
                append_collapsed_directed_edge(
                    chunks,
                    s_idx,
                    d_idx,
                    n2_sd,
                    p_sd,
                    "to[bend right=18]",
                    "to[bend right=12]",
                )
                drawn_pairs.add((s, d))
                continue

            append_collapsed_directed_edge(
                chunks,
                s_idx,
                d_idx,
                n2_sd,
                p_sd,
                "--",
                "to[bend left=10]",
            )
            drawn_pairs.add((s, d))

        chunks.append("\\end{tikzpicture}%\n")
        chunks.append("}\n")
        if is_scc1_full_page:
            chunks.append("}%\n")
            chunks.append(
                f"\\ifdim\\wd0>\\dimexpr {AUT_SCC1_FULL_PAGE_MAX_WIDTH_FRAC}\\linewidth\\relax\n"
                f"  \\resizebox{{{AUT_SCC1_FULL_PAGE_MAX_WIDTH_FRAC}\\linewidth}}{{!}}{{\\box0}}%\n"
                "\\else\n"
                "  \\box0%\n"
                "\\fi\n"
            )
        chunks.append("\\end{center}\n\n")
        if is_scc1_full_page:
            chunks.append("\\vfill\n\\clearpage\n")

        chunks.append("\\noindent\\textit{Node index list for this component.}\n")
        chunks.append("\\begin{itemize}[leftmargin=*]\n")
        for nm in comp_nodes_sorted:
            boxnum = boxnum_by_node[nm]
            chunks.append(
                rf"\item Box ${latex_roman_for_class(boxnum)}$ $= {latex_state_name(nm)}$."
                + "\n"
            )
        chunks.append("\\end{itemize}\n\n")
        if is_scc1_full_page:
            chunks.append("\\clearpage\n")

    chunks.append("\n\\subsection*{Visual depiction of full preAUT (one node per box)}\n")
    chunks.append(
        "This is the box-collapsed preAUT: each node is one Roman box (I--XIV). "
        "A directed edge is drawn from one box to another whenever preAUT has at least one edge between their corresponding classes. "
        "As in the AUT diagrams, blue counts Step~2 transitions only and green counts permutation ($\\varphi$) edges along each directed box pair.\n\n"
    )
    box_ids = sorted(boxes.keys())
    box_adj: Dict[int, Set[int]] = {bid: set() for bid in box_ids}
    box_edge_counts = {}
    for e in kept_preaut_edges:
        src_box = node_by_name[e.src].box_id
        dst_box = node_by_name[e.dst].box_id
        if src_box not in box_adj or dst_box not in box_adj:
            continue
        box_adj[src_box].add(dst_box)
        key = (src_box, dst_box)
        box_edge_counts[key] = box_edge_counts.get(key, 0) + 1

    seen_boxes: Set[int] = set()
    box_components: List[List[int]] = []
    for bid in box_ids:
        if bid in seen_boxes:
            continue
        stack = [bid]
        comp: List[int] = []
        while stack:
            u = stack.pop()
            if u in seen_boxes:
                continue
            seen_boxes.add(u)
            comp.append(u)
            neighbors = box_adj[u] | {x for x in box_ids if u in box_adj[x]}
            for v in sorted(neighbors):
                if v not in seen_boxes:
                    stack.append(v)
        comp.sort()
        box_components.append(comp)
    box_components.sort(key=lambda c: (-len(c), c))

    for comp_idx, comp_boxes in enumerate(box_components, start=1):
        if comp_idx > 1:
            chunks.append("\\medskip\n")
        chunks.append(rf"\paragraph{{Box-collapsed preAUT component {comp_idx}.}}" + "\n")
        comp_set = set(comp_boxes)
        comp_pairs = [
            (a, b)
            for (a, b) in sorted(box_edge_counts.keys())
            if a in comp_set and b in comp_set
        ]
        idx_by_box: Dict[int, int] = {bid: i + 1 for i, bid in enumerate(comp_boxes)}

        pos: Dict[int, Tuple[float, float]] = {}
        n_nodes = len(comp_boxes)
        if set(comp_boxes) == set(MANUAL_BOX_POS.keys()):
            for bid in comp_boxes:
                pos[bid] = MANUAL_BOX_POS[bid]
        else:
            radius = max(6.2, 1.0 + 1.25 * len(comp_boxes))
            for i, bid in enumerate(comp_boxes):
                theta = 2.0 * pi * i / max(1, n_nodes)
                pos[bid] = (radius * cos(theta), radius * sin(theta))

        chunks.append("\\begin{center}\n")
        chunks.append(
            f"\\resizebox{{{AUT_BOX_COLLAPSED_RESIZE_WIDTH_FRAC:.4f}\\linewidth}}{{!}}{{%\n"
        )
        chunks.append("\\begin{tikzpicture}[\n")
        chunks.append("  >=stealth,\n")
        chunks.append(
            f"  autnode/.style={{circle, draw=black, fill=blue!8, minimum size={AUT_NODE_MIN_MM_BOXCOLLAPSE}mm, "
            f"inner sep={AUT_NODE_INNER_SEP_BOXCOLLAPSE_PT:.1f}pt, font={tikz_braced_font(TIKZ_AUT_NODE_FONT_CMD)}}},\n"
        )
        chunks.append(
            f"  autedge/.style={{->, draw=blue!60, line width={AUT_EDGE_LINE_PT:.2f}pt}},\n"
        )
        chunks.append("  autlbl/.style={" + TIKZ_AUTLBL_STYLE + "},\n")
        chunks.append(
            f"  autedgeperm/.style={{->, draw=green!55!black, line width={AUT_EDGE_LINE_PT:.2f}pt}},\n"
        )
        chunks.append("  autlblperm/.style={" + TIKZ_AUTLBL_PERM_STYLE + "}\n")
        chunks.append("]\n")
        for bid in comp_boxes:
            x, y = pos[bid]
            idx = idx_by_box[bid]
            chunks.append(
                rf"\node[autnode] (n{idx}) at ({x:.4f},{y:.4f}) "
                rf"{{${latex_roman_for_class(bid)}$}};"
                + "\n"
            )

        pair_set = set(comp_pairs)
        drawn_pairs: Set[Tuple[int, int]] = set()
        for (a, b) in comp_pairs:
            if (a, b) in drawn_pairs:
                continue
            a_idx = idx_by_box[a]
            b_idx = idx_by_box[b]
            n2_ab, p_ab = collapsed_step2_perm_for_pair(a, b, box_edge_counts, box_perm_counts)

            if a == b:
                chunks.append(latex_aut_self_loop_collapsed(a, f"n{a_idx}", n2_ab, p_ab))
                drawn_pairs.add((a, b))
                continue

            if (b, a) in pair_set and (b, a) not in drawn_pairs:
                n2_ba, p_ba = collapsed_step2_perm_for_pair(b, a, box_edge_counts, box_perm_counts)
                if {a, b} == {11, 14}:
                    i11, i14 = idx_by_box[11], idx_by_box[14]
                    n2_11_14, p_11_14 = collapsed_step2_perm_for_pair(
                        11, 14, box_edge_counts, box_perm_counts
                    )
                    n2_14_11, p_14_11 = collapsed_step2_perm_for_pair(
                        14, 11, box_edge_counts, box_perm_counts
                    )
                    append_collapsed_directed_edge(
                        chunks,
                        i11,
                        i14,
                        n2_11_14,
                        p_11_14,
                        "to[bend left=20]",
                        "to[bend left=14]",
                    )
                    append_collapsed_directed_edge(
                        chunks,
                        i14,
                        i11,
                        n2_14_11,
                        p_14_11,
                        "--",
                        "to[bend left=6]",
                    )
                    drawn_pairs.add((a, b))
                    drawn_pairs.add((b, a))
                    continue
                if {a, b} == {5, 7}:
                    i5, i7 = idx_by_box[5], idx_by_box[7]
                    n2_57, p_57 = collapsed_step2_perm_for_pair(
                        5, 7, box_edge_counts, box_perm_counts
                    )
                    n2_75, p_75 = collapsed_step2_perm_for_pair(
                        7, 5, box_edge_counts, box_perm_counts
                    )
                    append_collapsed_directed_edge(
                        chunks,
                        i5,
                        i7,
                        n2_57,
                        p_57,
                        "to[bend left=20]",
                        "to[bend left=14]",
                    )
                    append_collapsed_directed_edge(
                        chunks,
                        i7,
                        i5,
                        n2_75,
                        p_75,
                        "--",
                        "to[bend left=6]",
                    )
                    drawn_pairs.add((a, b))
                    drawn_pairs.add((b, a))
                    continue
                append_collapsed_directed_edge(
                    chunks,
                    a_idx,
                    b_idx,
                    n2_ab,
                    p_ab,
                    "to[bend left=20]",
                    "to[bend left=14]",
                )
                append_collapsed_directed_edge(
                    chunks,
                    b_idx,
                    a_idx,
                    n2_ba,
                    p_ba,
                    "to[bend left=20]",
                    "to[bend left=14]",
                )
                drawn_pairs.add((a, b))
                drawn_pairs.add((b, a))
                continue

            if (a, b) in {(12, 5), (5, 12)}:
                # Visibility tweak: route the V<->VI edge around the left side.
                append_collapsed_directed_edge(
                    chunks,
                    a_idx,
                    b_idx,
                    n2_ab,
                    p_ab,
                    "to[out=180,in=180,looseness=1.2]",
                    "to[out=175,in=175,looseness=1.05]",
                )
                drawn_pairs.add((a, b))
                continue
            if (a, b) == (11, 13):
                append_collapsed_directed_edge(
                    chunks,
                    a_idx,
                    b_idx,
                    n2_ab,
                    p_ab,
                    "to[bend left=10]",
                    "to[bend left=6]",
                )
                drawn_pairs.add((a, b))
                continue
            if (a, b) == (13, 11):
                append_collapsed_directed_edge(
                    chunks,
                    a_idx,
                    b_idx,
                    n2_ab,
                    p_ab,
                    "to[bend right=18]",
                    "to[bend right=12]",
                )
                drawn_pairs.add((a, b))
                continue

            append_collapsed_directed_edge(
                chunks,
                a_idx,
                b_idx,
                n2_ab,
                p_ab,
                "--",
                "to[bend left=10]",
            )
            drawn_pairs.add((a, b))

        chunks.append("\\end{tikzpicture}%\n")
        chunks.append("}\n")
        chunks.append("\\end{center}\n\n")

        chunks.append("\\noindent\\textit{Box index list for this preAUT diagram.}\n")
        chunks.append("\\begin{itemize}[leftmargin=*]\n")
        for bid in comp_boxes:
            idx = idx_by_box[bid]
            members = ", ".join(latex_node_name(nm) for nm in sorted(boxes[bid]))
            chunks.append(
                rf"\item Box ${latex_roman_for_class(bid)}$ "
                rf"$= \mathrm{{graphs}}_{{{bid}}}=\{{{members}\}}$."
                + "\n"
            )
        chunks.append("\\end{itemize}\n\n")

    chunks.append("\n\\subsection*{preAUT edges omitted in AUT (cross-SCC/exiting edges)}\n")
    chunks.append(
        "The AUT figures keep only edges whose source and target are in the same maximal SCC. "
        "The following preAUT edges leave those SCCs and are therefore omitted from AUT.\n\n"
    )
    chunks.append("\\begin{enumerate}[leftmargin=*]\n")
    for idx, comp in enumerate(graph_sccs, start=1):
        comp_set = set(comp)
        exiting = [e for e in kept_preaut_edges if e.src in comp_set and e.dst not in comp_set]
        chunks.append(rf"\item From $\mathrm{{SCC}}_{{{idx}}}$:" + "\n")
        if not exiting:
            chunks.append("none.\n")
            continue
        chunks.append("\\begin{itemize}[leftmargin=*]\n")
        for e in exiting:
            src = latex_node_name(e.src)
            dst = latex_node_name(e.dst)
            if e.kind == "step2":
                lbl = latex_step2_label(e.label)
                chunks.append(rf"\item ${src} \xrightarrow{{{lbl}}} {dst}$." + "\n")
            else:
                chunks.append(
                    rf"\item ${src} \xrightarrow{{\varphi}} {dst}$, where $\varphi={e.label}$."
                    + "\n"
                )
        chunks.append("\\end{itemize}\n")
    chunks.append("\\end{enumerate}\n\n")

    chunks.append("\\subsection*{Visual depiction of omitted preAUT edges by SCC}\n")
    chunks.append(
        "For each AUT component $\\mathrm{SCC}_i$, we draw the edges that start in "
        "$\\mathrm{SCC}_i$ and leave it in preAUT. Internal AUT edges are omitted in these diagrams.\n\n"
    )
    for comp_idx, comp_nodes in enumerate(graph_sccs, start=1):
        if comp_idx > 1:
            chunks.append("\\medskip\n")
        chunks.append(rf"\paragraph{{Omitted preAUT edges from $\mathrm{{SCC}}_{{{comp_idx}}}$.}}" + "\n")

        comp_set = set(comp_nodes)
        exiting = [e for e in kept_preaut_edges if e.src in comp_set and e.dst not in comp_set]
        if not exiting:
            chunks.append("\\noindent None.\n\n")
            continue

        internal_nodes = sorted(comp_nodes)
        external_nodes = sorted({e.dst for e in exiting})

        idx_by_node: Dict[str, int] = {}
        internal_tags: Dict[str, str] = {}
        external_tags: Dict[str, str] = {}

        counter = 1
        for nm in internal_nodes:
            idx_by_node[nm] = counter
            internal_tags[nm] = f"in{counter}"
            counter += 1
        for nm in external_nodes:
            idx_by_node[nm] = counter
            external_tags[nm] = f"out{counter}"
            counter += 1

        # Deterministic compact layout: internal on left circle, external on right column.
        internal_pos: Dict[str, Tuple[float, float]] = {}
        r = 3.1 if len(internal_nodes) > 1 else 0.0
        for i, nm in enumerate(internal_nodes):
            if len(internal_nodes) == 1:
                internal_pos[nm] = (-3.0, 0.0)
            else:
                theta = 2.0 * pi * i / len(internal_nodes)
                internal_pos[nm] = (-4.2 + r * cos(theta), r * sin(theta))

        external_pos: Dict[str, Tuple[float, float]] = {}
        if len(external_nodes) == 1:
            external_pos[external_nodes[0]] = (4.0, 0.0)
        else:
            top = 2.6
            step = 5.2 / max(1, len(external_nodes) - 1)
            for i, nm in enumerate(external_nodes):
                external_pos[nm] = (4.0, top - i * step)

        # Aggregate labels when multiple omitted edges share same src->dst.
        pair_to_labels: Dict[Tuple[str, str], List[str]] = {}
        for e in exiting:
            lbl = latex_step2_label(e.label) if e.kind == "step2" else rf"\varphi:\ {e.label}"
            pair_to_labels.setdefault((e.src, e.dst), []).append(lbl)

        chunks.append("\\begin{center}\n")
        if comp_idx == 1:
            chunks.append(f"\\resizebox{{{OMITTED_COMPONENT_SCC1_WIDTH}\\linewidth}}{{!}}{{%\n")
        else:
            chunks.append(f"\\resizebox{{{OMITTED_COMPONENT_DEFAULT_WIDTH}\\linewidth}}{{!}}{{%\n")
        chunks.append("\\begin{tikzpicture}[\n")
        chunks.append("  >=stealth,\n")
        chunks.append(
            f"  autnode/.style={{circle, draw=black, fill=gray!10, minimum size={AUT_NODE_MIN_MM}mm, "
            f"inner sep={AUT_NODE_INNER_SEP_PT:.1f}pt, font={tikz_braced_font(TIKZ_AUT_NODE_FONT_CMD)}}},\n"
        )
        chunks.append(
            f"  outnode/.style={{circle, draw=black!70, fill=yellow!12, minimum size={AUT_OUTNODE_MIN_MM}mm, "
            f"inner sep={AUT_OUTNODE_INNER_SEP_PT:.1f}pt, font={tikz_braced_font(TIKZ_AUT_NODE_FONT_CMD)}}},\n"
        )
        chunks.append(
            f"  autedge/.style={{->, line width={AUT_EDGE_LINE_PT:.2f}pt}},\n"
        )
        chunks.append("  autlbl/.style={" + TIKZ_AUTLBL_STYLE + "}\n")
        chunks.append("]\n")

        for nm in internal_nodes:
            x, y = internal_pos[nm]
            idx = idx_by_node[nm]
            tag = internal_tags[nm]
            class_num = node_by_name[nm].box_id
            chunks.append(
                rf"\node[autnode] ({tag}) at ({x:.4f},{y:.4f}) "
                rf"{{${latex_roman_for_class(class_num)}$}};"
                + "\n"
            )
        for nm in external_nodes:
            x, y = external_pos[nm]
            idx = idx_by_node[nm]
            tag = external_tags[nm]
            class_num = node_by_name[nm].box_id
            chunks.append(
                rf"\node[outnode] ({tag}) at ({x:.4f},{y:.4f}) "
                rf"{{${latex_roman_for_class(class_num)}$}};"
                + "\n"
            )

        for (src, dst), labels in sorted(
            pair_to_labels.items(),
            key=lambda t: (idx_by_node[t[0][0]], idx_by_node[t[0][1]]),
        ):
            s_tag = internal_tags[src]
            d_tag = external_tags[dst]
            label_text = r"\; ;\; ".join(labels)
            chunks.append(
                rf"\draw[autedge] ({s_tag}) -- node[autlbl, pos=0.52] {{$ {label_text} $}} ({d_tag});"
                + "\n"
            )

        chunks.append(
            rf"\node[font={tikz_braced_font(TIKZ_AUT_CAPTION_FONT_CMD)}] at (-6.4,-4.2) "
            rf"{{inside $\mathrm{{SCC}}_{{{comp_idx}}}$}};"
            + "\n"
        )
        chunks.append(
            rf"\node[font={tikz_braced_font(TIKZ_AUT_CAPTION_FONT_CMD)}] at (4.0,-4.2) "
            rf"{{outside $\mathrm{{SCC}}_{{{comp_idx}}}$}};"
            + "\n"
        )
        chunks.append("\\end{tikzpicture}%\n")
        chunks.append("}\n")
        chunks.append("\\end{center}\n\n")

        chunks.append("\\noindent\\textit{Node index list for this omitted-edge diagram.}\n")
        chunks.append("\\begin{itemize}[leftmargin=*]\n")
        for nm in internal_nodes:
            idx = idx_by_node[nm]
            class_num = node_by_name[nm].box_id
            chunks.append(
                rf"\item Box ${latex_roman_for_class(class_num)}$ "
                rf"$= {latex_node_name(nm)}$ (inside $\mathrm{{SCC}}_{{{comp_idx}}}$)."
                + "\n"
            )
        for nm in external_nodes:
            idx = idx_by_node[nm]
            class_num = node_by_name[nm].box_id
            chunks.append(
                rf"\item Box ${latex_roman_for_class(class_num)}$ "
                rf"$= {latex_node_name(nm)}$ (outside $\mathrm{{SCC}}_{{{comp_idx}}}$)."
                + "\n"
            )
        chunks.append("\\end{itemize}\n\n")

    total_ep_classes = 14
    covered_classes = len(boxes)
    step6_pass = covered_classes >= total_ep_classes

    chunks.append("\n\\subsection*{Step 6: coverage check across ep-isomorphism classes}\n")
    chunks.append(
        rf"Covered ep-isomorphism classes: ${covered_classes}$ out of ${total_ep_classes}$. "
    )
    if step6_pass:
        chunks.append(
            "All classes are represented by the constructed preAUT, so no additional seed run is required.\n\n"
        )
    else:
        chunks.append(
            "Not all classes are represented; per Step~6, one would restart Steps~1--6 from an uncovered seed class.\n\n"
        )

    chunks.append("\\subsection*{Step 7: maximal SCCs and AUT (box-collapsed)}\n")
    chunks.append(
        "Each maximal strongly connected component (SCC) of the box-collapsed preAUT is listed below; "
        "AUT is their disjoint union.\n\n"
    )

    chunks.append("\\paragraph{SCC decomposition of preAUT.}\n")
    chunks.append("\\begin{enumerate}[leftmargin=*]\n")
    for idx, comp in enumerate(box_sccs, start=1):
        members = ", ".join(latex_state_name(nm) for nm in comp)
        chunks.append(rf"\item $\mathrm{{SCC}}_{{{idx}}}=\{{{members}\}}$." + "\n")
    chunks.append("\\end{enumerate}\n\n")

    chunks.append("\\paragraph{Directed edges of AUT.}\n")
    chunks.append(
        "These are exactly the box-collapsed preAUT edges whose endpoints lie in the same maximal SCC.\n"
    )
    chunks.append("\\begin{enumerate}[leftmargin=*]\n")
    for e in box_aut_edges:
        src = latex_state_name(e.src)
        dst = latex_state_name(e.dst)
        scc_idx = box_node_to_scc[e.src]
        edge_word = "edge" if e.label == "1" else "edges"
        chunks.append(
            rf"\item ${src} \xrightarrow{{{e.label}\,\mathrm{{{edge_word}}}}} {dst}$ "
            rf"(inside $\mathrm{{SCC}}_{{{scc_idx}}}$)."
            + "\n"
        )
    chunks.append("\\end{enumerate}\n")

    path.write_text("".join(chunks), encoding="utf-8")


def main() -> None:
    repo = Path(__file__).resolve().parent
    out = repo / "preaut_appendix_generated.tex"
    write_appendix(out)
    print(f"Wrote {out.relative_to(repo)}", flush=True)


if __name__ == "__main__":
    main()

