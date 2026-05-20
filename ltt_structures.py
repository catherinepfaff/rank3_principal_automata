from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import combinations, permutations, product
from typing import Dict, FrozenSet, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

Label = str
Edge = Tuple[Label, Label]
TriplePartition = Tuple[Tuple[Label, ...], Tuple[Label, ...], Tuple[Label, ...]]


def edge(a: Label, b: Label) -> Edge:
    """Create an unordered edge representation."""
    return tuple(sorted((a, b)))


def parse_label(label: Label) -> Tuple[int, bool]:
    """Return (pair_index, is_barred) for labels like x3 / xb3."""
    if label.startswith("xb"):
        return int(label[2:]), True
    if label.startswith("x"):
        return int(label[1:]), False
    raise ValueError(f"Unknown label format: {label}")


def make_label(pair_index: int, barred: bool) -> Label:
    """Create a label string from pair metadata."""
    return f"xb{pair_index}" if barred else f"x{pair_index}"


def inverse_label(label: Label) -> Label:
    """Return the paired inverse label."""
    pair_index, barred = parse_label(label)
    return make_label(pair_index, not barred)


def base_labels(n_pairs: int = 5) -> Tuple[Label, ...]:
    """Return tuple (x1, xb1, x2, xb2, ..., xn, xbn)."""
    out: List[Label] = []
    for i in range(1, n_pairs + 1):
        out.extend((f"x{i}", f"xb{i}"))
    return tuple(out)


def black_edges(n_pairs: int = 5) -> FrozenSet[Edge]:
    """Return required black pair edges {x_i, xb_i}."""
    return frozenset(edge(f"x{i}", f"xb{i}") for i in range(1, n_pairs + 1))


def clique_edges(vertices: Iterable[Label]) -> Set[Edge]:
    """Return all edges of a complete graph on given vertices."""
    vv = list(vertices)
    return {edge(a, b) for a, b in combinations(vv, 2)}


def partitions_into_3_triples(items: Sequence[Label]) -> Iterator[TriplePartition]:
    """Enumerate unique unordered partitions of 9 items into 3 triples."""
    if len(items) != 9:
        raise ValueError("This helper expects exactly 9 items.")

    ordered = sorted(items)
    seen: Set[TriplePartition] = set()

    for t1 in combinations(ordered, 3):
        rem1 = [x for x in ordered if x not in t1]
        for t2 in combinations(rem1, 3):
            t3 = tuple(x for x in rem1 if x not in t2)
            triples = tuple(sorted((tuple(sorted(t1)), tuple(sorted(t2)), tuple(sorted(t3)))))
            if triples in seen:
                continue
            seen.add(triples)
            yield triples


@dataclass(frozen=True)
class LTT:
    labels: Tuple[Label, ...]
    red_vertex: Label
    red_edge: Edge
    purple_edges: FrozenSet[Edge]
    black_edges: FrozenSet[Edge]


def graph_signature(g: LTT) -> Tuple:
    """Sortable immutable signature for exact labeled equality."""
    return (
        g.red_vertex,
        g.red_edge,
        tuple(sorted(g.purple_edges)),
        tuple(sorted(g.black_edges)),
    )


def relabel_graph(g: LTT, mapping: Dict[Label, Label]) -> LTT:
    """Apply a label permutation to the graph."""
    new_labels = tuple(mapping[x] for x in g.labels)
    new_red_vertex = mapping[g.red_vertex]
    new_red_edge = edge(mapping[g.red_edge[0]], mapping[g.red_edge[1]])
    new_purple = frozenset(edge(mapping[a], mapping[b]) for a, b in g.purple_edges)
    new_black = frozenset(edge(mapping[a], mapping[b]) for a, b in g.black_edges)
    return LTT(
        labels=new_labels,
        red_vertex=new_red_vertex,
        red_edge=new_red_edge,
        purple_edges=new_purple,
        black_edges=new_black,
    )


def all_pair_preserving_permutations(n_pairs: int = 5) -> Iterator[Dict[Label, Label]]:
    """
    Enumerate all label permutations that preserve inverse-pair structure.

    For each pair i, choose target pair p(i), and whether to flip bar status.
    """
    pair_ids = list(range(1, n_pairs + 1))
    for perm in permutations(pair_ids):
        for flips in product((False, True), repeat=n_pairs):
            mapping: Dict[Label, Label] = {}
            for src in pair_ids:
                dst = perm[src - 1]
                flip = flips[src - 1]
                for barred in (False, True):
                    src_label = make_label(src, barred)
                    dst_label = make_label(dst, barred ^ flip)
                    mapping[src_label] = dst_label
            yield mapping


