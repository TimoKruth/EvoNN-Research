---
document_kind: traceability
status: active
authoritative: true
installed_execution_plan: CONSOLIDATED_PLAN.md
historical_pre_bootstrap_plan_name: LAB_PLAN.md
governing_sources:
  - id: claude-spec
    path: claude-spec/
    normative_role: lab_specification
  - id: program-charter
    path: PROGRAM_CHARTER.md
    normative_role: program_boundaries
  - id: product-research-interop
    path: claudex-spec/19-research-interop.md
    normative_role: product_consumer_acceptance
interop_authorization:
  lab_producer_authorizes_product_behavior: false
  real_product_influence_requires:
    - I1
    - I2
  product_acceptance_authority: claudex-spec/19-research-interop.md
---

# Governing Source Traceability

| Governing source | Normative role | Consumer acceptance authority |
|---|---|---|
| `claude-spec/` | Complete Lab normative specification. It defines Lab architecture, scientific integrity, evidence, engineering standards, and producer obligations; it wins over `CONSOLIDATED_PLAN.md` on disagreement. | No |
| `PROGRAM_CHARTER.md` | Program boundaries, the independent Lab and Product workstreams, and the I0–I4 relationship. It does not create executable work packages. | No |
| `claudex-spec/19-research-interop.md` | Product-side authority for what may be consumed, how it is validated, and when imported research may affect Product behavior. | Yes |

## Interop Authorization Relationship

Lab producer work can establish I0 and I1 publishing/conformance evidence. Lab producer work never authorizes Product behavior. A real Lab artifact may influence Product behavior only after Lab-owned I1 and Product-owned I2 both pass; the first real crossing is then recorded as I3. Product acceptance, revalidation, adoption, and default changes remain governed by `claudex-spec/19-research-interop.md`.

## Precedence and Change Control

`claude-spec/` is normative over the Lab execution plan. `PROGRAM_CHARTER.md` sets program scope and boundaries. The Product interop chapter alone owns consumer acceptance. All three sources are pinned in `governance/authority-provenance.yaml`; changes follow `governance/SPEC_UPGRADE_PROCESS.md` and must state their traceability impact and supersession relationship.
