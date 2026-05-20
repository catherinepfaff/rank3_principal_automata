"""
Generate ``box_internal_maps_appendix_generated.tex``: TikZ panels for each
ep-isomorphism class (paper ``box''), showing graphs$_k$ nodes in that class
and all internal preAUT edges (Step~2 in blue, permutations in green).

Run from the repository root::

    python generate_box_internal_maps_appendix_tex.py
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from generate_preaut_appendix_tex import (
    PreAutEdge,
    filter_preaut_components_with_edges,
    latex_edge_set_with_last_five_new_line,
    latex_math_vertex,
    latex_node_name,
    latex_purple_partition_lines,
    latex_roman_for_class,
    latex_step2_label,
    roman_for_class,
    run_algorithm,
    underlying_key,
)

# Order appendix panels as I, II, III, …, XIV (standard Roman numeric value).
_ROMAN_NUMERIC_ORDER: Dict[str, int] = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
}


def _box_id_sort_roman(box_id: int) -> int:
    return _ROMAN_NUMERIC_ORDER.get(roman_for_class(box_id), 99)


# Scale abstract layout coordinates in TikZ (no \resizebox), so node text stays true
# document size while the figure stays compact.
_DIAGRAM_COORD_SCALE = 0.52


def _tikz_vertex_name(graph_name: str) -> str:
    if graph_name == "G":
        return "vG"
    if graph_name.startswith("G") and graph_name[1:].isdigit():
        return f"v{graph_name[1:]}"
    raise ValueError(f"unexpected graph name {graph_name!r}")


def _member_sort_key(name: str) -> Tuple[int, str]:
    if name == "G":
        return (0, name)
    if name.startswith("G") and name[1:].isdigit():
        return (int(name[1:]), name)
    return (999, name)


def _legend_item_tex(e: PreAutEdge) -> str:
    src = latex_node_name(e.src)
    dst = latex_node_name(e.dst)
    if e.kind == "step2":
        lbl = latex_step2_label(e.label)
        return rf"\item ${src} \xrightarrow{{{lbl}}} {dst}$ \textit{{(Step~2)}}."
    return (
        rf"\item ${src} \xrightarrow{{\varphi}} {dst}$, where $\varphi={e.label}$ "
        r"\textit{(permutation / ep-isomorphism).}"
    )


def _other_box_footnote_tex(other_node: str, node_by_name: Dict[str, Any]) -> str:
    bid = node_by_name[other_node].box_id
    rom = latex_roman_for_class(bid)
    return rf"{{\footnotesize ($\mathrm{{graphs}}_{{{bid}}}$, Box ${rom}$)}}"


def _cross_box_edge_item_tex(e: PreAutEdge, other_node: str, node_by_name: Dict[str, Any]) -> str:
    """One preAUT edge with a footnote for the other endpoint's $\mathrm{graphs}_k$ / Box."""
    src = latex_node_name(e.src)
    dst = latex_node_name(e.dst)
    note = _other_box_footnote_tex(other_node, node_by_name)
    if e.kind == "step2":
        lbl = latex_step2_label(e.label)
        return rf"\item ${src} \xrightarrow{{{lbl}}} {dst}$ {note} \textit{{(Step~2)}}."
    return (
        rf"\item ${src} \xrightarrow{{\varphi}} {dst}$, where $\varphi={e.label}$ "
        rf"{note} \textit{{(permutation / ep-isomorphism).}}"
    )


# Paper boxes drawn as a single horizontal row (same $y$), hub-centered, by ep class number.
_ROW_LAYOUT_BOX_IDS = frozenset({1, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14})


def _choose_hub(members: Sequence[str], internal: Sequence[PreAutEdge]) -> str:
    if len(members) == 1:
        return members[0]
    score = {m: 0 for m in members}
    for e in internal:
        if e.src == e.dst:
            score[e.src] += 2
        else:
            score[e.src] += 1
            score[e.dst] += 1
    mx = max(score[m] for m in members)
    cands = [m for m in members if score[m] == mx]
    if "G" in cands:
        return "G"
    return min(cands, key=_member_sort_key)


