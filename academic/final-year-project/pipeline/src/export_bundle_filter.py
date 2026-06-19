"""Portfolio copy of the authored final-year project pipeline.

Private run roots and account-specific paths have been replaced with placeholders.
The method structure is preserved for technical review.
"""

# %% Imports and runtime helpers

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import json
import math
import re
import shutil

import pandas as pd


# %% Policy constants

MASK_TOKEN = "<5"
SUPPRESSED_TOKEN = "masked"

# These fragments are treated as small-cell sensitive counts when they appear in
# exported structured artefacts.
SENSITIVE_COUNT_PATTERNS = (
    "participants_with_",
    "record_history_ge_",
    "code_history_ge_",
    "diag_token_count",
    "unique_icd_code_count",
    "token_count_in_window",
    "code_event_in_window",
    "participant_support_n",
    "event_occurrence_n",
)

# These are count-like fields that are explicitly *not* masked by default
# because the current instruction treats them as operational rather than
# phenotypic.
NON_PHENOTYPIC_COUNT_COLUMNS = {
    "n_train",
    "n_test",
    "n_runs",
    "selected_predictor_count",
    "selected_predictor_count_median",
    "selected_predictor_count_iqr",
}

NON_PHENOTYPIC_COUNT_PATTERNS = (
    "rows_input",
    "rows_output",
    "rows_removed",
    "epv_",
    "seed",
)

SIGNALLING_HEATMAP_RE = re.compile(r"weighted_similarity_heatmap_.*\.png$")
SIGNALLING_SEED_DIR_RE = re.compile(r"seed_?(\d+)$")


# %% Optional dependency helpers

def load_plotting_dependencies() -> tuple[Any, Any]:
    """
    Import plotting dependencies only when they are actually needed.

    Why this is lazy:
    - The non-observability export workflow should still run in secure research environment notebook
      environments that do not yet have matplotlib available.
    - Only the observability rerender step requires matplotlib/numpy.
    """

    try:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Observability rerender requires optional plotting dependencies. "
            "Install/import matplotlib and numpy in the secure research environment notebook kernel "
            "before running the observability preview/full-write cells."
        ) from exc

    return plt, np


# %% Configuration models

@dataclass
class FilterConfig:
    """
    Main runtime configuration for notebook use.

    Important:
    - `export_root` points at the live export bundle you want to inspect.
    - `filtered_output_root` should point at a new sibling/output folder.
    - The three run-directory roots should point at the original secure research environment testing
      folders so missing artefacts can be pulled into the completed export pack.
    """

    export_root: Path
    filtered_output_root: Path
    report_json_path: Path
    report_md_path: Path
    dry_run: bool = True
    overwrite_output: bool = False
    compact_primary_lrrf_run_dir: Path | None = None
    compact_primary_nn_run_dir: Path | None = None
    signalling_run_dir: Path | None = None


@dataclass
class ActionRecord:
    """
    One planned or executed action for one exported file.
    """

    relative_path: str
    family: str
    action: str
    destination_path: str
    source_path: str = ""
    source_dependencies: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    status: str = "planned"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# %% Path and validation helpers

def ensure_parent(path: Path) -> None:
    """
    Create the parent directory for a file if it does not already exist.
    """

    path.parent.mkdir(parents=True, exist_ok=True)


