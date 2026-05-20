"""
Write ``step3_seed_appendix_generated.tex'' for Prompt_extracted appendix B.

Run from repository root: ``python generate_step3_appendix_tex.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ltt_structures import (
    LTT,
    all_pair_preserving_permutations,
    graph_signature,
    relabel_graph,
    seed_ltt_structure,
    step2_terminals,
)


def latex_math_vertex(lb: str) -> str:
    if lb.startswith("xb"):
        return "\\bar{x}_{" + lb[2:] + "}"
    if lb.startswith("x"):
        return "x_{" + lb[1:] + "}"
    raise ValueError(f"unknown label {lb!r}")


def latex_variant_name(name: str) -> str:
    if name == "G":
        return "G"
    if not name.startswith("G_"):
        return name
    body = name[2:]
    left, sep, right = body.partition(";")
    if sep:
        return f"G_{{{left}{right}}}"
    return name


def latex_edge_label(label: str) -> str:
    out = label
    for i in range(1, 6):
        out = out.replace(f"xb{i}", f"\\bar{{x}}_{{{i}}}")
    for i in range(1, 6):
        out = out.replace(f"x{i}", f"x_{{{i}}}")
    return out


def latex_math_edge(e: Tuple[str, str]) -> str:
    a, b = e
    return rf"\{{{latex_math_vertex(a)},\,{latex_math_vertex(b)}\}}"


def edge_sort_key(e: Tuple[str, str]) -> Tuple[str, str]:
    return (e[0], e[1])


def latex_edge_list_inline(edges: Iterable[Tuple[str, str]]) -> str:
    return ",\\; ".join(latex_math_edge(e) for e in sorted(edges, key=edge_sort_key))


def purple_partition_edge_rows(edges: Iterable[Tuple[str, str]]) -> List[List[Tuple[str, str]]]:
    sorted_edges = sorted(edges, key=edge_sort_key)
    vertices = sorted({v for a, b in sorted_edges for v in (a, b)})
    adj = {v: set() for v in vertices}
    for a, b in sorted_edges:
        adj[a].add(b)
        adj[b].add(a)

    seen: set[str] = set()
    components: List[List[str]] = []
    for v in vertices:
        if v in seen:
            continue
        stack = [v]
        comp: List[str] = []
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
    rows: List[List[Tuple[str, str]]] = []
    for comp in components:
        comp_set = set(comp)
        row = [e for e in sorted_edges if e[0] in comp_set and e[1] in comp_set]
        if row:
            rows.append(row)
    return rows


def latex_purple_partition_lines(edges: Iterable[Tuple[str, str]]) -> str:
    rows = purple_partition_edge_rows(edges)
    lines: List[str] = []
    for idx, row in enumerate(rows, start=1):
        row_tex = ",\\; ".join(latex_math_edge(e) for e in row)
        lines.append(rf"$P_{{{idx}}}: {row_tex}$")
    return "\\\\\n".join(lines)


def epi_class_key(g: LTT) -> Tuple:
    best: Optional[Tuple] = None
    for mapping in all_pair_preserving_permutations():
        if mapping[g.red_vertex] != "x1":
            continue
        sig = graph_signature(relabel_graph(g, mapping))
        if best is None or sig < best:
            best = sig
    if best is None:
        raise RuntimeError("No canonical ep-class key found.")
    return best


def epi_isomorphic_mapping(source: LTT, target: LTT) -> Optional[Dict[str, str]]:
    target_sig = graph_signature(target)
    for mapping in all_pair_preserving_permutations():
        if mapping[source.red_vertex] != target.red_vertex:
            continue
        if graph_signature(relabel_graph(source, mapping)) == target_sig:
            return mapping
    return None


def cycle_notation(mapping: Dict[str, str], labels: Sequence[str]) -> str:
    seen = set()
    cycles: List[str] = []
    for start in labels:
        if start in seen:
            continue
        cur = start
        cyc: List[str] = []
        while cur not in seen:
            seen.add(cur)
            cyc.append(cur)
            cur = mapping[cur]
        if len(cyc) > 1:
            cycles.append("(" + " ".join(cyc) + ")")
    return "".join(cycles) if cycles else "()"


def x_images_notation(mapping: Dict[str, str]) -> str:
    """
    Display phi by images of x_1,...,x_5 only.
    """
    rows: List[str] = []
    for i in range(1, 6):
        src = f"x{i}"
        dst = mapping[src]
        rows.append(rf"{latex_math_vertex(src)} \mapsto {latex_math_vertex(dst)}")
    return r",\; ".join(rows)


@dataclass
class PreAutEdge:
    src: str
    dst: str
    label: str
    kind: str


def write_appendix_tex(path: Path) -> None:
    seed = seed_ltt_structure()
    terminals = [row for row in step2_terminals(seed, None) if row[3]]

    graphs: List[LTT] = [seed]
    graph_names: List[str] = ["G"]
    class_to_box: Dict[Tuple, int] = {epi_class_key(seed): 1}
    boxes: Dict[int, List[int]] = {1: [0]}
    graphs_k_plus_1: List[int] = []
    edges: List[PreAutEdge] = []

    per_terminal_lines: List[str] = []

    for variant, edge_label, g_prime, _ in terminals:
        sig_prime = graph_signature(g_prime)

        exact_match_idx: Optional[int] = None
        for idx, existing in enumerate(graphs):
            if graph_signature(existing) == sig_prime:
                exact_match_idx = idx
                break

        if exact_match_idx is not None:
            dst_name = graph_names[exact_match_idx]
            edges.append(PreAutEdge(src="G", dst=dst_name, label=edge_label, kind="step2"))
            per_terminal_lines.append(
                rf"\item ${latex_variant_name(variant)}$: exact match with ${latex_variant_name(dst_name)}$; "
                rf"add edge $G \to {latex_variant_name(dst_name)}$ with label "
                rf"${latex_edge_label(edge_label)}$."
            )
            per_terminal_lines.append("\\begin{description}[style=nextline, font=\\normalfont\\bfseries]")
            per_terminal_lines.append(rf"\item[Red vertex] $\displaystyle {latex_math_vertex(g_prime.red_vertex)}$.")
            per_terminal_lines.append(rf"\item[Red edge] $\displaystyle {latex_math_edge(g_prime.red_edge)}$.")
            per_terminal_lines.append(
                rf"\item[Purple edges (${len(g_prime.purple_edges)}$)]\mbox{{}}\\"
                + "\n"
                + latex_purple_partition_lines(g_prime.purple_edges)
            )
            per_terminal_lines.append(
                rf"\item[Black edges (${len(g_prime.black_edges)}$)] "
                + rf"$\displaystyle {latex_edge_list_inline(g_prime.black_edges)}$."
            )
            per_terminal_lines.append("\\end{description}")
            continue

        key_prime = epi_class_key(g_prime)
        if key_prime in class_to_box:
            box_id = class_to_box[key_prime]
            new_index = len(graphs)
            new_name = variant
            graphs.append(g_prime)
            graph_names.append(new_name)
            boxes[box_id].append(new_index)

            rep_idx = boxes[box_id][0]
            rep_name = graph_names[rep_idx]
            mapping = epi_isomorphic_mapping(g_prime, graphs[rep_idx])
            if mapping is None:
                raise RuntimeError(f"Expected ep-isomorphism mapping from {new_name} to {rep_name}.")
            perm_label = x_images_notation(mapping)
            edges.append(PreAutEdge(src=new_name, dst=rep_name, label=perm_label, kind="permutation"))
            per_terminal_lines.append(
                rf"\item ${latex_variant_name(variant)}$: ep-isomorphic to "
                rf"${latex_variant_name(rep_name)}$ (box $\mathrm{{graphs}}_{{{box_id}}}$), not equal; "
                rf"add ${latex_variant_name(variant)}$ to $\mathrm{{GRAPHS}}$ and "
                rf"$\mathrm{{graphs}}_{{{box_id}}}$, and add permutation edge "
                rf"${latex_variant_name(variant)} \xrightarrow{{\varphi}} {latex_variant_name(rep_name)}$ "
                rf"with $\varphi={perm_label}$."
            )
            per_terminal_lines.append("\\begin{description}[style=nextline, font=\\normalfont\\bfseries]")
            per_terminal_lines.append(rf"\item[Red vertex] $\displaystyle {latex_math_vertex(g_prime.red_vertex)}$.")
            per_terminal_lines.append(rf"\item[Red edge] $\displaystyle {latex_math_edge(g_prime.red_edge)}$.")
            per_terminal_lines.append(
                rf"\item[Purple edges (${len(g_prime.purple_edges)}$)]\mbox{{}}\\"
                + "\n"
                + latex_purple_partition_lines(g_prime.purple_edges)
            )
            per_terminal_lines.append(
                rf"\item[Black edges (${len(g_prime.black_edges)}$)] "
                + rf"$\displaystyle {latex_edge_list_inline(g_prime.black_edges)}$."
            )
            per_terminal_lines.append("\\end{description}")
            continue

        new_box_id = max(boxes.keys()) + 1
        class_to_box[key_prime] = new_box_id
        new_index = len(graphs)
        new_name = variant
        graphs.append(g_prime)
        graph_names.append(new_name)
        boxes[new_box_id] = [new_index]
        graphs_k_plus_1.append(new_index)
        edges.append(PreAutEdge(src="G", dst=new_name, label=edge_label, kind="step2"))
        per_terminal_lines.append(
            rf"\item ${latex_variant_name(variant)}$: new ep-isomorphism class; "
            rf"add ${latex_variant_name(variant)}$ to $\mathrm{{GRAPHS}}$ and preAUT, create "
            rf"$\mathrm{{graphs}}_{{{new_box_id}}}=\{{{latex_variant_name(variant)}\}}$, add "
            rf"${latex_variant_name(variant)}$ to $\mathrm{{GRAPHS}}_{{2}}$, and add edge "
            rf"$G \to {latex_variant_name(variant)}$ with label ${latex_edge_label(edge_label)}$."
        )
        per_terminal_lines.append("\\begin{description}[style=nextline, font=\\normalfont\\bfseries]")
        per_terminal_lines.append(rf"\item[Red vertex] $\displaystyle {latex_math_vertex(g_prime.red_vertex)}$.")
        per_terminal_lines.append(rf"\item[Red edge] $\displaystyle {latex_math_edge(g_prime.red_edge)}$.")
        per_terminal_lines.append(
            rf"\item[Purple edges (${len(g_prime.purple_edges)}$)]\mbox{{}}\\"
            + "\n"
            + latex_purple_partition_lines(g_prime.purple_edges)
        )
        per_terminal_lines.append(
            rf"\item[Black edges (${len(g_prime.black_edges)}$)] "
            + rf"$\displaystyle {latex_edge_list_inline(g_prime.black_edges)}$."
        )
        per_terminal_lines.append("\\end{description}")

    chunks: List[str] = []
    chunks.append("\\subsection*{Step $3$ on seed output (Task~\\ref{t:Step3})}\n")
    chunks.append(
        "\\noindent Starting from Step~1 initialization "
        "$\\mathrm{GRAPHS}=\\{G\\}$, "
        "$\\mathrm{graphs}_{1}=\\{G\\}$, "
        "$\\mathrm{boxes}=\\{\\mathrm{graphs}_{1}\\}$, "
        "$\\mathrm{GRAPHS}_{1}=\\{G\\}$, "
        "apply Step~$3$ in the Step~$2$ order "
        "$\\{G_{1a},G_{1b},G_{2a},G_{2b}\\}$.\n\n"
    )
    chunks.append("\\begin{enumerate}[label=\\textbf{\\arabic*.}, leftmargin=*]\n")
    chunks.extend(line + "\n" for line in per_terminal_lines)
    chunks.append("\\end{enumerate}\n\n")

    chunks.append("\\paragraph{Outcome after Step $3$ for the seed.}\n")
    chunks.append(rf"$\mathrm{{GRAPHS}}=\{{{', '.join(latex_variant_name(n) for n in graph_names)}\}}$.\\")
    chunks.append("\n")
    chunks.append(f"$|\\mathrm{{boxes}}|={len(boxes)}$, with:\n")
    chunks.append("\\begin{itemize}[leftmargin=*]\n")
    for box_id in sorted(boxes):
        members = ", ".join(latex_variant_name(graph_names[i]) for i in boxes[box_id])
        chunks.append(rf"\item $\mathrm{{graphs}}_{{{box_id}}}=\{{{members}\}}$." + "\n")
    chunks.append("\\end{itemize}\n")
    layer2_names = ", ".join(latex_variant_name(graph_names[i]) for i in graphs_k_plus_1)
    chunks.append(f"$\\mathrm{{GRAPHS}}_{{2}}=\\{{{layer2_names}\\}}$.\n\n")

    chunks.append("\\paragraph{preAUT edges added in this Step~$3$ pass.}\n")
    chunks.append("\\begin{itemize}[leftmargin=*]\n")
    for e in edges:
        src = latex_variant_name(e.src)
        dst = latex_variant_name(e.dst)
        if e.kind == "step2":
            chunks.append(rf"\item ${src} \xrightarrow{{{latex_edge_label(e.label)}}} {dst}$." + "\n")
        else:
            chunks.append(rf"\item ${src} \xrightarrow{{\varphi}} {dst}$ with $\varphi={e.label}$." + "\n")
    chunks.append("\\end{itemize}\n")

    path.write_text("".join(chunks), encoding="utf-8")


def main() -> None:
    repo = Path(__file__).resolve().parent
    out = repo / "step3_seed_appendix_generated.tex"
    write_appendix_tex(out)
    print(f"Wrote {out.relative_to(repo)}", flush=True)


if __name__ == "__main__":
    main()

