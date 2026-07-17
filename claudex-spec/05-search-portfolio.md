# 05 — Automatic Search Portfolio and Distinct Engines

## 1. Portfolio objective

The portfolio planner MUST maximize expected deployable utility under finite budgets, hard constraints, uncertainty, and model-origin policies. It MUST not optimize only an engine-local fitness value.

## 2. Portfolio stages

1. **Problem profiling:** task, modality, sample regime, target structure, groups, sequence lengths, feature types, deployment constraints.
2. **Capability filtering:** reject incompatible engines/models/backends before allocation.
3. **Baseline floor:** evaluate deterministic classical and simple neural baselines.
4. **Cheap probes:** small-fidelity tests across eligible strategy families.
5. **Initial allocation:** assign budget using priors plus probe evidence.
6. **Adaptive allocation:** promote, pause, or retire branches based on uncertainty-aware expected value.
7. **Transfer/synthesis:** move validated motifs, cells, backbones, weights, adapters, or candidates through declared converters.
8. **Ensembling/routing:** evaluate combinations only after member evidence qualifies them.
9. **Final candidate set:** produce feasible Pareto set and recommendation evidence.

PORT-001: The resolved plan MUST explain every material inclusion, exclusion, and allocation.  
PORT-002: Hard constraints MUST filter eligibility before ranking.  
PORT-003: The planner MUST reserve budget for strong baselines.  
PORT-004: Probe evidence MUST not be represented as full-fidelity evidence.  
PORT-005: Adaptive changes MUST be evented and budget-accounted.  
PORT-006: Expert overrides MUST be preserved exactly.

## 3. Recommendation policy artifact

Every automatic recommendation MUST reference an immutable versioned policy artifact containing:

- hard-constraint feasibility and unknown-value treatment;
- primary metric and benchmark-specific utility transformations;
- task/benchmark weights and missing-result penalties;
- uncertainty/risk treatment;
- practical-significance threshold;
- secondary preferences and trade-off weights;
- tie-breaking order;
- default behavior when no feasible candidate exists;
- explanation template/version.

Given identical frozen evidence and policy, Web, CLI, and batch reporting MUST produce the same recommendation and rationale. The policy digest is frozen in the run envelope and recorded in selected-model evidence.

## 4. Engine families

All subsections in this section are required v1 portfolio branches. Each branch MUST have at least one decision-grade qualifying workflow in `18-v1-conformance-matrix.md`, but no branch is required to support every task or modality.

### 4.1 Contender/baseline engine

Runs fixed classical, pretrained, and simple neural baselines. It establishes an external quality floor and provides normalization anchors. Baseline failure or unsupported modalities MUST be visible.

### 4.2 Family engine (Prism lineage)

Searches curated model families and their architectural/training parameters. Strengths preserved:

- content-addressed candidate specs;
- family compatibility;
- domain-aware mutation;
- multi-fidelity and promotion;
- specialist and generalist archives;
- deployment-aware objectives.

It MUST not directly average raw heterogeneous metrics; portfolio utility uses registry-defined normalized utilities.

### 4.3 Topology engine (Topograph lineage)

Searches explicit acyclic graphs, operators, connectivity, precision, sparsity, and device-aware structure.

Required invariants:

- homologous initial and structural events share innovation identity;
- speciation, if advertised, materially affects reproduction;
- graph validity is checked before compilation;
- no runtime-created unregistered fallback layers;
- crossover aligns complete genotype state;
- archives store stable candidate IDs, not population indices;
- actual parameters/model bytes are measured, not mislabeled proxies.

### 4.4 Hierarchy engine (Stratograph lineage)

Searches macro graphs over reusable micrograph/cell definitions, including cloning, specialization, sharing, and hierarchical mutation.

It MUST expose hierarchy-specific descriptors and ablations proving whether reuse or hierarchy adds value. A hierarchical label alone MUST not imply benefit.

### 4.5 Primitive/motif engine (Primordia lineage)