def require_existing_directory(path: Path, label: str) -> None:
    """
    Fail early with a clear message if an expected directory does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"{label} is not a directory: {path}")


def require_existing_file(path: Path | None, label: str) -> Path:
    """
    Resolve a required source file path, which may still be unset in the config.
    """

    if path is None:
        raise FileNotFoundError(
            f"{label} has not been configured. Fill in the notebook placeholder first."
        )
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")
    return path


def first_matching_file(root: Path, pattern: str, label: str) -> Path:
    """
    Resolve the first matching file under a root with a clear failure mode.
    """

    require_existing_directory(root, label)
    matches = sorted(root.rglob(pattern))
    files = [path for path in matches if path.is_file()]
    if not files:
        raise FileNotFoundError(f"{label} not found under {root} with pattern {pattern!r}")
    return files[0]


def all_matching_files(root: Path, pattern: str) -> list[Path]:
    """
    Return all matching files under a root.
    """

    require_existing_directory(root, f"Search root for {pattern}")
    return sorted([path for path in root.rglob(pattern) if path.is_file()])


def should_overwrite_output(config: FilterConfig) -> bool:
    """
    Whether the filtered output root may be cleared/reused in write mode.
    """

    return bool(config.overwrite_output)


# %% File-family classification

def classify_export_file(relative_path: PurePosixPath) -> tuple[str, str, list[str]]:
    """
    Classify one relative export path into:
    - family
    - action
    - notes

    Current action classes:
    - pass
    - sanitize_csv
    - sanitize_json
    - rerender_observability
    """

    rel_text = relative_path.as_posix()
    name = relative_path.name
    notes: list[str] = []

    if SIGNALLING_HEATMAP_RE.match(name):
        notes.append("Weighted similarity heatmaps are intentionally excluded from the export-ready bundle.")
        return "excluded_heatmap_png", "exclude", notes

    if rel_text == "cohort_observability/cohort_observability_history_depth_2026-03-25.png":
        notes.append("Observability history-depth plot is rerendered from masked source summary CSVs.")
        return "observability_history_depth_png", "rerender_observability", notes

    if rel_text == "cohort_observability/cohort_observability_code_density_2026-03-25.png":
        notes.append("Observability code-density plot is rerendered from masked source summary CSVs.")
        return "observability_code_density_png", "rerender_observability", notes

    if rel_text == "cohort_observability/cohort_observability_history_depth_summary_2026-03-25.csv":
        notes.append("Observability history-depth summary requires small-cell masking and paired-percentage suppression.")
        return "observability_history_summary_csv", "sanitize_csv", notes

    if rel_text == "cohort_observability/cohort_observability_window_density_summary_2026-03-25.csv":
        notes.append("Observability window-density summary requires small-cell masking and paired-percentage suppression.")
        return "observability_window_density_summary_csv", "sanitize_csv", notes

    if rel_text == "cohort_observability/cohort_observability_manifest_2026-03-25.json":
        notes.append("Observability manifest is approved to copy as-is.")
        return "observability_manifest_json", "pass", notes

    if rel_text.startswith("final_branch/") and name.startswith("model_run_interpretation_summary_") and name.endswith(".csv"):
        notes.append("Compact-primary interpretation summary is approved to copy as-is.")
        return "compact_primary_interpretation_summary_csv", "pass", notes

    if rel_text.startswith("final_branch/") and name.startswith("model_run_interpretation_seed_detail_") and name.endswith(".csv"):
        notes.append("Compact-primary seed detail requires class-distribution masking only if small cells are present.")
        return "compact_primary_interpretation_seed_detail_csv", "sanitize_csv", notes

    if rel_text.startswith("final_branch/traceability/") and name.startswith("model_metrics_") and name.endswith(".json"):
        notes.append("Compact-primary metrics JSON is exported in filtered form without unsafe confusion-count blocks.")
        return "compact_primary_model_metrics_json", "sanitize_json", notes

    if rel_text.startswith("final_branch/traceability/") and name.endswith(".json"):
        notes.append("Compact-primary traceability JSON is approved to copy as-is.")
        return "compact_primary_traceability_json", "pass", notes

    if rel_text.startswith("final_branch/traceability/") and name.endswith(".csv"):
        notes.append("Compact-primary traceability CSV is approved to copy as-is.")
        return "compact_primary_traceability_csv", "pass", notes

    if rel_text.startswith("signalling/") and name in {
        "summary_metrics_by_seed.csv",
    }:
        notes.append("Per-seed signalling summary requires class-distribution masking only if small cells are present.")
        return "signalling_summary_by_seed_csv", "sanitize_csv", notes

    if rel_text == "signalling/summary_metrics_aggregate.csv":
        notes.append("Aggregate signalling summary is approved to copy as-is.")
        return "signalling_summary_aggregate_csv", "pass", notes

    if rel_text in {
        "signalling/best_seed_appendix_summary.csv",
        "signalling/README_run_summary.md",
        "signalling/run_manifest.json",
    }:
        notes.append("Signalling root summary artefact is approved to copy as-is.")
        return "signalling_root_summary_artifact", "pass", notes

    if rel_text == "signalling/all_groups_long.csv":
        notes.append("Root group table requires masking of low support counts.")
        return "signalling_all_groups_csv", "sanitize_csv", notes

    if rel_text == "signalling/all_codes_long.csv":
        notes.append("Root code table requires dropping contingency-cell columns and masking low support counts.")
        return "signalling_all_codes_csv", "sanitize_csv", notes

    if rel_text.startswith("signalling/seed") and name == "group_definition_table.csv":
        notes.append("Per-seed group-definition table requires masking of low support counts.")
        return "signalling_group_definition_csv", "sanitize_csv", notes

    if rel_text.startswith("signalling/seed") and name == "support_threshold_tuning.csv":
        notes.append("Per-seed support-threshold tuning table is approved to copy as-is.")
        return "signalling_support_tuning_csv", "pass", notes

    if rel_text.startswith("signalling/seed") and name == "code_to_group_mapping.csv":
        notes.append("Per-seed code-to-group mapping table is approved to copy as-is.")
        return "signalling_code_to_group_mapping_csv", "pass", notes

    if rel_text.startswith("final_branch/") and name.endswith(".png"):
        notes.append("Compact-primary ROC/PR curves are passed through unchanged under the current export rule.")
        return "compact_primary_curve_png", "pass", notes

    if rel_text.startswith("signalling/seed") and name in {
        "roc_curves.png",
        "pr_curves.png",
        "calibration_curves.png",
        "support_score_histogram.png",
        "support_threshold_tuning.png",
        "top_phi_lollipop.png",
    }:
        notes.append("Signalling figure is approved to copy as-is under the current export rule.")
        return "signalling_safe_png", "pass", notes

    notes.append("No explicit masking or transformation is required under the current export rule.")
    return "unclassified_export", "pass", notes


# %% CSV masking helpers

def is_non_phenotypic_count_column(column_name: str) -> bool:
    """
    Return True if a count-like column is operational and should not be masked
    in the current export policy.
    """

    if column_name in NON_PHENOTYPIC_COUNT_COLUMNS:
        return True
    return any(fragment in column_name for fragment in NON_PHENOTYPIC_COUNT_PATTERNS)


def is_sensitive_count_column(column_name: str) -> bool:
    """
    Return True if a column name looks like a small-cell-sensitive count field.
    """

    if is_non_phenotypic_count_column(column_name):
        return False
    return any(fragment in column_name for fragment in SENSITIVE_COUNT_PATTERNS)


def parse_mapping_text(value: Any) -> dict[str, Any] | None:
    """
    Parse a JSON-like mapping stored as text.
    """

    if value is None:
        return None
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if text in {"", "nan", "<NA>", "None"}:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def mapping_has_small_count(mapping: dict[str, Any] | None) -> bool:
    """
    Whether any value in a parsed mapping is an integer count below five.
    """

    if not mapping:
        return False
    for value in mapping.values():
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(numeric):
            continue
        if float(numeric).is_integer() and 0 <= int(numeric) < 5:
            return True
    return False


def mask_small_numeric_value(value: Any) -> Any:
    """
    Mask an exact numeric count if it is between 0 and 4 inclusive.
    """

    try:
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    except Exception:
        return value

    if pd.isna(numeric):
        return value
    if float(numeric).is_integer() and 0 <= int(numeric) < 5:
        return MASK_TOKEN
    return value


def sanitize_csv_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply generic small-cell masking rules to a structured export DataFrame.

    Current behavior:
    - Only mask exact low counts in sensitive count columns.
    - Leave operational counts untouched.
    - If a sensitive count column is masked, mask the paired percentage column
      with the same prefix when present to avoid easy reverse calculation.
    """

    cleaned = df.copy()
    modified_columns: list[str] = []
    secondary_suppressed_columns: list[str] = []

    for column in cleaned.columns:
        if not is_sensitive_count_column(column):
            continue

        original_series = cleaned[column].copy()
        cleaned[column] = cleaned[column].map(mask_small_numeric_value)

        if not cleaned[column].equals(original_series):
            modified_columns.append(column)

            pct_column = f"{column}_pct"
            if pct_column in cleaned.columns:
                cleaned[pct_column] = SUPPRESSED_TOKEN
                secondary_suppressed_columns.append(pct_column)

    details = {
        "modified_columns": modified_columns,
        "secondary_suppressed_columns": secondary_suppressed_columns,
        "row_count": int(len(cleaned)),
        "column_count": int(len(cleaned.columns)),
    }
    return cleaned, details