def _layout_row_positions(
    members: Sequence[str], internal: Sequence[PreAutEdge],
) -> Dict[str, Tuple[float, float]]:
    """
    One horizontal line: the high-degree ``hub'' sits in the middle, with the
    remaining nodes split evenly to its left and right (sorted order within each side).
    """
    members_list = list(members)
    n = len(members_list)
    if n == 0:
        return {}
    if n == 1:
        return {members_list[0]: (0.0, 0.0)}

    hub = _choose_hub(members_list, internal)
    others = sorted([m for m in members_list if m != hub], key=_member_sort_key)
    if len(others) == 1:
        row = [others[0], hub]
    else:
        n_left = len(others) // 2
        left = others[:n_left]
        right = others[n_left:]
        row = left + [hub] + right

    dx = 3.65
    total = (len(row) - 1) * dx
    x0 = -0.5 * total
    return {row[i]: (x0 + i * dx, 0.0) for i in range(len(row))}


def _layout_positions(
    box_id: int,
    members: List[str],
    internal: Sequence[PreAutEdge],
) -> Dict[str, Tuple[float, float]]:
    """Return node name -> (x,y) in TikZ units."""
    if box_id == 2 and set(members) == {"G", "G2", "G4", "G7", "G8", "G9"}:
        return {
            "G": (0.0, 0.0),
            "G2": (3.4, 1.1),
            "G4": (3.4, -1.1),
            "G7": (-3.5, 1.35),
            "G8": (-3.5, 0.0),
            "G9": (-3.5, -1.35),
        }

    if box_id in _ROW_LAYOUT_BOX_IDS:
        return _layout_row_positions(members, internal)

    hub = _choose_hub(members, internal)
    others = [m for m in members if m != hub]
    if not others:
        return {hub: (0.0, 0.0)}

    n = len(others)
    radius = 3.2 if n <= 4 else 3.9
    pos: Dict[str, Tuple[float, float]] = {hub: (0.0, 0.0)}
    others_sorted = sorted(others, key=_member_sort_key)
    for i, m in enumerate(others_sorted):
        theta = -math.pi / 2 + 2 * math.pi * i / n
        pos[m] = (radius * math.cos(theta), radius * math.sin(theta))
    return pos


def _step2_edges_with_reverse_perm(internal: Sequence[PreAutEdge]) -> List[PreAutEdge]:
    out: List[PreAutEdge] = []
    for e in internal:
        if e.kind != "step2" or e.src == e.dst:
            continue
        if any(
            f.kind == "permutation" and f.src == e.dst and f.dst == e.src for f in internal
        ):
            out.append(e)
    out.sort(key=lambda e: (e.src, e.dst))
    return out


def _emit_edges(lines: List[str], internal: Sequence[PreAutEdge]) -> None:
    special = _step2_edges_with_reverse_perm(internal)
    special_index = {id(e): i for i, e in enumerate(special)}

    for e in internal:
        vs, vt = _tikz_vertex_name(e.src), _tikz_vertex_name(e.dst)
        style = "permmap" if e.kind == "permutation" else "stepmap"
        if e.src == e.dst:
            lines.append(
                rf"  \draw[{style}] ({vs}) to[out=130,in=50,looseness=14] ({vt});"
            )
        elif e.kind == "step2" and id(e) in special_index:
            idx = special_index[id(e)]
            bend = "bend left=12" if idx % 2 == 0 else "bend right=12"
            lines.append(rf"  \draw[{style}] ({vs}) to[{bend}] ({vt});")
        else:
            lines.append(rf"  \draw[{style}] ({vs}) -- ({vt});")


