r"""
Console output for Task ``Run Step 2 for the seed ltt structure'' (Prompt_extracted).

See subsection ``Step 2 (determining outgoing edges \& terminal graphs)''.
"""

from __future__ import annotations

from ltt_structures import (
    graph_signature,
    seed_ltt_structure,
    step2_terminals,
)


def main() -> None:
    seed = seed_ltt_structure()  # Concrete seed graph from the Base Step section of the prompt.
    # Step $2$ uses the cached list of $270$ distinguished graphs inside ``step2_terminals``.
    rows = step2_terminals(seed, None)

    print("Seed ltt structure G:")  # Banner for the starting graph's raw data.
    print(f"  red vertex: {seed.red_vertex}")  # Must be ``x1'' for this seed.
    print(f"  red edge: {seed.red_edge}")  # Seed uses red edge {x1, xb5} == {x_1, bar x_5}.
    print(f"  purple edges ({len(seed.purple_edges)}): {sorted(seed.purple_edges)}")  # Three $K_3$ blocks.
    print(f"  black edges ({len(seed.black_edges)}): {sorted(seed.black_edges)}")  # Five inverse pairs.
    print()

    d_r = seed.red_vertex  # Same as ``d_r'' in Step $2$ bullets.
    ra, rb = seed.red_edge  # Ordered endpoints from ``edge'' --- treat as unordered pair internally.
    d_p = rb if d_r == ra else ra  # Purple endpoint $v_p$ opposite the red vertex along the red edge.
    print(f"Step 2: d_r = {d_r}, d_p (purple endpoint of red edge) = {d_p}")
    print()

    print(
        "terminal(G) = { G_1;a, G_1;b, G_2;a, G_2;b } "
        "(PLTT membership = ep-isomorphic to some distinguished graph):"
    )
    print()

    for variant, edge_label, g, in_pltt in rows:  # Fixed order $1a,1b,2a,2b$.
        status = "kept (in PLTT)" if in_pltt else "removed (not in PLTT)"
        print(f"{variant}  directed-edge label: {edge_label}")  # TeX-like morphism label string.
        print(f"  {status}")  # Post ``Remove $\\ldots$ not in $\\mathrm{PLTT}$'' flag.
        print(f"  red vertex: {g.red_vertex}   red edge: {g.red_edge}")  # Sanity: red $\\in$ red edge.
        print(f"  purple edges ({len(g.purple_edges)}): {sorted(g.purple_edges)}")  # Terminal purple set.
        print(f"  graph_signature (exact labeled): {graph_signature(g)}")  # Stable tuple for debugging.
        print()


if __name__ == "__main__":
    main()