def sanitize_class_distribution_fields(
    df: pd.DataFrame,
    mapping_columns: list[str],
    paired_prevalence_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Suppress class-distribution and paired prevalence fields when any class
    count in the mapping falls below five.
    """

    cleaned = df.copy()
    modified_columns: list[str] = []
    prevalence_columns = paired_prevalence_columns or []

    for column in mapping_columns:
        if column not in cleaned.columns:
            continue
        mask_rows = cleaned[column].map(lambda value: mapping_has_small_count(parse_mapping_text(value)))
        if bool(mask_rows.any()):
            cleaned.loc[mask_rows, column] = SUPPRESSED_TOKEN
            modified_columns.append(column)
            for prevalence_column in prevalence_columns:
                if prevalence_column in cleaned.columns:
                    cleaned.loc[mask_rows, prevalence_column] = SUPPRESSED_TOKEN
                    modified_columns.append(prevalence_column)

    details = {
        "modified_columns": sorted(set(modified_columns)),
        "row_count": int(len(cleaned)),
        "column_count": int(len(cleaned.columns)),
    }
    return cleaned, details


def sanitize_group_support_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Mask low support counts in grouped signalling tables.
    """

    cleaned = df.copy()
    modified_columns: list[str] = []
    for column in ("participant_support_n_train",):
        if column in cleaned.columns:
            original = cleaned[column].copy()
            cleaned[column] = cleaned[column].map(mask_small_numeric_value)
            if not cleaned[column].equals(original):
                modified_columns.append(column)
    return cleaned, {
        "modified_columns": modified_columns,
        "row_count": int(len(cleaned)),
        "column_count": int(len(cleaned.columns)),
    }


def sanitize_observability_history_summary_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply schema-aware masking to the observability history-depth summary.

    Why this is custom:
    - The history-depth CSV mixes true participant counts with paired percentage
      columns and non-count summary statistics.
    - Generic substring matching is too blunt here because `_pct` columns and
      descriptive statistics should not be treated as raw counts.
    """

    cleaned = df.copy()
    modified_columns: list[str] = []
    suppressed_pct_columns: list[str] = []

    count_columns = [
        "participants_total",
        "participants_with_sequencing_date",
        "participants_with_any_preseq_record",
        "participants_with_any_preseq_code_event",
    ]
    count_columns.extend(
        [
            column
            for column in cleaned.columns
            if (
                (column.startswith("record_history_ge_") or column.startswith("code_history_ge_"))
                and not column.endswith("_pct")
            )
        ]
    )

    percentage_columns = [column for column in cleaned.columns if column.endswith("_pct")]
    suppress_all_pct_rows = pd.Series(False, index=cleaned.index)

    for column in count_columns:
        if column not in cleaned.columns:
            continue
        original = cleaned[column].copy()
        cleaned[column] = cleaned[column].map(mask_small_numeric_value)
        changed_rows = cleaned[column] != original
        if bool(changed_rows.fillna(False).any()):
            modified_columns.append(column)
            if column in {"participants_total", "participants_with_sequencing_date"}:
                suppress_all_pct_rows = suppress_all_pct_rows | changed_rows.fillna(False)

            pct_column = f"{column}_pct"
            if pct_column in cleaned.columns:
                cleaned[pct_column] = cleaned[pct_column].astype("object")
                cleaned.loc[changed_rows.fillna(False), pct_column] = SUPPRESSED_TOKEN
                suppressed_pct_columns.append(pct_column)

    if bool(suppress_all_pct_rows.any()):
        for pct_column in percentage_columns:
            cleaned[pct_column] = cleaned[pct_column].astype("object")
            cleaned.loc[suppress_all_pct_rows, pct_column] = SUPPRESSED_TOKEN
            suppressed_pct_columns.append(pct_column)

    return cleaned, {
        "modified_columns": sorted(set(modified_columns)),
        "secondary_suppressed_columns": sorted(set(suppressed_pct_columns)),
        "row_count": int(len(cleaned)),
        "column_count": int(len(cleaned.columns)),
    }


def sanitize_observability_window_density_summary_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply schema-aware masking to the observability window-density summary.

    Important:
    - Median/p25/p75 token/code statistics are descriptive summaries, not
      participant counts, so they must not be masked simply because the values
      are numerically below five.
    - Only the true participant-count columns and their paired percentages are
      masked/suppressed.
    """

    cleaned = df.copy()
    modified_columns: list[str] = []
    suppressed_pct_columns: list[str] = []

    count_columns = [
        "participants_total",
        "participants_with_sequencing_date",
        "participants_with_any_code_event_in_window",
    ]
    percentage_columns = [column for column in cleaned.columns if column.endswith("_pct")]
    suppress_all_pct_rows = pd.Series(False, index=cleaned.index)

    for column in count_columns:
        if column not in cleaned.columns:
            continue
        original = cleaned[column].copy()
        cleaned[column] = cleaned[column].map(mask_small_numeric_value)
        changed_rows = cleaned[column] != original
        if bool(changed_rows.fillna(False).any()):
            modified_columns.append(column)
            if column in {"participants_total", "participants_with_sequencing_date"}:
                suppress_all_pct_rows = suppress_all_pct_rows | changed_rows.fillna(False)

            pct_column = f"{column}_pct"
            if pct_column in cleaned.columns:
                cleaned[pct_column] = cleaned[pct_column].astype("object")
                cleaned.loc[changed_rows.fillna(False), pct_column] = SUPPRESSED_TOKEN
                suppressed_pct_columns.append(pct_column)

    if bool(suppress_all_pct_rows.any()):
        for pct_column in percentage_columns:
            cleaned[pct_column] = cleaned[pct_column].astype("object")
            cleaned.loc[suppress_all_pct_rows, pct_column] = SUPPRESSED_TOKEN
            suppressed_pct_columns.append(pct_column)

    return cleaned, {
        "modified_columns": sorted(set(modified_columns)),
        "secondary_suppressed_columns": sorted(set(suppressed_pct_columns)),
        "row_count": int(len(cleaned)),
        "column_count": int(len(cleaned.columns)),
    }


def sanitize_signalling_all_codes_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Drop explicit phenotype contingency-cell counts and mask low support counts.
    """

    cleaned = df.copy()
    removed_columns: list[str] = []
    for column in (
        "a_present_target1",
        "b_present_target0",
        "c_absent_target1",
        "d_absent_target0",
    ):
        if column in cleaned.columns:
            cleaned = cleaned.drop(columns=[column])
            removed_columns.append(column)

    masked_columns: list[str] = []
    for column in (
        "participant_support_n_train",
        "participant_support_n_stage_a_global",
        "event_occurrence_n_stage_a_global",
    ):
        if column in cleaned.columns:
            original = cleaned[column].copy()
            cleaned[column] = cleaned[column].map(mask_small_numeric_value)
            if not cleaned[column].equals(original):
                masked_columns.append(column)

    return cleaned, {
        "removed_columns": removed_columns,
        "masked_columns": masked_columns,
        "row_count": int(len(cleaned)),
        "column_count": int(len(cleaned.columns)),
    }


def sanitize_model_metrics_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Remove or suppress compact-primary JSON fields that could disclose
    threshold-derived small phenotype counts.
    """

    cleaned = json.loads(json.dumps(payload))
    removed_blocks: list[str] = []
    modified_fields: list[str] = []

    split_summary = cleaned.get("split_summary", {})
    if isinstance(split_summary, dict):
        for field in ("class_dist_train", "class_dist_test", "prevalence_train", "prevalence_test"):
            if field in split_summary:
                split_summary[field] = SUPPRESSED_TOKEN
                modified_fields.append(f"split_summary.{field}")

    metrics = cleaned.get("metrics", {})
    if isinstance(metrics, dict) and "confusion_matrix" in metrics:
        metrics["confusion_matrix"] = SUPPRESSED_TOKEN
        modified_fields.append("metrics.confusion_matrix")
        removed_blocks.append("explicit_confusion_counts")

    return cleaned, {
        "removed_blocks": removed_blocks,
        "modified_fields": modified_fields,
    }


# %% Observability-safe rerender helpers

WINDOW_RE = re.compile(r"(record_history_ge_|code_history_ge_)(\d+)y$")


def infer_windows_from_history_summary(df: pd.DataFrame) -> list[int]:
    """
    Infer available lookback windows from the source summary column names.
    """

    windows: set[int] = set()
    for column in df.columns:
        match = WINDOW_RE.match(column)
        if match:
            windows.add(int(match.group(2)))
    return sorted(windows)


def safe_pct_point(count_value: Any, pct_value: Any) -> float | None:
    """
    Keep a plotted percentage only when the underlying exact count is >= 5.
    """

    count_numeric = pd.to_numeric(pd.Series([count_value]), errors="coerce").iloc[0]
    pct_numeric = pd.to_numeric(pd.Series([pct_value]), errors="coerce").iloc[0]
    if pd.isna(count_numeric) or pd.isna(pct_numeric):
        return None
    if int(count_numeric) < 5:
        return None
    return float(pct_numeric) * 100.0


def rerender_observability_history_depth(
    history_summary_csv: Path,
    output_png: Path,
) -> dict[str, Any]:
    """
    Build a conservative, masked observability history-depth figure.

    Safety choices:
    - Use only the `all` stratum.
    - Plot percentages only when the underlying supporting count is >= 5.
    - Suppress low-count source-specific points rather than attempting to
      visually blur already-exported rasters.
    """

    plt, np = load_plotting_dependencies()
    summary_df = pd.read_csv(history_summary_csv)
    windows = infer_windows_from_history_summary(summary_df)

    all_rows = summary_df.loc[summary_df["stratum"] == "all"].copy()
    if all_rows.empty:
        raise ValueError("Observability history summary does not contain stratum='all'.")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    any_row = all_rows.loc[all_rows["source_table"] == "any"]
    if any_row.empty:
        axes[0].text(0.5, 0.5, "Any-source summary missing.", ha="center", va="center")
        axes[0].axis("off")
    else:
        any_row = any_row.iloc[0]
        record_points = [
            safe_pct_point(any_row.get(f"record_history_ge_{window}y"), any_row.get(f"record_history_ge_{window}y_pct"))
            for window in windows
        ]
        code_points = [
            safe_pct_point(any_row.get(f"code_history_ge_{window}y"), any_row.get(f"code_history_ge_{window}y_pct"))
            for window in windows
        ]

        axes[0].plot(windows, record_points, marker="o", label="Any-source record history")
        axes[0].plot(windows, code_points, marker="o", label="Any-source code history")
        axes[0].set_title("Any-source observed history depth")
        axes[0].set_xlabel("Years before sequencing")
        axes[0].set_ylabel("% participants with observed history >= window")
        axes[0].set_xticks(windows)
        axes[0].set_ylim(bottom=0)
        axes[0].legend()

    panel_b = all_rows.loc[all_rows["source_table"].isin(["hes_apc", "hes_op", "hes_ae"])].copy()
    sources = ["hes_apc", "hes_op", "hes_ae"]
    positions = np.arange(len(windows))
    bar_width = 0.25

    if panel_b.empty:
        axes[1].text(0.5, 0.5, "Source-specific summary missing.", ha="center", va="center")
        axes[1].axis("off")
    else:
        for idx, source_name in enumerate(sources):
            row = panel_b.loc[panel_b["source_table"] == source_name]
            values: list[float] = []
            if row.empty:
                values = [np.nan for _ in windows]
            else:
                row = row.iloc[0]
                values = [
                    safe_pct_point(row.get(f"code_history_ge_{window}y"), row.get(f"code_history_ge_{window}y_pct"))
                    for window in windows
                ]
                values = [np.nan if value is None else value for value in values]

            offsets = positions + ((idx - 1) * bar_width)
            axes[1].bar(offsets, values, width=bar_width, label=source_name)

        axes[1].set_title("Source-specific code-history depth")
        axes[1].set_xlabel("Years before sequencing")
        axes[1].set_ylabel("% participants with code history >= window")
        axes[1].set_xticks(positions)
        axes[1].set_xticklabels([str(window) for window in windows])
        axes[1].set_ylim(bottom=0)
        axes[1].legend()
        axes[1].text(
            0.02,
            0.98,
            "Cells with underlying counts <5 suppressed.",
            transform=axes[1].transAxes,
            va="top",
            fontsize=9,
        )

    fig.tight_layout()
    ensure_parent(output_png)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)

    return {
        "windows": windows,
        "source_csv": str(history_summary_csv),
        "output_png": str(output_png),
        "note": "Source-specific points with underlying counts <5 were suppressed.",
    }


