# 19 — Product Interop: Exporting To The claudex-spec Product

The claudex-spec product ("the Product") is a parallel development track
that consumes this platform's discoveries. This chapter defines what the
research platform ("the Lab") owes that relationship. It changes nothing
about how research is done here — it makes the research *consumable*.

The consumer-side acceptance rules live in
`claudex-spec/19-research-interop.md`; that document governs what the
Product accepts. This one governs what the Lab publishes and how it stays
stable enough to be worth consuming.

## The Deal In One Paragraph

The Lab moves fast and optimizes for comparative insight; the Product moves
deliberately and optimizes for validated deployable models. The Lab
publishes versioned, self-describing artifacts and dossiers; the Product
revalidates everything under its own harness and reports back what survived.
Neither imports the other's code. Lab evidence is never product proof — and
Product rejections are never Lab failures; both are information.

## What The Lab Publishes

Five export surfaces, all of which already exist in this spec — the interop
requirement is only that they stay **versioned, digest-addressed, and
append-only**:

1. **Benchmark identities and packs** (ch. 02). The canonical benchmark ID
   registry is append-only and published; an ID never changes meaning.
   Pack YAMLs carry their ladder tier and admission status so the Product
   can treat Lab admission as advisory input.
2. **Seed artifacts and motif banks** (chs. 10–11). The seed artifact
   contract of chapter 11 is the shared minimum schema. Schema changes are
   semantically versioned with a changelog; fields are never silently
   repurposed.
3. **Mechanism dossiers** (new, small). When a research finding stabilizes
   — the kind of thing that today lands in `RESEARCH_NOTES.md` — the owning
   engine SHOULD distill it into a short dossier: claim, expected effect
   and scope, evidence registry labels, known risks and negative results.
   This is a lightweight extraction from artifacts that already exist, not
   a new research burden. Negative results (e.g. "the broad exploitation
   slot was tried and removed") MUST be included; they are the cheapest
   thing the Lab can export and the most expensive thing the Product can
   rediscover.
4. **Promoted evidence** (ch. 12). Registry rows already carry git commit,
   labels, lane states, and checksums — exactly the provenance the Product
   needs to consume them as foreign priors. No change; keep the registry
   validation green.
5. **Engine graduation candidates** (ch. 12 portfolio rules). When an
   engine's portfolio status stabilizes, its role label, capability
   summary, and evidence bundle form the graduation dossier the Product
   needs to evaluate adoption as a new strategy branch.

## Stability Obligations

- **Contract versioning.** The export contract (`manifest.json` /
  `results.json` / `summary.json`), the seed artifact schema, and the
  canonical ID registry carry semantic versions. Breaking changes bump the
  major version and are announced in the changelog — the Product's
  staleness rules key off exactly this.
- **Commit provenance everywhere.** Anything published for consumption
  states the Lab spec version and git commit it was produced from (the
  evidence registry already enforces this; extend the habit to seed
  artifacts and dossiers).
- **No compatibility freeze.** The Lab is free to evolve internals at any
  speed. The obligation is honesty at the boundary, not stability of the
  internals: publish the version, let the Product's converters and
  staleness rules do their job.

## What The Lab Accepts Back

The reverse channel feeds the `HARD_REMAINDER` backlog process (ch. 18
planning hierarchy) as ordinary backlog input with a `product-feedback`
origin marker:

- **Defect findings** — the Product's engineering rigor (atomic
  checkpoints, RNG stream models, measurement honesty) will surface bugs in
  shared mechanisms; treat these as high-value bug reports.
- **Backend qualification data** — operator parity and determinism results
  from the Product's qualification matrix strengthen chapter 13's
  portability truth without the Lab rerunning them.
- **Failed-adoption reports** — when a Lab win does not survive
  product-grade revalidation (governed splits, physical test isolation),
  that is a scientific signal about the original result: possibly a leakage
  artifact, a benchmark-specific effect, or a fairness-model gap. Failed
  adoptions SHOULD be triaged like any other evidence, and MAY justify
  revisiting the original claim's decision label.

## Rules Of Engagement

- Lab internals never bend to Product convenience: search-core distinctness
  (ch. 01) outranks interop symmetry. If the Product needs something the
  Lab's science doesn't, the answer is a converter on the Product side, not
  a Lab redesign.
- The Lab makes no claims in Product vocabulary and vice versa: "adopted by
  the Product" is not a Lab evidence category, and Lab lane states are not
  Product evidence grades. The mapping table in the Product's chapter 19 is
  the only translation layer.
- Both directions run on dossiers, not meetings: if an idea is worth
  transferring, it is worth the ten lines of provenance that make the
  transfer auditable.

## Why This Is Cheap

Nearly everything above already exists in this spec: canonical IDs (ch. 02),
the seed contract (ch. 11), the evidence registry with commit provenance
(ch. 12), portfolio role labels (ch. 12), and the research-notes discipline
(ch. 18). The only genuinely new artifact is the mechanism dossier, and it
is a distillation of notes the Lab already writes. Interop, done this way,
is a publishing discipline — not a second project.
