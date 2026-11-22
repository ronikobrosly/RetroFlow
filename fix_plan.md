# Fix Plan: Clean Edges in Complex Diagrams

```
   today                              goal
   ─────                              ────
   │││││                              │ │ │
   ┴┴┼└──────┐                  ┌─────┘ │ └─────┐
   ▼─▼───┘   ▼                  ▼       ▼       ▼
```

Status: **implemented** (phases 0 to 7) on 2026-11-22. Phase 8, retiring the
classic drawer, is deliberately left open; see "Implementation notes" at the
end. Sections 1 to 9 are the original plan, written against version 0.10.1
(commit `0e516b9`), and describe the state *before* the work.

## 1. Summary

Complex diagrams are not just crowded, most of them are **wrong**: reading
the picture gives a different graph from the one that was typed in. Of 206
complex renderings tested, 28 (14%) are structurally correct and 13 (6%) are
fully clean. All 32 simple renderings are clean.

The cause is architectural, not a collection of small bugs. Each edge is
routed and painted on its own, with the character canvas as the only shared
state. Nothing gives two edges different rows, and nothing knows which lines
pass through a cell. Extra spacing does not help: doubling both spacing
options changed the number of correct diagrams from 28 to 27 out of 192.

The proposed fix is to **plan all routes first, then paint once**: allocate
ports, lanes and tracks so that unrelated edges never share a cell, and
derive every glyph from the lines that actually pass through it.

Simple diagrams are protected twice: 32 golden files pin their exact output,
and during the migration the existing renderer keeps drawing every diagram
it already draws cleanly (section 6).

Eight decisions need your input before work starts (section 8).

## 2. How "clean" is measured

New files, all under `tests/integration/`:

| File | Purpose |
|------|---------|
| `diagram_checker.py` | Reads a rendered diagram the way a person would and reports defects |
| `diagram_corpus.py` | 17 simple cases, 68 complex cases, 35 seeded random graphs |
| `test_complex_diagrams.py` | 1,053 tests: each complex rendering, one concern per test |
| `test_simple_diagram_goldens.py` | 65 tests: simple diagrams match their golden files and are clean |
| `test_diagram_checker.py` | 46 tests of the checker itself, on hand-drawn pictures |
| `diagram_scorecard.py` | Prints a clean/defect summary for the whole corpus |
| `golden/*.txt` | 32 pinned outputs |

The checker compares the canvas after boxes are drawn with the finished
canvas (both come from `generate(debug=True)`), so everything that differs
is edge drawing. It then follows the line glyphs by their arms (`┌` reaches
down and right, `┬` reaches left, right and down) and reads off which boxes
each line connects. It never looks at renderer internals, so it stays valid
through a rewrite.

| Code | Meaning | Your words |
|------|---------|------------|
| `phantom_edge` | The picture shows an edge that is not in the input | lines overlap |
| `missing_edge` | An input edge cannot be traced | lines overlap |
| `stray_line` | A line with no source box or no arrowhead | errors |
| `dangling_line` | A line glyph reaches toward nothing | errors |
| `dangling_port` | A port mark on a box with no line attached | errors |
| `floating_arrow`, `arrow_no_tail`, `arrow_hit_sideways` | Arrowhead defects | floating arrows |
| `box_missing`, `box_damaged`, `group_border_damaged` | Boxes or labels overwritten | errors |
| `adjacent_lines` (warning) | Unrelated vertical strokes in touching columns | muddled |

Commands:

```bash
uv run pytest tests/integration/test_complex_diagrams.py     # the failing suite
uv run pytest -k goldens                                     # simple-diagram guard
uv run python tests/integration/diagram_scorecard.py -v      # per-diagram summary
uv run python tests/integration/diagram_scorecard.py cicd-TB # show one diagram + issues
```

## 3. Results

Whole suite: 1,683 tests. The 630 outside `test_complex_diagrams.py` all
pass (519 that existed before, 65 golden, 46 checker). Inside it, 370 to 374
of 1,053 fail (seen over eight runs); the count moves because of the
run-to-run instability described in R6. Coverage is 94% (92% without the new tests). Ruff is clean.

| Test | Failing | Of |
|------|---------|----|
| `test_boxes_and_labels_are_intact` | 0 | 136 |
| `test_no_broken_line_ends` | 94 | 136 |
| `test_no_floating_arrowheads` | 17 | 136 |
| `test_picture_shows_exactly_the_input_edges` | 104 | 136 |
| `test_lines_are_not_crammed_together` | 85 | 206 |
| `TestRandomGraphsAreClean::test_diagram_is_correct` | 66 | 70 |
| `test_crossing_free_graphs_are_drawn_without_crossings` | 6 | 26 |
| `test_rendering_does_not_depend_on_the_hash_seed` | 1 | 1 |
| `test_rendering_is_repeatable` (same process) | 0 | 206 |