def rerender_observability_code_density(
    window_density_summary_csv: Path,
    output_png: Path,
) -> dict[str, Any]:
    """
    Build a conservative, summary-based observability code-density figure.

    Safety choices:
    - Use summary statistics only, not participant-level histograms.
    - Restrict to the `all` stratum and `any` source table.
    - Plot medians and IQR bands by window.
    """

    plt, _np = load_plotting_dependencies()
    density_df = pd.read_csv(window_density_summary_csv)
    plot_df = density_df.loc[
        (density_df["stratum"] == "all")
        & (density_df["source_table"] == "any")
        & (density_df["window_years"].astype(str) != "all_preseq")
    ].copy()

    if plot_df.empty:
        raise ValueError("Observability window density summary does not contain usable all/any rows.")

    plot_df["window_years_num"] = pd.to_numeric(plot_df["window_years"], errors="coerce")
    plot_df = plot_df.sort_values("window_years_num").reset_index(drop=True)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    x = plot_df["window_years_num"].astype(float)

    diag_median = pd.to_numeric(plot_df["median_diag_token_count_in_window"], errors="coerce")
    diag_p25 = pd.to_numeric(plot_df["p25_diag_token_count_in_window"], errors="coerce")
    diag_p75 = pd.to_numeric(plot_df["p75_diag_token_count_in_window"], errors="coerce")
    axes[0].plot(x, diag_median, marker="o", color="#4C78A8")
    axes[0].fill_between(x, diag_p25, diag_p75, color="#4C78A8", alpha=0.20)
    axes[0].set_title("Median diagnostic token count by window")
    axes[0].set_xlabel("Years before sequencing")
    axes[0].set_ylabel("Median tokens")
    axes[0].set_xticks(x.tolist())
    axes[0].set_ylim(bottom=0)

    unique_median = pd.to_numeric(plot_df["median_unique_icd_code_count_in_window"], errors="coerce")
    unique_p25 = pd.to_numeric(plot_df["p25_unique_icd_code_count_in_window"], errors="coerce")
    unique_p75 = pd.to_numeric(plot_df["p75_unique_icd_code_count_in_window"], errors="coerce")
    axes[1].plot(x, unique_median, marker="o", color="#54A24B")
    axes[1].fill_between(x, unique_p25, unique_p75, color="#54A24B", alpha=0.20)
    axes[1].set_title("Median unique ICD codes by window")
    axes[1].set_xlabel("Years before sequencing")
    axes[1].set_ylabel("Median unique codes")
    axes[1].set_xticks(x.tolist())
    axes[1].set_ylim(bottom=0)

    safe_proportion: list[float | None] = []
    for _, row in plot_df.iterrows():
        safe_proportion.append(
            safe_pct_point(
                row.get("participants_with_any_code_event_in_window"),
                row.get("participants_with_any_code_event_in_window_pct"),
            )
        )
    axes[2].plot(x, safe_proportion, marker="o", color="#F58518")
    axes[2].set_title("Participants with any code event by window")
    axes[2].set_xlabel("Years before sequencing")
    axes[2].set_ylabel("% participants")
    axes[2].set_xticks(x.tolist())
    axes[2].set_ylim(0, 105)
    axes[2].text(
        0.02,
        0.92,
        "Points with underlying counts <5 suppressed.",
        transform=axes[2].transAxes,
        va="top",
        fontsize=9,
    )

    fig.tight_layout()
    ensure_parent(output_png)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)

    return {
        "source_csv": str(window_density_summary_csv),
        "output_png": str(output_png),
        "note": "Participant histograms were replaced with summary-based window plots.",
    }


