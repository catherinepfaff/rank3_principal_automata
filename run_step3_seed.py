"""
Run Prompt_extracted Task t:Step3 for the seed ltt structure.

This script assumes Step 2 has already been computed from the seed graph, then applies
Step 3 exactly once (for k=1, starting from GRAPHS_1={G}).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ltt_structures import (
    LTT,
    all_pair_preserving_permutations,
    graph_signature,
    relabel_graph,
    seed_ltt_structure,
    step2_terminals,
)


def epi_class_key(g: LTT) -> Tuple:
    """
    Canonical key for ep-isomorphism classes.

    We allow pair-preserving relabelings that send the red vertex of ``g`` to ``x1``.
    """
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
    """
    Return one pair-preserving relabeling phi with phi(source)=target, if it exists.
    """
    target_sig = graph_signature(target)
    for mapping in all_pair_preserving_permutations():
        if mapping[source.red_vertex] != target.red_vertex:
            continue
        if graph_signature(relabel_graph(source, mapping)) == target_sig:
            return mapping
    return None


def inverse_mapping(mapping: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in mapping.items():
        out[v] = k
    return out


def cycle_notation(mapping: Dict[str, str], labels: Sequence[str]) -> str:
    """
    Display permutation in cycle notation on the label alphabet.
    """
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


@dataclass
class PreAutEdge:
    src: str
    dst: str
    label: str
    kind: str  # "step2" or "permutation"


def main() -> None:
    # Step 1 initialization for the first component.
    seed = seed_ltt_structure()
    graphs: List[LTT] = [seed]
    graph_names: List[str] = ["G"]
    graph_boxes: List[int] = [1]
    class_to_box: Dict[Tuple, int] = {epi_class_key(seed): 1}

    boxes: Dict[int, List[int]] = {1: [0]}  # box id -> indices in ``graphs``
    graphs_k_plus_1: List[int] = []  # indices of nodes in GRAPHS_2
    edges: List[PreAutEdge] = []

    # Step 2 output (already filtered to PLTT by step2_terminals flags).
    rows = [row for row in step2_terminals(seed, None) if row[3]]

    print("Step 3 on seed output (human-readable)")
    print("=" * 72)
    print("Initial state from Step 1:")
    print("  GRAPHS = {G}")
    print("  graphs_1 = {G}")
    print("  boxes = {graphs_1}")
    print("  GRAPHS_1 = {G}")
    print()
    print("Processing terminal(G) in Step 2 order:")
    print("  {G_{1;a}, G_{1;b}, G_{2;a}, G_{2;b}}")
    print()

    for variant, edge_label, g_prime, _ in rows:
        sig_prime = graph_signature(g_prime)

        exact_match_idx: Optional[int] = None
        for idx, existing in enumerate(graphs):
            if graph_signature(existing) == sig_prime:
                exact_match_idx = idx
                break

        if exact_match_idx is not None:
            dst_name = graph_names[exact_match_idx]
            edges.append(PreAutEdge(src="G", dst=dst_name, label=edge_label, kind="step2"))
            print(f"- {variant}: exact match with {dst_name}")
            print(f"    add directed edge  G --[{edge_label}]--> {dst_name}")
            continue

        key_prime = epi_class_key(g_prime)
        if key_prime in class_to_box:
            # Step 3 case 1: ep-isomorphic to an existing graph, but not equal.
            box_id = class_to_box[key_prime]
            new_index = len(graphs)
            new_name = variant
            graphs.append(g_prime)
            graph_names.append(new_name)
            graph_boxes.append(box_id)
            boxes[box_id].append(new_index)

            # Use a representative in the same box as target.
            rep_idx = boxes[box_id][0]
            rep_name = graph_names[rep_idx]
            mapping = epi_isomorphic_mapping(g_prime, graphs[rep_idx])
            if mapping is None:
                raise RuntimeError(f"Expected ep-isomorphism mapping from {new_name} to {rep_name}.")
            perm_label = cycle_notation(mapping, g_prime.labels)
            edges.append(PreAutEdge(src=new_name, dst=rep_name, label=perm_label, kind="permutation"))

            print(f"- {variant}: ep-isomorphic to existing box graphs_{box_id} (not equal)")
            print(f"    add node {new_name} to GRAPHS and graphs_{box_id}")
            print(f"    add permutation edge  {new_name} --[phi={perm_label}]--> {rep_name}")
            continue

        # Step 3 case 3: genuinely new graph (new box + new layer node).
        new_box_id = max(boxes.keys()) + 1
        class_to_box[key_prime] = new_box_id

        new_index = len(graphs)
        new_name = variant
        graphs.append(g_prime)
        graph_names.append(new_name)
        graph_boxes.append(new_box_id)
        boxes[new_box_id] = [new_index]
        graphs_k_plus_1.append(new_index)
        edges.append(PreAutEdge(src="G", dst=new_name, label=edge_label, kind="step2"))

        print(f"- {variant}: new ep-isomorphism class")
        print(f"    add node {new_name} to GRAPHS and preAUT")
        print(f"    create new box graphs_{new_box_id} = {{{new_name}}}")
        print(f"    add {new_name} to GRAPHS_2")
        print(f"    add directed edge  G --[{edge_label}]--> {new_name}")

    print()
    print("Outcome after Step 3 (for the seed graph at level 1):")
    print("-" * 72)
    print(f"|GRAPHS| = {len(graphs)}")
    print("GRAPHS = {" + ", ".join(graph_names) + "}")
    print()
    print(f"|boxes| = {len(boxes)}")
    for box_id in sorted(boxes):
        members = ", ".join(graph_names[i] for i in boxes[box_id])
        print(f"  graphs_{box_id} = {{{members}}}")
    print()
    layer2_names = ", ".join(graph_names[i] for i in graphs_k_plus_1)
    print(f"GRAPHS_2 = {{{layer2_names}}}")
    print()
    print("preAUT edges added during Step 3:")
    for e in edges:
        if e.kind == "step2":
            print(f"  {e.src} --[{e.label}]--> {e.dst}")
        else:
            print(f"  {e.src} --[phi = {e.label}]--> {e.dst}")


if __name__ == "__main__":
    main()

