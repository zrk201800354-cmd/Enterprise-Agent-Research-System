# Strategy Optimization Design

## Goal

Add a safe first-pass strategy optimizer that searches deterministic strategy parameters and validates the chosen set on a holdout period. The optimizer must help improve the strategy without silently overfitting the full sample.

## Approach

Use a small grid search over:

- short moving-average window
- long moving-average window
- RSI entry ceiling
- target allocation

The optimizer splits each symbol's bars into a training segment and a test segment. It ranks candidates by training score, then reports both training and holdout test metrics for the selected parameters.

## Rules

- Do not use test-period data to choose parameters.
- Reject candidates where `short_window >= long_window`.
- Keep target allocation inside existing risk limits.
- Preserve long-only, no-live-trading behavior.
- Keep output deterministic.

## CLI

Add:

```powershell
python -m quant_agent optimize
```

The command writes:

- `logs/optimization-summary.md`
- `logs/optimization-results.json`

## Testing

Tests must cover:

- invalid candidate parameters are skipped
- data split keeps train and test periods separate
- best parameters are selected from training score
- test metrics are reported but not used for selection
- CLI optimize runs offline and writes both reports