Structurally correct renderings, by kind:

| Kind | TB | LR |
|------|----|----|
| No groups | 21 of 98 | 7 of 98 |
| With groups | 0 of 5 | 0 of 5 |

Two things work well and should be kept: boxes and labels are never
damaged, and simple diagrams are clean.

### What the defects look like

Smallest failing input found: three nodes, `A -> B`, `B -> C`, `A -> C` in
LR. The skip edge has no arrowhead and joins two unrelated gaps, so the
picture also says `B -> B`.

```
┌────────┐             ┌────────┐             ┌────────┐
│   A    │──────┬─────►│   B    │──────┬─────►│   C    │░
└────────┘░     │      └────────┘░     │      └────────┘░
 ░░░░░░░░░░     │       ░░░░░░░░░░     │       ░░░░░░░░░░
                │                      │
                │                      │
                │                      │
                └──────────────────────┘
```

| Defect | Output today (long runs shortened) | From |
|--------|-------------------------------------|------|
| Skip edges fused; only one continues | `│ └└────────┐` | `skip_mixed-TB` |
| Two fan-outs fused on one row | `──┴┬┴──────┘┌┘` | `binary_tree_depth_3-TB` |
| Line through arrowheads | `▼─▼────────┘` | `microservices-TB` |
| Junction with nothing attached | `┬ ├────────┤ ┬` | `ladder_4-TB` |
| Tee that does not join its own line | `│  Hub   │──────┤─────►│ Leaf 2 │` | `fan_out_3-LR` |
| Back edge cuts the forward edge | `│ Parse  │─┘──────────►│  Save  │` | `loop_from_middle-LR` |
| Back-edge corner replaces the forward line | `└───────────┘` with `│` continuing below | `two_way_chain-TB` |
| Four lines in four touching columns | `└──┬┬┬┬───┘` then `││││` | `microservices-TB` |

## 4. Root causes

Ranked by how much of the damage each explains. Line numbers refer to
`src/retroflow/` at commit `0e516b9`.

**R1. Every edge between two layers gets the same routing row.**
`_get_safe_horizontal_y` (`edge_drawing.py:1004`) returns the middle row of
the gap for every edge leaving a layer; `_get_safe_vertical_x` (`:1034`)
does the same with the middle column in LR. Unrelated edges land on top of
each other and fuse. This is the main source of `phantom_edge` (748 across
the corpus) and `missing_edge` (494). LR is hit hardest because compact
boxes have one row, so every edge in a gap shares both its row and its
column.

**R2. Glyphs are guessed from the character already on the canvas.**
`_draw_vertical_line`, `_draw_horizontal_line` and `_set_corner`
(`edge_drawing.py:1064-1282`) look at the existing character and infer what
to write. The canvas does not record which lines pass through a cell, so
the inference is often wrong. Several places skip even that and write
unconditionally: the `fanout_junction` `┬` (`:573`, which alone accounts for
76 dangling ends), the detour corners (`:442-473`), every back-edge glyph
(`:1378-1488`, `:2166-2288`), and an LR case whose comment says another edge
will fix it up (`:1809-1817`).

**R3. Ports are allocated per feature, not per box side.** Forward exits
use `calculate_port_x` (`positioning.py:394`), back-edge exits use
`src_x + 1 + offset` (`edge_drawing.py:1374`) or `src_y + 1 + offset`
(`:2128`), back-edge entries use `tgt_y + 1 + index` (`:1349`). Nothing
stops two of them choosing the same cell, and in LR a compact box has only
one row to choose from. Port pitch also drops to one column on narrow boxes
(`positioning.py:415`), which gives `││││` and `▼▼▼`. Ports are ordered by
layer index rather than by where the other end is, which produces avoidable
crossings (`fan_out_3-TB` crosses its own edges).

**R4. Skip-layer edges have no reserved lane.** `_draw_edge` detours around
boxes with fixed offsets (`max_right_x + 2` at `edge_drawing.py:433`,
`max_bottom + 2` at `:564`). All long edges in a region pick the same
detour column, and the detour row can be another box's arrow row. All 47
`arrow_hit_sideways` and 51 `arrow_no_tail` issues are in TB; the ones
inspected by hand trace back to these detours.

