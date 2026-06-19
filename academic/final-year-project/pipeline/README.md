# Final-year project pipeline

This folder is the portfolio version of the code I authored for my undergraduate final-year project. The code was designed externally and mirrored into the secure research environment for runs. This repository keeps the real pipeline structure visible while replacing private run roots, account-specific paths and restricted inputs with placeholders.

## What is included

- `src/build_features.py`: participant-level cohort, HES, ICD/OPCS and observability feature construction.
- `src/build_features_execute_and_audit.py`: execution wrapper and integrity audit for a dated run folder.
- `src/feature_engineering_execute_and_audit_driver.py`: notebook-style driver preserving the staged execution narrative.
- `src/train_models.py`: LR/RF/NN model training, train/test splitting, threshold handling, metrics, curves and feature-effect outputs.
- `src/raw_icd_signalling_pipeline.py`: exploratory raw ICD signal-discovery branch with fold-local screening and grouped-code modelling.
- `src/eda_plots.py`: EDA plots for feature-matrix and missingness review.
- `src/export_bundle_filter.py`: export-bundle filtering and figure/table preparation logic used around released outputs.
- `config/`: feature-family, ICD grouping, investigation-control, recency, screening and preprocessing policies.
- `notebooks/export_bundle_filter_notebook_cells.md`: notebook-cell record for the export-bundle workflow.

## Expected inputs

The scripts expect a run folder with dated cohort and hospital episode files using the same broad contract as the project run:

- cohort table with `participant_id`, sequencing/index timing fields and target labels.
- admitted care, outpatient and emergency-care tables with participant IDs, dates and diagnosis/procedure fields.
- config files from `config/` to define feature groups, recency policies, target profiles and preprocessing rules.

Use `--run-root`, `--run-dir`, `--cohort-csv`, `--hes-apc-csv`, `--hes-op-csv`, `--hes-ae-csv` or equivalent CLI arguments to point at local placeholder files. Do not hard-code personal paths or restricted data locations.

## Typical review commands

```bash
python src/build_features.py \
  --cohort-csv data/example_run/cohort_basic_with_haplotype_YYYY-MM-DD.csv \
  --hes-apc-csv data/example_run/hes_apc_censored_YYYY-MM-DD.csv \
  --hes-op-csv data/example_run/hes_op_censored_YYYY-MM-DD.csv \
  --hes-ae-csv data/example_run/hes_ae_censored_YYYY-MM-DD.csv \
  --out-dir output/features

python src/build_features_execute_and_audit.py \
  --run-root data/example_run \
  --stamp YYYY-MM-DD

python src/train_models.py \
  --run-root data/example_run \
  --model-type lr \
  --feature-profile icd_relevant_only \
  --target-col promoter_carrier

python src/raw_icd_signalling_pipeline.py \
  --investigation-id raw_icd_homozygous_vs_noncarrier_signal_v1 \
  --force-run-dir output/signalling
```

## Method flow

1. Load and align cohort plus hospital episode tables.
2. Build temporal, service-mix, ICD, OPCS, burden-domain, recency and observability features.
3. Write a raw governed feature matrix plus preprocessing contract and feature metadata.
4. Audit feature integrity, capture missingness, dictionary and diagnosis-code coverage checks.
5. Select target profile, cohort filter and feature family profile from config.
6. Split train/test, fit preprocessing on training data only and train LR/RF/NN baselines.
7. Export metrics, threshold sweeps, predictions, feature effects and model manifests.
8. Run optional raw ICD signal discovery and approved figure/table preparation workflows.

## What is not included

This folder does not include private data, participant-level rows, exported result tables, account-specific run roots, access material or private file-system paths. The code and config are here so a technical reviewer can see the actual authored workflow and its modelling decisions.
