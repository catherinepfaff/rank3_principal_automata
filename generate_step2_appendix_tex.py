"""
Write ``step2_seed_appendix_generated.tex'' for Prompt_extracted appendix B.

Produces readable LaTeX (math notation for labels, structured lists).

Run from repository root: ``python generate_step2_appendix_tex.py''.

Rule~(j;a) terminals have ``red_vertex'' $=d_r$; morphism labels still name the branch vertex $d_j$
from Step~$2$ (see ``branch_params'' vs. ``g.red_vertex'' in the listing below).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ltt_structures import (
    Edge,
    Label,
    purple_neighbor_pair_ordered,
    seed_ltt_structure,
    step2_terminals,
)


def latex_math_vertex(lb: Label) -> str:
    """Map internal label ``xb5'' / ``x3'' to LaTeX math ``\\bar{x}_{5}'' / ``x_{3}''."""
    if lb.startswith("xb"):
        return "\\bar{x}_{" + lb[2:] + "}"
    if lb.startswith("x"):
        return "x_{" + lb[1:] + "}"
    raise ValueError(f"unknown label {lb!r}")


def latex_math_edge(e: Edge) -> str:
    """Format one undirected edge as ``\\{left,\\,right\\}'' inside math."""
    a, b = e
    return rf"\{{{latex_math_vertex(a)},\,{latex_math_vertex(b)}\}}"


def latex_math_edge_arrow_word(left: Label, mid: Label, right: Label) -> str:
    """Automaton-type morphism label ``left \\to mid\\,right'' (three vertex symbols)."""
    return (
        rf"{latex_math_vertex(left)} \to {latex_math_vertex(mid)}\,"
        rf"{latex_math_vertex(right)}"
    )


def latex_itemize_edges(edges: Iterable[Edge]) -> str:
    """Enumerate edges as a compact numbered ``enumerate'' inside LaTeX."""
    rows = [rf"\item $\displaystyle {latex_math_edge(e)}$" for e in sorted(edges)]
    return (
        "\\begin{enumerate}[label=\\arabic*., itemsep=0.15ex, leftmargin=*]\n"
        + "\n".join(rows)
        + "\n\\end{enumerate}"
    )


def edge_sort_key(e: Edge) -> tuple[str, str]:
    a, b = e
    return (a, b)


def latex_edge_list_inline(edges: Iterable[Edge]) -> str:
    """Render edges as a single inline list in math mode."""
    return ",\\; ".join(latex_math_edge(e) for e in sorted(edges, key=edge_sort_key))


def purple_partition_edge_rows(edges: Iterable[Edge]) -> list[list[Edge]]:
    """
    Group purple edges into the three partition-element triangles.
    Each row should contain exactly 3 edges.
    """
    sorted_edges = sorted(edges, key=edge_sort_key)
    vertices = sorted({v for e in sorted_edges for v in e})
    adj = {v: set() for v in vertices}
    for a, b in sorted_edges:
        adj[a].add(b)
        adj[b].add(a)

    seen: set[Label] = set()
    components: list[list[Label]] = []
    for v in vertices:
        if v in seen:
            continue
        stack = [v]
        comp: list[Label] = []
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
    rows: list[list[Edge]] = []
    for comp in components:
        comp_set = set(comp)
        row = [e for e in sorted_edges if e[0] in comp_set and e[1] in comp_set]
        if row:
            rows.append(row)
    return rows


def latex_purple_partition_lines(edges: Iterable[Edge]) -> str:
    """Render purple edges as one line per partition element."""
    rows = purple_partition_edge_rows(edges)
    lines: list[str] = []
    for idx, row in enumerate(rows, start=1):
        row_tex = ",\\; ".join(latex_math_edge(e) for e in row)
        lines.append(rf"$P_{{{idx}}}: {row_tex}$")
    return "\\\\\n".join(lines)


def variant_latex_name(variant: str) -> str:
    """Pretty-print variant key ``G_1;a'' as ``G_{1a}``."""
    if not variant.startswith("G_"):
        return variant
    body = variant[2:]
    left, sep, right = body.partition(";")
    if not sep:
        return variant
    return f"G_{{{left}{right}}}"


def write_appendix_tex(path: Path) -> None:
    """Emit appendix body (no ``\\documentclass'') into ``path''."""
    seed = seed_ltt_structure()  # Seed graph from Prompt_extracted Base Step.
    rows = step2_terminals(seed, None)  # Same Step $2$ logic as ``run_step2_seed.py''.

    ra, rb = seed.red_edge  # Locate ``d_p'' from seed red edge endpoints.
    d_r = seed.red_vertex
    d_p = rb if d_r == ra else ra
    # ``d_1,d_2'' order matters for morphism labels---recover explicitly (do not read from ``g.red_vertex'' for rule 2a).
    branch_d1, branch_d2 = purple_neighbor_pair_ordered(seed, d_p)

    chunks: list[str] = []

    chunks.append("\\subsection*{Seed \\emph{ltt} structure $G$}\n")
    chunks.append("\\begin{description}[style=nextline, font=\\normalfont\\bfseries]\n")
    chunks.append(f"\\item[Red vertex] $\\displaystyle {latex_math_vertex(seed.red_vertex)}$.\n")
    chunks.append(f"\\item[Red edge] $\\displaystyle {latex_math_edge(seed.red_edge)}$.\n")
    chunks.append(
        f"\\item[Purple edges (${len(seed.purple_edges)}$)]\\mbox{{}}\\\\\n"
        + latex_purple_partition_lines(seed.purple_edges)
        + "\n"
    )
    chunks.append(
        f"\\item[Black edges (${len(seed.black_edges)}$)] "
        + rf"$\displaystyle {latex_edge_list_inline(seed.black_edges)}$."
        + "\n"
    )
    chunks.append("\\end{description}\n\n")

    chunks.append("\\subsection*{Step $2$ parameters}\n")
    chunks.append(
        f"$d_r = {latex_math_vertex(d_r)}$, "
        f"$d_p = {latex_math_vertex(d_p)}$ "
        "(purple endpoint of the red edge).\\par\\smallskip\n"
        "\\noindent\\textit{Prompt alignment:} rule~(j;a) specifies red vertex $d_r$, red edge "
        "$\\{d_r,\\bar{d}_j\\}$, and purple edges exactly as in $G$; "
        "rule~(j;b) adds purple edges from colored neighbors of $d_j$ and inherits only purple "
        "edges not incident to $d_j$ (see \\texttt{ltt\\_structures.terminal\\_ga\\_step2} and "
        "\\texttt{ltt\\_structures.terminal\\_gb\\_step2}). Directed-edge labels use $(d_r,d_j)$.\n\n"
    )
    chunks.append(
        "Membership in $\\mathrm{PLTT}$ uses ep-isomorphism to one of the $270$ distinguished "
        "graphs (same enumeration as \\texttt{list\\_admissible\\_ltt\\_classes.py}).\\par\\smallskip\n\n"
    )

    chunks.append(
        "\\subsection*{Terminal graphs "
        "$\\mathrm{terminal}(G)=\\{G_{1a},G_{1b},G_{2a},G_{2b}\\}$}\n"
    )
    chunks.append("\\begin{enumerate}[label=\\textbf{\\arabic*.}, leftmargin=*]\n")

    branch_params = (branch_d1, branch_d2)
    for idx, (variant, _edge_tex, g, in_pltt) in enumerate(rows):
        j_idx = idx // 2
        rule_kind = "a" if idx % 2 == 0 else "b"
        d_j_branch = branch_params[j_idx]

        if rule_kind == "a":
            edge_words = latex_math_edge_arrow_word(d_r, d_j_branch, d_r)
            expl = "(rule 2a: $d_r \\to d_j\\, d_r$)"
        else:
            edge_words = latex_math_edge_arrow_word(d_j_branch, d_r, d_j_branch)
            expl = "(rule 2b: $d_j \\to d_r\\, d_j$)"

        status = (
            "\\textbf{retained} (in $\\mathrm{PLTT}$)"
            if in_pltt
            else "\\textbf{removed} (not in $\\mathrm{PLTT}$)"
        )

        vn = variant_latex_name(variant)
        chunks.append("\\item ")
        chunks.append(f"${vn}$: directed edge label ${edge_words}$, {expl}. ")
        chunks.append(f"{status}.\n")
        chunks.append("\\begin{description}[style=nextline, font=\\normalfont\\bfseries]\n")
        chunks.append(f"\\item[Red vertex] $\\displaystyle {latex_math_vertex(g.red_vertex)}$.\n")
        chunks.append(f"\\item[Red edge] $\\displaystyle {latex_math_edge(g.red_edge)}$.\n")
        chunks.append(
            f"\\item[Purple edges (${len(g.purple_edges)}$)]\\mbox{{}}\\\\\n"
            + latex_purple_partition_lines(g.purple_edges)
            + "\n"
        )
        chunks.append(
            f"\\item[Black edges (${len(g.black_edges)}$)] "
            + rf"$\displaystyle {latex_edge_list_inline(g.black_edges)}$."
            + "\n"
        )
        chunks.append("\\end{description}\n")

    chunks.append("\\end{enumerate}\n")

    path.write_text("".join(chunks), encoding="utf-8")


def main() -> None:
    repo = Path(__file__).resolve().parent
    out = repo / "step2_seed_appendix_generated.tex"
    write_appendix_tex(out)
    print(f"Wrote {out.relative_to(repo)}", flush=True)


if __name__ == "__main__":
    main()