def _build_diagram_tikzpicture(
    box_id: int,
    members: List[str],
    internal: List[PreAutEdge],
) -> str:
    """TikZ only: nodes, edges, rounded frame, and corner label (natural PDF size)."""
    pos = _layout_positions(box_id, members, internal)
    for m in members:
        if m not in pos:
            raise RuntimeError(f"Missing layout for member {m!r} in box {box_id}")

    sc = _DIAGRAM_COORD_SCALE
    lines: List[str] = []
    lines.append(r"\begin{tikzpicture}[")
    lines.append(r"  font=\normalsize,")
    lines.append(r"  >=Stealth,")
    lines.append(
        r"  grnode/.style={circle, draw=black, fill=gray!12, minimum size=6.2mm, inner sep=1pt},"
    )
    lines.append(r"  stepmap/.style={->, draw=blue!65, line width=0.75pt},")
    lines.append(r"  permmap/.style={->, draw=green!55!black, line width=0.75pt}")
    lines.append(r"]")

    for nm in sorted(members, key=_member_sort_key):
        x, y = pos[nm]
        xs, ys = x * sc, y * sc
        vid = _tikz_vertex_name(nm)
        lbl = latex_node_name(nm)
        lines.append(rf"  \node[grnode] ({vid}) at ({xs:.2f},{ys:.2f}) {{${lbl}$}};")

    _emit_edges(lines, internal)

    fit_arg = "".join(f"({_tikz_vertex_name(nm)})" for nm in sorted(members, key=_member_sort_key))
    lines.append(
        rf"  \node[draw=black, line width=0.75pt, rounded corners=4pt, inner sep=10pt, "
        rf"fit={fit_arg}] (boxframe) {{}};"
    )
    rom = latex_roman_for_class(box_id)
    lines.append(
        r"  \node[anchor=south east, inner sep=2pt, font=\footnotesize] at (boxframe.north east) "
        rf"{{$\mathrm{{graphs}}_{{{box_id}}}$ (Box ${rom}$)}};"
    )

    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines) + "\n"


def _build_box_text_below_frame(
    box_id: int,
    members: List[str],
    internal: List[PreAutEdge],
    kept_edges: Sequence[PreAutEdge],
    node_by_name: Dict[str, Any],
    key_by_node: Dict[str, Tuple[Tuple[int, int], ...]],
    underlying_label_by_key: Dict[Tuple[Tuple[int, int], ...], str],
) -> str:
    """
    LaTeX (outside TikZ): graph dictionary, internal maps, then cross-box preAUT edges.
    """
    rom = latex_roman_for_class(box_id)
    member_set = set(members)
    parts: List[str] = []
    parts.append(r"\raggedright")
    parts.append(
        r"\textbf{Graph data (ltt structures in this box).}\par\smallskip"
        r"\begin{enumerate}[leftmargin=*, itemsep=2pt]"
    )
    for nm in sorted(members, key=_member_sort_key):
        g = node_by_name[nm].graph
        ulabel = underlying_label_by_key[key_by_node[nm]]
        parts.append(rf"\item ${latex_node_name(nm)}$:")
        parts.append(r"\begin{itemize}[leftmargin=*, itemsep=0pt]")
        parts.append(rf"\item underlying graph class $= {ulabel}$.")
        parts.append(rf"\item red vertex $= {latex_math_vertex(g.red_vertex)}$.")
        parts.append(
            rf"\item red edge $= \{{{latex_math_vertex(g.red_edge[0])},\,"
            rf"{latex_math_vertex(g.red_edge[1])}\}}$."
        )
        parts.append(
            rf"\item purple edges ($|\mathcal{{P}}|={len(g.purple_edges)}$):\mbox{{}}\\"
            + latex_purple_partition_lines(sorted(g.purple_edges))
            + "."
        )
        black_tex = latex_edge_set_with_last_five_new_line(sorted(g.black_edges))
        parts.append(
            rf"\item black edges ($|\mathcal{{B}}|={len(g.black_edges)}$): "
            rf"${black_tex}$."
        )
        parts.append(r"\end{itemize}")
    parts.append(r"\end{enumerate}")
    parts.append(r"\par\medskip")

    outgoing = [
        e
        for e in kept_edges
        if e.kind != "box" and e.src in member_set and e.dst not in member_set
    ]
    incoming = [
        e
        for e in kept_edges
        if e.kind != "box" and e.dst in member_set and e.src not in member_set
    ]
    outgoing.sort(key=lambda e: (e.src, e.dst, e.kind))
    incoming.sort(key=lambda e: (e.src, e.dst, e.kind))

    parts.append(
        r"\textbf{Arrows.}\; "
        r"Blue: Step~$2$ edge label. Green: permutation $\varphi$ from ep-isomorphism (Step~$3$). "
        r"\par\smallskip"
        rf"\textbf{{Maps represented (internal to Box~${rom}$).}}"
    )
    parts.append(r"\begin{enumerate}[leftmargin=*, itemsep=2pt]")
    for e in sorted(internal, key=lambda x: (x.src, x.dst, x.kind)):
        parts.append(_legend_item_tex(e))
    parts.append(r"\end{enumerate}")
    parts.append(r"\par\medskip")

    parts.append(r"\textbf{Incoming preAUT edges (into this box).}\par\smallskip")
    if not incoming:
        parts.append(r"\textit{(None.)}")
    else:
        parts.append(r"\begin{enumerate}[leftmargin=*, itemsep=2pt]")
        for e in incoming:
            parts.append(_cross_box_edge_item_tex(e, e.src, node_by_name))
        parts.append(r"\end{enumerate}")
    parts.append(r"\par\medskip")

    parts.append(r"\textbf{Outgoing preAUT edges (from this box).}\par\smallskip")
    if not outgoing:
        parts.append(r"\textit{(None.)}")
    else:
        parts.append(r"\begin{enumerate}[leftmargin=*, itemsep=2pt]")
        for e in outgoing:
            parts.append(_cross_box_edge_item_tex(e, e.dst, node_by_name))
        parts.append(r"\end{enumerate}")
    return "\n".join(parts) + "\n"