**R5. Back edges are painted last, by separate code, straight onto the
canvas.** `draw_back_edges` (`edge_drawing.py:1284`) and
`draw_back_edges_horizontal` (`:2035`) do not know where forward edges ran.
The exit corner lands on a forward line, entries into one target share a
row, and the run from the margin to the target is checked for boxes but not
for lines.

**R6. Output depends on Python's per-process hash seed.** Back edges are
sorted by source layer only (`edge_drawing.py:1315`, `:2068`) from a `set`,
so ties come out in hash order. At least 23 renderings in the corpus change
between runs, including 15 of the 16 renderings of the nine-edge review
workflow. The pinned simple diagrams are not affected: each has at most one
back edge.

**R7. Layout does not account for long edges or geometry.** Layering has no
placeholder nodes for skip edges (`layout.py:146-238`), so crossing
reduction ignores them, and each layer is centered independently
(`positioning.py:161`), so children are not under their parents (the
15-node binary tree is 172 columns wide). This lengthens runs and raises
the odds of R1 collisions. It is a contributing factor, not a cause of
incorrect pictures.

**R8. Groups (experimental).** Group-aware positioning moves nodes off
their layer rows, but routing rows still come from
`calculate_layer_boundaries` (`positioning.py:243`, called at
`generator.py:274`), which ignores groups. Side-by-side edges start one
cell late (`edge_drawing.py:831`), leaving `│ A │░───►`. Lines that leave
the canvas are dropped silently (`renderer.py:111`) because canvas size is
computed from boxes only (`positioning.py:367`). The group example in the
README renders with two broken connectors today.

## 5. Proposed design: plan routes, then paint once

```
today      for each edge:  decide ──► draw          (canvas is the only memory)

proposed   ports ──► lanes and tracks ──► routes ──► wire grid ──► glyphs
           └────────── pure data, testable ───────┘
```

Five rules, each closing one root cause. Each is also directly checkable by
the test suite.

| Rule | Closes | Checked by |
|------|--------|-----------|
| 1. A glyph is computed from the arms in its cell; arms only come from route segments | R2 | `dangling_line`, `dangling_port`, arrow codes |
| 2. Two routes may run along the same cells only as a *bundle*, and a bundle is legal only if every source on it really connects to every target on it | R1 | `phantom_edge`, `missing_edge` |
| 3. One allocator per box side hands out ports for all edges touching that side | R3, R5 | `adjacent_lines`, `dangling_line` |
| 4. Every segment lies in space reserved for it; the canvas is sized from routes | R4, R8 | arrow codes, `stray_line` |
| 5. Every ordering is total and derived from input order | R6 | hash-seed test |

Components, all pure Python with no new dependencies:

- **Wire grid** (new, about 150 lines). A grid holding, per cell, a set of
  arms (up, down, left, right) and which route owns each axis. Segments are
  added to it; glyphs are looked up from arms at the end. Adding a segment
  along cells owned by a different bundle is reported as a conflict instead
  of drawn. This replaces `_draw_vertical_line`, `_draw_horizontal_line`
  and `_set_corner`.
- **Port allocator.** Collects every edge end on each box side (forward
  out, forward in, back out, back in), orders them by where the other end
  lies, and spaces them at least two cells apart. When a side is too short,
  the box grows: wider in TB, taller in LR.
- **Track allocator.** The gap between two layers is a channel. Each route
  needs one span across it. Spans that overlap get different tracks using
  the classic left-edge interval method; the gap grows by one row per extra
  track. The exit row below a box and the arrow row above a box are never
  used as tracks.
- **Lanes for long edges.** A skip edge gets a one-cell placeholder in each
  layer it passes, included in the ordering step, so it has its own column
  and crossing reduction can see it.
- **Back edges** use the same allocators: a real exit port, a lane in the
  margin, and an entry that is checked against boxes and lines.

Two hand-drawn targets, both verified clean by the checker. Box positions
are the ones the current layout already produces; only the edges differ.

TB, `A -> B`, `B -> C`, `C -> D`, `A -> C`, `A -> D`. Each skip edge has its
own port, its own track and its own lane (today this input produces 9
issues, including a lost `A -> D`):