def ltt_is_connected(g: LTT) -> bool:
    """
    True iff the underlying undirected graph on ``g.labels`` is connected, using
    every purple, black, and red edge.
    """
    labels = list(g.labels)
    if len(labels) <= 1:
        return True

    adj: Dict[Label, Set[Label]] = {v: set() for v in labels}

    def add_edge(u: Label, v: Label) -> None:
        adj[u].add(v)
        adj[v].add(u)

    for a, b in g.purple_edges:
        add_edge(a, b)
    for a, b in g.black_edges:
        add_edge(a, b)
    ra, rb = g.red_edge
    add_edge(ra, rb)

    start = labels[0]
    seen: Set[Label] = {start}
    q: deque[Label] = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                q.append(v)
    return len(seen) == len(labels)


def canonical_signature(g: LTT) -> Tuple:
    """
    Canonical signature under ep-isomorphism candidates.

    We only allow relabelings that preserve pair structure and keep the unique
    red vertex fixed (required by vertex-color preservation).
    """
    best = None
    for mapping in all_pair_preserving_permutations():
        if mapping[g.red_vertex] != g.red_vertex:
            continue
        sig = graph_signature(relabel_graph(g, mapping))
        if best is None or sig < best:
            best = sig
    if best is None:
        raise RuntimeError("No valid canonical signature found.")
    return best


def iter_distinguished_ltt() -> Iterator[LTT]:
    """
    Yield each distinguished admissible ltt structure in the prompt.

    - red vertex: x1
    - red edge: {x1, x2}
    - purple edges: 3 disjoint triangles on
      {xb1, x2, xb2, x3, xb3, x4, xb4, x5, xb5}
    - black edges: {x_i, xb_i} for i=1..5
    - the full graph (red, purple, and black edges) must be connected
    """
    labels = base_labels(5)
    fixed_black = black_edges(5)
    red_vertex = "x1"
    red_edge = edge("x1", "x2")
    purple_vertex_pool = ["xb1", "x2", "xb2", "x3", "xb3", "x4", "xb4", "x5", "xb5"]

    seen_exact: Set[Tuple] = set()

    for triples in partitions_into_3_triples(purple_vertex_pool):
        purple: Set[Edge] = set()
        for triple in triples:
            purple |= clique_edges(triple)

        g = LTT(
            labels=labels,
            red_vertex=red_vertex,
            red_edge=red_edge,
            purple_edges=frozenset(purple),
            black_edges=fixed_black,
        )
        if not ltt_is_connected(g):
            continue
        sig = graph_signature(g)
        if sig not in seen_exact:
            seen_exact.add(sig)
            yield g


def generate_distinguished_ltt() -> List[LTT]:
    """Same structures as iter_distinguished_ltt(), collected into a list."""
    return list(iter_distinguished_ltt())


def representatives_up_to_epi_isomorphism(graphs: Iterable[LTT]) -> List[LTT]:
    """Return one representative for each ep-isomorphism class."""
    by_class: Dict[Tuple, LTT] = {}
    for g in graphs:
        key = canonical_signature(g)
        if key not in by_class:
            by_class[key] = g
    return list(by_class.values())


# Lazily computed list of all distinguished admissible graphs (expensive; used by Step 2 PLTT checks).
_DISTINGUISHED_LTT_LIST: Optional[List[LTT]] = None


def get_distinguished_ltt_list() -> List[LTT]:
    """Return (cached) list of all distinguished admissible ltt structures."""
    global _DISTINGUISHED_LTT_LIST
    if _DISTINGUISHED_LTT_LIST is None:
        _DISTINGUISHED_LTT_LIST = generate_distinguished_ltt()
    return _DISTINGUISHED_LTT_LIST


def label_order_rank(label: Label, n_pairs: int = 5) -> int:
    """Order inherited from $\\mathcal{L}$ as $(x_1,\\bar x_1,x_2,\\ldots)$."""
    order = {lb: i for i, lb in enumerate(base_labels(n_pairs))}
    if label not in order:
        raise ValueError(f"Unknown label {label!r}")
    return order[label]


