from collections import defaultdict
from typing import Dict, List, Tuple

from ltt_structures import LTT, canonical_signature, iter_distinguished_ltt


def print_one_structure(index: int, graph: LTT) -> None:
    purple = sorted(graph.purple_edges)
    print(f"distinguished {index}:", flush=True)
    print(f"  red vertex: {graph.red_vertex}")
    print(f"  red edge: {graph.red_edge}")
    print(f"  purple edges ({len(purple)}): {purple}")
    print(flush=True)


def main() -> None:
    class_members: Dict[Tuple, List[int]] = defaultdict(list)
    representatives: Dict[Tuple, LTT] = {}

    print("distinguished structures (streaming):", flush=True)
    print(flush=True)

    idx = 0
    for idx, graph in enumerate(iter_distinguished_ltt(), start=1):
        print_one_structure(idx, graph)
        class_key = canonical_signature(graph)
        class_members[class_key].append(idx)
        if class_key not in representatives:
            representatives[class_key] = graph

    ordered_keys = sorted(class_members.keys())

    print(f"distinguished: {idx}")
    print(f"up_to_epi_isomorphism: {len(ordered_keys)}")
    print()

    for class_number, class_key in enumerate(ordered_keys, start=1):
        rep = representatives[class_key]
        members = class_members[class_key]
        purple = sorted(rep.purple_edges)
        print(f"class {class_number}:")
        print(f"  size: {len(members)}")
        print(f"  members (distinguished indices): {members}")
        print(f"  representative red vertex: {rep.red_vertex}")
        print(f"  representative red edge: {rep.red_edge}")
        print(f"  representative purple edges ({len(purple)}): {purple}")
        print()


if __name__ == "__main__":
    main()