# %% Export-tree scanning and action planning

def scan_export_tree(export_root: Path) -> list[PurePosixPath]:
    """
    Recursively list files under the export root and return paths relative to it.
    """

    require_existing_directory(export_root, "Export root")
    relative_files: list[PurePosixPath] = []
    for path in sorted(export_root.rglob("*")):
        if path.is_file():
            relative_files.append(PurePosixPath(path.relative_to(export_root).as_posix()))
    return relative_files


def signalling_seed_output_dir(source_seed_dir: Path) -> Path:
    """
    Map source seed folder names like `seed_42` to export folder names `seed42`.
    """

    match = SIGNALLING_SEED_DIR_RE.match(source_seed_dir.name)
    if match:
        return Path(f"signalling/seed{int(match.group(1))}")
    return Path("signalling") / source_seed_dir.name


def infer_compact_traceability_output_path(source_path: Path, run_family: str) -> Path:
    """
    Place compact-primary traceability files in a dedicated subfolder to avoid
    collisions between the LR/RF and NN run directories.
    """

    return Path("final_branch") / "traceability" / run_family / source_path.name


def build_additional_records(
    config: FilterConfig,
    existing_relative_paths: set[str],
) -> list[ActionRecord]:
    """
    Build records for source artefacts that are missing from the current export
    tree but are needed for the complete export-ready bundle.
    """

    records: list[ActionRecord] = []

    def add_record(source_path: Path, relative_path: Path, note: str = "") -> None:
        rel_text = relative_path.as_posix()
        if rel_text in existing_relative_paths:
            return
        family, action, notes = classify_export_file(PurePosixPath(rel_text))
        if action == "exclude":
            return
        if note:
            notes.append(note)
        records.append(
            ActionRecord(
                relative_path=rel_text,
                family=family,
                action=action,
                destination_path=str(config.filtered_output_root / relative_path),
                source_path=str(source_path),
                source_dependencies=[str(source_path)],
                notes=notes,
            )
        )

    def add_globbed_compact_files(run_dir: Path | None, run_family: str) -> None:
        if run_dir is None:
            return
        require_existing_directory(run_dir, f"Compact-primary {run_family} run directory")
        for pattern in (
            "model_metrics_*.json",
            "model_curves_*.csv",
            "model_threshold_sweep_*.csv",
            "model_preprocessing_artifacts_*.json",
            "model_feature_effects_*.csv",
            "model_run_manifest_*.json",
            "model_metrics_seed_aggregate_*.csv",
        ):
            for source_path in all_matching_files(run_dir, pattern):
                relative_path = infer_compact_traceability_output_path(source_path, run_family)
                add_record(source_path, relative_path, note=f"Pulled from compact-primary {run_family} source run directory.")

    add_globbed_compact_files(config.compact_primary_lrrf_run_dir, "lrrf")
    add_globbed_compact_files(config.compact_primary_nn_run_dir, "nn")

    if config.compact_primary_lrrf_run_dir is not None:
        obs_root = config.compact_primary_lrrf_run_dir / "cohort_observability"
        if obs_root.exists():
            for name in (
                "cohort_observability_history_depth_summary_2026-03-25.csv",
                "cohort_observability_window_density_summary_2026-03-25.csv",
                "cohort_observability_manifest_2026-03-25.json",
            ):
                source_path = obs_root / name
                if source_path.exists():
                    add_record(
                        source_path,
                        Path("cohort_observability") / name,
                        note="Pulled from compact-primary LR/RF observability support folder.",
                    )

    if config.signalling_run_dir is not None:
        require_existing_directory(config.signalling_run_dir, "Signalling run directory")
        for name in (
            "best_seed_appendix_summary.csv",
            "all_groups_long.csv",
            "all_codes_long.csv",
            "README_run_summary.md",
            "run_manifest.json",
        ):
            source_path = config.signalling_run_dir / name
            if source_path.exists():
                add_record(source_path, Path("signalling") / name, note="Pulled from signalling root summary pack.")

        for seed_dir in sorted([path for path in config.signalling_run_dir.iterdir() if path.is_dir() and SIGNALLING_SEED_DIR_RE.match(path.name)]):
            output_seed_dir = signalling_seed_output_dir(seed_dir)
            for name in (
                "support_threshold_tuning.csv",
                "group_definition_table.csv",
                "code_to_group_mapping.csv",
            ):
                source_path = seed_dir / name
                if source_path.exists():
                    add_record(source_path, output_seed_dir / name, note="Pulled from signalling seed folder.")

    return records