def seed_ltt_structure(n_pairs: int = 5) -> LTT:
    """
    Seed ltt structure from Prompt_extracted (Base Step): red edge $(x_1,\\bar x_5)$,
    triples $L_1=\\{\\bar x_1,\\bar x_2,x_3\\}$, $L_2=\\{x_2,x_4,x_5\\}$,
    $L_3=\\{\\bar x_3,\\bar x_4,\\bar x_5\\}$.
    """
    if n_pairs != 5:
        raise ValueError("Seed structure is defined only for 5 inverse pairs.")
    labels = base_labels(n_pairs)
    triples = (
        ("xb1", "xb2", "x3"),
        ("x2", "x4", "x5"),
        ("xb3", "xb4", "xb5"),
    )
    purple: Set[Edge] = set()
    for t in triples:
        purple |= clique_edges(t)
    return LTT(
        labels=labels,
        red_vertex="x1",
        red_edge=edge("x1", "xb5"),
        purple_edges=frozenset(purple),
        black_edges=black_edges(n_pairs),
    )


def red_or_purple_neighbors(g: LTT, v: Label) -> Set[Label]:
    """
    Neighbors of ``v`` along *colored* (red or purple) edges only; see
    Prompt_extracted Definition~\\ref{d:graph} (black edges are not ``colored'').
    """
    out: Set[Label] = set()  # Accumulate endpoints of purple or red edges incident with ``v``.
    # Walk purple edges first: each undirected purple edge contributes the opposite endpoint.
    for a, b in g.purple_edges:
        if a == v:
            out.add(b)
        elif b == v:
            out.add(a)
    ra, rb = g.red_edge  # Unpack the unique red edge (exactly two endpoints).
    if v == ra:
        out.add(rb)  # ``v`` is one endpoint of red; include the other.
    elif v == rb:
        out.add(ra)
    return out


def purple_neighbor_pair_ordered(g: LTT, d_p: Label) -> Tuple[Label, Label]:
    """
    The two vertices joined to ``d_p`` by purple edges, ordered by ``label_order_rank``.
    """
    nbrs: List[Label] = []
    # Collect both endpoints from every purple edge touching ``d_p``.
    for a, b in g.purple_edges:
        if a == d_p:
            nbrs.append(b)
        elif b == d_p:
            nbrs.append(a)
    # Prompt: order inherited from $\\mathcal{L}$ $\\cong$ ``base_labels`` enumeration order.
    ordered = sorted(nbrs, key=lambda lb: label_order_rank(lb))
    if len(ordered) != 2:
        raise ValueError(f"Expected exactly 2 purple neighbors of {d_p}, got {ordered}")
    return ordered[0], ordered[1]


def terminal_ga_step2(g: LTT, d_r: Label, d_j: Label) -> LTT:
    """
    Step 2(a) / ``(j;a)'': edge label $d_r \\to d_j\\, d_r$ (Prompt_extracted Recursive Step).

    Terminal has red vertex $d_r$, red edge $\\{d_r,\\bar{d}_j\\}$. Per Prompt_extracted Step 2,
    ``G_{j;a}`` keeps exactly the purple edges of $G$ unchanged.
    """
    new_red_e = edge(d_r, inverse_label(d_j))  # $\\{d_r,\\bar{d}_j\\}$ using inverse pairs.
    # Black pairing edges $\\{x_i,\\bar{x}_i\\}$ are unchanged from $G$.
    # ``red_vertex`` MUST be $d_r$ here so $(\\texttt{red\\_vertex})\\in(\\texttt{red\\_edge})$ holds.
    return LTT(
        labels=g.labels,
        red_vertex=d_r,
        red_edge=new_red_e,
        purple_edges=g.purple_edges,
        black_edges=g.black_edges,
    )


def terminal_gb_step2(g: LTT, d_r: Label, d_j: Label) -> LTT:
    """Step 2(b): edge label $d_j \\to d_r\\, d_j$. Here ``red edge'' $\\{d_j,\\bar{d}_r\\}$ contains $d_j$, so ``red_vertex $= d_j$'' is consistent."""
    new_red_e = edge(d_j, inverse_label(d_r))  # $\\{d_j,\\bar{d}_r\\}$.
    purp: Set[Edge] = set()
    # Purple rule part 1: $\\{d_r,d'\\}$ whenever $\\{d_j,d'\\}$ was colored (red $\\cup$ purple).
    for d_prime in red_or_purple_neighbors(g, d_j):
        purp.add(edge(d_r, d_prime))
    # Purple rule part 2: inherit purple edges not incident to $d_j$.
    for a, b in g.purple_edges:
        if a != d_j and b != d_j:
            purp.add(edge(a, b))
    return LTT(
        labels=g.labels,
        red_vertex=d_j,
        red_edge=new_red_e,
        purple_edges=frozenset(purp),
        black_edges=g.black_edges,
    )


