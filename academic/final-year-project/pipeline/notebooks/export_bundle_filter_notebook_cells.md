# Export Bundle Filter Notebook Paste Pack

Use this file as a notebook driver surface when the export-bundle workflow needs to be run interactively.

Preparation:
- Copy `src/export_bundle_filter.py` into the same working folder as the notebook you create.
- Create a fresh Python notebook in that same folder.
- Paste the cells below into the notebook in order.

This paste pack keeps the earlier numbering from the chat:
- use `Cell 1` to `Cell 7`
- skip the old optional branch entirely
- then use `Cell 11` and `Cell 12`

Heatmaps are excluded automatically by the script. You do not need to delete them manually.

## Cell 1 (Markdown)
```md
# Export Bundle Filter

Notebook-first execution surface for the ORION export-ready bundle builder.

Current v2 policy:
- exclude weighted similarity heatmaps automatically
- keep release-ready artefacts as-is
- mask or transform only the structured artefacts that can disclose phenotype-linked small counts
- pull missing compact-primary and signalling artefacts from the original secure research environment run folders
- rerender the two observability PNGs from the original observability summary CSVs
- write to a new filtered output tree by default, not back into the original exports folder
```

## Cell 2 (Code)
```python
# Dependency bootstrap for the full workflow, including observability rerender.
# This installs missing packages only if the current notebook kernel does not already have them.

from pathlib import Path
import importlib
import subprocess
import sys

for package_name, module_name in [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("matplotlib", "matplotlib"),
]:
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

import pandas as pd

import export_bundle_filter as ebf

# Reload during iterative notebook work so edits to the .py file are picked up.
importlib.reload(ebf)
```

## Cell 3 (Markdown)
```md
## Configure paths

Fill in the run-relative paths below before running the dry-run or write cells.

- `EXPORT_ROOT` points at the current manually gathered exports folder.
- `COMPACT_PRIMARY_LRRF_RUN_DIR` points at the testing folder that contains:
  - the compact-primary LR/RF run outputs
  - the observability support files
  - the signalling run directory
- `COMPACT_PRIMARY_NN_RUN_DIR` points at the separate testing folder that contains the compact-primary NN run outputs.
- `SIGNALLING_RUN_DIR` points at the completed signalling run directory inside the LR/RF testing folder.
```

## Cell 4 (Code)
```python
# ------------------------------------------------------------------
# USER-EDITABLE PATH PLACEHOLDERS
# ------------------------------------------------------------------

EXPORT_ROOT = Path("data/example_run/exports")
FILTERED_OUTPUT_ROOT = Path("output/exports_filtered_v2")

# Original testing roots / run directories.
COMPACT_PRIMARY_LRRF_RUN_DIR = Path("data/example_run/testing_<lrrf_folder>")
COMPACT_PRIMARY_NN_RUN_DIR = Path("data/example_run/testing_<nn_folder>")
SIGNALLING_RUN_DIR = Path("data/example_run/testing_<lrrf_folder>/<signalling_run_directory>")

REPORT_JSON_PATH = FILTERED_OUTPUT_ROOT / "export_bundle_manifest.json"
REPORT_MD_PATH = FILTERED_OUTPUT_ROOT / "export_bundle_report.md"

config = ebf.FilterConfig(
    export_root=EXPORT_ROOT,
    filtered_output_root=FILTERED_OUTPUT_ROOT,
    report_json_path=REPORT_JSON_PATH,
    report_md_path=REPORT_MD_PATH,
    dry_run=True,
    overwrite_output=False,
    compact_primary_lrrf_run_dir=COMPACT_PRIMARY_LRRF_RUN_DIR,
    compact_primary_nn_run_dir=COMPACT_PRIMARY_NN_RUN_DIR,
    signalling_run_dir=SIGNALLING_RUN_DIR,
)

config
```

## Cell 5 (Code)
```python
# Scan the live export folder first.

relative_files = ems.scan_export_tree(config.export_root)
len(relative_files), relative_files[:20]
```

## Cell 6 (Code)
```python
# Build and inspect the action plan.
# This combines the current exports folder with the source run directories.
# Weighted similarity heatmaps are excluded automatically and should not appear here.

records = ems.build_action_plan(config)
plan_df = ems.action_plan_dataframe(records)
summary_df = ems.summarise_action_plan(records)

display(summary_df)
display(plan_df[["relative_path", "family", "action", "source_path", "notes"]])
```

## Cell 7 (Code)
```python
# Dry-run only.
# This writes the JSON + Markdown reports without copying, sanitising, or rerendering files.

config.dry_run = True
records = ems.build_action_plan(config)
records = ems.execute_action_plan(config, records)
payload = ems.write_all_reports(config, records)

display(ems.summarise_action_plan(records))
REPORT_JSON_PATH, REPORT_MD_PATH
```

## Cell 11 (Code)
```python
# Observability rerender preview.
# The helper resolves the original observability summary CSVs from the LR/RF testing folder automatically.

history_summary_csv, density_summary_csv = ems.resolve_observability_support_files(config)

preview_history_png = FILTERED_OUTPUT_ROOT / "cohort_observability" / "cohort_observability_history_depth_2026-03-25.png"
preview_density_png = FILTERED_OUTPUT_ROOT / "cohort_observability" / "cohort_observability_code_density_2026-03-25.png"

history_preview = ems.rerender_observability_history_depth(history_summary_csv, preview_history_png)
density_preview = ems.rerender_observability_code_density(density_summary_csv, preview_density_png)

history_preview, density_preview
```

## Cell 12 (Code)
```python
# Full write run.
# If you are replacing an older output folder and it still exists, set overwrite_output=True.

config.dry_run = False
config.overwrite_output = False

records = ems.build_action_plan(config)
records = ems.execute_action_plan(config, records)
payload = ems.write_all_reports(config, records)

display(pd.DataFrame(payload["summary"]))
FILTERED_OUTPUT_ROOT, REPORT_JSON_PATH, REPORT_MD_PATH
```

## Minimal secure research environment workflow
1. Copy `export_masking_filter.py` into the secure research environment feature-engineering folder.
2. Create a new notebook in the same folder.
3. Paste `Cell 1` to `Cell 7`, then `Cell 11`, then `Cell 12`.
4. Fill in the three source-root placeholders in `Cell 4`.
5. Run through `Cell 7` first and inspect the dry-run report.
6. Run `Cell 11` to preview the observability rerenders.
7. Run `Cell 12` to write the completed export-ready bundle.
