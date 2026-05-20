"""
Build a standalone TikZ figure: graphs inside Box~I (Class~$2$) and all internal preAUT maps.

Output: ``box_I_internal_map_standalone.tex`` (compile with pdflatex).

Usage:
    python generate_box_I_internal_map_tex.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from generate_preaut_appendix_tex import (
    filter_preaut_components_with_edges,
    latex_node_name,
    latex_step2_label,
    run_algorithm,
)

# Box Roman I = ep-isomorphism class number $2$ in ``CLASS_TO_ROMAN``.
BOX_I_CLASS_ID = 2


def _tikz_vertex_name(graph_name: str) -> str:
    if graph_name == "G":
        return "vG"
    if graph_name.startswith("G") and graph_name[1:].isdigit():
        return f"v{graph_name[1:]}"
    raise ValueError(f"unexpected graph name {graph_name!r}")


def _legend_item_tex(e) -> str:
    src = latex_node_name(e.src)
    dst = latex_node_name(e.dst)
    if e.kind == "step2":
        lbl = latex_step2_label(e.label)
        return rf"\item ${src} \xrightarrow{{{lbl}}} {dst}$ \textit{{(Step~2)}}."
    return (
        rf"\item ${src} \xrightarrow{{\varphi}} {dst}$, where $\varphi={e.label}$ "
        r"\textit{(permutation / ep-isomorphism).}"
    )


def build_standalone_tex() -> str:
    nodes, _boxes, _levels, edges = run_algorithm()
    node_by_name = {n.name: n for n in nodes}
    node_names_all = [n.name for n in nodes]
    kept_nodes, kept_edges = filter_preaut_components_with_edges(node_names_all, edges)

    members = sorted(
        [nm for nm in kept_nodes if node_by_name[nm].box_id == BOX_I_CLASS_ID],
        key=lambda s: (0 if s == "G" else int(s[1:]) if s[1:].isdigit() else 999, s),
    )
    member_set = set(members)
    internal = [e for e in kept_edges if e.src in member_set and e.dst in member_set]
    internal.sort(key=lambda e: (e.src, e.dst, e.kind))

    # Layout: $G$ central; Step~2 targets to the right; $G_7,G_8,G_9$ on the left (perm into $G$).
    pos: Dict[str, Tuple[float, float]] = {
        "G": (0.0, 0.0),
        "G2": (3.4, 1.1),
        "G4": (3.4, -1.1),
        "G7": (-3.5, 1.35),
        "G8": (-3.5, 0.0),
        "G9": (-3.5, -1.35),
    }
    for m in members:
        if m not in pos:
            raise RuntimeError(f"Missing layout for member {m!r}")

    lines: List[str] = []
    lines.append(r"\documentclass[tikz,border=8pt]{standalone}")
    lines.append(r"\usepackage{amsmath,amssymb}")
    lines.append(r"\usepackage{enumitem}")
    lines.append(r"\usetikzlibrary{arrows.meta,fit,calc}")
    lines.append(r"\begin{document}")
    lines.append(r"\begin{tikzpicture}[")
    lines.append(r"  font=\small,")
    lines.append(r"  >=Stealth,")
    lines.append(
        r"  grnode/.style={circle, draw=black, fill=gray!12, minimum size=8mm, inner sep=1pt},"
    )
    lines.append(
        r"  stepmap/.style={->, draw=blue!65, line width=0.9pt},"
    )
    lines.append(
        r"  permmap/.style={->, draw=green!55!black, line width=0.9pt}"
    )
    lines.append(r"]")

    for nm in members:
        x, y = pos[nm]
        vid = _tikz_vertex_name(nm)
        lbl = latex_node_name(nm)
        lines.append(
            rf"  \node[grnode] ({vid}) at ({x:.2f},{y:.2f}) {{${lbl}$}};"
        )

    # Directed edges: green (permutation) = straight chords; blue (Step~2) = light bend only.
    for e in internal:
        vs, vt = _tikz_vertex_name(e.src), _tikz_vertex_name(e.dst)
        style = "permmap" if e.kind == "permutation" else "stepmap"
        if {e.src, e.dst} == {"G", "G2"}:
            if e.kind == "permutation":
                lines.append(rf"  \draw[{style}] ({vs}) -- ({vt});")
            else:
                lines.append(rf"  \draw[{style}] ({vs}) to[bend left=12] ({vt});")
        elif {e.src, e.dst} == {"G", "G4"}:
            if e.kind == "permutation":
                lines.append(rf"  \draw[{style}] ({vs}) -- ({vt});")
            else:
                lines.append(rf"  \draw[{style}] ({vs}) to[bend right=12] ({vt});")
        elif e.dst == "G" and e.src in {"G7", "G8", "G9"}:
            lines.append(rf"  \draw[{style}] ({vs}) -- ({vt});")
        else:
            lines.append(rf"  \draw[{style}] ({vs}) -- ({vt});")

    fit_arg = "".join(f"({_tikz_vertex_name(nm)})" for nm in members)
    lines.append(
        rf"  \node[draw=black, line width=0.9pt, rounded corners=5pt, inner sep=16pt, "
        rf"fit={fit_arg}] (boxframe) {{}};"
    )
    lines.append(
        r"  \node[anchor=south east, inner sep=2pt, font=\footnotesize] at (boxframe.north east) "
        r"{$\mathrm{graphs}_2$ (Box $\mathrm{I}$)};"
    )

    # Legend below the frame.
    lines.append(
        r"  \node[anchor=north west, align=left, text width=12.8cm] at ($(boxframe.south west)+(0,-0.35)$) {"
    )
    lines.append(
        r"\textbf{Arrows.}\; "
        r"Blue: Step~$2$ edge label. Green: permutation $\varphi$ from ep-isomorphism (Step~$3$). "
        r"\par\smallskip"
        r"\textbf{Maps represented (internal to Box~$\mathrm{I}$).}"
    )
    lines.append(r"\begin{enumerate}[leftmargin=*, itemsep=2pt]")
    for e in internal:
        lines.append(_legend_item_tex(e))
    lines.append(r"\end{enumerate}")
    lines.append(r"};")

    lines.append(r"\end{tikzpicture}")
    lines.append(r"\end{document}")
    return "\n".join(lines) + "\n"


def main() -> None:
    repo = Path(__file__).resolve().parent
    out = repo / "box_I_internal_map_standalone.tex"
    out.write_text(build_standalone_tex(), encoding="utf-8")
    print(f"Wrote {out.relative_to(repo)}", flush=True)


if __name__ == "__main__":
    main()