def build_action_plan(config: FilterConfig) -> list[ActionRecord]:
    """
    Build the planned action list for all files present in the live export tree.
    """

    records: list[ActionRecord] = []
    existing_relative_paths: set[str] = set()
    for relative_path in scan_export_tree(config.export_root):
        family, action, notes = classify_export_file(relative_path)
        if action == "exclude":
            continue
        destination_path = config.filtered_output_root / Path(relative_path.as_posix())
        source_dependencies: list[str] = []
        existing_relative_paths.add(relative_path.as_posix())

        if family == "observability_history_depth_png":
            source_dependencies.append(str((config.compact_primary_lrrf_run_dir or Path("<FILL_ME>")) / "cohort_observability"))
        elif family == "observability_code_density_png":
            source_dependencies.append(str((config.compact_primary_lrrf_run_dir or Path("<FILL_ME>")) / "cohort_observability"))

        records.append(
            ActionRecord(
                relative_path=relative_path.as_posix(),
                family=family,
                action=action,
                destination_path=str(destination_path),
                source_path=str(config.export_root / Path(relative_path.as_posix())),
                source_dependencies=source_dependencies,
                notes=notes,
            )
        )

    records.extend(build_additional_records(config, existing_relative_paths))
    return sorted(records, key=lambda record: record.relative_path)


