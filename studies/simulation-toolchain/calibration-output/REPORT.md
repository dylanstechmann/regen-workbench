# Perfusion calibration analysis

Input SHA-256: `0878d191bc76b93435b2e5a337fd62f9cb3c641d0ce25ca6fef0034d6dc7a030`

Density used: 1 mg/µL. Startup interval discarded: 0 s. Outlier method: iqr.

| Target (µL/min) | Runs | Mean measured (µL/min) | Error (%) | Repeat SD (µL/min) | 95% run-bootstrap interval (µL/min) |
|---:|---:|---:|---:|---:|---:|
| 25.000 | 5 | 23.238 | -7.05 | 0.100 | [23.151, 23.309] |
| 50.000 | 5 | 46.476 | -7.05 | 0.399 | [46.184, 46.807] |
| 100.000 | 5 | 92.855 | -7.15 | 0.572 | [92.427, 93.315] |

## Measurement-system uncertainty

Budget status: not_provided. Input SHA-256: `not supplied`.
Component contributions are separate from run-bootstrap intervals. The combined value is a standard uncertainty, not a 95% interval.

| Target (µL/min) | density | balance_gain | balance_slope_drift | evaporation_rate | timing_scale | Combined standard uncertainty (µL/min) | Status | Unquantified |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 25.000 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | density, balance_gain, balance_slope_drift, evaporation_rate, timing_scale |
| 50.000 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | density, balance_gain, balance_slope_drift, evaporation_rate, timing_scale |
| 100.000 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | density, balance_gain, balance_slope_drift, evaporation_rate, timing_scale |

## Flow after available corrections

Uncorrected measured flow remains in the main summary above. This table applies only source-linked corrections marked `measured`.

| Target (µL/min) | Mean after available corrections (µL/min) | Correction status | 95% run-bootstrap interval after corrections (µL/min) |
|---:|---:|---|---:|
| 25.000 | 23.238 | none_available | [23.156, 23.309] |
| 50.000 | 46.476 | none_available | [46.184, 46.814] |
| 100.000 | 92.855 | none_available | [92.427, 93.315] |

## Run diagnostics

- synthetic-100-0: outlier_readings_detected(3)
- synthetic-100-1: no diagnostic flags
- synthetic-100-2: outlier_readings_detected(1)
- synthetic-100-3: no diagnostic flags
- synthetic-100-4: outlier_readings_detected(1)
- synthetic-25-0: outlier_readings_detected(1)
- synthetic-25-1: no diagnostic flags
- synthetic-25-2: no diagnostic flags
- synthetic-25-3: no diagnostic flags
- synthetic-25-4: outlier_readings_detected(1)
- synthetic-50-0: no diagnostic flags
- synthetic-50-1: outlier_readings_detected(2)
- synthetic-50-2: no diagnostic flags
- synthetic-50-3: outlier_readings_detected(3)
- synthetic-50-4: outlier_readings_detected(1)

## Interpretation

- Offline research analysis. No hardware commands are generated.
- This report alone is not a physical pump calibration or acceptance decision.
- Intervals resample independent run slopes, not serially correlated readings.
- Fewer than three runs: no interval. Small repeat counts give unstable intervals.
- The run-bootstrap interval excludes density, balance, evaporation and timing uncertainty.
- The optional uncertainty budget applies only source-linked corrections that are explicitly marked measured.
- Correlated uncertainty components require covariance propagation; this tool only combines components declared independent.
- Retained droplets, collection losses and other unlisted effects are not quantified.
- R-squared <0.95 and >20% half-run drift are diagnostic flags, not acceptance standards.
- IQR and Grubbs outlier flags do not alter regression weights; Grubbs' independent-normal assumptions may not hold for correlated linear-fit residuals.
- Flagged runs remain in summaries; inspect them before interpreting mean flow.
