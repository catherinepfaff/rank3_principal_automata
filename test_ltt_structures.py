import unittest

from ltt_structures import (
    LTT,
    all_pair_preserving_permutations,
    base_labels,
    black_edges,
    canonical_signature,
    clique_edges,
    edge,
    generate_distinguished_ltt,
    graph_signature,
    inverse_label,
    ltt_is_connected,
    make_label,
    parse_label,
    partitions_into_3_triples,
    relabel_graph,
    representatives_up_to_epi_isomorphism,
    seed_ltt_structure,
    step2_terminals,
)


class TestLTTStructures(unittest.TestCase):
    def test_edge(self) -> None:
        self.assertEqual(edge("xb2", "x1"), ("x1", "xb2"))

    def test_parse_make_inverse_label(self) -> None:
        self.assertEqual(parse_label("x3"), (3, False))
        self.assertEqual(parse_label("xb3"), (3, True))
        self.assertEqual(make_label(4, False), "x4")
        self.assertEqual(make_label(4, True), "xb4")
        self.assertEqual(inverse_label("x2"), "xb2")
        self.assertEqual(inverse_label("xb2"), "x2")
        with self.assertRaises(ValueError):
            parse_label("bad")

    def test_base_labels(self) -> None:
        self.assertEqual(base_labels(2), ("x1", "xb1", "x2", "xb2"))

    def test_black_edges(self) -> None:
        be = black_edges(2)
        self.assertEqual(be, {("x1", "xb1"), ("x2", "xb2")})

    def test_clique_edges(self) -> None:
        edges = clique_edges(["a", "b", "c"])
        self.assertEqual(edges, {("a", "b"), ("a", "c"), ("b", "c")})

    def test_partitions_into_3_triples(self) -> None:
        items = [f"v{i}" for i in range(9)]
        parts = list(partitions_into_3_triples(items))
        # Number of ways to partition 9 labeled items into 3 unlabeled triples:
        # 9! / ((3!)^3 * 3!) = 280
        self.assertEqual(len(parts), 280)
        for triples in parts:
            flattened = [x for t in triples for x in t]
            self.assertEqual(sorted(flattened), sorted(items))

    def test_all_pair_preserving_permutations_count(self) -> None:
        # n! * 2^n for n=3
        maps = list(all_pair_preserving_permutations(3))
        self.assertEqual(len(maps), 48)
        first = maps[0]
        self.assertEqual(set(first.keys()), set(base_labels(3)))
        self.assertEqual(len(set(first.values())), 6)

    def test_relabel_graph_and_signature(self) -> None:
        g = LTT(
            labels=("x1", "xb1", "x2", "xb2"),
            red_vertex="x1",
            red_edge=edge("x1", "x2"),
            purple_edges=frozenset({edge("xb1", "x2")}),
            black_edges=frozenset({edge("x1", "xb1"), edge("x2", "xb2")}),
        )
        mapping = {
            "x1": "x1",
            "xb1": "xb1",
            "x2": "xb2",
            "xb2": "x2",
        }
        g2 = relabel_graph(g, mapping)
        self.assertEqual(g2.red_vertex, "x1")
        self.assertEqual(g2.red_edge, edge("x1", "xb2"))
        self.assertEqual(
            graph_signature(g2),
            ("x1", ("x1", "xb2"), (("xb1", "xb2"),), (("x1", "xb1"), ("x2", "xb2"))),
        )

    def test_generate_distinguished_ltt(self) -> None:
        graphs = generate_distinguished_ltt()
        self.assertEqual(len(graphs), 270)
        for g in graphs:
            self.assertEqual(g.red_vertex, "x1")
            self.assertEqual(g.red_edge, edge("x1", "x2"))
            self.assertEqual(len(g.purple_edges), 9)  # three triangles -> 3*3 edges
            self.assertEqual(len(g.black_edges), 5)
            self.assertTrue(ltt_is_connected(g))

    def test_ltt_is_connected_excludes_disconnected_partition(self) -> None:
        # $x_2$ lies in $K_3$ on $\{x_2,\bar x_1,\bar x_2\}$; all black/purple cross
        # links to the other two triangle blocks are missing, so the graph splits.
        labels = base_labels(5)
        purple: set = set()
        for t in (("xb1", "x2", "xb2"), ("x3", "x4", "x5"), ("xb3", "xb4", "xb5")):
            purple |= clique_edges(t)
        g = LTT(
            labels=labels,
            red_vertex="x1",
            red_edge=edge("x1", "x2"),
            purple_edges=frozenset(purple),
            black_edges=black_edges(5),
        )
        self.assertFalse(ltt_is_connected(g))

    def test_canonical_signature_and_representatives(self) -> None:
        graphs = generate_distinguished_ltt()
        reps = representatives_up_to_epi_isomorphism(graphs)
        # Must be a strict quotient, non-empty and <= input size.
        self.assertGreater(len(reps), 0)
        self.assertLessEqual(len(reps), len(graphs))

        # Canonical signatures of reps are unique.
        canonical_keys = [canonical_signature(g) for g in reps]
        self.assertEqual(len(canonical_keys), len(set(canonical_keys)))

        # Every original graph lands in one representative class.
        rep_keys = set(canonical_keys)
        for g in graphs:
            self.assertIn(canonical_signature(g), rep_keys)

    def test_step2_seed_red_vertex_incident_to_red_edge(self) -> None:
        """Every Step 2 terminal must satisfy Definition structure graph: red vertex lies on red edge."""
        seed = seed_ltt_structure()
        for _, _, g, _ in step2_terminals(seed, None):
            ra, rb = g.red_edge
            self.assertIn(g.red_vertex, (ra, rb))

    def test_step2_seed_pltt_membership(self) -> None:
        """Seed Step 2 PLTT flags: all four terminals should remain in PLTT."""
        seed = seed_ltt_structure()
        by_variant = {variant: pl for variant, _, _, pl in step2_terminals(seed, None)}
        self.assertTrue(by_variant["G_1;a"])
        self.assertTrue(by_variant["G_1;b"])
        self.assertTrue(by_variant["G_2;a"])
        self.assertTrue(by_variant["G_2;b"])


if __name__ == "__main__":
    unittest.main()
