"""Read-only, ledger-derived diagnostics; no learned model or engine imports."""
from collections import defaultdict, Counter


def research_diagnostics(attempts):
    groups = defaultdict(list)
    for row in attempts:
        groups[row['benchmark_id']].append(row)
    panels = {}
    for benchmark, rows in groups.items():
        successful = [row for row in rows if row['status'] == 'ok']
        histories = defaultdict(list)
        for row in successful:
            histories[row['genome_id']].append(row)
        revisits = []
        for identity, history in sorted(histories.items()):
            for earlier, later in zip(history, history[1:]):
                revisits.append(dict(candidate=identity, before=earlier['outcome_id'], after=later['outcome_id'],
                                     quality_change=later['score']-earlier['score'],
                                     allocated_before=earlier['allocated_epochs'], allocated_after=later['allocated_epochs']))
        # Ranking reversals require two distinct genotypes each observed screened
        # and at full allocation. No extrapolation for architectures never revisited.
        paired = {}
        for identity, history in histories.items():
            low = next((row for row in history if row['screen_epoch_reduction'] > 0), None)
            full = next((row for row in history if row['screen_epoch_reduction'] == 0 and low is not None and rows.index(row) > rows.index(low)), None)
            if low is not None and full is not None:
                paired[identity] = (low['score'], full['score'])
        comparable, reversals = 0, 0
        values = list(paired.values())
        for i, a in enumerate(values):
            for b in values[i+1:]:
                if a[0] != b[0] and a[1] != b[1]:
                    comparable += 1
                    reversals += int((a[0]-b[0])*(a[1]-b[1]) < 0)
        panels[benchmark] = dict(
            attempts=len(rows), successful=len(successful), failed=len(rows)-len(successful),
            fits_charged=sum(row['charged'] for row in rows),
            optimizer_updates=sum(row.get('updates', 0) for row in rows),
            measured_train_seconds=sum(row.get('train_seconds', 0) for row in rows),
            selection_counts=dict(Counter(row['research_evaluation']['lane'] for row in rows)),
            distinct_genotypes=len(histories),
            macro_sizes=sorted({len(row['genome']['macro_nodes']) for row in rows}),
            widths=sorted({node['width'] for row in rows for cell in row['genome']['cells'] for node in cell['nodes']}),
            primitives=sorted({node['primitive'] for row in rows for cell in row['genome']['cells'] for node in cell['nodes']}),
            revisits=revisits,
            screening_rank_check=dict(paired_genotypes=len(paired), comparable_pairs=comparable, reversals=reversals,
                                      status='available' if comparable else 'insufficient_revisited_pairs'),
        )
    return dict(schema_version=2, benchmarks=panels, scientific_qualification='pending',
                interpretation='Descriptive charged-work and revisitation diagnostics. Repeated fits may inherit weights; rank changes do not isolate training duration or prove superiority.')