```
┌────────┐
│   A    │░
└─┬──┬─┬─┘░
 ░│░░│░│░░░
  │  │ │
  │  │ └───────────┐
  │  └───────┐     │
  ▼          │     │
┌────────┐   │     │
│   B    │░  │     │
└───┬────┘░  │     │
 ░░░│░░░░░░  │     │
    │        │     │
    │        │     │
    │ ┌──────┘     │
    ▼ ▼            │
┌────────┐         │
│   C    │░        │
└───┬────┘░        │
 ░░░│░░░░░░        │
    │              │
    │              │
    │ ┌────────────┘
    ▼ ▼
┌────────┐
│   D    │░
└────────┘░
 ░░░░░░░░░░
```

LR, `A -> B`, `B -> C`, `A -> C`. The skip edge leaves and enters through
the bottom borders and has its own arrowhead:

```
┌────────┐             ┌────────┐             ┌────────┐
│   A    │────────────►│   B    │────────────►│   C    │░
└───┬────┘░            └────────┘░            └────────┘░
 ░░░│░░░░░░             ░░░░░░░░░░             ░░░▲░░░░░░
    │                                             │
    └─────────────────────────────────────────────┘
```

### Alternative considered: patch the existing drawer

Fixing the defects one at a time inside `edge_drawing.py` was considered and
rejected. The file is 2,288 lines of per-case branches whose correctness
depends on drawing order, and the two worst causes (R1, R2) are properties
of the whole approach, so each patch would move the collision somewhere
else. The exceptions are R6 and the off-by-one in R8, which are local and
are fixed in place in phase 0.

## 6. Protecting simple diagrams

1. **Golden files.** `tests/integration/golden/` pins 32 simple renderings
   character for character: chains, two-way fan-out and fan-in, diamond,
   small tree, three-node cycle, retry loop, self loop, multi-word and
   wrapped names, two separate chains, title, no shadow, rounded, expanded.
   Any phase that changes one of them fails CI. Add more cases to
   `SIMPLE_CASES` for anything else you want frozen.
2. **Gate during migration.** `generate()` renders with the existing drawer
   first and checks the result. If it is clean, that output is returned
   unchanged. Only otherwise is the new router used, and only if its result
   is clean. A diagram the current code draws well is therefore identical
   by construction, including diagrams nobody thought to put in the corpus.
   This needs the checker moved from `tests/` into `src/retroflow/`.
3. **Same geometry when there is no conflict.** The new router uses today's
   numbers whenever they suffice: one port sits at the center, two ports
   use the current formula, a channel with one track uses the middle row of
   the default gap. Gaps and boxes grow only when a diagram needs more.

## 7. Phases

Each phase ends with ruff clean, coverage above 90%, goldens unchanged, and
README and CLAUDE.md updated where behavior is user-visible. Sizes are
relative.

| Phase | Work | Size | Done when |
|-------|------|------|-----------|
| 0 | Stable tie-break for back edges (R6); start stacked edges on the shadow cell (R8) | S | Hash-seed test passes; failure count is the same on every run |
| 1 | Wire grid; move checker to `src/retroflow/`; gate wired in with the new path empty | M | No output changes; wire grid has unit tests |
| 2 | Router core for TB edges between neighbouring layers: ports, tracks, bundles, growing gaps and boxes | L | `-k "TB and (fan_out_ or fan_in_ or hourglass or bipartite or dense or braid or tree or ladder)"` passes |
| 3 | Lanes for skip-layer edges | M | `-k "TB and (complete_dag or skip_ or random_dag)"` passes |
| 4 | Back edges and self loops through the same allocators | M | `-k "TB and not groups"` passes |
| 5 | LR by running the same router with the axes swapped | M | `-k "not groups"` passes |
| 6 | Groups: routing space from real box rectangles, borders and titles as obstacles | M | `-k groups` passes |
| 7 | Fewer crossings and narrower diagrams: geometry-aware port order, parents over children | M | Crossing-free test passes; scorecard crossings drop |
| 8 | Retire the old drawer once the new router matches it on diagrams the old one draws cleanly | S | One renderer remains |

The scorecard should improve at every phase and never regress, because the
gate only substitutes a rendering that checks clean.

Risks:

- **Complex diagrams get larger.** Separate tracks and ports need rows and
  columns. A diagram that fuses eight lines into two rows today will need
  more rows to draw them apart.
- **A visible switch at the gate.** Adding one edge can move a diagram from
  the old drawer to the new one. Rule 3 in section 6 keeps the two close,
  but spacing can differ until phase 8.
- **Checker blind spots.** The gate and the tests share one checker. Its 46
  tests on hand-drawn pictures and the golden files limit this; sampling
  scorecard output by eye at each phase is still worthwhile.
- **Scope of phase 2.** It is the largest step. If it runs long, the gate
  means partial progress still ships safely.