def action_plan_dataframe(records: list[ActionRecord]) -> pd.DataFrame:
    """
    Convert records into a DataFrame for notebook display.
    """

    return pd.DataFrame([record.to_dict() for record in records])


def summarise_action_plan(records: list[ActionRecord]) -> pd.DataFrame:
    """
    Produce a compact action summary table for notebook use.
    """

    if not records:
        return pd.DataFrame(columns=["action", "file_count"])
    df = action_plan_dataframe(records)
    return (
        df.groupby("action", dropna=False)
        .size()
        .reset_index(name="file_count")
        .sort_values(["action"])
        .reset_index(drop=True)
    )


# %% Plan/report writers

def write_json_report(payload: dict[str, Any], output_path: Path) -> None:
    """
    Write a JSON report payload.
    """

    ensure_parent(output_path)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown_report(records: list[ActionRecord], config: FilterConfig, output_path: Path) -> None:
    """
    Write a human-readable Markdown report for the export masking run.
    """

    summary_df = summarise_action_plan(records)
    lines = [
        "# Export Masking Filter Report",
        "",
        "## Run configuration",
        "",
        f"- export root: `{config.export_root}`",
        f"- filtered output root: `{config.filtered_output_root}`",
        f"- dry run: `{config.dry_run}`",
        f"- compact-primary LR/RF run dir: `{config.compact_primary_lrrf_run_dir}`",
        f"- compact-primary NN run dir: `{config.compact_primary_nn_run_dir}`",
        f"- signalling run dir: `{config.signalling_run_dir}`",
        "",
        "## Action summary",
        "",
    ]

    if summary_df.empty:
        lines.append("- No files were discovered under the export root.")
    else:
        for row in summary_df.itertuples(index=False):
            lines.append(f"- `{row.action}`: {int(row.file_count)} file(s)")

    lines.extend(
        [
            "",
            "## File-by-file plan",
            "",
        ]
    )

    for record in records:
        lines.append(f"- `{record.relative_path}`")
        lines.append(f"  - family: `{record.family}`")
        lines.append(f"  - action: `{record.action}`")
        lines.append(f"  - status: `{record.status}`")
        if record.source_dependencies:
            lines.append(f"  - source dependencies: `{', '.join(record.source_dependencies)}`")
        if record.notes:
            lines.append(f"  - notes: {' '.join(record.notes)}")
        if record.details:
            lines.append(f"  - details: `{json.dumps(record.details, sort_keys=True)}`")

    ensure_parent(output_path)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# %% Execution helpers

