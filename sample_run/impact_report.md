# Randomized-Holdout Impact Analysis Report

## Experiment: `exp_dialect_boost_2026`

### Executive Summary
This report presents the causal impact evaluation of the OTT Dialect Agent recommendations using a randomized holdout design (**Intention-To-Treat** analysis).

---

## 1. Experimental Design & Sample Sizes

- **Unit of Randomization**: `viewer_id`
- **Primary Methodology**: `Intention-To-Treat (ITT)`

| Group | Sample Size (N) | Success Count | Conversion Rate (%) |
|---|---|---|---|
| **Treatment (Assigned to Agent)** | 2 | 0 | 0.00% |
| **Control (Holdout)** | 1 | 0 | 0.00% |

---

## 2. Causal Impact Metrics

- **Absolute Percentage-Point Difference**: **`+0.00 pp`**
- **Relative Lift**: **`+0.00%`**
- **95% Confidence Interval**: `[+0.00 pp, +0.00 pp]`
- **Z-statistic**: `0.0`
- **P-value**: `1.0` (Statistically Significant: **False**)

---

## 3. Methodological Rigor & Selection Bias Explanation

> **Methodological Note on Selection Bias**:
> Naive comparison of served viewers vs non-served viewers suffers from selection bias, because the agent selectively targets active, highly-engaged viewers. The randomized Intention-To-Treat (ITT) holdout comparison isolates true causal impact.
> Comparing only served viewers against unserved viewers introduces severe selection bias. The randomized ITT holdout design guarantees unconfounded causal inference.