Searches low-level operators, motifs, and microcircuits intended primarily as priors or seeds rather than broad standalone generalists.

It MUST publish portable motif artifacts with input/output contracts, required operators, provenance, cost, confidence, and compatible target engines.

### 4.6 Pretrained/adaptation engine

Searches:

- exact base model/revision;
- tokenizer/processor;
- heads and pooling;
- frozen/unfrozen regions;
- LoRA/adapter configuration;
- quantization and precision;
- learning schedule;
- context/input policy.

Base weights and adapters form one deployable dependency set. Memory reporting MUST distinguish base weights, trainable parameters, optimizer state, activations, and peak device memory.

### 4.7 Compression/deployment engine

Searches pruning, distillation, quantization, operator substitution, width/depth reduction, and target-specific conversion under measured quality-retention and deployment constraints.

### 4.8 Ensemble/routing engine

Searches weighted voting, stacking, bagging, cascades, routers, mixture-of-experts, and modality fusion. It MUST use out-of-fold predictions for trainable combiners and MUST account for all member latency, memory, size, and external assets.

### 4.9 Cross-strategy hybrid synthesis

Builds candidates by combining typed outputs from two or more distinct strategy branches—for example a primitive-seeded topology, pretrained encoder plus evolved hierarchy, or family backbone plus evolved router. It MUST use explicit converters and produce a new candidate identity; it MUST NOT directly merge internal genomes or bypass transfer/prior accounting.

## 5. No universal genome

SEARCH-001: Each engine owns its representation and repair semantics.  
SEARCH-002: Cross-engine interchange MUST use typed candidate, motif, cell, feature, adapter, checkpoint, or prediction artifacts.  
SEARCH-003: Shared contracts MUST not constrain all engines to a lowest-common-denominator graph.  
SEARCH-004: The portfolio planner reasons over capabilities and evidence, not internal genes.

## 6. Evolutionary operator contract

Every mutation or crossover outcome MUST record:

- operator ID/version;
- parent identities;
- proposed changes;
- applied/repaired/no-op status;
- repair actions;
- resulting candidate digest;
- RNG event identity;
- compatibility changes.

Repeated no-ops MUST be measurable. Hidden fallbacks to unrelated mutations are forbidden.

## 7. Speciation and diversity

When enabled, speciation MUST influence parent selection, offspring allocation, survival, or stagnation policy. Reporting-only inferred species MUST be labeled diagnostic.

Quality-diversity MAY use novelty, MAP-Elites, MOME, or related archives, but descriptors, bins, distance metrics, update rules, and archive selection MUST be versioned. QD-adjusted fitness MUST remain separate from native quality.

## 8. Multi-objective optimization

Objectives and constraints MUST be explicit. Supported objectives include quality, calibration, latency, peak memory, parameter count, serialized size, energy proxy or measurement, training cost, robustness, fairness, novelty, and export capability.

The system MUST retain non-dominated candidate sets. Scalar recommendation is a product decision applied after feasibility and MUST preserve the Pareto evidence.

## 9. Transfer and priors

Transfer types:

- motif/primitive to topology or hierarchy;
- cell to hierarchy;
- family candidate to topology initialization;
- pretrained weights/backbone to adaptation;
- checkpoint inheritance within compatible lineages;
- teacher to distillation;
- candidate predictions to ensemble.

Every transfer MUST identify source artifact, converter, compatibility checks, inherited information, cost policy, and target effect.

Prior-cost classes:

- `external_pretraining`
- `free_prior` (allowed only for operational, not equal-compute claims)
- `reported_prior`
- `charged_prior`

Decision-grade equal-budget claims MUST use a policy that accounts for prior creation or clearly limits the claim to operational utility.

## 10. Portfolio governance

Engine implementations have portfolio statuses:

`reference | default | challenger | specialist | seed_source | experimental | archive_candidate`

Status changes MUST cite current promoted evidence generated against a compatible code range. Stale evidence MUST be marked stale automatically.
