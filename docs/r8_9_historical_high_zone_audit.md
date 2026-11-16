# R8.9 Historical High-Zone Audit (research-only)

Status: candidate implementation, not production deployed. Existing CEWAY v1.12.4 UI, prediction scoring, random ticket generation, cloud sync and payout code are unchanged.

## Reproducible audit

Run from repository root:

```bash
python3 -m unittest discover -s tests -p 'test_historical_high_zone_audit.py' -v
python3 -m engine.historical_high_zone_audit backend/data/dlt_history.csv --lower 29 --upper 35 --start 7001 --end 13153
python3 -m engine.historical_high_zone_audit backend/data/dlt_history.csv --lower 25 --upper 35 --start 7001 --end 13153
```

The audit validates per-draw number ranges and duplicates, reports full K=0..5 histograms, and calculates exact hypergeometric expectations plus an exact binomial upper tail for K>=3. It never modifies input data.

## Research conclusions and caveats

The Muse R8.8 report states 1014 draws, 1392 total occurrences of 29..35 in 2007..2013, and 1022 in a subsequent 1014-draw window. These are **reported observations**, not guaranteed by this repository. Check date/issue range and input source independently before comparing. A small fixed-hypothesis p-value does not establish a physical cause, data provenance, or prospective predictability. In particular, a data-selected zone/window/cutoff requires a scan-adjusted p-value, and an apparent change near issue 13100 is a candidate, not an equipment-change finding.

The Monte Carlo settlement/sedimentation method showed no demonstrated advantage over random controls (reported p=0.7174 simulated and p=0.86 historical). Keep it research-only and never promote it to production weights without independent walk-forward advantage, calibration, multiplicity control, and reproducible provenance. Physics-inspired seeded simulations are not physical entropy.

## Acceptance gates

1. Independently compare each 2007..2016 draw to official published results, preserving source URLs and mismatches.
2. Reproduce full per-draw K histogram and each individual high number.
3. Compute change-point scan p-values under the same scan procedure, not an unadjusted fixed split.
4. For proposed prediction features, run leakage-free walk-forward comparisons against uniform baseline with equal ticket budget, joint front/back combination collision statistics, and a frozen holdout.
5. Record data/code hashes, seeds, periods, and results. Do not alter production recommendation logic based on historic anomalies alone.

Official rule reference: https://m.lottery.gov.cn/ksjz/m/yxgz_dlt/