def prepare_output_root(config: FilterConfig) -> None:
    """
    Create or validate the filtered output root before a write run.
    """

    if config.dry_run:
        return

    if config.filtered_output_root.exists():
        if not should_overwrite_output(config):
            raise FileExistsError(
                "Filtered output root already exists. Set overwrite_output=True or choose a new path."
            )
        shutil.rmtree(config.filtered_output_root)

    config.filtered_output_root.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
    """
    Copy a file while ensuring the destination parent exists.

    Why this avoids a hard dependency on metadata-preserving copy:
    - Some secure research environment/shared-export filesystems allow content writes but fail on the
      metadata-copy stage used by shutil.copy2, surfacing opaque errors such as
      "Unknown error 524".
    - For this filter, preserving timestamps/ownership is not required.
      The exported file content matters; metadata fidelity does not.
    """

    ensure_parent(dst)
    try:
        shutil.copy2(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def resolve_observability_support_files(config: FilterConfig) -> tuple[Path, Path]:
    """
    Resolve the original observability summary CSVs from the compact-primary
    LR/RF testing folder.
    """

    run_dir = config.compact_primary_lrrf_run_dir
    if run_dir is None:
        raise FileNotFoundError(
            "compact_primary_lrrf_run_dir is not configured. "
            "Point it at the LR/RF testing folder before rerendering observability artefacts."
        )
    history_csv = first_matching_file(
        run_dir / "cohort_observability",
        "cohort_observability_history_depth_summary_*.csv",
        "Observability history summary CSV",
    )
    density_csv = first_matching_file(
        run_dir / "cohort_observability",
        "cohort_observability_window_density_summary_*.csv",
        "Observability window density summary CSV",
    )
    return history_csv, density_csv


def execute_action_plan(config: FilterConfig, records: list[ActionRecord]) -> list[ActionRecord]:
    """
    Execute the planned actions against the live export tree.
    """

    prepare_output_root(config)

    history_summary_csv: Path | None = None
    density_summary_csv: Path | None = None

    for record in records:
        src = Path(record.source_path) if record.source_path else (config.export_root / Path(record.relative_path))
        dst = Path(record.destination_path)

        if config.dry_run:
            record.status = "dry_run"
            continue

        if record.action == "pass":
            copy_file(src, dst)
            record.status = "copied"
            continue

        if record.action == "sanitize_csv":
            df = pd.read_csv(src)
            if record.family == "compact_primary_interpretation_seed_detail_csv":
                cleaned_df, details = sanitize_class_distribution_fields(
                    df,
                    mapping_columns=["class_dist_train", "class_dist_test"],
                    paired_prevalence_columns=["train_prevalence", "test_prevalence"],
                )
            elif record.family == "signalling_summary_by_seed_csv":
                cleaned_df, details = sanitize_class_distribution_fields(
                    df,
                    mapping_columns=["train_class_dist", "test_class_dist"],
                )
            elif record.family == "observability_history_summary_csv":
                cleaned_df, details = sanitize_observability_history_summary_dataframe(df)
            elif record.family == "observability_window_density_summary_csv":
                cleaned_df, details = sanitize_observability_window_density_summary_dataframe(df)
            elif record.family in {"signalling_all_groups_csv", "signalling_group_definition_csv"}:
                cleaned_df, details = sanitize_group_support_dataframe(df)
            elif record.family == "signalling_all_codes_csv":
                cleaned_df, details = sanitize_signalling_all_codes_dataframe(df)
            else:
                cleaned_df, details = sanitize_csv_dataframe(df)
            ensure_parent(dst)
            cleaned_df.to_csv(dst, index=False)
            record.status = "filtered_csv"
            record.details = details
            continue

        if record.action == "sanitize_json":
            payload = json.loads(src.read_text(encoding="utf-8"))
            cleaned_payload, details = sanitize_model_metrics_payload(payload)
            ensure_parent(dst)
            dst.write_text(json.dumps(cleaned_payload, indent=2), encoding="utf-8")
            record.status = "filtered_json"
            record.details = details
            continue

        if record.family == "observability_history_depth_png":
            if history_summary_csv is None or density_summary_csv is None:
                history_summary_csv, density_summary_csv = resolve_observability_support_files(config)
            record.details = rerender_observability_history_depth(history_summary_csv, dst)
            record.status = "rerendered"
            continue

        if record.family == "observability_code_density_png":
            if history_summary_csv is None or density_summary_csv is None:
                history_summary_csv, density_summary_csv = resolve_observability_support_files(config)
            record.details = rerender_observability_code_density(density_summary_csv, dst)
            record.status = "rerendered"
            continue

        raise ValueError(f"Unhandled action record: {record}")

    return records


# %% Notebook-facing convenience entrypoints

def build_report_payload(config: FilterConfig, records: list[ActionRecord]) -> dict[str, Any]:
    """
    Build a machine-readable manifest/report payload.
    """

    return {
        "config": {
            "export_root": str(config.export_root),
            "filtered_output_root": str(config.filtered_output_root),
            "report_json_path": str(config.report_json_path),
            "report_md_path": str(config.report_md_path),
            "dry_run": bool(config.dry_run),
            "overwrite_output": bool(config.overwrite_output),
            "compact_primary_lrrf_run_dir": str(config.compact_primary_lrrf_run_dir)
            if config.compact_primary_lrrf_run_dir
            else "",
            "compact_primary_nn_run_dir": str(config.compact_primary_nn_run_dir)
            if config.compact_primary_nn_run_dir
            else "",
            "signalling_run_dir": str(config.signalling_run_dir)
            if config.signalling_run_dir
            else "",
        },
        "summary": summarise_action_plan(records).to_dict(orient="records"),
        "records": [record.to_dict() for record in records],
    }


def write_all_reports(config: FilterConfig, records: list[ActionRecord]) -> dict[str, Any]:
    """
    Write the JSON manifest and Markdown report and return the payload.
    """

    payload = build_report_payload(config, records)
    write_json_report(payload, config.report_json_path)
    write_markdown_report(records, config, config.report_md_path)
    return payload


def run_full_workflow(config: FilterConfig) -> tuple[list[ActionRecord], dict[str, Any]]:
    """
    One-call helper for notebook users who want the whole flow at once.
    """

    records = build_action_plan(config)
    execute_action_plan(config, records)
    payload = write_all_reports(config, records)
    return records, payload