## 8. Decisions needed

1. **Gate or straight replacement?** Recommended: gate through phase 7,
   then decide on phase 8 with a side-by-side comparison in hand. The
   alternative is to rely on the 32 goldens alone, which is simpler but
   protects only what is pinned.
2. **Three- and four-way fans on narrow boxes.** Today these are correct
   but crammed (`┬┬┬`, `▼▼▼`), and `fan_out_3-TB` has a needless crossing.
   Should the gate send them to the new router (they become `▼ ▼ ▼`, with
   a slightly wider box where needed), or leave them exactly as they are?
   Recommended: send them, after you have looked at before and after.
3. **Larger complex diagrams.** Is growth in exchange for separated lines
   acceptable? There is no dense alternative that stays unambiguous.
4. **Taller boxes in LR.** A compact LR box has one row, so two unrelated
   edges on one side need either a taller box or ports on the top and
   bottom borders (as in the LR target above). Recommended: top and bottom
   ports for skip and back edges, taller boxes only when that is not
   enough.
5. **Shared lines.** Keep merging edges into one trunk when it is exact, as
   LR fan-in does today (`──┤`), or give every edge its own arrowhead
   everywhere? Recommended: keep today's behavior, trunks in LR and
   separate arrowheads in TB.
6. **How to land the failing tests.** About 370 tests fail by design, and
   `publish.yml` runs the suite, so merging them to `main` as they are
   blocks releases. Recommended: keep them on the working branch for this
   plan. The alternative is to mark `test_complex_diagrams.py` as expected
   failures and remove the mark phase by phase.
7. **`router.py`.** `EdgeRouter`, `BoxInfo` and `EdgeRoute` are exported
   from `retroflow` but unused by the generator. Reuse the module for the
   new router, or leave it and add a new one? Removing the exports would be
   a breaking change.
8. **Version.** Suggested: 0.11.0 for the first release with visibly
   different complex output; the API does not change. To be confirmed at
   release time.

## 9. Noticed along the way

- The group example output in `README.md` no longer matches what the code
  produces (README shows the group stacked vertically; the code lays it out
  side by side with a broken connector).
- `uv.lock` records `retroflow 0.10.0` while `pyproject.toml` says 0.10.1,
  so every `uv run` rewrites the lockfile. That change was reverted to keep
  this work's diff to tests and this plan.
- `uv` warns that `tool.uv.dev-dependencies` is deprecated in favor of
  `dependency-groups.dev`.

## 10. Implementation notes

What was built, and where it differs from the plan above.

| Plan item | Outcome |
|-----------|---------|
| Phase 0 | Back edges are sorted with a total order (`EdgeDrawer._sort_back_edges`); side-by-side group edges start on the shadow cell |
| Phase 1 | `wire_grid.py`; checker moved to `src/retroflow/checker.py`; gate in `FlowchartGenerator.generate` |
| Phases 2 to 5 | `route_planner.py` + `channel_router.py`, planned in flow coordinates so LR is TB with the axes swapped |
| Phase 6 | Groups: members share a layer, direct lines between neighbours, titles kept clear of entering lines |
| Phase 7 | Boxes line up middle to middle, lone ports slide to straighten lines, ports are ordered by where the other end lies |
| Phase 8 | Not done. Both renderers remain; the gate decides |

Decisions from section 8, as implemented:

1. **Gate**, as recommended. Clean classic output is returned unchanged; `generator.last_renderer` says which renderer was used.
2. **Crammed fans go to the planned renderer** (a warning counts as "not clean").
3. Complex diagrams do get larger; gaps and boxes grow only as far as their lines need.
4. **LR uses top and bottom ports** for skip edges, back edges and whatever does not fit the single row of a facing side. A box only grows taller inside a group.
5. **Trunks in LR, separate arrowheads in TB**, restricted to stars (one source or one target per shared line).
6. All tests pass, so nothing needed to be marked as an expected failure.
7. `router.py` was left untouched; the new code lives in new modules.
8. The version was **not** bumped.

Differences worth knowing about:

- A same-net four-way meeting is never drawn as `┼`. It is split into two tees, because the checker (and a reader) cannot tell it from a crossing.
- Back edges in TB keep today's look (`┌───►│ box │`) while the target has a free side row, and enter through the top after that.
- In LR, arcs choose between above and below the row so that few of them interleave.
- The planned renderer falls back to the classic picture if it raises.

Results on the enlarged corpus (662 renderings, both directions): every
rendering has no errors and no warnings, both through the gate and from the
planned renderer on its own.
