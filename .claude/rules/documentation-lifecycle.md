# Documentation Lifecycle

Maintain three central documents: README.md for capabilities and operations,
CONSOLIDATED_PLAN.md for execution and acceptance, and PROJECT_HISTORY.md for
completed work, decisions and verification. Update them in place; package
READMEs link to them rather than repeating status or plans.

Keep active normative sources and current contracts locally readable. A pin or
a test that requires an old filename is not by itself a reason to retain a
working-tree copy forever. For historical evidence, prefer exact Git object
verification after a tested validator migration; preserve provenance, corruption
rejection and behavioral coverage. Until that migration passes, do not bypass
the existing gate. Historical status does not describe current work.

When consolidating superseded process reports, designs, plans or analyses,
record their durable decisions and evidence in PROJECT_HISTORY.md. Preserve an
exact committed source reference for each original before removing duplicate
working-tree copies. Originals remain retrievable through Git history; never
rewrite that history or replace a historical proof with a new summary.

A detailed historical file still required by a validator stays in place. Other
unconsolidated historical material belongs under archive/ with its date and
non-authoritative status. Run the relevant policy and link/reference checks.

Before adding or retaining a document, identify the current decision, operation,
contract or regression it supports. Remove duplicate Product-only references,
obsolete instructions and prose-only test obligations when they add no current
Lab value. Record concrete policy/test migrations in the consolidated plan;
never delete a meaningful behavioral or adversarial test merely to enable cleanup.