def build_appendix_tex() -> str:
    nodes, boxes, _levels, edges = run_algorithm()
    node_by_name = {n.name: n for n in nodes}
    node_names_all = [n.name for n in nodes]
    kept_nodes, kept_edges = filter_preaut_components_with_edges(node_names_all, edges)

    key_by_node: Dict[str, Tuple[Tuple[int, int], ...]] = {
        nm: underlying_key(node_by_name[nm].graph) for nm in kept_nodes
    }
    unique_underlying_keys = sorted(set(key_by_node.values()))
    underlying_label_by_key: Dict[Tuple[Tuple[int, int], ...], str] = {
        k: f"U_{i}" for i, k in enumerate(unique_underlying_keys, start=1)
    }

    chunks: List[str] = []
    chunks.append(
        "% Auto-generated by generate_box_internal_maps_appendix_tex.py — do not edit by hand.\n"
    )
    chunks.append(
        r"\section[Box internal preAUT maps]{Internal preAUT maps within each ep-isomorphism class}"
        + "\n\n"
    )
    chunks.append(
        r"The Roman numeral for each class matches the translation table in the next section. "
        r"Each diagram shows only edges whose source and target lie in the same class "
        r"(edges induced inside one $\mathrm{graphs}_k$ box). "
        r"\par\smallskip\noindent"
        r"\textit{Regeneration.} Run \texttt{python generate\_box\_internal\_maps\_appendix\_tex.py} "
        r"from the repository root."
        + "\n\n"
    )

    for box_id in sorted(boxes.keys(), key=_box_id_sort_roman):
        members = sorted(
            [nm for nm in kept_nodes if node_by_name[nm].box_id == box_id],
            key=_member_sort_key,
        )
        member_set = set(members)
        internal = [
            e
            for e in kept_edges
            if e.src in member_set and e.dst in member_set and e.kind != "box"
        ]
        if not members:
            continue

        rom = latex_roman_for_class(box_id)
        chunks.append(
            rf"\subsection*{{Class ${box_id}$ (Box ${rom}$): internal preAUT maps}}" + "\n\n"
        )
        chunks.append(r"\begin{center}" + "\n")
        chunks.append(_build_diagram_tikzpicture(box_id, members, internal))
        chunks.append(r"\end{center}" + "\n")
        chunks.append(r"\begingroup\sloppy\normalsize\noindent" + "\n")
        chunks.append(
            _build_box_text_below_frame(
                box_id,
                members,
                internal,
                kept_edges,
                node_by_name,
                key_by_node,
                underlying_label_by_key,
            )
        )
        chunks.append(r"\par\endgroup" + "\n\n")

    return "".join(chunks)


def main() -> None:
    repo = Path(__file__).resolve().parent
    out = repo / "box_internal_maps_appendix_generated.tex"
    out.write_text(build_appendix_tex(), encoding="utf-8")
    print(f"Wrote {out.relative_to(repo)}", flush=True)


if __name__ == "__main__":
    main()