def distinguished_exact_signatures(n_pairs: int = 5) -> FrozenSet[Tuple]:
    """Exact ``graph_signature`` tuple for every distinguished graph (cheap membership pre-filter)."""
    return frozenset(graph_signature(g) for g in generate_distinguished_ltt())


def is_admissible_ltt_structure(
    g: LTT,
    distinguished: Optional[Sequence[LTT]] = None,
) -> bool:
    """
    True iff ``g`` is ep-isomorphic to **some** distinguished admissible graph.

    After some pair-preserving relabeling that sends ``g.red_vertex`` to ``x1``, the colored graph
    (red vertex, red edge, purple multiset, black multiset) must coincide with **some**
    distinguished representative. We compare ``graph_signature(relabeled)`` to distinguished
    signatures rather than ``LTT`` dataclass equality: ``relabel_graph`` keeps vertex images in the
    **source** ``labels`` tuple order, while distinguished graphs store ``labels = base_labels()``,
    so identical colored graphs can still fail ``==`` despite matching edges.
    """
    graphs = distinguished if distinguished is not None else get_distinguished_ltt_list()
    admissible_sigs = frozenset(graph_signature(d) for d in graphs)
    for mapping in all_pair_preserving_permutations():
        if mapping[g.red_vertex] != "x1":
            continue
        relabeled = relabel_graph(g, mapping)
        if graph_signature(relabeled) in admissible_sigs:
            return True
    return False


def step2_terminals(
    g: LTT,
    distinguished: Optional[Sequence[LTT]] = None,
) -> List[Tuple[str, str, LTT, bool]]:
    """
    Apply Prompt_extracted Step $2$ to ``g``. Returns tuples
    ``(variant, edge_label_tex, terminal_graph, in_PLTT)`` in fixed order
    ``G_{1;a}, G_{1;b}, G_{2;a}, G_{2;b}``.
    ``in_PLTT`` holds after ``Remove $\\ldots$ not in $\\mathrm{PLTT}$``.
    Pass ``distinguished=None`` (default) to reuse the cached distinguished list + index internally.
    """
    d_r = g.red_vertex  # Unique red-colored vertex label of the input graph $G$.
    ra, rb = g.red_edge  # Endpoints $\\{v_r,v_p\\}$ of the oriented red edge.
    d_p = rb if d_r == ra else ra  # Purple endpoint ($v_p$): opposite $d_r$ along the red edge.

    d1, d2 = purple_neighbor_pair_ordered(g, d_p)  # $(d_1,d_2)$ adjacent to $d_p$ via purple only.
    out: List[Tuple[str, str, LTT, bool]] = []

    graphs = distinguished if distinguished is not None else get_distinguished_ltt_list()
    admissible_sigs = frozenset(graph_signature(d) for d in graphs)

    def in_pltt(h: LTT) -> bool:
        """True if some relabeling (fixing red at ``x1``) yields a distinguished ``graph_signature``."""
        for mapping in all_pair_preserving_permutations():
            if mapping[h.red_vertex] != "x1":
                continue
            relabeled = relabel_graph(h, mapping)
            if graph_signature(relabeled) in admissible_sigs:
                return True
        return False

    # Build each $G_{j;a}$, $G_{j;b}$ for $j\\in\\{1,2\\}$.
    for j, d_j in enumerate((d1, d2), start=1):
        ga = terminal_ga_step2(g, d_r, d_j)
        gb = terminal_gb_step2(g, d_r, d_j)
        out.append(
            (
                f"G_{j};a",
                rf"{d_r} \to {d_j}\,{d_r}",
                ga,
                in_pltt(ga),
            )
        )
        out.append(
            (
                f"G_{j};b",
                rf"{d_j} \to {d_r}\,{d_j}",
                gb,
                in_pltt(gb),
            )
        )
    return out
