"""Portfolio copy of the authored final-year project pipeline.

Private run roots and account-specific paths have been replaced with placeholders.
The method structure is preserved for technical review.
"""

from __future__ import annotations

# %% ---------------------------------------------------------------------------
# Imports and constants
# -----------------------------------------------------------------------------
import argparse
import json
import re
from itertools import combinations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    auc,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.inspection import permutation_importance
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold, train_test_split
from sklearn.neural_network import MLPClassifier


DEFAULT_RUN_ROOT = Path(
    "data/example_run"
)
DEFAULT_ICD_POLICY_CSV = Path(__file__).resolve().parent / "config" / "icd_group_policy.csv"
DEFAULT_FEATURE_PROFILE_CSV = Path(__file__).resolve().parent / "config" / "feature_family_profiles.csv"
DEFAULT_TARGET_PROFILE_CSV = Path(__file__).resolve().parent / "config" / "target_profile_mappings.csv"
DEFAULT_INVESTIGATION_CONTROL_CSV = (
    Path(__file__).resolve().parent / "config" / "investigation_controls.csv"
)
DEFAULT_RECENCY_POLICY_CSV = Path(__file__).resolve().parent / "config" / "recency_policy.csv"
DEFAULT_SCREENING_SCENARIO_CSV = Path(__file__).resolve().parent / "config" / "screening_scenarios.csv"
DEFAULT_PREPROCESSING_POLICY_JSON = (
    Path(__file__).resolve().parent / "config" / "preprocessing_policy_v1.json"
)
LOCKED_BASELINE_REFERENCE = "projects/fyp_orion/run_reports/20260223_first_modeling_baseline_run.md"
SIGNAL_DISCOVERY_SCREENING_MODE = "raw_icd_signal_discovery"
SIGNAL_DISCOVERY_OUTER_N_SPLITS = 5
SIGNAL_DISCOVERY_OUTER_N_REPEATS = 1
KNOWN_TARGET_COLUMNS = {
    "promoter_carrier",
    "monogenic_high",
    "modifier_only",
    "scn5a_negative",
    "burden_class",
}
LEGACY_FEATURE_SET_TO_PROFILE = {
    "icd_only_relevant": "icd_relevant_only",
    "icd_core_all": "icd_core_only",
    "full_no_opcs": "full_hes_no_opcs",
    "full_matrix": "full_hes_all",
}


def clean_optional_arg(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def clean_token(value: Any) -> str:
    if pd.isna(value):
        return ""
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() in {"nan", "<na>", "none", "null"}:
        return ""
    return cleaned


# %% ---------------------------------------------------------------------------
# STEP 0 helpers: argument parsing and run resolution
# -----------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train LR/RF/NN with unified evaluation outputs")
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT), help="Path containing testing_<n> folders")
    parser.add_argument("--run-dir", default=None, help="Specific testing_<n> folder (default: latest)")
    parser.add_argument("--stamp", default=None, help="Optional date stamp override (YYYY-MM-DD)")

    parser.add_argument("--model-type", choices=["lr", "rf", "nn"], default="lr")
    parser.add_argument("--feature-set", default="icd_only_relevant", help="Legacy feature selector alias")
    parser.add_argument("--feature-profile", default=None, help="Feature profile name from feature profile CSV")
    parser.add_argument("--feature-profile-csv", default=str(DEFAULT_FEATURE_PROFILE_CSV))
    parser.add_argument("--icd-group-policy-csv", default=str(DEFAULT_ICD_POLICY_CSV))
    parser.add_argument(
        "--preprocessing-policy-json",
        default=str(DEFAULT_PREPROCESSING_POLICY_JSON),
        help="Version-controlled preprocessing policy JSON used to validate the emitted preprocessing spec",
    )

    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--threshold", type=float, default=0.5, help="Probability threshold for class labels")
    parser.add_argument(
        "--threshold-policy",
        choices=[
            "fixed",
            "train_balanced_accuracy",
            "train_balanced_accuracy_min_specificity",
        ],
        default="train_balanced_accuracy_min_specificity",
        help="Threshold selection policy for binary models",
    )
    parser.add_argument(
        "--min-specificity-floor",
        type=float,
        default=0.55,
        help=(
            "Minimum train specificity required when using "
            "--threshold-policy train_balanced_accuracy_min_specificity"
        ),
    )
    parser.add_argument(
        "--class-weight-mode",
        choices=["none", "balanced"],
        default="none",
        help="Primary analyses default to unweighted models; balanced weighting is sensitivity-only.",
    )
    parser.add_argument(
        "--calibration-mode",
        choices=["none"],
        default="none",
        help="Calibration readiness flag; calibration is disabled by default in this refactor.",
    )
    parser.add_argument(
        "--run-tag-suffix",
        default=None,
        help="Optional run-tag suffix (for repeated seed / tuning runs)",
    )
    parser.add_argument(
        "--nn-hidden-layers",
        default="64,32",
        help="NN hidden layers as comma-separated widths (e.g. 64,32)",
    )
    parser.add_argument("--nn-alpha", type=float, default=0.0001, help="NN L2 penalty term")
    parser.add_argument("--nn-learning-rate-init", type=float, default=0.001, help="NN initial learning rate")
    parser.add_argument("--nn-max-iter", type=int, default=500, help="NN max iterations")
    parser.add_argument(
        "--nn-early-stopping",
        action="store_true",
        help="Enable NN early stopping",
    )
    parser.add_argument(
        "--nn-permutation-repeats",
        type=int,
        default=20,
        help="Permutation repeats for NN feature effects",
    )
    parser.add_argument(
        "--nn-permutation-max-rows",
        type=int,
        default=0,
        help="Optional cap on rows used for NN permutation importance (0 uses full test set)",
    )
    parser.add_argument(
        "--epv-warn-threshold",
        type=float,
        default=10.0,
        help="Warn when estimated EPV falls below this threshold",
    )
    parser.add_argument(
        "--epv-severe-threshold",
        type=float,
        default=5.0,
        help="Severe warning when estimated EPV falls below this threshold",
    )
    parser.add_argument("--target-col", default=None, help="Direct target column for training")
    parser.add_argument("--target-profile", default=None, help="Target profile from target mapping CSV")
    parser.add_argument("--target-profile-csv", default=str(DEFAULT_TARGET_PROFILE_CSV))
    parser.add_argument("--investigation-id", default=None, help="Investigation row id from controls CSV")
    parser.add_argument(
        "--investigation-control-csv",
        default=str(DEFAULT_INVESTIGATION_CONTROL_CSV),
        help="Investigation control CSV path",
    )
    parser.add_argument(
        "--recency-policy-csv",
        default=str(DEFAULT_RECENCY_POLICY_CSV),
        help="Recency policy CSV path",
    )
    parser.add_argument(
        "--screening-scenario-csv",
        default=str(DEFAULT_SCREENING_SCENARIO_CSV),
        help="Signal-discovery screening scenario CSV path",
    )
    parser.add_argument(
        "--driver-manifest",
        default=None,
        help="Optional feature_engineering_driver_manifest_<stamp>.json path for signal-discovery runs",
    )

    # parse_known_args keeps the script notebook-friendly when kernels add extra argv.
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print(f"[STEP 0] Ignoring unrecognized args: {unknown}")
    args.feature_set = clean_optional_arg(args.feature_set) or "icd_only_relevant"
    args.feature_profile = clean_optional_arg(args.feature_profile)
    args.target_col = clean_optional_arg(args.target_col)
    args.target_profile = clean_optional_arg(args.target_profile)
    args.investigation_id = clean_optional_arg(args.investigation_id)
    args.run_tag_suffix = clean_optional_arg(args.run_tag_suffix)
    args.driver_manifest = clean_optional_arg(args.driver_manifest)
    if args.investigation_id:
        if args.target_col or args.target_profile:
            raise ValueError(
                "When --investigation-id is set, do not pass --target-col/--target-profile."
            )
    elif bool(args.target_col) == bool(args.target_profile):
        raise ValueError(
            "Specify exactly one of --target-col or --target-profile when --investigation-id is not used."
        )
    return args


def print_step(step_title: str) -> None:
    bar = "=" * 88
    print(f"\n{bar}\n{step_title}\n{bar}")


