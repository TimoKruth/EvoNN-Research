# Initial JEPA qualification — 2026-09-14

The implementation executes both predictive representation learning and frozen
teacher transfer across all four actual engine compilers, with Contenders in
every arm. These pilots are exploratory validation observations, not scientific
acceptance or promotion evidence.

The NumPy smoke completed **90 worker cases / 108 fits**, covering digits, breast
cancer and diabetes with all six controls, one seed, one fixed candidate per
engine and two updates per phase. The MLX CPU pilot at producer `49a4b6a` completed
**108 worker cases / 120 fits**: 96 neural fits and 24 contender fits, with 8,704
neural optimizer updates. All 96 neural outputs passed fresh-compilation replay.
Its two tasks, one seed, two fixed candidates and 10% labeled training inputs used
32 pretraining and 64 fine-tuning steps; supervised-long used 96 supervised steps.
The raw summed worker time was approximately 163 seconds, under uncontrolled
host load. This is not a speed comparison.

The source-bound compact receipt is
[native-pilot-receipt.json](native-pilot-receipt.json). Full local artifacts are in
`.artifacts/jepa-native-pilot`, including per-fit loss curves, weights, teacher
embeddings, data lineage and all candidate comparisons. The receipt retains
result hashes and the frozen manifest identity; it is not a canonical evidence
registry entry. The later runner-only patch adds active-session source checks
and optional-MLX metadata handling; it does not change the training objective.

Mean paired **accuracy-point** change for JEPA versus supervised-long, averaging
the two fixed candidates at seed 131:

| Engine | Digits | Breast cancer |
|---|---:|---:|
| Prism | -16.67 | 0.00 |
| Topograph | -11.11 | +0.88 |
| Stratograph | -4.86 | +1.32 |
| Primordia | -18.06 | +1.32 |

These means are not independent seed replications. The image deficit is clear
within this bounded setup; the tabular improvements are small and unconfirmed.
Frozen masked teacher prediction also failed to consistently improve over
full-input distillation. All engines, all candidates and both datasets remain
in the receipt; no unfavorable result is excluded. The final JEPA mean feature
standard deviations ranged from 0.51 to 1.19 across candidates. Avoiding constant
representations is not evidence of useful semantics or broad success.

This establishes an executable experiment with genuine encoder updates,
controls, artifact transfer and honest negative observations. It does not decide
whether a larger representation, different masking/regularization, more training,
stronger datasets or architecture evolution would change the result. The root
consolidated plan retains repeated and measured-compute qualification as open work.