def find_run_dir(run_root: Path, run_dir_arg: str | None) -> Path:
    if run_dir_arg:
        run_dir = Path(run_dir_arg)
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
        return run_dir

    run_dirs = sorted(run_root.glob("testing_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not run_dirs:
        raise FileNotFoundError(f"No testing_<n> folders found in {run_root}")
    return run_dirs[0]


def infer_stamp(run_dir: Path, stamp_arg: str | None) -> str:
    if stamp_arg:
        return stamp_arg

    meta_paths = sorted(
        run_dir.glob("features_matrix_metadata_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not meta_paths:
        raise FileNotFoundError(f"No features_matrix_metadata_*.json found in {run_dir}")

    match = re.search(r"(\d{4}-\d{2}-\d{2})", meta_paths[0].name)
    if not match:
        raise RuntimeError(f"Could not infer stamp from metadata filename: {meta_paths[0].name}")
    return match.group(1)


# %% ---------------------------------------------------------------------------
# STEP 1 helpers: metadata, raw feature loading, and preprocessing spec loading
# -----------------------------------------------------------------------------
def load_metadata(run_dir: Path, stamp: str) -> dict[str, Any]:
    meta_path = run_dir / f"features_matrix_metadata_{stamp}.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing metadata file: {meta_path}")
    return json.loads(meta_path.read_text())


def resolve_output_path(path_like: str, run_dir: Path) -> Path:
    path = Path(path_like)
    if path.exists():
        return path
    if not path.is_absolute():
        candidate = run_dir / path
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Output file not found: {path_like}")


def load_governed_feature_store(metadata: dict[str, Any], run_dir: Path) -> tuple[pd.DataFrame, Path]:
    outputs = metadata.get("outputs", {})
    raw_key = "features_matrix_raw"
    if raw_key not in outputs:
        raise KeyError(
            f"Metadata outputs missing required key: {raw_key}. Available: {sorted(outputs.keys())}"
        )
    matrix_path = resolve_output_path(outputs[raw_key], run_dir)
    matrix = pd.read_csv(matrix_path)

    required_cols = {"participant_id"}
    missing_required = required_cols.difference(matrix.columns)
    if missing_required:
        raise RuntimeError(f"Matrix missing required columns: {sorted(missing_required)}")

    return matrix, matrix_path


def load_preprocessing_spec(
    metadata: dict[str, Any],
    run_dir: Path,
    preprocessing_policy_path: Path,
) -> tuple[dict[str, Any], Path]:
    outputs = metadata.get("outputs", {})
    spec_key = "feature_preprocessing_spec"
    if spec_key not in outputs:
        raise KeyError(
            f"Metadata outputs missing required key: {spec_key}. Available: {sorted(outputs.keys())}"
        )
    spec_path = resolve_output_path(outputs[spec_key], run_dir)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if preprocessing_policy_path.exists():
        configured_policy = json.loads(preprocessing_policy_path.read_text(encoding="utf-8"))
        if configured_policy.get("policy_id") != spec.get("policy_id"):
            raise RuntimeError(
                "Preprocessing spec policy_id does not match the configured preprocessing policy JSON. "
                f"spec={spec.get('policy_id')!r} config={configured_policy.get('policy_id')!r}"
            )
    return spec, spec_path


# %% ---------------------------------------------------------------------------
# STEP 2 helpers: ICD policy and predictor subset selection
# -----------------------------------------------------------------------------
def load_icd_policy(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"ICD policy CSV not found: {path}")

    df = pd.read_csv(path)
    required = {
        "group_name",
        "group_level",
        "include_in_default_model",
        "include_in_lr_relevant_baseline",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"ICD policy missing columns: {sorted(missing)}")

    cleaned = df.copy()
    cleaned["group_name"] = cleaned["group_name"].astype(str).str.strip()
    cleaned["group_level"] = cleaned["group_level"].astype(str).str.strip().str.lower()
    cleaned["include_in_default_model"] = (
        pd.to_numeric(cleaned["include_in_default_model"], errors="coerce").fillna(0).astype(int)
    )
    cleaned["include_in_lr_relevant_baseline"] = (
        pd.to_numeric(cleaned["include_in_lr_relevant_baseline"], errors="coerce").fillna(0).astype(int)
    )
    return cleaned


def load_feature_profile_rules(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[STEP 2] Feature profile CSV not found; legacy feature_set routing only: {path}")
        return pd.DataFrame(
            columns=[
                "profile_name",
                "rule_order",
                "action",
                "selector_type",
                "selector_value",
                "description",
            ]
        )

    df = pd.read_csv(path)
    required = {"profile_name", "rule_order", "action", "selector_type", "selector_value"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Feature profile CSV missing columns: {sorted(missing)}")

    cleaned = df.copy()
    cleaned["profile_name"] = cleaned["profile_name"].astype(str).str.strip()
    cleaned["rule_order"] = pd.to_numeric(cleaned["rule_order"], errors="coerce")
    cleaned["action"] = cleaned["action"].astype(str).str.strip().str.lower()
    cleaned["selector_type"] = cleaned["selector_type"].astype(str).str.strip().str.lower()
    cleaned["selector_value"] = cleaned["selector_value"].astype(str).str.strip().replace({"": "*"})
    cleaned = cleaned[(cleaned["profile_name"] != "") & (cleaned["rule_order"].notna())].copy()
    cleaned["rule_order"] = cleaned["rule_order"].astype(int)

    invalid_actions = set(cleaned["action"].unique()).difference({"include", "exclude"})
    if invalid_actions:
        raise ValueError(f"Feature profile CSV contains invalid actions: {sorted(invalid_actions)}")
    return cleaned.sort_values(["profile_name", "rule_order"]).reset_index(drop=True)


def load_target_profile_mappings(path: Path, required: bool) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Target profile mapping CSV not found: {path}")
        return pd.DataFrame(
            columns=[
                "profile_name",
                "source_column",
                "source_value",
                "action",
                "mapped_target_value",
                "description",
            ]
        )

    df = pd.read_csv(path)
    required_cols = {
        "profile_name",
        "source_column",
        "source_value",
        "action",
        "mapped_target_value",
    }
    missing = required_cols.difference(df.columns)
    if missing:
        raise ValueError(f"Target profile mapping CSV missing columns: {sorted(missing)}")

    cleaned = df.copy()
    cleaned["profile_name"] = cleaned["profile_name"].astype(str).str.strip()
    cleaned["source_column"] = cleaned["source_column"].astype(str).str.strip()
    cleaned["action"] = cleaned["action"].astype(str).str.strip().str.lower()
    cleaned = cleaned[(cleaned["profile_name"] != "") & (cleaned["source_column"] != "")].copy()

    invalid_actions = set(cleaned["action"].unique()).difference({"map", "drop"})
    if invalid_actions:
        raise ValueError(f"Target profile mapping CSV contains invalid actions: {sorted(invalid_actions)}")
    return cleaned.reset_index(drop=True)


def load_investigation_controls(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Investigation control CSV not found: {path}")

    df = pd.read_csv(path)
    if "target_profile" not in df.columns:
        df["target_profile"] = ""
    if "screening_enabled" not in df.columns:
        df["screening_enabled"] = 0
    if "screening_scenario_id" not in df.columns:
        df["screening_scenario_id"] = ""
    if "screening_mode" not in df.columns:
        df["screening_mode"] = ""
    required = {
        "investigation_id",
        "target_name",
        "target_column",
        "target_type",
        "cohort_filter",
        "feature_profile",
        "recency_policy_id",
        "include_missingness_flags",
        "run_lr",
        "run_rf",
        "run_nn",
        "screening_enabled",
        "screening_scenario_id",
        "screening_mode",
        "notes",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Investigation control CSV missing columns: {sorted(missing)}")

    cleaned = df.copy()
    for col in (
        "investigation_id",
        "target_name",
        "target_column",
        "target_profile",
        "target_type",
        "cohort_filter",
        "feature_profile",
        "recency_policy_id",
        "screening_scenario_id",
        "screening_mode",
        "notes",
    ):
        cleaned[col] = cleaned[col].astype(str).str.strip().replace({"nan": "", "None": ""})
    for col in ("include_missingness_flags", "run_lr", "run_rf", "run_nn", "screening_enabled"):
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").fillna(0).astype(int)

    cleaned = cleaned[cleaned["investigation_id"] != ""].copy()
    cleaned["target_profile"] = cleaned["target_profile"].replace({"": np.nan}).fillna("")
    cleaned["target_column"] = cleaned["target_column"].replace({"": np.nan})
    target_name_fallback = cleaned["target_name"].replace({"": np.nan})
    direct_target_mask = cleaned["target_profile"] == ""
    cleaned.loc[direct_target_mask, "target_column"] = cleaned.loc[
        direct_target_mask, "target_column"
    ].fillna(target_name_fallback.loc[direct_target_mask])
    cleaned["target_column"] = cleaned["target_column"].fillna("")
    cleaned["cohort_filter"] = cleaned["cohort_filter"].replace({"": "all"}).str.lower()
    cleaned["target_type"] = cleaned["target_type"].str.lower()

    invalid_selector_rows = cleaned.loc[
        ((cleaned["target_column"] == "") & (cleaned["target_profile"] == ""))
        | ((cleaned["target_column"] != "") & (cleaned["target_profile"] != ""))
    ]
    if not invalid_selector_rows.empty:
        bad_ids = invalid_selector_rows["investigation_id"].astype(str).tolist()
        raise ValueError(
            "Each investigation row must define exactly one of target_column or target_profile. "
            f"Invalid investigation ids: {bad_ids}"
        )
    return cleaned.reset_index(drop=True)


def load_recency_policy(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Recency policy CSV not found: {path}")

    df = pd.read_csv(path)
    required = {
        "recency_policy_id",
        "icd_group_name",
        "include_days_since_last",
        "include_days_since_first",
        "binning_policy",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Recency policy CSV missing columns: {sorted(missing)}")

    cleaned = df.copy()
    cleaned["recency_policy_id"] = cleaned["recency_policy_id"].astype(str).str.strip()
    cleaned["icd_group_name"] = cleaned["icd_group_name"].astype(str).str.strip()
    cleaned["binning_policy"] = cleaned["binning_policy"].astype(str).str.strip()
    cleaned["include_days_since_last"] = (
        pd.to_numeric(cleaned["include_days_since_last"], errors="coerce").fillna(0).astype(int)
    )
    cleaned["include_days_since_first"] = (
        pd.to_numeric(cleaned["include_days_since_first"], errors="coerce").fillna(0).astype(int)
    )
    cleaned = cleaned[(cleaned["recency_policy_id"] != "") & (cleaned["icd_group_name"] != "")].copy()
    return cleaned.reset_index(drop=True)


def canonicalize_policy_token(value: Any) -> str:
    if pd.isna(value):
        return ""

    token = str(value).strip()
    if token == "":
        return ""

    as_num = pd.to_numeric(pd.Series([token]), errors="coerce").iloc[0]
    if not pd.isna(as_num):
        if float(as_num).is_integer():
            return str(int(as_num))
        return str(float(as_num))
    return token.lower()


def extract_icd_group_from_col(col: str) -> str | None:
    if not col.startswith("icd_grp_"):
        return None

    body = col[len("icd_grp_") :]
    markers = [
        "_ever_",
        "_count_",
        "_days_since_last_",
        "_days_since_first_",
        "_rate_per_year_",
    ]
    for marker in markers:
        idx = body.find(marker)
        if idx > 0:
            return body[:idx]
    return None


def parse_icd_recency_column(col: str) -> tuple[str, str] | None:
    if not col.startswith("icd_grp_"):
        return None
    m = re.match(r"^icd_grp_(.+?)_(days_since_last|days_since_first)_.+$", col)
    if not m:
        return None
    return m.group(1), m.group(2)


def keep_icd_cols_by_group(cols: list[str], allowed_groups: set[str]) -> list[str]:
    selected: list[str] = []
    for col in cols:
        group = extract_icd_group_from_col(col)
        if group and group in allowed_groups:
            selected.append(col)
    return selected


def resolve_feature_profile_name(feature_set: str, feature_profile: str | None) -> tuple[str, str]:
    if feature_profile:
        return feature_profile, "feature_profile_arg"
    if feature_set in LEGACY_FEATURE_SET_TO_PROFILE:
        return LEGACY_FEATURE_SET_TO_PROFILE[feature_set], "feature_set_legacy_alias"
    return feature_set, "feature_set_profile_name"


def resolve_tier12_series(matrix: pd.DataFrame) -> pd.Series:
    if "tier12_positive" in matrix.columns:
        return pd.to_numeric(matrix["tier12_positive"], errors="coerce").fillna(0).astype(int)
    if "scn5a_plp_flag" in matrix.columns:
        return pd.to_numeric(matrix["scn5a_plp_flag"], errors="coerce").fillna(0).astype(int)
    raise RuntimeError(
        "Cohort filter requires tier12 signal but neither 'tier12_positive' nor 'scn5a_plp_flag' is present."
    )


def apply_cohort_filter(matrix: pd.DataFrame, cohort_filter: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    filter_key = (cohort_filter or "all").strip().lower()
    rows_in = int(len(matrix))
    if filter_key in {"", "all"}:
        return matrix.copy(), {
            "cohort_filter": "all",
            "rows_input": rows_in,
            "rows_output": rows_in,
            "rows_removed": 0,
        }

    tier12 = resolve_tier12_series(matrix)
    if filter_key == "exclude_tier12_positive":
        keep_mask = tier12 == 0
    elif filter_key in {"tier_only", "tier12_only"}:
        keep_mask = tier12 == 1
    else:
        raise ValueError(f"Unsupported cohort_filter: {cohort_filter}")

    filtered = matrix.loc[keep_mask].copy()
    rows_out = int(len(filtered))
    return filtered, {
        "cohort_filter": filter_key,
        "rows_input": rows_in,
        "rows_output": rows_out,
        "rows_removed": int(rows_in - rows_out),
    }


def resolve_investigation_row(
    controls: pd.DataFrame,
    investigation_id: str,
    model_type: str,
) -> dict[str, Any]:
    rows = controls.loc[controls["investigation_id"] == investigation_id].copy()
    if rows.empty:
        available = sorted(controls["investigation_id"].astype(str).unique().tolist())
        raise ValueError(
            f"Investigation id '{investigation_id}' not found in controls CSV. Available: {available}"
        )
    if len(rows) > 1:
        raise ValueError(f"Investigation id '{investigation_id}' is duplicated in controls CSV.")

    row = rows.iloc[0]
    run_key = f"run_{model_type}"
    if run_key not in row.index:
        raise ValueError(f"Missing model execution column in controls CSV: {run_key}")
    if int(row.get(run_key, 0)) != 1:
        raise RuntimeError(
            f"Investigation '{investigation_id}' disables model '{model_type}' ({run_key}=0)."
        )

    feature_profile = str(row.get("feature_profile", "")).strip()
    if feature_profile == "":
        raise ValueError(f"Investigation '{investigation_id}' must define a non-empty feature_profile.")

    target_column = str(row.get("target_column", "")).strip()
    target_profile = str(row.get("target_profile", "")).strip()
    if bool(target_column) == bool(target_profile):
        raise ValueError(
            f"Investigation '{investigation_id}' must define exactly one of target_column or target_profile."
        )

    recency_policy_id = str(row.get("recency_policy_id", "")).strip()
    if recency_policy_id == "":
        recency_policy_id = "minimal"

    target_name = str(row.get("target_name", "")).strip() or target_column or target_profile
    return {
        "investigation_id": str(row.get("investigation_id")).strip(),
        "target_name": target_name,
        "target_column": target_column,
        "target_profile": target_profile,
        "target_type": str(row.get("target_type", "")).strip().lower(),
        "cohort_filter": str(row.get("cohort_filter", "all")).strip().lower() or "all",
        "feature_profile": feature_profile,
        "recency_policy_id": recency_policy_id,
        "include_missingness_flags": int(row.get("include_missingness_flags", 0)),
        "run_lr": int(row.get("run_lr", 0)),
        "run_rf": int(row.get("run_rf", 0)),
        "run_nn": int(row.get("run_nn", 0)),
        "screening_enabled": int(row.get("screening_enabled", 0)),
        "screening_scenario_id": str(row.get("screening_scenario_id", "")).strip(),
        "screening_mode": str(row.get("screening_mode", "")).strip(),
        "notes": str(row.get("notes", "")).strip(),
    }


def resolve_recency_policy_rules(
    recency_policy_df: pd.DataFrame,
    recency_policy_id: str | None,
) -> tuple[dict[str, dict[str, bool]], list[dict[str, Any]]]:
    policy_key = (recency_policy_id or "").strip()
    if policy_key == "":
        return {}, []

    rows = recency_policy_df.loc[recency_policy_df["recency_policy_id"] == policy_key].copy()
    if rows.empty:
        available = sorted(recency_policy_df["recency_policy_id"].astype(str).unique().tolist())
        raise ValueError(
            f"Recency policy id '{policy_key}' not found in recency policy CSV. Available: {available}"
        )

    rules: dict[str, dict[str, bool]] = {}
    records: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        group = str(row["icd_group_name"]).strip()
        if group == "":
            continue
        include_last = bool(int(row["include_days_since_last"]))
        include_first = bool(int(row["include_days_since_first"]))
        rules[group] = {
            "days_since_last": include_last,
            "days_since_first": include_first,
        }
        records.append(
            {
                "icd_group_name": group,
                "include_days_since_last": int(include_last),
                "include_days_since_first": int(include_first),
                "binning_policy": str(row.get("binning_policy", "")).strip(),
            }
        )
    return rules, records


def apply_predictor_policy_pruning(
    selected_cols: list[str],
    include_missingness_flags: bool,
    recency_rules: dict[str, dict[str, bool]],
) -> tuple[list[str], dict[str, Any]]:
    kept_cols: list[str] = []
    removed_missingness: list[str] = []
    removed_recency: list[str] = []

    for col in selected_cols:
        if col.endswith("_is_missing") and not include_missingness_flags:
            removed_missingness.append(col)
            continue

        recency_tokens = parse_icd_recency_column(col)
        if recency_tokens:
            group_name, recency_metric = recency_tokens
            policy = recency_rules.get(group_name)
            if policy is not None and not policy.get(recency_metric, True):
                removed_recency.append(col)
                continue

        kept_cols.append(col)

    policy_meta = {
        "include_missingness_flags": int(bool(include_missingness_flags)),
        "removed_missingness_columns": sorted(removed_missingness),
        "removed_recency_columns": sorted(removed_recency),
        "selected_columns_before_policy": int(len(selected_cols)),
        "selected_columns_after_policy": int(len(kept_cols)),
    }
    return kept_cols, policy_meta


def governed_predictors_from_metadata(
    matrix: pd.DataFrame,
    metadata: dict[str, Any],
    excluded_cols: set[str],
) -> list[str]:
    prep_meta = metadata.get("preprocessing_meta", {})
    ordered_candidates: list[str] = []
    for key in ("predictor_columns", "one_hot_columns", "missing_indicator_columns"):
        vals = prep_meta.get(key, [])
        if isinstance(vals, list):
            ordered_candidates.extend([str(v) for v in vals])

    if ordered_candidates:
        seen: set[str] = set()
        governed = []
        for col in ordered_candidates:
            if col in matrix.columns and col not in seen:
                seen.add(col)
                governed.append(col)
    else:
        governed = [c for c in matrix.columns if c != "participant_id"]

    blocked = {"participant_id"} | KNOWN_TARGET_COLUMNS | set(excluded_cols)
    return [c for c in governed if c not in blocked]


def select_by_profile_selector(
    selector_type: str,
    selector_value: str,
    predictors: list[str],
    icd_policy: pd.DataFrame,
    metadata: dict[str, Any],
) -> set[str]:
    predictor_set = set(predictors)
    icd_cols = [c for c in predictors if c.startswith("icd_grp_")]
    feature_meta = metadata.get("feature_meta", {})
    prep_meta = metadata.get("preprocessing_meta", {})

    if selector_type == "all_predictors":
        return predictor_set
    if selector_type == "icd_policy_relevant":
        allowed = set(
            icd_policy.loc[icd_policy["include_in_lr_relevant_baseline"] == 1, "group_name"].tolist()
        )
        return set(keep_icd_cols_by_group(icd_cols, allowed))
    if selector_type == "icd_policy_core":
        allowed = set(icd_policy.loc[icd_policy["group_level"] == "core", "group_name"].tolist())
        return set(keep_icd_cols_by_group(icd_cols, allowed))
    if selector_type == "metadata_family":
        family_name = selector_value.strip()
        selected: set[str] = set()
        family_columns: set[str] = set()
        for source in (feature_meta, prep_meta):
            vals = source.get(family_name, [])
            if isinstance(vals, list):
                family_columns.update([str(v) for v in vals])
        for col in family_columns:
            if col in predictor_set:
                selected.add(col)
            onehot_prefix = f"{col}_"
            selected.update([p for p in predictors if p.startswith(onehot_prefix)])
        return selected
    if selector_type == "prefix":
        if selector_value in {"", "*"}:
            return set()
        return {c for c in predictors if c.startswith(selector_value)}
    if selector_type in {"column", "columns"}:
        names = [tok.strip() for tok in selector_value.split("|") if tok.strip()]
        return {name for name in names if name in predictor_set}
    if selector_type == "regex":
        pattern = re.compile(selector_value)
        return {c for c in predictors if pattern.search(c)}

    raise ValueError(f"Unsupported selector_type in feature profile: {selector_type}")


def apply_feature_profile_rules(
    profile_name: str,
    profile_rules: pd.DataFrame,
    predictors: list[str],
    icd_policy: pd.DataFrame,
    metadata: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    selected: set[str] = set()
    rule_audit: list[dict[str, Any]] = []

    for _, row in profile_rules.sort_values("rule_order").iterrows():
        selector_cols = select_by_profile_selector(
            selector_type=str(row["selector_type"]),
            selector_value=str(row["selector_value"]),
            predictors=predictors,
            icd_policy=icd_policy,
            metadata=metadata,
        )
        before_n = len(selected)
        action = str(row["action"])
        if action == "include":
            selected.update(selector_cols)
        else:
            selected.difference_update(selector_cols)
        after_n = len(selected)
        rule_audit.append(
            {
                "profile_name": profile_name,
                "rule_order": int(row["rule_order"]),
                "action": action,
                "selector_type": str(row["selector_type"]),
                "selector_value": str(row["selector_value"]),
                "selector_match_count": int(len(selector_cols)),
                "selected_count_before": int(before_n),
                "selected_count_after": int(after_n),
            }
        )

    selected_cols = [c for c in predictors if c in selected]
    return selected_cols, rule_audit


def select_predictor_columns_legacy(
    predictors: list[str],
    feature_set: str,
    icd_policy: pd.DataFrame,
) -> list[str]:
    icd_cols = [c for c in predictors if c.startswith("icd_grp_")]
    opcs_cols = [c for c in predictors if c.startswith("opcs_grp_")]
    policy_core = set(icd_policy.loc[icd_policy["group_level"] == "core", "group_name"].tolist())
    policy_relevant = set(
        icd_policy.loc[icd_policy["include_in_lr_relevant_baseline"] == 1, "group_name"].tolist()
    )

    if feature_set == "full_matrix":
        return predictors
    if feature_set == "full_no_opcs":
        return [c for c in predictors if c not in set(opcs_cols)]
    if feature_set == "icd_core_all":
        return keep_icd_cols_by_group(icd_cols, policy_core)
    if feature_set == "icd_only_relevant":
        return keep_icd_cols_by_group(icd_cols, policy_relevant)
    if feature_set in {"full_hes_all", "full_hes_no_opcs", "icd_core_only", "icd_relevant_only"}:
        translated = {
            "full_hes_all": "full_matrix",
            "full_hes_no_opcs": "full_no_opcs",
            "icd_core_only": "icd_core_all",
            "icd_relevant_only": "icd_only_relevant",
        }[feature_set]
        return select_predictor_columns_legacy(predictors, translated, icd_policy)
    raise ValueError(f"Unsupported feature_set: {feature_set}")


def select_predictor_columns(
    matrix: pd.DataFrame,
    metadata: dict[str, Any],
    feature_set: str,
    feature_profile: str | None,
    feature_profile_rules: pd.DataFrame,
    icd_policy: pd.DataFrame,
    target_excluded_cols: set[str],
) -> tuple[list[str], dict[str, Any]]:
    predictors = governed_predictors_from_metadata(matrix, metadata, target_excluded_cols)
    icd_cols = [c for c in predictors if c.startswith("icd_grp_")]
    opcs_cols = [c for c in predictors if c.startswith("opcs_grp_")]
    policy_core = set(icd_policy.loc[icd_policy["group_level"] == "core", "group_name"].tolist())
    policy_relevant = set(
        icd_policy.loc[icd_policy["include_in_lr_relevant_baseline"] == 1, "group_name"].tolist()
    )
    resolved_profile, selector_source = resolve_feature_profile_name(feature_set, feature_profile)
    profile_rules = feature_profile_rules.loc[feature_profile_rules["profile_name"] == resolved_profile].copy()
    rule_audit: list[dict[str, Any]] = []
    if not profile_rules.empty:
        selected_cols, rule_audit = apply_feature_profile_rules(
            profile_name=resolved_profile,
            profile_rules=profile_rules,
            predictors=predictors,
            icd_policy=icd_policy,
            metadata=metadata,
        )
        selection_mode = "profile_rules_csv"
    else:
        selected_cols = select_predictor_columns_legacy(predictors, feature_set, icd_policy)
        selection_mode = "legacy_feature_set"

    if not selected_cols:
        raise RuntimeError(
            "No predictors selected "
            f"(feature_set={feature_set}, feature_profile={feature_profile}, resolved_profile={resolved_profile})."
        )

    feature_meta = {
        "feature_set": feature_set,
        "feature_profile": feature_profile,
        "resolved_feature_profile": resolved_profile,
        "selection_mode": selection_mode,
        "selection_source": selector_source,
        "rule_audit": rule_audit,
        "target_excluded_columns": sorted(target_excluded_cols),
        "total_predictors_available": len(predictors),
        "selected_predictor_count": len(selected_cols),
        "selected_predictors": selected_cols,
        "opcs_predictor_count": len(opcs_cols),
        "icd_predictor_count": len(icd_cols),
        "policy_core_group_count": len(policy_core),
        "policy_relevant_group_count": len(policy_relevant),
    }
    return selected_cols, feature_meta


def resolve_target_definition(
    matrix: pd.DataFrame,
    target_col: str | None,
    target_profile: str | None,
    target_profile_mappings: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, str, set[str], dict[str, Any]]:
    if target_col:
        if target_col not in matrix.columns:
            raise RuntimeError(f"Target column not found in matrix: {target_col}")
        target_values = pd.to_numeric(matrix[target_col], errors="coerce")
        target_meta = {
            "target_mode": "direct_column",
            "target_col": target_col,
            "target_profile": None,
            "source_column": target_col,
            "rows_input": int(len(matrix)),
            "rows_output": int(len(matrix)),
            "rows_dropped": 0,
        }
        return matrix.copy(), target_values, target_col, {target_col}, target_meta

    if not target_profile:
        raise ValueError("Target definition missing: set either --target-col or --target-profile.")

    profile_rows = target_profile_mappings.loc[
        target_profile_mappings["profile_name"] == target_profile
    ].copy()
    if profile_rows.empty:
        available_profiles = sorted(target_profile_mappings["profile_name"].unique().tolist())
        raise ValueError(
            f"Target profile '{target_profile}' not found in mapping CSV. "
            f"Available profiles: {available_profiles}"
        )

    source_columns = sorted(profile_rows["source_column"].dropna().astype(str).str.strip().unique().tolist())
    if len(source_columns) != 1:
        raise ValueError(
            f"Target profile '{target_profile}' must map from exactly one source_column. Found: {source_columns}"
        )
    source_col = source_columns[0]
    if source_col not in matrix.columns:
        raise RuntimeError(
            f"Target profile '{target_profile}' requires source column '{source_col}', "
            "but it is missing in matrix."
        )

    profile_rows["source_key"] = profile_rows["source_value"].map(canonicalize_policy_token)
    dup_source_keys = profile_rows["source_key"][profile_rows["source_key"].duplicated()].unique().tolist()
    if dup_source_keys:
        raise ValueError(
            f"Target profile '{target_profile}' has duplicate source_value mappings: {dup_source_keys}"
        )

    map_actions: dict[str, int | None] = {}
    for _, row in profile_rows.iterrows():
        key = str(row["source_key"])
        action = str(row["action"])
        if action == "drop":
            map_actions[key] = None
            continue
        mapped = pd.to_numeric(pd.Series([row["mapped_target_value"]]), errors="coerce").iloc[0]
        if pd.isna(mapped):
            raise ValueError(
                f"Target profile '{target_profile}' has non-numeric mapped_target_value for source_value={row['source_value']}"
            )
        map_actions[key] = int(mapped)

    source_keys = matrix[source_col].map(canonicalize_policy_token)
    mapped_target = source_keys.map(map_actions)
    keep_mask = mapped_target.notna()
    filtered = matrix.loc[keep_mask].copy()
    target_values = mapped_target.loc[keep_mask].astype(int)

    hit_mask = source_keys.isin(set(map_actions.keys()))
    dropped_unmapped = int((~hit_mask).sum())
    dropped_drop_rule = int((hit_mask & (~keep_mask)).sum())

    target_col_resolved = f"target_profile__{target_profile}"
    target_meta = {
        "target_mode": "target_profile_mapping",
        "target_col": target_col_resolved,
        "target_profile": target_profile,
        "source_column": source_col,
        "rows_input": int(len(matrix)),
        "rows_output": int(len(filtered)),
        "rows_dropped": int(len(matrix) - len(filtered)),
        "rows_dropped_drop_rule": dropped_drop_rule,
        "rows_dropped_unmapped": dropped_unmapped,
        "profile_rule_count": int(len(profile_rows)),
        "profile_rules": profile_rows[
            ["source_column", "source_value", "action", "mapped_target_value"]
        ].to_dict(orient="records"),
    }
    return filtered, target_values, target_col_resolved, {source_col, target_col_resolved}, target_meta


# %% ---------------------------------------------------------------------------
# STEP 2B helpers: signal-discovery context and screening
# -----------------------------------------------------------------------------
def load_screening_scenarios(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Screening scenario CSV not found: {path}")

    df = pd.read_csv(path)
    required = {
        "screening_scenario_id",
        "description",
        "stage_a_min_overall_support",
        "stage_a_min_class_support",
        "stage_a_apply_conditional_sparsity",
        "stage_a_nzv_max_prevalence",
        "stage_b_fdr_alpha",
        "stage_b_effect_size_metric",
        "stage_b_min_effect_size",
        "stage_b_top_k_cap",
        "stability_min_selection_frequency",
        "stability_min_effect_direction_consistency",
        "dosage_candidate_policy",
        "global_dosage_annotation",
        "notes",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Screening scenario CSV missing columns: {sorted(missing)}")

    cleaned = df.copy()
    for col in (
        "screening_scenario_id",
        "description",
        "stage_b_effect_size_metric",
        "dosage_candidate_policy",
        "notes",
    ):
        cleaned[col] = cleaned[col].astype(str).str.strip()
    for col in (
        "stage_a_min_overall_support",
        "stage_a_min_class_support",
        "stage_a_apply_conditional_sparsity",
        "stage_b_top_k_cap",
        "global_dosage_annotation",
    ):
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").fillna(0).astype(int)
    for col in (
        "stage_a_nzv_max_prevalence",
        "stage_b_fdr_alpha",
        "stage_b_min_effect_size",
        "stability_min_selection_frequency",
        "stability_min_effect_direction_consistency",
    ):
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    cleaned = cleaned.loc[cleaned["screening_scenario_id"] != ""].copy()
    return cleaned.reset_index(drop=True)


def resolve_screening_scenario(
    scenarios: pd.DataFrame,
    screening_scenario_id: str,
) -> dict[str, Any]:
    rows = scenarios.loc[scenarios["screening_scenario_id"] == screening_scenario_id].copy()
    if rows.empty:
        available = sorted(scenarios["screening_scenario_id"].astype(str).unique().tolist())
        raise ValueError(
            f"Screening scenario '{screening_scenario_id}' not found. Available: {available}"
        )
    if len(rows) > 1:
        raise ValueError(f"Screening scenario '{screening_scenario_id}' is duplicated.")

    row = rows.iloc[0]
    if str(row["stage_b_effect_size_metric"]).strip() != "abs_risk_difference":
        raise ValueError(
            "First-cycle signal discovery only supports "
            f"stage_b_effect_size_metric='abs_risk_difference'. Got: {row['stage_b_effect_size_metric']}"
        )
    if str(row["dosage_candidate_policy"]).strip() != "tiered_union_pairwise":
        raise ValueError(
            "First-cycle signal discovery only supports "
            f"dosage_candidate_policy='tiered_union_pairwise'. Got: {row['dosage_candidate_policy']}"
        )

    return {
        "screening_scenario_id": str(row["screening_scenario_id"]).strip(),
        "description": str(row["description"]).strip(),
        "stage_a_min_overall_support": int(row["stage_a_min_overall_support"]),
        "stage_a_min_class_support": int(row["stage_a_min_class_support"]),
        "stage_a_apply_conditional_sparsity": int(row["stage_a_apply_conditional_sparsity"]),
        "stage_a_nzv_max_prevalence": float(row["stage_a_nzv_max_prevalence"]),
        "stage_b_fdr_alpha": float(row["stage_b_fdr_alpha"]),
        "stage_b_effect_size_metric": str(row["stage_b_effect_size_metric"]).strip(),
        "stage_b_min_effect_size": float(row["stage_b_min_effect_size"]),
        "stage_b_top_k_cap": int(row["stage_b_top_k_cap"]),
        "stability_min_selection_frequency": float(row["stability_min_selection_frequency"]),
        "stability_min_effect_direction_consistency": float(
            row["stability_min_effect_direction_consistency"]
        ),
        "dosage_candidate_policy": str(row["dosage_candidate_policy"]).strip(),
        "global_dosage_annotation": int(row["global_dosage_annotation"]),
        "notes": str(row["notes"]).strip(),
    }


def resolve_driver_manifest_path(run_dir: Path, stamp: str, driver_manifest_arg: str | None) -> Path:
    if driver_manifest_arg:
        path = Path(driver_manifest_arg)
    else:
        path = run_dir / f"feature_engineering_driver_manifest_{stamp}.json"
    if not path.exists():
        raise FileNotFoundError(f"Signal-discovery driver manifest not found: {path}")
    return path


def load_driver_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_repo_relative_path(path_like: str) -> Path:
    path = Path(path_like)
    if path.exists():
        return path.resolve()

    parents = Path(__file__).resolve().parents
    repo_root = parents[4] if len(parents) > 4 else Path.cwd()
    candidate = repo_root / path_like
    if candidate.exists():
        return candidate.resolve()

    raise FileNotFoundError(f"Path not found: {path_like}")


def resolve_signal_discovery_context(
    driver_manifest: dict[str, Any],
    investigation_id: str,
) -> dict[str, Any]:
    investigations = driver_manifest.get("investigations", [])
    matches = [
        row for row in investigations if str(row.get("investigation_id", "")).strip() == investigation_id
    ]
    if not matches:
        raise ValueError(
            f"Investigation '{investigation_id}' not found in driver manifest signal-discovery contexts."
        )
    if len(matches) > 1:
        raise ValueError(
            f"Investigation '{investigation_id}' appears multiple times in driver manifest."
        )

    context = matches[0]
    if not bool(context.get("screening_enabled")):
        raise ValueError(
            f"Investigation '{investigation_id}' resolved from driver manifest but screening_enabled is false."
        )
    if str(context.get("branch_mode", "")).strip() != "signal_discovery_opt_in":
        raise ValueError(
            f"Investigation '{investigation_id}' has invalid branch_mode for signal discovery: "
            f"{context.get('branch_mode')!r}"
        )
    if str(context.get("screening_mode", "")).strip() != SIGNAL_DISCOVERY_SCREENING_MODE:
        raise ValueError(
            f"Investigation '{investigation_id}' has invalid screening_mode: "
            f"{context.get('screening_mode')!r}"
        )
    if str(context.get("baseline_reference", "")).strip() != LOCKED_BASELINE_REFERENCE:
        raise ValueError(
            f"Investigation '{investigation_id}' baseline_reference does not match the locked baseline."
        )

    grouped_anchor = context.get("comparison_only_grouped_anchor_artifacts", {})
    if not bool(grouped_anchor.get("comparison_only")) or not bool(grouped_anchor.get("not_model_input")):
        raise ValueError(
            f"Investigation '{investigation_id}' grouped-anchor context must remain comparison-only."
        )

    constraints = context.get("signal_discovery_constraints", {})
    if str(constraints.get("authoritative_source", "")).strip() != "diag_all":
        raise ValueError(
            f"Investigation '{investigation_id}' authoritative_source must be 'diag_all'."
        )
    for table_name, cols in dict(constraints.get("source_columns_by_table", {})).items():
        normalized_cols = [str(col).strip() for col in cols]
        if normalized_cols != ["diag_all"]:
            raise ValueError(
                f"Investigation '{investigation_id}' source columns for {table_name} are "
                f"{normalized_cols}; expected ['diag_all']."
            )
    return context


def resolve_signal_discovery_artifact_path(path_like: str, run_dir: Path) -> Path:
    path = Path(path_like)
    if path.exists():
        return path.resolve()
    if not path.is_absolute():
        candidate = run_dir / path
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"Signal-discovery artifact not found: {path_like}")


def load_signal_discovery_artifacts(
    signal_discovery_context: dict[str, Any],
    run_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]:
    discovery_inputs = signal_discovery_context.get("discovery_inputs", {})
    grouped_anchor_artifacts = signal_discovery_context.get("comparison_only_grouped_anchor_artifacts", {})
    raw_code_matrix_path = resolve_signal_discovery_artifact_path(
        str(discovery_inputs.get("raw_code_matrix_path", "")),
        run_dir,
    )
    stage_a_preparation_path = resolve_signal_discovery_artifact_path(
        str(discovery_inputs.get("stage_a_preparation_path", "")),
        run_dir,
    )
    grouped_anchor_path = resolve_signal_discovery_artifact_path(
        str(grouped_anchor_artifacts.get("grouped_anchor_comparison_path", "")),
        run_dir,
    )

    raw_code_matrix = pd.read_csv(raw_code_matrix_path)
    stage_a_preparation = pd.read_csv(stage_a_preparation_path)
    grouped_anchor = pd.read_csv(grouped_anchor_path)

    raw_required = {"participant_id"}
    stage_a_required = {
        "normalized_code",
        "feature_column",
        "participant_support_n",
        "event_occurrence_n",
        "participant_prevalence",
        "binary_majority_share",
        "nonzero_variance_flag",
        "source_tables",
        "source_table_count",
        "stage_a_preparation_only",
    }
    grouped_anchor_required = {
        "normalized_code",
        "feature_column",
        "group_anchor",
        "group_level",
        "include_in_default_model",
        "include_in_lr_relevant_baseline",
    }
    if raw_required.difference(raw_code_matrix.columns):
        raise RuntimeError(
            "Signal-discovery raw-code matrix missing required columns: "
            f"{sorted(raw_required.difference(raw_code_matrix.columns))}"
        )
    if stage_a_required.difference(stage_a_preparation.columns):
        raise RuntimeError(
            "Signal-discovery Stage A preparation table missing required columns: "
            f"{sorted(stage_a_required.difference(stage_a_preparation.columns))}"
        )
    if grouped_anchor_required.difference(grouped_anchor.columns):
        raise RuntimeError(
            "Grouped-anchor comparison artifact missing required columns: "
            f"{sorted(grouped_anchor_required.difference(grouped_anchor.columns))}"
        )

    forbidden_stage_a_tokens = (
        "target_",
        "target_name",
        "class_support",
        "class_coverage",
        "stage_a_keep",
        "stage_a_retain",
        "stage_b_retain",
        "candidate_policy",
        "contrast_id",
        "pairwise_view",
    )
    lower_columns = [str(col).strip().lower() for col in stage_a_preparation.columns]
    forbidden = sorted(
        {
            col
            for col in lower_columns
            for token in forbidden_stage_a_tokens
            if token in col
        }
    )
    if forbidden:
        raise RuntimeError(
            "Global Stage A preparation artifact contains forbidden target-aware columns: "
            f"{forbidden}"
        )
    if not (pd.to_numeric(stage_a_preparation["stage_a_preparation_only"], errors="coerce").fillna(0) == 1).all():
        raise RuntimeError(
            "Signal-discovery Stage A preparation artifact must remain label-agnostic "
            "(stage_a_preparation_only=1 for all rows)."
        )

    return (
        raw_code_matrix,
        stage_a_preparation,
        grouped_anchor,
        {
            "raw_code_matrix_path": str(raw_code_matrix_path),
            "stage_a_preparation_path": str(stage_a_preparation_path),
            "grouped_anchor_comparison_path": str(grouped_anchor_path),
        },
    )


def prepare_signal_discovery_inputs(
    target_matrix: pd.DataFrame,
    raw_code_matrix: pd.DataFrame,
    target_col: str,
    target_values: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict[str, Any], str, list[int], list[str]]:
    if "participant_id" not in target_matrix.columns:
        raise RuntimeError("Signal-discovery target matrix missing participant_id")

    target_frame = target_matrix[["participant_id"]].copy()
    raw_frame = raw_code_matrix.copy()
    raw_frame["participant_id"] = pd.to_numeric(raw_frame["participant_id"], errors="coerce")
    raw_frame = raw_frame.dropna(subset=["participant_id"]).copy()
    raw_frame["participant_id"] = raw_frame["participant_id"].astype(int)

    raw_feature_columns = [c for c in raw_frame.columns if c != "participant_id"]
    if not raw_feature_columns:
        raise RuntimeError("Signal-discovery raw-code matrix does not contain any discovery features.")
    invalid_columns = [c for c in raw_feature_columns if not str(c).startswith("icd_raw_")]
    if invalid_columns:
        raise RuntimeError(
            "Signal-discovery model inputs must originate from raw ICD features only. "
            f"Invalid columns: {sorted(invalid_columns)[:10]}"
        )

    merged = target_frame.merge(raw_frame, on="participant_id", how="left")
    merged[raw_feature_columns] = (
        merged[raw_feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0).astype(float)
    )

    if target_values is None:
        if target_col not in target_matrix.columns:
            raise RuntimeError(f"Signal-discovery target column not found in target matrix: {target_col}")
        y = pd.to_numeric(target_matrix[target_col], errors="coerce")
    else:
        y = pd.to_numeric(target_values.reindex(target_matrix.index), errors="coerce")
    if y.isna().any():
        raise RuntimeError(f"Signal-discovery target '{target_col}' contains NaN values")

    y = y.astype(int)
    target_labels = sorted([int(v) for v in pd.Series(y).dropna().unique().tolist()])
    if len(target_labels) < 2:
        raise RuntimeError(f"Signal-discovery target must contain at least 2 classes. Found: {target_labels}")
    target_type = "binary" if len(target_labels) == 2 else "multiclass"

    binary_label_mapping: dict[int, int] | None = None
    if target_type == "binary" and target_labels != [0, 1]:
        binary_label_mapping = {target_labels[0]: 0, target_labels[1]: 1}
        y = y.map(binary_label_mapping).astype(int)
        target_labels = [0, 1]

    prep_meta = {
        "n_rows": int(len(merged)),
        "n_predictors_selected": int(len(raw_feature_columns)),
        "missing_cells_before_fill": 0,
        "missing_cells_after_fill": 0,
        "target_col": target_col,
        "target_type": target_type,
        "target_labels": target_labels,
        "target_class_distribution_full": {
            str(k): int(v) for k, v in y.value_counts(dropna=False).sort_index().items()
        },
        "target_prevalence_full": float(y.mean()) if target_type == "binary" else None,
        "signal_discovery_mode": True,
        "signal_discovery_feature_source": "diag_all_raw_code_matrix",
    }
    if binary_label_mapping is not None:
        prep_meta["binary_label_mapping"] = binary_label_mapping
    return (
        merged[raw_feature_columns].copy(),
        y.copy(),
        merged["participant_id"].copy(),
        prep_meta,
        target_type,
        target_labels,
        raw_feature_columns,
    )


def resolve_signal_discovery_outer_splitter(
    y: pd.Series,
    random_state: int,
) -> tuple[RepeatedStratifiedKFold, int, int]:
    class_counts = y.value_counts().sort_index()
    if class_counts.empty:
        raise RuntimeError("Signal-discovery target distribution is empty.")
    min_class_n = int(class_counts.min())
    if min_class_n < 2:
        raise RuntimeError(
            "Signal-discovery nested resampling requires at least 2 samples in every class. "
            f"Observed minimum class count: {min_class_n}"
        )
    n_splits = min(SIGNAL_DISCOVERY_OUTER_N_SPLITS, min_class_n)
    if n_splits < 2:
        raise RuntimeError(
            f"Signal-discovery nested resampling requires at least 2 outer folds. Computed n_splits={n_splits}."
        )
    splitter = RepeatedStratifiedKFold(
        n_splits=n_splits,
        n_repeats=SIGNAL_DISCOVERY_OUTER_N_REPEATS,
        random_state=random_state,
    )
    return splitter, n_splits, SIGNAL_DISCOVERY_OUTER_N_REPEATS


def benjamini_hochberg_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    ordered = p[order]
    n = len(ordered)
    adjusted = np.empty(n, dtype=float)
    prev = 1.0
    for idx in range(n - 1, -1, -1):
        rank = idx + 1
        current = min(prev, (ordered[idx] * n) / rank)
        adjusted[idx] = current
        prev = current
    out = np.empty(n, dtype=float)
    out[order] = adjusted
    return out.tolist()


def evaluate_binary_predictions(
    y_true: pd.Series,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
) -> dict[str, Any]:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    sensitivity = float(tp / (tp + fn)) if (tp + fn) > 0 else float("nan")
    specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else float("nan")
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "pr_auc": float(average_precision_score(y_true, y_proba)),
        "brier": float(brier_score_loss(y_true, y_proba)),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def build_binary_screening_table(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    scenario: dict[str, Any],
    contrast_id: str,
    pairwise_view: str | None,
    training_only: bool,
) -> pd.DataFrame:
    if not training_only:
        raise RuntimeError(
            "Signal-discovery target-aware Stage A/Stage B screening must not run outside training folds."
        )
    unique_labels = sorted([int(v) for v in pd.Series(y_train).dropna().unique().tolist()])
    if unique_labels != [0, 1]:
        raise RuntimeError(
            f"Binary signal screening requires labels [0, 1]. Found: {unique_labels}"
        )

    min_overall = int(scenario["stage_a_min_overall_support"])
    min_class = int(scenario["stage_a_min_class_support"])
    apply_conditional = int(scenario["stage_a_apply_conditional_sparsity"]) == 1
    nzv_max = float(scenario["stage_a_nzv_max_prevalence"])

    pos_mask = y_train == 1
    neg_mask = y_train == 0
    n_pos = int(pos_mask.sum())
    n_neg = int(neg_mask.sum())
    if n_pos == 0 or n_neg == 0:
        raise RuntimeError("Binary signal screening requires both classes to be present in the training fold.")

    rows: list[dict[str, Any]] = []
    for feature in X_train.columns:
        present = (pd.to_numeric(X_train[feature], errors="coerce").fillna(0.0) > 0).astype(int)
        support_total = int(present.sum())
        pos_support = int(present.loc[pos_mask].sum())
        neg_support = int(present.loc[neg_mask].sum())
        prevalence_total = float(support_total / len(present)) if len(present) else 0.0
        stage_a_retain = int(
            support_total >= min_overall
            and pos_support >= min_class
            and neg_support >= min_class
            and (
                not apply_conditional
                or (0.0 < prevalence_total < nzv_max)
            )
        )

        row: dict[str, Any] = {
            "feature_column": feature,
            "contrast_id": contrast_id,
            "pairwise_view": pairwise_view or "",
            "train_support_overall": support_total,
            "train_support_class_1": pos_support,
            "train_support_class_0": neg_support,
            "train_prevalence_overall": prevalence_total,
            "stage_a_retain": stage_a_retain,
            "risk_difference": np.nan,
            "effect_size": np.nan,
            "odds_ratio": np.nan,
            "p_value": np.nan,
            "bh_fdr": np.nan,
            "stage_b_retain": 0,
            "stage_b_rank": np.nan,
        }
        if stage_a_retain:
            table = np.array(
                [
                    [pos_support, int(n_pos - pos_support)],
                    [neg_support, int(n_neg - neg_support)],
                ],
                dtype=int,
            )
            odds_ratio, p_value = fisher_exact(table, alternative="two-sided")
            pos_prev = float(pos_support / n_pos) if n_pos else 0.0
            neg_prev = float(neg_support / n_neg) if n_neg else 0.0
            risk_diff = pos_prev - neg_prev
            row.update(
                {
                    "risk_difference": float(risk_diff),
                    "effect_size": float(abs(risk_diff)),
                    "odds_ratio": float(odds_ratio) if np.isfinite(odds_ratio) else np.inf,
                    "p_value": float(p_value),
                }
            )
        rows.append(row)

    df = pd.DataFrame(rows)
    eligible = df.loc[df["stage_a_retain"] == 1].copy()
    if eligible.empty:
        return df

    eligible["bh_fdr"] = benjamini_hochberg_adjust(eligible["p_value"].astype(float).tolist())
    retain_mask = (
        (eligible["bh_fdr"] <= float(scenario["stage_b_fdr_alpha"]))
        & (eligible["effect_size"] >= float(scenario["stage_b_min_effect_size"]))
    )
    retained = eligible.loc[retain_mask].copy()
    if int(scenario["stage_b_top_k_cap"]) > 0 and not retained.empty:
        retained = retained.sort_values(
            ["bh_fdr", "effect_size", "train_support_overall", "feature_column"],
            ascending=[True, False, False, True],
        ).head(int(scenario["stage_b_top_k_cap"]))
    if not retained.empty:
        retained = retained.sort_values(
            ["bh_fdr", "effect_size", "train_support_overall", "feature_column"],
            ascending=[True, False, False, True],
        )
        rank_map = {int(idx): int(rank) for rank, idx in enumerate(retained.index.tolist(), start=1)}
        df.loc[eligible.index, "bh_fdr"] = eligible["bh_fdr"]
        df.loc[retained.index, "stage_b_retain"] = 1
        df.loc[retained.index, "stage_b_rank"] = [rank_map[int(idx)] for idx in retained.index]
    else:
        df.loc[eligible.index, "bh_fdr"] = eligible["bh_fdr"]

    return df


def build_binary_candidate_manifest(
    screening_df: pd.DataFrame,
    *,
    investigation_id: str,
    target_name: str,
    screening_scenario_id: str,
    screening_mode: str,
    contrast_id: str,
    pairwise_view: str,
    fold_id: int,
    repeat_id: int,
    random_seed: int,
    baseline_reference: str,
    candidate_policy: str,
) -> pd.DataFrame:
    retained = screening_df.loc[screening_df["stage_b_retain"] == 1].copy()
    if retained.empty:
        return pd.DataFrame(
            columns=[
                "investigation_id",
                "target_name",
                "screening_scenario_id",
                "screening_mode",
                "contrast_id",
                "pairwise_view",
                "fold_id",
                "repeat_id",
                "random_seed",
                "baseline_reference",
                "candidate_policy",
                "created_from_training_only",
                "feature_column",
                "train_support_overall",
                "train_support_class_1",
                "train_support_class_0",
                "train_prevalence_overall",
                "risk_difference",
                "effect_size",
                "odds_ratio",
                "p_value",
                "bh_fdr",
                "stage_b_rank",
            ]
        )
    retained.insert(0, "investigation_id", investigation_id)
    retained.insert(1, "target_name", target_name)
    retained.insert(2, "screening_scenario_id", screening_scenario_id)
    retained.insert(3, "screening_mode", screening_mode)
    retained["contrast_id"] = contrast_id
    retained["pairwise_view"] = pairwise_view
    retained["fold_id"] = int(fold_id)
    retained["repeat_id"] = int(repeat_id)
    retained["random_seed"] = int(random_seed)
    retained["baseline_reference"] = baseline_reference
    retained["candidate_policy"] = candidate_policy
    retained["created_from_training_only"] = True
    return retained.reset_index(drop=True)


def build_dosage_candidate_manifest(
    pairwise_manifests: dict[str, pd.DataFrame],
    *,
    investigation_id: str,
    target_name: str,
    screening_scenario_id: str,
    screening_mode: str,
    fold_id: int,
    repeat_id: int,
    random_seed: int,
    baseline_reference: str,
    candidate_policy: str,
) -> pd.DataFrame:
    feature_records: dict[str, dict[str, Any]] = {}
    for pairwise_view, manifest_df in pairwise_manifests.items():
        if manifest_df.empty:
            continue
        for _, row in manifest_df.iterrows():
            feature = str(row["feature_column"])
            payload = feature_records.setdefault(
                feature,
                {
                    "supporting_contrasts": [],
                    "effect_sizes": {},
                    "fdr": {},
                    "supports": {},
                },
            )
            payload["supporting_contrasts"].append(pairwise_view)
            payload["effect_sizes"][pairwise_view] = float(row["effect_size"])
            payload["fdr"][pairwise_view] = float(row["bh_fdr"])
            payload["supports"][pairwise_view] = int(row["train_support_overall"])

    rows: list[dict[str, Any]] = []
    for feature in sorted(feature_records):
        record = feature_records[feature]
        supporting = sorted(set(record["supporting_contrasts"]))
        contrast_support_count = int(len(supporting))
        tier = "tier1_multi_contrast" if contrast_support_count >= 2 else "tier2_single_contrast"
        mean_abs_effect = (
            float(np.mean([abs(v) for v in record["effect_sizes"].values()]))
            if record["effect_sizes"]
            else np.nan
        )
        rows.append(
            {
                "investigation_id": investigation_id,
                "target_name": target_name,
                "screening_scenario_id": screening_scenario_id,
                "screening_mode": screening_mode,
                "contrast_id": "",
                "pairwise_view": "all_pairwise_tiered_union",
                "fold_id": int(fold_id),
                "repeat_id": int(repeat_id),
                "random_seed": int(random_seed),
                "baseline_reference": baseline_reference,
                "candidate_policy": candidate_policy,
                "created_from_training_only": True,
                "feature_column": feature,
                "supporting_contrasts": "|".join(supporting),
                "contrast_support_count": contrast_support_count,
                "dosage_candidate_tier": tier,
                "mean_abs_effect_size": mean_abs_effect,
                "contrast_effect_sizes_json": json.dumps(record["effect_sizes"], sort_keys=True),
                "contrast_q_values_json": json.dumps(record["fdr"], sort_keys=True),
                "contrast_supports_json": json.dumps(record["supports"], sort_keys=True),
            }
        )

    return pd.DataFrame(rows)


def build_signal_discovery_manifest_path(
    run_dir: Path,
    investigation_id: str,
    target_name: str,
    screening_scenario_id: str,
    stamp: str,
    repeat_id: int,
    fold_id: int,
    random_seed: int,
) -> Path:
    token = "_".join(
        [
            slug_token(investigation_id),
            slug_token(target_name),
            slug_token(screening_scenario_id),
            stamp,
            f"repeat{int(repeat_id)}",
            f"fold{int(fold_id)}",
            f"seed{int(random_seed)}",
        ]
    )
    return run_dir / f"signal_discovery_candidate_manifest_{token}.csv"


def persist_or_validate_shared_candidate_manifest(
    manifest_path: Path,
    manifest_df: pd.DataFrame,
    *,
    dosage_mode: bool,
) -> pd.DataFrame:
    if manifest_df.empty:
        raise RuntimeError(
            f"Signal-discovery fold-local candidate manifest would be empty: {manifest_path.name}"
        )
    required = {
        "investigation_id",
        "target_name",
        "screening_scenario_id",
        "screening_mode",
        "fold_id",
        "repeat_id",
        "random_seed",
        "baseline_reference",
        "candidate_policy",
        "created_from_training_only",
        "feature_column",
    }
    if dosage_mode:
        required.update(
            {
                "pairwise_view",
                "supporting_contrasts",
                "contrast_support_count",
                "dosage_candidate_tier",
            }
        )
    else:
        required.update({"contrast_id"})

    missing = required.difference(manifest_df.columns)
    if missing:
        raise RuntimeError(
            f"Signal-discovery candidate manifest missing required columns: {sorted(missing)}"
        )
    if not manifest_df["created_from_training_only"].astype(bool).all():
        raise RuntimeError("Signal-discovery candidate manifest must mark created_from_training_only=true.")

    manifest_df = manifest_df.copy()
    manifest_df["feature_column"] = manifest_df["feature_column"].astype(str)
    if manifest_path.exists():
        existing = pd.read_csv(manifest_path)
        existing_features = sorted(existing["feature_column"].astype(str).unique().tolist())
        current_features = sorted(manifest_df["feature_column"].astype(str).unique().tolist())
        if existing_features != current_features:
            raise RuntimeError(
                f"Fold-local candidate manifest mismatch detected across model families: {manifest_path}"
            )
        return existing

    manifest_df.to_csv(manifest_path, index=False)
    return manifest_df


def parse_locked_baseline_metrics(path_like: str) -> dict[str, dict[str, float]]:
    baseline_path = resolve_repo_relative_path(path_like)
    text = baseline_path.read_text(encoding="utf-8")

    section_headers = {
        "lr": "### Logistic regression",
        "rf": "### Random forest",
        "nn": "### Neural network",
    }
    metric_patterns = {
        "roc_auc": r"- ROC AUC:\s*`([^`]+)`",
        "pr_auc": r"- PR AUC:\s*`([^`]+)`",
        "brier": r"- Brier:\s*`([^`]+)`",
        "accuracy": r"- Accuracy:\s*`([^`]+)`",
        "sensitivity": r"- Sensitivity:\s*`([^`]+)`",
        "specificity": r"- Specificity:\s*`([^`]+)`",
        "precision": r"- Precision:\s*`([^`]+)`",
    }
    results: dict[str, dict[str, float]] = {}
    for model_type, header in section_headers.items():
        start_idx = text.find(header)
        if start_idx < 0:
            continue
        tail = text[start_idx:]
        next_idx = tail.find("\n### ", len(header))
        section = tail if next_idx < 0 else tail[:next_idx]
        model_metrics: dict[str, float] = {}
        for metric_name, pattern in metric_patterns.items():
            match = re.search(pattern, section, flags=re.IGNORECASE)
            if match:
                model_metrics[metric_name] = float(match.group(1))
        if model_metrics:
            results[model_type] = model_metrics
    return results


def build_signal_discovery_output_paths(run_dir: Path, run_tag: str) -> dict[str, Path]:
    return {
        "fold_metrics": run_dir / f"signal_discovery_fold_metrics_{run_tag}.csv",
        "screening_summary": run_dir / f"signal_discovery_screening_summary_{run_tag}.csv",
        "baseline_delta": run_dir / f"signal_discovery_baseline_delta_{run_tag}.json",
        "selection_summary": run_dir / f"signal_discovery_selection_summary_{run_tag}.csv",
    }


def run_signal_discovery_training(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    stamp: str,
    metadata: dict[str, Any],
    matrix_path: Path,
    matrix_for_model: pd.DataFrame,
    target_values: pd.Series,
    resolved_target_col: str,
    target_resolution_meta: dict[str, Any],
    cohort_filter_meta: dict[str, Any],
    investigation_context: dict[str, Any],
    recency_policy_id: str | None,
) -> None:
    if not args.investigation_id:
        raise RuntimeError("Signal-discovery mode requires --investigation-id.")
    if int(investigation_context.get("screening_enabled", 0)) != 1:
        raise RuntimeError("Signal-discovery training was invoked for a non-screening investigation row.")
    if str(investigation_context.get("screening_mode", "")).strip() != SIGNAL_DISCOVERY_SCREENING_MODE:
        raise RuntimeError(
            "Signal-discovery training requires screening_mode='raw_icd_signal_discovery'."
        )

    screening_scenarios = load_screening_scenarios(Path(args.screening_scenario_csv))
    screening_scenario = resolve_screening_scenario(
        screening_scenarios,
        str(investigation_context.get("screening_scenario_id", "")).strip(),
    )
    driver_manifest_path = resolve_driver_manifest_path(run_dir, stamp, args.driver_manifest)
    driver_manifest = load_driver_manifest(driver_manifest_path)
    signal_discovery_context = resolve_signal_discovery_context(
        driver_manifest,
        str(investigation_context["investigation_id"]),
    )
    raw_code_matrix, stage_a_preparation, grouped_anchor_comparison, signal_artifact_paths = (
        load_signal_discovery_artifacts(signal_discovery_context, run_dir)
    )
    if not bool(
        signal_discovery_context.get("comparison_only_grouped_anchor_artifacts", {}).get("not_model_input")
    ):
        raise RuntimeError("Grouped-anchor artifacts must remain comparison-only and never enter model inputs.")

    X, y, pid, prep_meta, target_type, target_labels, raw_feature_columns = prepare_signal_discovery_inputs(
        target_matrix=matrix_for_model,
        raw_code_matrix=raw_code_matrix,
        target_col=resolved_target_col,
        target_values=target_values,
    )
    prep_meta["target_resolution"] = target_resolution_meta
    prep_meta["signal_discovery_context"] = {
        "branch_mode": signal_discovery_context.get("branch_mode"),
        "screening_mode": signal_discovery_context.get("screening_mode"),
        "screening_scenario_id": signal_discovery_context.get("screening_scenario_id"),
        "baseline_reference": signal_discovery_context.get("baseline_reference"),
        "driver_manifest": str(driver_manifest_path),
    }
    prep_meta["signal_discovery_artifacts"] = signal_artifact_paths
    prep_meta["global_stage_a_preparation_only"] = True
    prep_meta["comparison_only_grouped_anchor_rows"] = int(len(grouped_anchor_comparison))
    signal_meta = metadata.get("signal_discovery_meta", {})
    if str(signal_meta.get("authoritative_source", "")).strip() != "diag_all":
        raise RuntimeError("Signal-discovery metadata authoritative_source must remain 'diag_all'.")
    stage_a_feature_columns = set(stage_a_preparation["feature_column"].astype(str).tolist())
    missing_stage_a_features = sorted(set(raw_feature_columns).difference(stage_a_feature_columns))
    if missing_stage_a_features:
        raise RuntimeError(
            "Signal-discovery Stage A preparation artifact is missing raw-code features required "
            f"for modelling: {missing_stage_a_features[:10]}"
        )

    splitter, outer_n_splits, outer_n_repeats = resolve_signal_discovery_outer_splitter(
        y=y,
        random_state=int(args.random_state),
    )
    class_counts = y.value_counts().sort_index().to_dict()
    print_step("STEP 3: Signal-discovery nested resampling and fold-local screening")
    print(f"SIGNAL_DISCOVERY_MODE: {signal_discovery_context.get('screening_mode')}")
    print(f"SCREENING_SCENARIO_ID: {screening_scenario['screening_scenario_id']}")
    print(f"OUTER_SPLITS: {outer_n_splits}")
    print(f"OUTER_REPEATS: {outer_n_repeats}")
    print(f"TARGET_TYPE: {target_type}")
    print(f"TARGET_LABELS: {target_labels}")
    print(f"CLASS_COUNTS_FULL: {class_counts}")

    fold_metrics_rows: list[dict[str, Any]] = []
    oof_predictions: list[pd.DataFrame] = []
    manifest_paths: list[str] = []
    screening_summary_rows: list[pd.DataFrame] = []
    manifest_frames: list[pd.DataFrame] = []
    fold_threshold_rows: list[dict[str, Any]] = []

    baseline_reference = str(signal_discovery_context.get("baseline_reference", LOCKED_BASELINE_REFERENCE))
    target_name = str(investigation_context.get("target_name", "")).strip() or resolved_target_col

    for split_idx, (train_idx, test_idx) in enumerate(splitter.split(X, y)):
        repeat_id = int(split_idx // outer_n_splits)
        fold_id = int(split_idx % outer_n_splits)
        fold_seed = int(args.random_state + split_idx)

        X_train = X.iloc[train_idx].reset_index(drop=True)
        y_train = y.iloc[train_idx].reset_index(drop=True)
        X_test = X.iloc[test_idx].reset_index(drop=True)
        y_test = y.iloc[test_idx].reset_index(drop=True)
        pid_test = pid.iloc[test_idx].reset_index(drop=True)

        if target_type == "binary":
            screening_df = build_binary_screening_table(
                X_train=X_train,
                y_train=y_train,
                scenario=screening_scenario,
                contrast_id=resolved_target_col,
                pairwise_view="",
                training_only=True,
            )
            screening_summary_rows.append(
                screening_df.assign(
                    repeat_id=repeat_id,
                    fold_id=fold_id,
                    random_seed=fold_seed,
                )
            )
            manifest_df = build_binary_candidate_manifest(
                screening_df=screening_df,
                investigation_id=str(investigation_context["investigation_id"]),
                target_name=target_name,
                screening_scenario_id=screening_scenario["screening_scenario_id"],
                screening_mode=SIGNAL_DISCOVERY_SCREENING_MODE,
                contrast_id=resolved_target_col,
                pairwise_view="",
                fold_id=fold_id,
                repeat_id=repeat_id,
                random_seed=fold_seed,
                baseline_reference=baseline_reference,
                candidate_policy="shared_first_pass_binary",
            )
        else:
            pairwise_manifests: dict[str, pd.DataFrame] = {}
            for left_label, right_label in combinations(target_labels, 2):
                pairwise_view = f"{left_label}_vs_{right_label}"
                mask = y_train.isin([left_label, right_label])
                X_pair = X_train.loc[mask].reset_index(drop=True)
                y_pair = y_train.loc[mask].map({left_label: 0, right_label: 1}).astype(int).reset_index(drop=True)
                screening_df = build_binary_screening_table(
                    X_train=X_pair,
                    y_train=y_pair,
                    scenario=screening_scenario,
                    contrast_id=pairwise_view,
                    pairwise_view=pairwise_view,
                    training_only=True,
                )
                screening_summary_rows.append(
                    screening_df.assign(
                        repeat_id=repeat_id,
                        fold_id=fold_id,
                        random_seed=fold_seed,
                    )
                )
                pairwise_manifests[pairwise_view] = build_binary_candidate_manifest(
                    screening_df=screening_df,
                    investigation_id=str(investigation_context["investigation_id"]),
                    target_name=target_name,
                    screening_scenario_id=screening_scenario["screening_scenario_id"],
                    screening_mode=SIGNAL_DISCOVERY_SCREENING_MODE,
                    contrast_id=pairwise_view,
                    pairwise_view=pairwise_view,
                    fold_id=fold_id,
                    repeat_id=repeat_id,
                    random_seed=fold_seed,
                    baseline_reference=baseline_reference,
                    candidate_policy="pairwise_binary_screen",
                )
            manifest_df = build_dosage_candidate_manifest(
                pairwise_manifests=pairwise_manifests,
                investigation_id=str(investigation_context["investigation_id"]),
                target_name=target_name,
                screening_scenario_id=screening_scenario["screening_scenario_id"],
                screening_mode=SIGNAL_DISCOVERY_SCREENING_MODE,
                fold_id=fold_id,
                repeat_id=repeat_id,
                random_seed=fold_seed,
                baseline_reference=baseline_reference,
                candidate_policy=screening_scenario["dosage_candidate_policy"],
            )

        manifest_path = build_signal_discovery_manifest_path(
            run_dir=run_dir,
            investigation_id=str(investigation_context["investigation_id"]),
            target_name=target_name,
            screening_scenario_id=screening_scenario["screening_scenario_id"],
            stamp=stamp,
            repeat_id=repeat_id,
            fold_id=fold_id,
            random_seed=fold_seed,
        )
        manifest_df = persist_or_validate_shared_candidate_manifest(
            manifest_path=manifest_path,
            manifest_df=manifest_df,
            dosage_mode=(target_type == "multiclass"),
        )
        candidate_columns = manifest_df["feature_column"].astype(str).tolist()
        if not candidate_columns:
            raise RuntimeError(f"No signal-discovery candidates survived for {manifest_path.name}.")
        if set(candidate_columns).difference(set(raw_feature_columns)):
            invalid = sorted(set(candidate_columns).difference(set(raw_feature_columns)))
            raise RuntimeError(
                "Signal-discovery model inputs must derive from the raw-code discovery matrix only. "
                f"Invalid candidate columns: {invalid[:10]}"
            )

        manifest_paths.append(str(manifest_path))
        manifest_frames.append(manifest_df.copy())

        X_train_selected = X_train[candidate_columns].copy()
        X_test_selected = X_test[candidate_columns].copy()
        model = build_model(
            model_type=args.model_type,
            random_state=fold_seed,
            target_type=target_type,
            nn_hidden_layers=parse_hidden_layers(args.nn_hidden_layers),
            nn_alpha=args.nn_alpha,
            nn_learning_rate_init=args.nn_learning_rate_init,
            nn_max_iter=args.nn_max_iter,
            nn_early_stopping=args.nn_early_stopping,
            class_weight_mode=args.class_weight_mode,
        )
        model.fit(X_train_selected, y_train)

        if target_type == "binary":
            class_values = list(getattr(model, "classes_", [0, 1]))
            if 1 not in class_values:
                raise RuntimeError(
                    f"Signal-discovery binary model requires positive class label 1. Found: {class_values}"
                )
            pos_idx = class_values.index(1)
            y_proba_test = model.predict_proba(X_test_selected)[:, pos_idx]
            y_train_oof_proba, threshold_inner_meta = generate_signal_discovery_training_oof_probabilities(
                X_train=X_train_selected,
                y_train=y_train,
                args=args,
                random_state_seed=fold_seed,
            )
            if y_train_oof_proba is None:
                selected_threshold = float(args.threshold)
                threshold_selection_meta = {
                    "policy": "fixed_fallback",
                    "selected_threshold": selected_threshold,
                    **threshold_inner_meta,
                }
            else:
                selected_threshold, _, threshold_selection_meta = select_threshold_from_policy(
                    policy=args.threshold_policy,
                    fixed_threshold=float(args.threshold),
                    y_train=y_train,
                    y_train_proba=y_train_oof_proba,
                    min_specificity_floor=float(args.min_specificity_floor),
                )
                threshold_selection_meta = {**threshold_selection_meta, **threshold_inner_meta}
            y_pred_test = (y_proba_test >= selected_threshold).astype(int)
            fold_metrics = evaluate_binary_predictions(y_test, y_pred_test, y_proba_test)
            fold_threshold_rows.append(
                {
                    "repeat_id": repeat_id,
                    "fold_id": fold_id,
                    "random_seed": fold_seed,
                    "selected_threshold": float(selected_threshold),
                    "threshold_policy": threshold_selection_meta.get("policy"),
                    "selection_scope": threshold_selection_meta.get("selection_scope"),
                }
            )
            pred_df = pd.DataFrame(
                {
                    "participant_id": pid_test.values,
                    "repeat_id": repeat_id,
                    "fold_id": fold_id,
                    "random_seed": fold_seed,
                    "y_true": y_test.values,
                    "y_pred": y_pred_test,
                    "p_hat": y_proba_test,
                    "candidate_manifest_path": str(manifest_path),
                }
            )
        else:
            y_proba_test = model.predict_proba(X_test_selected)
            y_pred_test = model.predict(X_test_selected)
            class_values = [int(c) for c in getattr(model, "classes_", target_labels)]
            fold_metrics, _ = evaluate_multiclass(y_test, y_pred_test, y_proba_test, class_values)
            pred_df = pd.DataFrame(
                {
                    "participant_id": pid_test.values,
                    "repeat_id": repeat_id,
                    "fold_id": fold_id,
                    "random_seed": fold_seed,
                    "y_true": y_test.values,
                    "y_pred": y_pred_test,
                    "candidate_manifest_path": str(manifest_path),
                }
            )
            for class_idx, cls in enumerate(class_values):
                pred_df[f"p_class_{cls}"] = y_proba_test[:, class_idx]
            if not {
                "pairwise_view",
                "supporting_contrasts",
                "contrast_support_count",
                "dosage_candidate_tier",
            }.issubset(set(manifest_df.columns)):
                raise RuntimeError(
                    "Signal-discovery dosage mode requires provenance fields in the fold-local candidate manifest."
                )

        fold_metrics_rows.append(
            {
                "repeat_id": repeat_id,
                "fold_id": fold_id,
                "random_seed": fold_seed,
                "n_train": int(len(X_train_selected)),
                "n_test": int(len(X_test_selected)),
                "candidate_count": int(len(candidate_columns)),
                "candidate_manifest_path": str(manifest_path),
                **{
                    k: v
                    for k, v in fold_metrics.items()
                    if not isinstance(v, (dict, list))
                },
            }
        )
        oof_predictions.append(pred_df)

    if not oof_predictions:
        raise RuntimeError("Signal-discovery nested resampling did not produce any outer-fold predictions.")

    run_tag = build_run_tag(
        model_type=args.model_type,
        feature_token=str(signal_discovery_context.get("screening_mode")),
        stamp=stamp,
        resolved_target_col=resolved_target_col,
        target_profile=None,
        investigation_id=str(investigation_context["investigation_id"]),
        target_name=target_name,
        recency_policy_id=recency_policy_id,
        run_tag_suffix=args.run_tag_suffix,
    )
    output_paths = build_output_paths(run_dir, run_tag)
    signal_output_paths = build_signal_discovery_output_paths(run_dir, run_tag)

    predictions_df = pd.concat(oof_predictions, ignore_index=True)
    fold_metrics_df = pd.DataFrame(fold_metrics_rows)
    screening_summary_df = (
        pd.concat(screening_summary_rows, ignore_index=True)
        if screening_summary_rows
        else pd.DataFrame()
    )

    if target_type == "binary":
        eval_metrics = evaluate_binary_predictions(
            predictions_df["y_true"].astype(int),
            predictions_df["y_pred"].astype(int).to_numpy(),
            predictions_df["p_hat"].astype(float).to_numpy(),
        )
        selected_threshold = float(np.mean([row["selected_threshold"] for row in fold_threshold_rows]))
        threshold_selection_meta = {
            "policy": args.threshold_policy,
            "selected_threshold": selected_threshold,
            "fold_thresholds": fold_threshold_rows,
            "selection_scope": "fold_local_training_only_oof_inner_cv",
        }
        _, curve_df = evaluate_binary(
            predictions_df["y_true"].astype(int),
            predictions_df["p_hat"].astype(float).to_numpy(),
            selected_threshold,
        )
        threshold_sweep_df = build_threshold_sweep(
            predictions_df["y_true"].astype(int),
            predictions_df["p_hat"].astype(float).to_numpy(),
        )
        save_curves(
            predictions_df["y_true"].astype(int),
            predictions_df["p_hat"].astype(float).to_numpy(),
            output_paths["roc_plot"],
            output_paths["pr_plot"],
        )
    else:
        class_prob_cols = [c for c in predictions_df.columns if c.startswith("p_class_")]
        class_values = [int(c.replace("p_class_", "")) for c in class_prob_cols]
        y_proba = predictions_df[class_prob_cols].to_numpy(dtype=float)
        eval_metrics, curve_df = evaluate_multiclass(
            predictions_df["y_true"].astype(int),
            predictions_df["y_pred"].astype(int).to_numpy(),
            y_proba,
            class_values,
        )
        threshold_selection_meta = {
            "policy": "multiclass_no_threshold",
            "selected_threshold": None,
            "selection_scope": "not_applicable",
        }
        threshold_sweep_df = pd.DataFrame(
            columns=[
                "threshold",
                "accuracy",
                "balanced_accuracy",
                "precision",
                "recall",
                "f1",
                "sensitivity",
                "specificity",
            ]
        )
        save_multiclass_placeholder_plots(output_paths["roc_plot"], output_paths["pr_plot"], target_labels)

    candidate_counter = (
        pd.concat([frame[["feature_column"]] for frame in manifest_frames], ignore_index=True)["feature_column"]
        .value_counts()
        .sort_index()
        if manifest_frames
        else pd.Series(dtype=int)
    )
    selection_summary_df = (
        candidate_counter.rename_axis("feature")
        .reset_index(name="selection_count")
        .assign(selection_frequency=lambda df: df["selection_count"] / max(len(manifest_frames), 1))
    )
    selection_summary_df.to_csv(signal_output_paths["selection_summary"], index=False)

    baseline_metrics_all = parse_locked_baseline_metrics(baseline_reference)
    baseline_metrics_for_model = baseline_metrics_all.get(args.model_type, {})
    delta_metrics = {}
    for metric_name, baseline_value in baseline_metrics_for_model.items():
        current_value = eval_metrics.get(metric_name)
        if current_value is None or isinstance(current_value, (dict, list)):
            continue
        delta_metrics[f"{metric_name}_delta"] = float(current_value) - float(baseline_value)
    baseline_delta_payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_reference": baseline_reference,
        "model_type": args.model_type,
        "target_name": target_name,
        "baseline_metrics": baseline_metrics_for_model,
        "current_metrics": {
            k: v for k, v in eval_metrics.items() if not isinstance(v, (dict, list))
        },
        "metric_deltas": delta_metrics,
        "comparison_note": (
            "same_target_baseline_delta"
            if target_name == "promoter_carrier"
            else "baseline_family_reference_only_target_differs"
        ),
    }
    signal_output_paths["baseline_delta"].write_text(json.dumps(baseline_delta_payload, indent=2))
    if not signal_output_paths["baseline_delta"].exists():
        raise RuntimeError("Signal-discovery baseline-delta digest was not written.")

    metrics_payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_tag": run_tag,
        "run_dir": str(run_dir),
        "stamp": stamp,
        "model_type": args.model_type,
        "matrix_path": str(matrix_path),
        "preprocessing_spec_path": None,
        "target_col": resolved_target_col,
        "target_profile": None,
        "target_resolution": target_resolution_meta,
        "target_type": target_type,
        "target_labels": target_labels,
        "args": {
            "random_state": int(args.random_state),
            "threshold": float(args.threshold),
            "threshold_policy": args.threshold_policy,
            "min_specificity_floor": float(args.min_specificity_floor),
            "run_tag_suffix": args.run_tag_suffix,
            "feature_set": None,
            "feature_profile": None,
            "target_col": resolved_target_col,
            "target_profile": None,
            "investigation_id": args.investigation_id,
            "screening_scenario_csv": str(Path(args.screening_scenario_csv).resolve()),
            "screening_scenario_id": screening_scenario["screening_scenario_id"],
            "driver_manifest": str(driver_manifest_path),
            "baseline_reference": baseline_reference,
            "nn_hidden_layers": [int(v) for v in parse_hidden_layers(args.nn_hidden_layers)],
            "nn_alpha": float(args.nn_alpha),
            "nn_learning_rate_init": float(args.nn_learning_rate_init),
            "nn_max_iter": int(args.nn_max_iter),
            "nn_early_stopping": bool(args.nn_early_stopping),
            "nn_permutation_repeats": int(args.nn_permutation_repeats),
            "nn_permutation_max_rows": int(args.nn_permutation_max_rows),
            "epv_warn_threshold": float(args.epv_warn_threshold),
            "epv_severe_threshold": float(args.epv_severe_threshold),
            "class_weight_mode": args.class_weight_mode,
            "calibration_mode": args.calibration_mode,
        },
        "data_prep": prep_meta,
        "split_summary": {
            "split_mode": "repeated_stratified_outer_cv",
            "outer_n_splits": outer_n_splits,
            "outer_n_repeats": outer_n_repeats,
            "n_outer_folds_completed": int(len(fold_metrics_df)),
            "class_dist_full": {str(k): int(v) for k, v in y.value_counts().sort_index().items()},
        },
        "feature_selection": {
            "selection_mode": "signal_discovery_fold_local_shared_candidate_manifests",
            "discovery_input_feature_count": int(len(raw_feature_columns)),
            "candidate_manifest_paths": manifest_paths,
            "selection_summary_path": str(signal_output_paths["selection_summary"]),
            "screening_summary_path": str(signal_output_paths["screening_summary"]),
            "grouped_anchor_comparison_only": True,
            "grouped_anchor_artifact_path": signal_artifact_paths["grouped_anchor_comparison_path"],
        },
        "investigation_context": investigation_context,
        "cohort_filter": cohort_filter_meta,
        "predictor_policy": {
            "grouped_anchor_comparison_only": True,
            "grouped_anchor_artifact_path": signal_artifact_paths["grouped_anchor_comparison_path"],
            "grouped_anchor_not_model_input": True,
            "baseline_reference": baseline_reference,
        },
        "threshold_selection": threshold_selection_meta,
        "preprocessing": {
            "policy_id": "not_applicable_signal_discovery_raw_code_path",
            "artifacts_path": str(output_paths["preprocessing_artifacts"]),
            "train_threshold_oof_path": str(output_paths["train_threshold_oof"]),
        },
        "epv_diagnostics": {
            "warning_level": "not_applicable_signal_discovery_nested_cv",
            "warning_reasons": [],
        },
        "metrics": eval_metrics,
        "signal_discovery": {
            "branch_mode": signal_discovery_context.get("branch_mode"),
            "screening_mode": signal_discovery_context.get("screening_mode"),
            "screening_scenario": screening_scenario,
            "baseline_delta_path": str(signal_output_paths["baseline_delta"]),
            "created_from_training_only": True,
        },
    }
    output_paths["preprocessing_artifacts"].write_text(
        json.dumps(
            {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "run_tag": run_tag,
                "model_type": args.model_type,
                "preprocessing_mode": "not_applicable_signal_discovery_raw_code_path",
                "outer_fold_thresholds": fold_threshold_rows,
            },
            indent=2,
        )
    )
    output_paths["metrics"].write_text(json.dumps(metrics_payload, indent=2))
    pd.DataFrame(columns=["participant_id", "y_true", "p_hat_oof"]).to_csv(
        output_paths["train_threshold_oof"], index=False
    )

    predictions_df.to_csv(output_paths["predictions"], index=False)
    curve_df.to_csv(output_paths["curves_table"], index=False)
    threshold_sweep_df.to_csv(output_paths["threshold_sweep"], index=False)
    fold_metrics_df.to_csv(signal_output_paths["fold_metrics"], index=False)
    screening_summary_df.to_csv(signal_output_paths["screening_summary"], index=False)

    feature_effects_df = selection_summary_df.rename(columns={"feature": "feature"})
    feature_effects_df.to_csv(output_paths["feature_effects"], index=False)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_tag": run_tag,
        "model_type": args.model_type,
        "feature_set": None,
        "feature_profile": None,
        "feature_profile_resolved": None,
        "target_col": resolved_target_col,
        "target_profile": None,
        "investigation_id": args.investigation_id,
        "recency_policy_id": recency_policy_id,
        "cohort_filter": cohort_filter_meta.get("cohort_filter"),
        "threshold_policy": args.threshold_policy,
        "min_specificity_floor": float(args.min_specificity_floor),
        "class_weight_mode": args.class_weight_mode,
        "calibration_mode": args.calibration_mode,
        "selected_threshold": threshold_selection_meta.get("selected_threshold"),
        "epv_estimate": None,
        "epv_warning_level": "not_applicable_signal_discovery_nested_cv",
        "epv_minority_class_events_train": None,
        "epv_predictor_count": int(len(raw_feature_columns)),
        "run_tag_suffix": args.run_tag_suffix,
        "target_type": target_type,
        "stamp": stamp,
        "signal_discovery_context": signal_discovery_context,
        "outputs": {
            **{k: str(v) for k, v in output_paths.items()},
            **{k: str(v) for k, v in signal_output_paths.items()},
        },
        "candidate_manifest_paths": manifest_paths,
    }
    output_paths["manifest"].write_text(json.dumps(manifest, indent=2))

    if not signal_output_paths["baseline_delta"].exists():
        raise RuntimeError("Baseline-delta digest missing after signal-discovery run finalization.")

    print("Signal-discovery output files:")
    for key, path in {**output_paths, **signal_output_paths}.items():
        print(f"- {key}: {path}")


# %% ---------------------------------------------------------------------------
# STEP 3 helpers: training-aware preprocessing
# -----------------------------------------------------------------------------
def one_hot_column_name(column: str, level: str, separator: str) -> str:
    safe_level = re.sub(r"[^A-Za-z0-9_]+", "_", str(level).strip()).strip("_") or "Unknown"
    return f"{column}{separator}{safe_level}"


def fallback_column_policy(column: str) -> dict[str, Any]:
    return {
        "feature_class": "continuous",
        "clinically_central": False,
        "missingness_policy_class": "numeric_selective",
        "protected_from_scaling": False,
        "protected_from_log": True,
        "eligible_for_log": False,
        "eligible_for_winsor": False,
        "eligible_for_scaling": True,
    }


def fit_training_preprocessor(
    X_train_raw: pd.DataFrame,
    preprocessing_spec: dict[str, Any],
    model_type: str,
    fit_scope: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    missingness_policy = preprocessing_spec.get("missingness_policy", {})
    categorical_policy = preprocessing_spec.get("categorical_policy", {})
    winsor_policy = preprocessing_spec.get("winsor_policy", {})
    column_policies = preprocessing_spec.get("column_policies", {})
    unknown_token = str(categorical_policy.get("unknown_token", "Unknown"))
    separator = str(categorical_policy.get("one_hot_prefix_separator", "__"))
    low_missing_threshold = float(missingness_policy.get("numeric_indicator_threshold_lt", 0.3))
    elevated_missing_threshold = float(missingness_policy.get("numeric_elevated_keep_threshold_lte", 0.6))
    categorical_unknown_drop_lr_gt = float(
        missingness_policy.get("categorical_unknown_drop_threshold_lr_gt", 0.5)
    )
    winsor_upper_q = float(winsor_policy.get("upper_quantile", 0.995))
    default_recency_sentinel = float(preprocessing_spec.get("default_recency_sentinel_days", 0.0))

    processed_frames: list[pd.DataFrame] = []
    final_feature_columns: list[str] = []
    artifacts: dict[str, Any] = {
        "model_type": model_type,
        "fit_scope": fit_scope,
        "policy_id": preprocessing_spec.get("policy_id"),
        "policy_version": preprocessing_spec.get("policy_version"),
        "policy_path": preprocessing_spec.get("policy_path"),
        "categorical_unknown_token": unknown_token,
        "selected_raw_columns": list(X_train_raw.columns),
        "column_states": {},
        "imputation_values": {},
        "binary_impute_values": {},
        "missing_indicator_columns": [],
        "category_maps": {},
        "winsor_caps": {},
        "log_transform_columns": [],
        "scaled_columns": [],
        "scaling_means": {},
        "scaling_stds": {},
        "dropped_columns": {},
        "elevated_missingness_retained_columns": {},
        "recency_sentinel_columns": [],
        "recency_sentinel_values": {},
        "categorical_unknown_drop_columns": [],
        "calibration": {
            "enabled": False,
            "mode": "none",
            "fit_scope": "training_only_fold_internal",
        },
    }

    for column in X_train_raw.columns:
        policy = dict(fallback_column_policy(column))
        policy.update(column_policies.get(column, {}))
        feature_class = str(policy.get("feature_class", "continuous"))
        state: dict[str, Any] = {
            "feature_class": feature_class,
            "clinically_central": bool(policy.get("clinically_central", False)),
        }

        if feature_class == "low_card_categorical":
            series = X_train_raw[column].map(clean_token).replace("", unknown_token).fillna(unknown_token)
            unknown_share = float((series == unknown_token).mean())
            drop_for_unknown = model_type == "lr" and unknown_share > categorical_unknown_drop_lr_gt
            state.update(
                {
                    "transform_kind": "categorical",
                    "unknown_share_train": unknown_share,
                    "drop_for_model": bool(drop_for_unknown),
                }
            )
            if drop_for_unknown:
                reason = (
                    f"categorical_unknown_share_{unknown_share:.4f}_exceeds_lr_threshold_"
                    f"{categorical_unknown_drop_lr_gt:.4f}"
                )
                artifacts["categorical_unknown_drop_columns"].append(column)
                artifacts["dropped_columns"][column] = {
                    "reason": reason,
                    "feature_class": feature_class,
                    "missingness_train_pct": unknown_share,
                }
                state["drop_reason"] = reason
                artifacts["column_states"][column] = state
                continue

            levels = sorted(set(series.tolist()) | {unknown_token})
            category_map = {level: one_hot_column_name(column, level, separator) for level in levels}
            encoded = pd.DataFrame(
                {
                    out_col: (series == level).astype(int)
                    for level, out_col in category_map.items()
                },
                index=X_train_raw.index,
            )
            artifacts["category_maps"][column] = category_map
            state["transform_kind"] = "categorical"
            state["category_levels"] = levels
            state["one_hot_columns"] = list(category_map.values())
            artifacts["column_states"][column] = state
            processed_frames.append(encoded)
            final_feature_columns.extend(encoded.columns.tolist())
            continue

        series = pd.to_numeric(X_train_raw[column], errors="coerce")
        missing_pct = float(series.isna().mean())
        state["missingness_train_pct"] = missing_pct

        if feature_class == "binary":
            fill_value = float(series.mode(dropna=True).iloc[0]) if not series.dropna().empty else 0.0
            if series.isna().any():
                series = series.fillna(fill_value)
                artifacts["binary_impute_values"][column] = fill_value
            state.update(
                {
                    "transform_kind": "binary",
                    "fill_value": fill_value,
                    "output_columns": [column],
                }
            )
            artifacts["column_states"][column] = state
            processed_frames.append(pd.DataFrame({column: series.astype(float)}, index=X_train_raw.index))
            final_feature_columns.append(column)
            continue

        drop_reason: str | None = None
        elevated_retention = False
        if missing_pct > elevated_missing_threshold:
            drop_reason = f"missingness_gt_{elevated_missing_threshold:.2f}"
        elif missing_pct >= low_missing_threshold and not bool(policy.get("clinically_central", False)):
            drop_reason = (
                f"missingness_between_{low_missing_threshold:.2f}_and_{elevated_missing_threshold:.2f}"
                "_without_clinically_central_flag"
            )
        elif missing_pct >= low_missing_threshold:
            elevated_retention = True

        if drop_reason:
            artifacts["dropped_columns"][column] = {
                "reason": drop_reason,
                "feature_class": feature_class,
                "missingness_train_pct": missing_pct,
            }
            state["drop_reason"] = drop_reason
            state["transform_kind"] = "dropped"
            artifacts["column_states"][column] = state
            continue

        indicator_column = None
        if series.isna().any():
            indicator_column = f"{column}__missing"
            indicator_series = series.isna().astype(int)
            processed_frames.append(pd.DataFrame({indicator_column: indicator_series}, index=X_train_raw.index))
            final_feature_columns.append(indicator_column)
            artifacts["missing_indicator_columns"].append(indicator_column)

        if feature_class == "recency":
            fill_value = default_recency_sentinel
            artifacts["recency_sentinel_columns"].append(column)
            artifacts["recency_sentinel_values"][column] = fill_value
        else:
            fill_value = float(series.median()) if not series.dropna().empty else 0.0
            artifacts["imputation_values"][column] = fill_value

        series = series.fillna(fill_value).astype(float)
        log_applied = False
        if (
            model_type in {"lr", "nn"}
            and bool(policy.get("eligible_for_log", False))
            and not series.empty
            and bool((series >= 0).all())
        ):
            series = np.log1p(series)
            log_applied = True
            artifacts["log_transform_columns"].append(column)

        winsor_mode = winsor_policy.get("apply_to_model_families", {}).get(model_type)
        winsor_cap = None
        if bool(policy.get("eligible_for_winsor", False)) and winsor_mode:
            winsor_cap = float(series.quantile(winsor_upper_q)) if not series.dropna().empty else None
            if winsor_cap is not None:
                series = series.clip(upper=winsor_cap)
                artifacts["winsor_caps"][column] = winsor_cap

        scale_mean = None
        scale_std = None
        if model_type in {"lr", "nn"} and bool(policy.get("eligible_for_scaling", False)):
            scale_mean = float(series.mean())
            scale_std = float(series.std(ddof=0))
            artifacts["scaling_means"][column] = scale_mean
            artifacts["scaling_stds"][column] = scale_std
            if scale_std > 0:
                series = (series - scale_mean) / scale_std
            else:
                series = pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
            artifacts["scaled_columns"].append(column)

        if elevated_retention:
            artifacts["elevated_missingness_retained_columns"][column] = {
                "missingness_train_pct": missing_pct,
                "feature_class": feature_class,
            }

        state.update(
            {
                "transform_kind": "numeric",
                "indicator_column": indicator_column,
                "fill_value": fill_value,
                "log_applied": bool(log_applied),
                "winsor_cap": winsor_cap,
                "scale_mean": scale_mean,
                "scale_std": scale_std,
                "output_columns": [column],
            }
        )
        artifacts["column_states"][column] = state
        processed_frames.append(pd.DataFrame({column: series}, index=X_train_raw.index))
        final_feature_columns.append(column)

    if processed_frames:
        processed = pd.concat(processed_frames, axis=1)
    else:
        processed = pd.DataFrame(index=X_train_raw.index)

    artifacts["final_feature_columns"] = final_feature_columns
    artifacts["final_feature_count"] = int(len(final_feature_columns))
    artifacts["dropped_column_count"] = int(len(artifacts["dropped_columns"]))
    return processed, artifacts


def apply_fitted_preprocessor(
    X_input_raw: pd.DataFrame,
    preprocessing_artifacts: dict[str, Any],
) -> pd.DataFrame:
    category_maps = preprocessing_artifacts.get("category_maps", {})
    unknown_token = str(preprocessing_artifacts.get("categorical_unknown_token", "Unknown"))
    if preprocessing_artifacts.get("selected_raw_columns"):
        column_order = list(preprocessing_artifacts["selected_raw_columns"])
    else:
        column_order = list(X_input_raw.columns)

    frames: list[pd.DataFrame] = []
    for column in column_order:
        state = preprocessing_artifacts.get("column_states", {}).get(column)
        if not state or state.get("transform_kind") == "dropped":
            continue
        if column in X_input_raw.columns:
            raw_series = X_input_raw[column]
        else:
            raw_series = pd.Series(np.nan, index=X_input_raw.index)

        transform_kind = str(state.get("transform_kind"))
        if transform_kind == "categorical":
            category_map = category_maps.get(column, {})
            allowed_levels = set(category_map.keys())
            series = raw_series.map(clean_token).replace("", unknown_token).fillna(unknown_token)
            series = series.map(lambda v: v if v in allowed_levels else unknown_token)
            encoded = pd.DataFrame(
                {
                    out_col: (series == level).astype(int)
                    for level, out_col in category_map.items()
                },
                index=X_input_raw.index,
            )
            frames.append(encoded)
            continue

        series = pd.to_numeric(raw_series, errors="coerce")
        indicator_column = state.get("indicator_column")
        if indicator_column:
            frames.append(
                pd.DataFrame({str(indicator_column): series.isna().astype(int)}, index=X_input_raw.index)
            )

        fill_value = float(state.get("fill_value", 0.0))
        series = series.fillna(fill_value).astype(float)
        if bool(state.get("log_applied", False)):
            series = np.log1p(series)
        winsor_cap = state.get("winsor_cap")
        if winsor_cap is not None:
            series = series.clip(upper=float(winsor_cap))
        scale_mean = state.get("scale_mean")
        scale_std = state.get("scale_std")
        if scale_mean is not None and scale_std is not None:
            if float(scale_std) > 0:
                series = (series - float(scale_mean)) / float(scale_std)
            else:
                series = pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
        frames.append(pd.DataFrame({column: series}, index=X_input_raw.index))

    if frames:
        transformed = pd.concat(frames, axis=1)
    else:
        transformed = pd.DataFrame(index=X_input_raw.index)

    expected_columns = preprocessing_artifacts.get("final_feature_columns", [])
    if expected_columns:
        missing = [col for col in expected_columns if col not in transformed.columns]
        for col in missing:
            transformed[col] = 0.0
        transformed = transformed[expected_columns]
    return transformed


def resolve_threshold_inner_splitter(
    y_train: pd.Series,
    random_state: int,
    requested_splits: int,
) -> tuple[StratifiedKFold | None, dict[str, Any]]:
    class_counts = y_train.value_counts().sort_index()
    if class_counts.empty:
        return None, {"available": False, "reason": "empty_training_target"}
    min_class_n = int(class_counts.min())
    n_splits = min(int(requested_splits), min_class_n)
    if n_splits < 2:
        return None, {
            "available": False,
            "reason": f"least_populated_class_has_{min_class_n}_sample(s)",
            "class_counts_train": {str(k): int(v) for k, v in class_counts.items()},
        }
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=int(random_state))
    return splitter, {
        "available": True,
        "n_splits": int(n_splits),
        "class_counts_train": {str(k): int(v) for k, v in class_counts.items()},
    }


def generate_training_oof_probabilities(
    X_train_raw: pd.DataFrame,
    y_train: pd.Series,
    preprocessing_spec: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    requested_splits = int(
        preprocessing_spec.get("evaluation_defaults", {}).get("threshold_inner_cv_folds", 5)
    )
    splitter, split_meta = resolve_threshold_inner_splitter(
        y_train=y_train,
        random_state=int(args.random_state),
        requested_splits=requested_splits,
    )
    if splitter is None:
        return None, {
            "selection_scope": "fallback_fixed_threshold_due_to_insufficient_inner_cv_support",
            "inner_cv": split_meta,
            "inner_fold_preprocessing_artifacts": [],
        }

    oof_proba = np.full(len(y_train), np.nan, dtype=float)
    inner_artifacts: list[dict[str, Any]] = []
    for fold_id, (fit_idx, val_idx) in enumerate(splitter.split(X_train_raw, y_train)):
        X_fit_raw = X_train_raw.iloc[fit_idx].reset_index(drop=True)
        y_fit = y_train.iloc[fit_idx].reset_index(drop=True)
        X_val_raw = X_train_raw.iloc[val_idx].reset_index(drop=True)

        X_fit, fold_artifacts = fit_training_preprocessor(
            X_train_raw=X_fit_raw,
            preprocessing_spec=preprocessing_spec,
            model_type=args.model_type,
            fit_scope=f"threshold_inner_fold_{int(fold_id)}",
        )
        X_val = apply_fitted_preprocessor(X_val_raw, fold_artifacts)
        if X_fit.shape[1] == 0:
            raise RuntimeError("Threshold inner-CV preprocessing dropped all predictors.")

        model = build_model(
            model_type=args.model_type,
            random_state=int(args.random_state + fold_id + 1),
            target_type="binary",
            nn_hidden_layers=parse_hidden_layers(args.nn_hidden_layers),
            nn_alpha=args.nn_alpha,
            nn_learning_rate_init=args.nn_learning_rate_init,
            nn_max_iter=args.nn_max_iter,
            nn_early_stopping=args.nn_early_stopping,
            class_weight_mode=args.class_weight_mode,
        )
        model.fit(X_fit, y_fit)
        class_values = list(getattr(model, "classes_", [0, 1]))
        if 1 not in class_values:
            raise RuntimeError(f"Inner-CV threshold model missing positive class 1: {class_values}")
        pos_idx = class_values.index(1)
        fold_proba = model.predict_proba(X_val)[:, pos_idx]
        oof_proba[val_idx] = fold_proba
        inner_artifacts.append(
            {
                "fold_id": int(fold_id),
                "n_fit": int(len(X_fit)),
                "n_val": int(len(X_val)),
                "preprocessing": fold_artifacts,
            }
        )

    if np.isnan(oof_proba).any():
        raise RuntimeError("Threshold inner-CV OOF probabilities contain NaN values.")
    return oof_proba, {
        "selection_scope": "training_only_oof_inner_cv",
        "inner_cv": split_meta,
        "inner_fold_preprocessing_artifacts": inner_artifacts,
    }


def generate_signal_discovery_training_oof_probabilities(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    args: argparse.Namespace,
    random_state_seed: int,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    splitter, split_meta = resolve_threshold_inner_splitter(
        y_train=y_train,
        random_state=int(random_state_seed),
        requested_splits=5,
    )
    if splitter is None:
        return None, {
            "selection_scope": "fallback_fixed_threshold_due_to_insufficient_inner_cv_support",
            "inner_cv": split_meta,
        }

    oof_proba = np.full(len(y_train), np.nan, dtype=float)
    for fold_id, (fit_idx, val_idx) in enumerate(splitter.split(X_train, y_train)):
        model = build_model(
            model_type=args.model_type,
            random_state=int(random_state_seed + fold_id + 1),
            target_type="binary",
            nn_hidden_layers=parse_hidden_layers(args.nn_hidden_layers),
            nn_alpha=args.nn_alpha,
            nn_learning_rate_init=args.nn_learning_rate_init,
            nn_max_iter=args.nn_max_iter,
            nn_early_stopping=args.nn_early_stopping,
            class_weight_mode=args.class_weight_mode,
        )
        X_fit = X_train.iloc[fit_idx].reset_index(drop=True)
        y_fit = y_train.iloc[fit_idx].reset_index(drop=True)
        X_val = X_train.iloc[val_idx].reset_index(drop=True)
        model.fit(X_fit, y_fit)
        class_values = list(getattr(model, "classes_", [0, 1]))
        if 1 not in class_values:
            raise RuntimeError(f"Signal-discovery inner-CV model missing positive class 1: {class_values}")
        pos_idx = class_values.index(1)
        oof_proba[val_idx] = model.predict_proba(X_val)[:, pos_idx]

    if np.isnan(oof_proba).any():
        raise RuntimeError("Signal-discovery threshold inner-CV OOF probabilities contain NaN values.")
    return oof_proba, {
        "selection_scope": "training_only_oof_inner_cv",
        "inner_cv": split_meta,
    }


# %% ---------------------------------------------------------------------------
# STEP 3/4 helpers: input preparation, split, and model fit
# -----------------------------------------------------------------------------
def prepare_modelling_inputs(
    matrix: pd.DataFrame,
    selected_cols: list[str],
    target_col: str,
    target_values: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict[str, Any], str, list[int]]:
    X = matrix[selected_cols].copy()
    if target_values is None:
        if target_col not in matrix.columns:
            raise RuntimeError(f"Target column not found in matrix: {target_col}")
        y = pd.to_numeric(matrix[target_col], errors="coerce")
    else:
        y = pd.to_numeric(target_values.reindex(matrix.index), errors="coerce")
    pid = matrix["participant_id"].copy()

    if y.isna().any():
        raise RuntimeError(f"{target_col} contains NaN values")

    y = y.astype(int)
    target_labels = sorted([int(v) for v in pd.Series(y).dropna().unique().tolist()])
    if len(target_labels) < 2:
        raise RuntimeError(
            f"{target_col} must contain at least 2 classes. Found: {target_labels}"
        )
    target_type = "binary" if len(target_labels) == 2 else "multiclass"

    binary_label_mapping: dict[int, int] | None = None
    if target_type == "binary" and target_labels != [0, 1]:
        binary_label_mapping = {target_labels[0]: 0, target_labels[1]: 1}
        y = y.map(binary_label_mapping).astype(int)
        target_labels = [0, 1]

    prep_meta = {
        "n_rows": int(len(matrix)),
        "n_raw_predictors_selected": int(len(selected_cols)),
        "missing_cells_before_preprocessing": int(X.isna().sum().sum()),
        "target_col": target_col,
        "target_type": target_type,
        "target_labels": target_labels,
        "target_class_distribution_full": {
            str(k): int(v) for k, v in y.value_counts(dropna=False).sort_index().items()
        },
        "target_prevalence_full": float(y.mean()) if target_type == "binary" else None,
        "raw_predictor_dtypes": {str(col): str(X[col].dtype) for col in X.columns},
    }
    if binary_label_mapping is not None:
        prep_meta["binary_label_mapping"] = binary_label_mapping
    return X, y, pid, prep_meta, target_type, target_labels


def split_dataset(
    X: pd.DataFrame,
    y: pd.Series,
    pid: pd.Series,
    test_size: float,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series, dict[str, Any]]:
    class_counts = y.value_counts().sort_index()
    n_rows = int(len(y))
    n_classes = int(class_counts.shape[0])
    n_test = int(np.ceil(n_rows * test_size))
    n_test = max(1, min(n_rows - 1, n_test))
    n_train = n_rows - n_test

    fallback_reasons: list[str] = []
    min_class_n = int(class_counts.min()) if not class_counts.empty else 0
    if min_class_n < 2:
        fallback_reasons.append(f"least populated class has {min_class_n} sample(s) (<2)")
    if n_test < n_classes:
        fallback_reasons.append(f"test partition size {n_test} < number of classes {n_classes}")
    if n_train < n_classes:
        fallback_reasons.append(f"train partition size {n_train} < number of classes {n_classes}")

    use_stratify = len(fallback_reasons) == 0
    stratify_arg = y if use_stratify else None
    if not use_stratify:
        print("[STEP 3] Stratified split disabled:", "; ".join(fallback_reasons))

    candidate_random_states = [random_state] if use_stratify else [random_state + i for i in range(10)]
    selected_split = None
    selected_random_state: int | None = None
    for rs in candidate_random_states:
        split = train_test_split(
            X,
            y,
            pid,
            test_size=test_size,
            random_state=rs,
            stratify=stratify_arg,
        )
        y_train_candidate = split[2]
        y_test_candidate = split[3]
        if y_train_candidate.nunique() == n_classes and y_test_candidate.nunique() == n_classes:
            selected_split = split
            selected_random_state = rs
            break

    if selected_split is None:
        raise RuntimeError(
            "Unable to produce train/test splits that preserve all classes in both partitions. "
            "Adjust --test-size or collect more samples for sparse classes."
        )

    X_train, X_test, y_train, y_test, pid_train, pid_test = selected_split
    split_meta = {
        "split_mode": "stratified" if use_stratify else "unstratified_fallback",
        "stratified": bool(use_stratify),
        "stratify_fallback_reason": None if use_stratify else "; ".join(fallback_reasons),
        "effective_random_state": int(selected_random_state if selected_random_state is not None else random_state),
        "attempted_random_states": [int(v) for v in candidate_random_states],
        "n_classes": n_classes,
        "class_counts_full": {str(k): int(v) for k, v in class_counts.items()},
    }
    return X_train, X_test, y_train, y_test, pid_train, pid_test, split_meta


def compute_epv_diagnostics(
    y_train: pd.Series,
    n_predictors: int,
    target_type: str,
    warn_threshold: float,
    severe_threshold: float,
) -> dict[str, Any]:
    class_counts = y_train.value_counts().sort_index()
    minority_class = int(class_counts.idxmin()) if not class_counts.empty else None
    minority_events = int(class_counts.min()) if not class_counts.empty else 0
    epv = float(minority_events / n_predictors) if n_predictors > 0 else None

    warning_level = "none"
    warning_reasons: list[str] = []
    if epv is None:
        warning_level = "warn"
        warning_reasons.append("EPV not computable because predictor count is zero.")
    else:
        if epv < float(severe_threshold):
            warning_level = "severe"
            warning_reasons.append(
                f"Estimated EPV {epv:.4f} is below severe threshold {float(severe_threshold):.4f}."
            )
        elif epv < float(warn_threshold):
            warning_level = "warn"
            warning_reasons.append(
                f"Estimated EPV {epv:.4f} is below warn threshold {float(warn_threshold):.4f}."
            )

    return {
        "target_type": target_type,
        "predictor_count": int(n_predictors),
        "minority_class_label": minority_class,
        "minority_class_events_train": int(minority_events),
        "epv_estimate": epv,
        "warn_threshold": float(warn_threshold),
        "severe_threshold": float(severe_threshold),
        "warning_level": warning_level,
        "warning_reasons": warning_reasons,
        "class_counts_train": {str(k): int(v) for k, v in class_counts.items()},
    }


def parse_hidden_layers(value: str) -> tuple[int, ...]:
    tokens = [tok.strip() for tok in str(value).split(",") if tok.strip()]
    if not tokens:
        raise ValueError(f"Invalid --nn-hidden-layers value: {value}")
    layers = tuple(int(tok) for tok in tokens)
    if any(v <= 0 for v in layers):
        raise ValueError(f"Hidden-layer widths must be positive integers: {value}")
    return layers


def build_model(
    model_type: str,
    random_state: int,
    target_type: str,
    nn_hidden_layers: tuple[int, ...],
    nn_alpha: float,
    nn_learning_rate_init: float,
    nn_max_iter: int,
    nn_early_stopping: bool,
    class_weight_mode: str = "none",
):
    class_weight = None if class_weight_mode == "none" else "balanced"
    if model_type == "lr":
        if target_type == "multiclass":
            return LogisticRegression(
                solver="lbfgs",
                class_weight=class_weight,
                max_iter=3000,
                random_state=random_state,
                multi_class="multinomial",
            )
        return LogisticRegression(
            solver="liblinear",
            class_weight=class_weight,
            max_iter=2000,
            random_state=random_state,
        )

    if model_type == "rf":
        return RandomForestClassifier(
            n_estimators=500,
            class_weight=class_weight,
            random_state=random_state,
            n_jobs=-1,
        )

    if model_type == "nn":
        return MLPClassifier(
            hidden_layer_sizes=nn_hidden_layers,
            activation="relu",
            solver="adam",
            alpha=float(nn_alpha),
            learning_rate_init=float(nn_learning_rate_init),
            max_iter=int(nn_max_iter),
            early_stopping=bool(nn_early_stopping),
            random_state=random_state,
        )

    raise ValueError(f"Unsupported model_type: {model_type}")


# %% ---------------------------------------------------------------------------
# STEP 5 helpers: evaluation
# -----------------------------------------------------------------------------
def build_threshold_sweep(y_true: pd.Series, y_proba: np.ndarray) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for threshold in np.linspace(0.05, 0.95, 91):
        y_pred = (y_proba >= threshold).astype(int)
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        sensitivity = float(tp / (tp + fn)) if (tp + fn) > 0 else float("nan")
        specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else float("nan")
        rows.append(
            {
                "threshold": float(threshold),
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
                "precision": float(precision_score(y_true, y_pred, zero_division=0)),
                "recall": float(recall_score(y_true, y_pred, zero_division=0)),
                "f1": float(f1_score(y_true, y_pred, zero_division=0)),
                "sensitivity": sensitivity,
                "specificity": specificity,
            }
        )
    return pd.DataFrame(rows)


def select_threshold_from_policy(
    policy: str,
    fixed_threshold: float,
    y_train: pd.Series,
    y_train_proba: np.ndarray,
    min_specificity_floor: float = 0.0,
) -> tuple[float, pd.DataFrame, dict[str, Any]]:
    sweep_df = build_threshold_sweep(y_train, y_train_proba)
    if policy == "fixed":
        selected = float(fixed_threshold)
        selection_meta = {
            "policy": "fixed",
            "selected_threshold": selected,
            "selection_metric": "fixed_value",
            "min_specificity_floor": None,
        }
        return selected, sweep_df, selection_meta

    if policy == "train_balanced_accuracy":
        ranked = sweep_df.sort_values(
            ["balanced_accuracy", "f1", "recall", "precision", "threshold"],
            ascending=[False, False, False, False, True],
        )
        best = ranked.iloc[0].to_dict()
        selected = float(best["threshold"])
        selection_meta = {
            "policy": "train_balanced_accuracy",
            "selected_threshold": selected,
            "selection_metric": "balanced_accuracy_then_f1_recall_precision",
            "train_selected_balanced_accuracy": float(best["balanced_accuracy"]),
            "train_selected_f1": float(best["f1"]),
            "train_selected_recall": float(best["recall"]),
            "train_selected_precision": float(best["precision"]),
            "train_selected_specificity": float(best["specificity"]),
            "min_specificity_floor": None,
        }
        return selected, sweep_df, selection_meta

    floor = float(min(max(min_specificity_floor, 0.0), 1.0))
    eligible = sweep_df.loc[sweep_df["specificity"] >= floor].copy()
    eligible_count_pre_fallback = int(len(eligible))
    fallback_used = False
    if eligible.empty:
        # Preserve run continuity: if no threshold meets the floor, fallback to the global optimum.
        eligible = sweep_df.copy()
        fallback_used = True

    ranked = eligible.sort_values(
        ["balanced_accuracy", "f1", "recall", "precision", "specificity", "threshold"],
        ascending=[False, False, False, False, False, True],
    )
    best = ranked.iloc[0].to_dict()
    selected = float(best["threshold"])
    selection_meta = {
        "policy": "train_balanced_accuracy_min_specificity",
        "selected_threshold": selected,
        "selection_metric": "balanced_accuracy_then_f1_recall_precision_specificity",
        "train_selected_balanced_accuracy": float(best["balanced_accuracy"]),
        "train_selected_f1": float(best["f1"]),
        "train_selected_recall": float(best["recall"]),
        "train_selected_precision": float(best["precision"]),
        "train_selected_specificity": float(best["specificity"]),
        "min_specificity_floor": floor,
        "eligible_threshold_count": eligible_count_pre_fallback,
        "fallback_used": bool(fallback_used),
    }
    return selected, sweep_df, selection_meta


def evaluate_binary(
    y_true: pd.Series,
    y_proba: np.ndarray,
    threshold: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    y_pred = (y_proba >= threshold).astype(int)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    sensitivity = float(tp / (tp + fn)) if (tp + fn) > 0 else float("nan")
    specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else float("nan")

    fpr, tpr, _ = roc_curve(y_true, y_proba)
    pr_precision, pr_recall, _ = precision_recall_curve(y_true, y_proba)

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "pr_auc": float(average_precision_score(y_true, y_proba)),
        "brier": float(brier_score_loss(y_true, y_proba)),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "threshold": float(threshold),
    }

    roc_df = pd.DataFrame(
        {
            "fpr": pd.Series(fpr, dtype=float),
            "tpr": pd.Series(tpr, dtype=float),
        }
    )
    pr_df = pd.DataFrame(
        {
            "precision": pd.Series(pr_precision, dtype=float),
            "recall": pd.Series(pr_recall, dtype=float),
        }
    )
    curve_df = roc_df.merge(pr_df, left_index=True, right_index=True, how="outer")
    return metrics, curve_df


def evaluate_multiclass(
    y_true: pd.Series,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    class_labels: list[int],
) -> tuple[dict[str, Any], pd.DataFrame]:
    cm = confusion_matrix(y_true, y_pred, labels=class_labels)
    precision_arr, recall_arr, f1_arr, support_arr = precision_recall_fscore_support(
        y_true, y_pred, labels=class_labels, zero_division=0
    )

    per_class_rows = []
    for idx, cls in enumerate(class_labels):
        per_class_rows.append(
            {
                "class_label": int(cls),
                "precision": float(precision_arr[idx]),
                "recall": float(recall_arr[idx]),
                "f1": float(f1_arr[idx]),
                "support": int(support_arr[idx]),
            }
        )
    per_class_df = pd.DataFrame(per_class_rows)

    roc_auc_macro_ovr = None
    pr_auc_macro_ovr = None
    try:
        y_true_onehot = pd.get_dummies(y_true).reindex(columns=class_labels, fill_value=0).to_numpy(dtype=float)
        roc_auc_macro_ovr = float(
            roc_auc_score(y_true_onehot, y_proba, average="macro", multi_class="ovr")
        )
        pr_auc_macro_ovr = float(average_precision_score(y_true_onehot, y_proba, average="macro"))
    except Exception:
        roc_auc_macro_ovr = None
        pr_auc_macro_ovr = None

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_precision": float(np.mean(precision_arr)),
        "macro_recall": float(np.mean(recall_arr)),
        "macro_f1": float(np.mean(f1_arr)),
        "weighted_f1": float(
            f1_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "roc_auc_macro_ovr": roc_auc_macro_ovr,
        "pr_auc_macro_ovr": pr_auc_macro_ovr,
        "brier": None,
        "confusion_matrix": {
            "labels": [int(c) for c in class_labels],
            "matrix": cm.astype(int).tolist(),
        },
        "per_class_metrics": per_class_rows,
        "threshold": None,
    }
    return metrics, per_class_df


def save_curves(y_true: pd.Series, y_proba: np.ndarray, roc_path: Path, pr_path: Path) -> None:
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    roc_auc_val = auc(fpr, tpr)

    precision, recall, _ = precision_recall_curve(y_true, y_proba)
    pr_auc_val = auc(recall, precision)

    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, label=f"ROC AUC={roc_auc_val:.3f}")
    plt.plot([0, 1], [0, 1], linestyle="--", color="grey")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(roc_path, dpi=180)
    plt.close()

    plt.figure(figsize=(6, 5))
    plt.plot(recall, precision, label=f"PR AUC={pr_auc_val:.3f}")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall Curve")
    plt.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(pr_path, dpi=180)
    plt.close()


def save_multiclass_placeholder_plots(
    roc_path: Path,
    pr_path: Path,
    class_labels: list[int],
) -> None:
    placeholder_text = (
        "Multiclass target active\\n"
        "ROC/PR single-curve plots not generated in this mode\\n"
        f"Classes: {class_labels}"
    )
    for out_path, title in ((roc_path, "ROC Placeholder"), (pr_path, "PR Placeholder")):
        plt.figure(figsize=(6, 5))
        plt.text(0.5, 0.5, placeholder_text, ha="center", va="center")
        plt.title(title)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(out_path, dpi=180)
        plt.close()


def build_feature_effects_table(
    model_type: str,
    model: Any,
    feature_names: list[str],
    X_eval: pd.DataFrame | None = None,
    y_eval: pd.Series | None = None,
    target_type: str = "binary",
    random_state: int = 42,
    nn_permutation_repeats: int = 20,
    nn_permutation_max_rows: int = 0,
) -> pd.DataFrame:
    if model_type == "lr":
        if getattr(model, "coef_", np.array([])).ndim == 2 and model.coef_.shape[0] > 1:
            frames: list[pd.DataFrame] = []
            classes = getattr(model, "classes_", list(range(model.coef_.shape[0])))
            for idx, cls in enumerate(classes):
                df_cls = pd.DataFrame(
                    {
                        "class_label": int(cls),
                        "feature": feature_names,
                        "coefficient": model.coef_[idx],
                        "odds_ratio": np.exp(model.coef_[idx]),
                    }
                )
                frames.append(df_cls)
            return pd.concat(frames, ignore_index=True).sort_values(
                ["class_label", "coefficient"], ascending=[True, False]
            )
        df = pd.DataFrame(
            {
                "feature": feature_names,
                "coefficient": model.coef_[0],
                "odds_ratio": np.exp(model.coef_[0]),
            }
        )
        return df.sort_values("coefficient", ascending=False)

    if model_type == "rf":
        df = pd.DataFrame(
            {
                "feature": feature_names,
                "importance": model.feature_importances_,
            }
        )
        return df.sort_values("importance", ascending=False)

    if model_type == "nn" and X_eval is not None and y_eval is not None:
        X_ref = X_eval.copy()
        y_ref = y_eval.copy()
        if nn_permutation_max_rows and len(X_ref) > int(nn_permutation_max_rows):
            keep_n = int(nn_permutation_max_rows)
            idx = np.random.RandomState(int(random_state)).choice(X_ref.index, size=keep_n, replace=False)
            X_ref = X_ref.loc[idx].copy()
            y_ref = y_ref.loc[idx].copy()

        if target_type == "binary":
            score_name = "balanced_accuracy"
        else:
            score_name = "f1_macro"

        perm = permutation_importance(
            model,
            X_ref,
            y_ref,
            scoring=score_name,
            n_repeats=max(1, int(nn_permutation_repeats)),
            random_state=int(random_state),
            n_jobs=1,
        )
        df = pd.DataFrame(
            {
                "feature": feature_names,
                "importance": perm.importances_mean,
                "importance_std": perm.importances_std,
                "scoring": score_name,
                "n_repeats": int(nn_permutation_repeats),
                "n_rows_used": int(len(X_ref)),
            }
        )
        return df.sort_values("importance", ascending=False)

    return pd.DataFrame({"feature": feature_names, "importance": np.nan})


# %% ---------------------------------------------------------------------------
# STEP 6 helper: output pathing and persistence
# -----------------------------------------------------------------------------
def slug_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    return cleaned.strip("_") or "unset"


def build_run_tag(
    model_type: str,
    feature_token: str,
    stamp: str,
    resolved_target_col: str,
    target_profile: str | None,
    investigation_id: str | None = None,
    target_name: str | None = None,
    recency_policy_id: str | None = None,
    run_tag_suffix: str | None = None,
) -> str:
    feature_tag = slug_token(feature_token)
    if investigation_id:
        inv_tag = slug_token(investigation_id)
        target_name_tag = slug_token(target_name or resolved_target_col)
        recency_tag = slug_token(recency_policy_id or "unset")
        base = f"{model_type}_{feature_tag}_inv_{inv_tag}_{target_name_tag}_{recency_tag}_{stamp}"
        if run_tag_suffix:
            return f"{base}_{slug_token(run_tag_suffix)}"
        return base
    if target_profile:
        target_tag = f"profile_{slug_token(target_profile)}"
        base = f"{model_type}_{feature_tag}_{target_tag}_{stamp}"
        if run_tag_suffix:
            return f"{base}_{slug_token(run_tag_suffix)}"
        return base
    if resolved_target_col == "promoter_carrier":
        base = f"{model_type}_{feature_tag}_{stamp}"
        if run_tag_suffix:
            return f"{base}_{slug_token(run_tag_suffix)}"
        return base
    base = f"{model_type}_{feature_tag}_{slug_token(resolved_target_col)}_{stamp}"
    if run_tag_suffix:
        return f"{base}_{slug_token(run_tag_suffix)}"
    return base


def build_output_paths(run_dir: Path, run_tag: str) -> dict[str, Path]:
    return {
        "metrics": run_dir / f"model_metrics_{run_tag}.json",
        "predictions": run_dir / f"model_test_predictions_{run_tag}.csv",
        "curves_table": run_dir / f"model_curves_{run_tag}.csv",
        "roc_plot": run_dir / f"model_roc_curve_{run_tag}.png",
        "pr_plot": run_dir / f"model_pr_curve_{run_tag}.png",
        "feature_effects": run_dir / f"model_feature_effects_{run_tag}.csv",
        "threshold_sweep": run_dir / f"model_threshold_sweep_{run_tag}.csv",
        "preprocessing_artifacts": run_dir / f"model_preprocessing_artifacts_{run_tag}.json",
        "train_threshold_oof": run_dir / f"model_train_threshold_oof_{run_tag}.csv",
        "manifest": run_dir / f"model_run_manifest_{run_tag}.json",
    }


# %% ---------------------------------------------------------------------------
# Orchestration
# -----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if float(args.epv_severe_threshold) > float(args.epv_warn_threshold):
        raise ValueError("--epv-severe-threshold must be <= --epv-warn-threshold")
    if not 0.0 <= float(args.min_specificity_floor) <= 1.0:
        raise ValueError("--min-specificity-floor must be between 0 and 1")

    print_step("STEP 0: Resolve run directory and run stamp")
    run_root = Path(args.run_root)
    run_dir = find_run_dir(run_root, args.run_dir)
    stamp = infer_stamp(run_dir, args.stamp)
    print(f"RUN_ROOT: {run_root}")
    print(f"RUN_DIR: {run_dir}")
    print(f"STAMP: {stamp}")

    print_step("STEP 1: Load metadata, raw governed features, and preprocessing spec")
    metadata = load_metadata(run_dir, stamp)
    preprocessing_policy_path = Path(args.preprocessing_policy_json)
    matrix, matrix_path = load_governed_feature_store(metadata, run_dir)
    preprocessing_spec, preprocessing_spec_path = load_preprocessing_spec(
        metadata=metadata,
        run_dir=run_dir,
        preprocessing_policy_path=preprocessing_policy_path,
    )
    print(f"MODEL_TYPE: {args.model_type}")
    print(f"RAW_FEATURE_STORE_PATH: {matrix_path}")
    print(f"PREPROCESSING_SPEC_PATH: {preprocessing_spec_path}")
    print(f"RAW_FEATURE_STORE_SHAPE: {matrix.shape}")

    print_step("STEP 2: Resolve target policy, ICD policy, and predictor subset")
    icd_policy_path = Path(args.icd_group_policy_csv)
    feature_profile_path = Path(args.feature_profile_csv)
    target_profile_path = Path(args.target_profile_csv)
    investigation_control_path = Path(args.investigation_control_csv)
    recency_policy_path = Path(args.recency_policy_csv)
    icd_policy = load_icd_policy(icd_policy_path)
    feature_profile_rules = load_feature_profile_rules(feature_profile_path)
    investigation_controls: pd.DataFrame | None = None
    investigation_context_preview: dict[str, Any] | None = None
    if args.investigation_id:
        investigation_controls = load_investigation_controls(investigation_control_path)
        investigation_context_preview = resolve_investigation_row(
            controls=investigation_controls,
            investigation_id=args.investigation_id,
            model_type=args.model_type,
        )
    target_profile_mappings = load_target_profile_mappings(
        target_profile_path,
        required=bool(args.target_profile or (investigation_context_preview or {}).get("target_profile")),
    )

    investigation_context: dict[str, Any] | None = None
    cohort_filter_meta = {
        "cohort_filter": "all",
        "rows_input": int(len(matrix)),
        "rows_output": int(len(matrix)),
        "rows_removed": 0,
    }
    recency_policy_id: str | None = None
    recency_rules: dict[str, dict[str, bool]] = {}
    recency_rule_rows: list[dict[str, Any]] = []
    include_missingness_flags = True

    effective_feature_set = args.feature_set
    effective_feature_profile = args.feature_profile
    effective_target_col = args.target_col
    effective_target_profile = args.target_profile

    matrix_after_filter = matrix.copy()
    if args.investigation_id:
        recency_policy_df = load_recency_policy(recency_policy_path)
        investigation_context = investigation_context_preview
        if investigation_context is None:
            raise RuntimeError("Investigation context preview was not initialised.")
        matrix_after_filter, cohort_filter_meta = apply_cohort_filter(
            matrix=matrix,
            cohort_filter=str(investigation_context["cohort_filter"]),
        )
        effective_feature_profile = str(investigation_context["feature_profile"])
        effective_target_col = str(investigation_context["target_column"])
        effective_target_profile = str(investigation_context["target_profile"]) or None
        recency_policy_id = str(investigation_context["recency_policy_id"])
        include_missingness_flags = bool(int(investigation_context["include_missingness_flags"]))
        recency_rules, recency_rule_rows = resolve_recency_policy_rules(recency_policy_df, recency_policy_id)

    if effective_feature_profile:
        has_profile = not feature_profile_rules.loc[
            feature_profile_rules["profile_name"] == effective_feature_profile
        ].empty
        if not has_profile:
            available = sorted(feature_profile_rules["profile_name"].dropna().unique().tolist())
            raise ValueError(
                f"Feature profile '{effective_feature_profile}' not found in feature profile CSV. "
                f"Available profiles: {available}"
            )

    matrix_for_model, target_values, resolved_target_col, target_excluded_cols, target_resolution_meta = (
        resolve_target_definition(
            matrix=matrix_after_filter,
            target_col=effective_target_col,
            target_profile=effective_target_profile,
            target_profile_mappings=target_profile_mappings,
        )
    )
    signal_discovery_mode = bool(
        investigation_context is not None and int(investigation_context.get("screening_enabled", 0)) == 1
    )
    if signal_discovery_mode:
        run_signal_discovery_training(
            args=args,
            run_dir=run_dir,
            stamp=stamp,
            metadata=metadata,
            matrix_path=matrix_path,
            matrix_for_model=matrix_for_model,
            target_values=target_values,
            resolved_target_col=resolved_target_col,
            target_resolution_meta=target_resolution_meta,
            cohort_filter_meta=cohort_filter_meta,
            investigation_context=investigation_context,
            recency_policy_id=recency_policy_id,
        )
        return
    selected_cols_pre_policy, feature_sel_meta = select_predictor_columns(
        matrix=matrix_for_model,
        metadata=metadata,
        feature_set=effective_feature_set,
        feature_profile=effective_feature_profile,
        feature_profile_rules=feature_profile_rules,
        icd_policy=icd_policy,
        target_excluded_cols=target_excluded_cols,
    )
    selected_cols, predictor_policy_meta = apply_predictor_policy_pruning(
        selected_cols=selected_cols_pre_policy,
        include_missingness_flags=include_missingness_flags,
        recency_rules=recency_rules,
    )
    if not selected_cols:
        raise RuntimeError("No predictors remain after investigation policy pruning.")
    feature_sel_meta["selected_predictors_pre_policy"] = selected_cols_pre_policy
    feature_sel_meta["selected_predictors"] = selected_cols
    feature_sel_meta["selected_predictor_count"] = len(selected_cols)
    feature_sel_meta["predictor_policy"] = predictor_policy_meta
    feature_sel_meta["cohort_filter"] = cohort_filter_meta
    feature_sel_meta["recency_policy_id"] = recency_policy_id
    feature_sel_meta["recency_policy_rules"] = recency_rule_rows

    feature_token = effective_feature_profile or effective_feature_set
    print(f"FEATURE_SET_ARG: {args.feature_set}")
    print(f"FEATURE_PROFILE_ARG: {args.feature_profile}")
    print(f"FEATURE_PROFILE_EFFECTIVE: {effective_feature_profile}")
    print(f"FEATURE_PROFILE_RESOLVED: {feature_sel_meta.get('resolved_feature_profile')}")
    print(f"TARGET_COL_RESOLVED: {resolved_target_col}")
    print(f"TARGET_PROFILE: {effective_target_profile}")
    print(f"INVESTIGATION_ID: {args.investigation_id if args.investigation_id else '<none>'}")
    print(f"COHORT_FILTER: {cohort_filter_meta.get('cohort_filter')}")
    print(f"RECENCY_POLICY_ID: {recency_policy_id if recency_policy_id else '<none>'}")
    print(f"LEGACY_MISSINGNESS_FLAG_CONTROL: {int(include_missingness_flags)}")
    print(f"TARGET_ROWS_INPUT: {target_resolution_meta.get('rows_input')}")
    print(f"TARGET_ROWS_OUTPUT: {target_resolution_meta.get('rows_output')}")
    print(f"SELECTED_PREDICTORS: {len(selected_cols)}")

    print_step("STEP 3: Build inputs, split train/test, and fit training-only preprocessing")
    X, y, pid, prep_meta, target_type, target_labels = prepare_modelling_inputs(
        matrix=matrix_for_model,
        selected_cols=selected_cols,
        target_col=resolved_target_col,
        target_values=target_values,
    )
    prep_meta["target_resolution"] = target_resolution_meta
    X_train_raw, X_test_raw, y_train, y_test, pid_train, pid_test, split_meta = split_dataset(
        X,
        y,
        pid,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    X_train, preprocessing_artifacts = fit_training_preprocessor(
        X_train_raw=X_train_raw,
        preprocessing_spec=preprocessing_spec,
        model_type=args.model_type,
        fit_scope="outer_train_split",
    )
    X_test = apply_fitted_preprocessor(X_test_raw, preprocessing_artifacts)
    if X_train.shape[1] == 0:
        raise RuntimeError("Training-only preprocessing dropped all predictors for the selected model family.")
    predictor_policy_meta["training_missingness_indicator_mode"] = "config_driven_train_only"
    predictor_policy_meta["preprocessing_policy_id"] = preprocessing_spec.get("policy_id")
    feature_sel_meta["post_preprocessing_predictor_count"] = int(X_train.shape[1])
    feature_sel_meta["post_preprocessing_predictors"] = X_train.columns.tolist()
    prep_meta["preprocessing_spec_path"] = str(preprocessing_spec_path)
    prep_meta["preprocessing_policy_id"] = preprocessing_spec.get("policy_id")
    prep_meta["raw_train_missing_cells"] = int(X_train_raw.isna().sum().sum())
    prep_meta["raw_test_missing_cells"] = int(X_test_raw.isna().sum().sum())
    prep_meta["post_preprocessing_train_shape"] = [int(X_train.shape[0]), int(X_train.shape[1])]
    prep_meta["post_preprocessing_test_shape"] = [int(X_test.shape[0]), int(X_test.shape[1])]
    epv_diagnostics = compute_epv_diagnostics(
        y_train=y_train,
        n_predictors=int(X_train.shape[1]),
        target_type=target_type,
        warn_threshold=float(args.epv_warn_threshold),
        severe_threshold=float(args.epv_severe_threshold),
    )
    print(f"N_TRAIN: {len(X_train_raw)}")
    print(f"N_TEST: {len(X_test_raw)}")
    print(f"TARGET_TYPE: {target_type}")
    print(f"TARGET_LABELS: {target_labels}")
    print(f"SPLIT_MODE: {split_meta['split_mode']}")
    if split_meta["stratify_fallback_reason"]:
        print("SPLIT_FALLBACK_REASON:", split_meta["stratify_fallback_reason"])
    if target_type == "binary":
        print(f"PREVALENCE_TRAIN: {float(y_train.mean()):.4f}")
        print(f"PREVALENCE_TEST: {float(y_test.mean()):.4f}")
    else:
        print("CLASS_DIST_TRAIN:", y_train.value_counts().sort_index().to_dict())
        print("CLASS_DIST_TEST:", y_test.value_counts().sort_index().to_dict())
    print(
        "EPV_ESTIMATE:",
        epv_diagnostics.get("epv_estimate"),
        "| EPV_WARNING_LEVEL:",
        epv_diagnostics.get("warning_level"),
    )
    print(f"POST_PREPROCESSING_FEATURES: {X_train.shape[1]}")

    print_step("STEP 4: Fit selected model")
    nn_hidden_layers = parse_hidden_layers(args.nn_hidden_layers)
    model = build_model(
        model_type=args.model_type,
        random_state=args.random_state,
        target_type=target_type,
        nn_hidden_layers=nn_hidden_layers,
        nn_alpha=args.nn_alpha,
        nn_learning_rate_init=args.nn_learning_rate_init,
        nn_max_iter=args.nn_max_iter,
        nn_early_stopping=args.nn_early_stopping,
        class_weight_mode=args.class_weight_mode,
    )
    model.fit(X_train, y_train)
    print("Model fit complete.")

    print_step("STEP 5: Evaluate hold-out performance")
    threshold_sweep_df = pd.DataFrame()
    train_threshold_oof_df = pd.DataFrame()
    threshold_selection_meta: dict[str, Any] = {
        "policy": args.threshold_policy,
        "selected_threshold": None,
    }
    if target_type == "binary":
        class_values = list(getattr(model, "classes_", [0, 1]))
        if 1 not in class_values:
            raise RuntimeError(f"Binary target requires positive class label 1. Found classes: {class_values}")
        pos_idx = class_values.index(1)
        y_proba = model.predict_proba(X_test)[:, pos_idx]
        if args.threshold_policy == "fixed":
            selected_threshold = float(args.threshold)
            threshold_selection_meta = {
                "policy": "fixed",
                "selected_threshold": selected_threshold,
                "selection_scope": "fixed_value_no_training_selection",
            }
        else:
            y_train_oof_proba, threshold_cv_meta = generate_training_oof_probabilities(
                X_train_raw=X_train_raw,
                y_train=y_train,
                preprocessing_spec=preprocessing_spec,
                args=args,
            )
            if y_train_oof_proba is None:
                selected_threshold = float(args.threshold)
                threshold_selection_meta = {
                    "policy": "fixed_fallback",
                    "selected_threshold": selected_threshold,
                    **threshold_cv_meta,
                }
            else:
                train_threshold_oof_df = pd.DataFrame(
                    {
                        "participant_id": pid_train.values,
                        "y_true": y_train.values,
                        "p_hat_oof": y_train_oof_proba,
                    }
                )
                selected_threshold, threshold_sweep_df, selection_meta = select_threshold_from_policy(
                    policy=args.threshold_policy,
                    fixed_threshold=float(args.threshold),
                    y_train=y_train,
                    y_train_proba=y_train_oof_proba,
                    min_specificity_floor=float(args.min_specificity_floor),
                )
                threshold_selection_meta = {**selection_meta, **threshold_cv_meta}
        print(
            "THRESHOLD_POLICY:",
            threshold_selection_meta.get("policy"),
            "| SELECTED_THRESHOLD:",
            threshold_selection_meta.get("selected_threshold"),
        )
        print("THRESHOLD_SELECTION_SCOPE:", threshold_selection_meta.get("selection_scope"))
        if threshold_selection_meta.get("policy") == "train_balanced_accuracy_min_specificity":
            print(
                "MIN_SPECIFICITY_FLOOR:",
                threshold_selection_meta.get("min_specificity_floor"),
                "| FLOOR_FALLBACK_USED:",
                threshold_selection_meta.get("fallback_used"),
            )
        y_pred = (y_proba >= selected_threshold).astype(int)
        eval_metrics, curve_df = evaluate_binary(y_test, y_proba, selected_threshold)
        print(f"ROC_AUC: {eval_metrics['roc_auc']:.4f}")
        print(f"PR_AUC: {eval_metrics['pr_auc']:.4f}")
        print(f"SENSITIVITY: {eval_metrics['sensitivity']:.4f}")
        print(f"SPECIFICITY: {eval_metrics['specificity']:.4f}")
    else:
        y_proba = model.predict_proba(X_test)
        y_pred = model.predict(X_test)
        class_values = [int(c) for c in getattr(model, "classes_", target_labels)]
        eval_metrics, curve_df = evaluate_multiclass(
            y_test, y_pred, y_proba, class_values
        )
        print(f"BALANCED_ACCURACY: {eval_metrics['balanced_accuracy']:.4f}")
        print(f"MACRO_F1: {eval_metrics['macro_f1']:.4f}")

    print_step("STEP 6: Persist metrics, predictions, curves, and feature effects")
    run_tag = build_run_tag(
        model_type=args.model_type,
        feature_token=str(feature_token),
        stamp=stamp,
        resolved_target_col=resolved_target_col,
        target_profile=effective_target_profile,
        investigation_id=(str(investigation_context["investigation_id"]) if investigation_context else None),
        target_name=(str(investigation_context["target_name"]) if investigation_context else resolved_target_col),
        recency_policy_id=recency_policy_id,
        run_tag_suffix=args.run_tag_suffix,
    )
    output_paths = build_output_paths(run_dir, run_tag)

    metrics_payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_tag": run_tag,
        "run_dir": str(run_dir),
        "stamp": stamp,
        "model_type": args.model_type,
        "matrix_path": str(matrix_path),
        "preprocessing_spec_path": str(preprocessing_spec_path),
        "target_col": resolved_target_col,
        "target_profile": effective_target_profile,
        "target_resolution": target_resolution_meta,
        "target_type": target_type,
        "target_labels": target_labels,
        "args": {
            "test_size": float(args.test_size),
            "random_state": int(args.random_state),
            "threshold": float(args.threshold),
            "threshold_policy": args.threshold_policy,
            "min_specificity_floor": float(args.min_specificity_floor),
            "run_tag_suffix": args.run_tag_suffix,
            "feature_set": effective_feature_set,
            "feature_profile": effective_feature_profile,
            "feature_profile_csv": (
                str(feature_profile_path.resolve()) if feature_profile_path.exists() else str(feature_profile_path)
            ),
            "preprocessing_policy_json": (
                str(preprocessing_policy_path.resolve())
                if preprocessing_policy_path.exists()
                else str(preprocessing_policy_path)
            ),
            "target_col": effective_target_col,
            "target_profile": effective_target_profile,
            "target_profile_csv": (
                str(target_profile_path.resolve()) if target_profile_path.exists() else str(target_profile_path)
            ),
            "investigation_id": args.investigation_id,
            "investigation_control_csv": (
                str(investigation_control_path.resolve())
                if investigation_control_path.exists()
                else str(investigation_control_path)
            ),
            "recency_policy_csv": (
                str(recency_policy_path.resolve()) if recency_policy_path.exists() else str(recency_policy_path)
            ),
            "recency_policy_id": recency_policy_id,
            "include_missingness_flags": int(include_missingness_flags),
            "class_weight_mode": args.class_weight_mode,
            "calibration_mode": args.calibration_mode,
            "nn_hidden_layers": [int(v) for v in nn_hidden_layers],
            "nn_alpha": float(args.nn_alpha),
            "nn_learning_rate_init": float(args.nn_learning_rate_init),
            "nn_max_iter": int(args.nn_max_iter),
            "nn_early_stopping": bool(args.nn_early_stopping),
            "nn_permutation_repeats": int(args.nn_permutation_repeats),
            "nn_permutation_max_rows": int(args.nn_permutation_max_rows),
            "epv_warn_threshold": float(args.epv_warn_threshold),
            "epv_severe_threshold": float(args.epv_severe_threshold),
        },
        "data_prep": prep_meta,
        "split_summary": {
            "n_train": int(len(X_train_raw)),
            "n_test": int(len(X_test_raw)),
            "split_mode": split_meta["split_mode"],
            "stratified": split_meta["stratified"],
            "stratify_fallback_reason": split_meta["stratify_fallback_reason"],
            "effective_random_state": split_meta["effective_random_state"],
            "attempted_random_states": split_meta["attempted_random_states"],
            "prevalence_train": float(y_train.mean()) if target_type == "binary" else None,
            "prevalence_test": float(y_test.mean()) if target_type == "binary" else None,
            "class_dist_train": {str(k): int(v) for k, v in y_train.value_counts().sort_index().items()},
            "class_dist_test": {str(k): int(v) for k, v in y_test.value_counts().sort_index().items()},
            "post_preprocessing_feature_count": int(X_train.shape[1]),
        },
        "feature_selection": feature_sel_meta,
        "icd_group_policy_csv": str(icd_policy_path.resolve()),
        "feature_profile_csv": (
            str(feature_profile_path.resolve()) if feature_profile_path.exists() else str(feature_profile_path)
        ),
        "target_profile_csv": (
            str(target_profile_path.resolve()) if target_profile_path.exists() else str(target_profile_path)
        ),
        "investigation_control_csv": (
            str(investigation_control_path.resolve())
            if investigation_control_path.exists()
            else str(investigation_control_path)
        ),
        "recency_policy_csv": (
            str(recency_policy_path.resolve()) if recency_policy_path.exists() else str(recency_policy_path)
        ),
        "investigation_context": investigation_context,
        "cohort_filter": cohort_filter_meta,
        "predictor_policy": predictor_policy_meta,
        "preprocessing": {
            "policy_id": preprocessing_spec.get("policy_id"),
            "policy_version": preprocessing_spec.get("policy_version"),
            "artifacts_path": str(output_paths["preprocessing_artifacts"]),
            "train_threshold_oof_path": str(output_paths["train_threshold_oof"]),
        },
        "threshold_selection": threshold_selection_meta,
        "epv_diagnostics": epv_diagnostics,
        "metrics": eval_metrics,
    }
    preprocessing_payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_tag": run_tag,
        "model_type": args.model_type,
        "preprocessing_spec_path": str(preprocessing_spec_path),
        "outer_split_preprocessing": preprocessing_artifacts,
        "threshold_selection_inner_folds": threshold_selection_meta.get(
            "inner_fold_preprocessing_artifacts", []
        ),
        "random_state": int(args.random_state),
        "split_mode": split_meta["split_mode"],
    }
    output_paths["preprocessing_artifacts"].write_text(json.dumps(preprocessing_payload, indent=2))
    output_paths["metrics"].write_text(json.dumps(metrics_payload, indent=2))

    if target_type == "binary":
        train_threshold_oof_df.to_csv(output_paths["train_threshold_oof"], index=False)
    else:
        pd.DataFrame(columns=["participant_id", "y_true", "p_hat_oof"]).to_csv(
            output_paths["train_threshold_oof"], index=False
        )

    pred_df = pd.DataFrame({"participant_id": pid_test.values, "y_true": y_test.values, "y_pred": y_pred})
    if target_type == "binary":
        pred_df["p_hat"] = y_proba
    else:
        for idx, cls in enumerate(class_values):
            pred_df[f"p_class_{cls}"] = y_proba[:, idx]
    pred_df.to_csv(output_paths["predictions"], index=False)

    curve_df.to_csv(output_paths["curves_table"], index=False)
    if target_type == "binary":
        threshold_sweep_df.to_csv(output_paths["threshold_sweep"], index=False)
    else:
        pd.DataFrame(
            columns=[
                "threshold",
                "accuracy",
                "balanced_accuracy",
                "precision",
                "recall",
                "f1",
                "sensitivity",
                "specificity",
            ]
        ).to_csv(output_paths["threshold_sweep"], index=False)
    if target_type == "binary":
        save_curves(y_test, y_proba, output_paths["roc_plot"], output_paths["pr_plot"])
    else:
        save_multiclass_placeholder_plots(
            output_paths["roc_plot"], output_paths["pr_plot"], class_values
        )

    feature_effects_df = build_feature_effects_table(
        model_type=args.model_type,
        model=model,
        feature_names=X_train.columns.tolist(),
        X_eval=X_test,
        y_eval=y_test,
        target_type=target_type,
        random_state=args.random_state,
        nn_permutation_repeats=args.nn_permutation_repeats,
        nn_permutation_max_rows=args.nn_permutation_max_rows,
    )
    feature_effects_df.to_csv(output_paths["feature_effects"], index=False)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_tag": run_tag,
        "model_type": args.model_type,
        "feature_set": effective_feature_set,
        "feature_profile": effective_feature_profile,
        "feature_profile_resolved": feature_sel_meta.get("resolved_feature_profile"),
        "target_col": resolved_target_col,
        "target_profile": effective_target_profile,
        "investigation_id": args.investigation_id,
        "recency_policy_id": recency_policy_id,
        "cohort_filter": cohort_filter_meta.get("cohort_filter"),
        "preprocessing_policy_id": preprocessing_spec.get("policy_id"),
        "preprocessing_spec_path": str(preprocessing_spec_path),
        "threshold_policy": args.threshold_policy,
        "min_specificity_floor": float(args.min_specificity_floor),
        "selected_threshold": threshold_selection_meta.get("selected_threshold"),
        "epv_estimate": epv_diagnostics.get("epv_estimate"),
        "epv_warning_level": epv_diagnostics.get("warning_level"),
        "epv_minority_class_events_train": epv_diagnostics.get("minority_class_events_train"),
        "epv_predictor_count": epv_diagnostics.get("predictor_count"),
        "run_tag_suffix": args.run_tag_suffix,
        "target_type": target_type,
        "stamp": stamp,
        "outputs": {k: str(v) for k, v in output_paths.items()},
    }
    output_paths["manifest"].write_text(json.dumps(manifest, indent=2))

    print("Output files:")
    for key, path in output_paths.items():
        print(f"- {key}: {path}")


if __name__ == "__main__":
    main()
