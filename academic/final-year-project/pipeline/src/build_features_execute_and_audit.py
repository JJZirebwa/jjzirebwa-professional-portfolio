"""Portfolio copy of the authored final-year project pipeline.

Private run roots and account-specific paths have been replaced with placeholders.
The method structure is preserved for technical review.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_RUN_ROOT = Path(
    "data/example_run"
)
DEFAULT_TARGET_COLUMNS = [
    "promoter_carrier",
    "promoter_dosage",
    "tier12_positive",
    "monogenic_high",
    "modifier_only",
    "scn5a_negative",
    "burden_class",
]
ICD_TOKEN_RE = re.compile(r"[A-Z][0-9]{2}[A-Z0-9]{0,2}")
ICD_VALID_RE = re.compile(r"^[A-Z][0-9]{2}[A-Z0-9]{0,2}$")
SIGNAL_DISCOVERY_OUTPUT_FILENAMES = {
    "icd_raw_discovery_matrix": "icd_raw_discovery_matrix_{stamp}.csv",
    "icd_raw_code_dictionary": "icd_raw_code_dictionary_{stamp}.csv",
    "icd_raw_stage_a_preparation": "icd_raw_stage_a_preparation_{stamp}.csv",
    "icd_group_anchor_comparison": "icd_group_anchor_comparison_{stamp}.csv",
}
EXPECTED_SIGNAL_DISCOVERY_STAGE_A_COLUMNS = [
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
]
EXPECTED_SIGNAL_DISCOVERY_DICTIONARY_COLUMNS = [
    "normalized_code",
    "feature_column",
    "source_tables",
    "source_table_count",
    "mapped_group_anchors",
    "mapped_group_anchor_count",
    "mapped_default_anchor_count",
    "mapped_lr_relevant_anchor_count",
]
EXPECTED_SIGNAL_DISCOVERY_GROUP_ANCHOR_COLUMNS = [
    "normalized_code",
    "feature_column",
    "group_anchor",
    "group_level",
    "include_in_default_model",
    "include_in_lr_relevant_baseline",
]
EXPECTED_DOSAGE_PROVENANCE_SUPPORT_FIELDS = [
    "pairwise_view",
    "supporting_contrasts",
    "contrast_support_count",
    "dosage_candidate_tier",
]
FORBIDDEN_GLOBAL_PREPROCESSING_OUTPUT_KEYS = {
    "features_model_hes_only_linear",
    "features_model_hes_only_tree",
    "features_matrix_canonical",
}
FORBIDDEN_STAGE_A_EXACT_COLUMNS = {
    "target_name",
    "target_column",
    "target_profile",
    "contrast_id",
    "pairwise_view",
    "class_coverage_rule",
    "class_coverage_min",
    "class_support_n",
    "class_support_min",
    "keep_flag",
    "drop_flag",
    "retain_flag",
    "retain_decision",
    "final_candidate_flag",
    "final_candidate_decision",
    "candidate_policy",
}
FORBIDDEN_STAGE_A_SUBSTRINGS = [
    "target_",
    "contrast",
    "pairwise",
    "class_coverage",
    "class_support",
    "keep",
    "drop",
    "retain",
    "candidate",
    "decision",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute build_features + full integrity audit")
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT), help="Path containing testing_<n> folders")
    parser.add_argument("--run-dir", default=None, help="Specific testing_<n> folder (default: latest)")
    parser.add_argument("--stamp", default=None, help="Optional date stamp override (YYYY-MM-DD)")

    parser.add_argument(
        "--build-script",
        default=None,
        help="Path to build_features.py (preferred when provided)",
    )
    parser.add_argument(
        "--build-notebook",
        default=None,
        help="Optional path to build_features notebook (.ipynb) for conversion fallback",
    )
    parser.add_argument(
        "--convert-notebook",
        action="store_true",
        help="Convert --build-notebook to .py before execution",
    )
    parser.add_argument(
        "--converted-script-out",
        default=None,
        help="Output path for converted notebook script (default: notebook path with .py suffix)",
    )

    parser.add_argument(
        "--icd-group-policy-csv",
        default=None,
        help="Optional path to ICD policy CSV; if omitted uses build_features default resolution",
    )
    parser.add_argument(
        "--include-missingness-indicators",
        action="store_true",
        help="Deprecated pass-through retained for compatibility; train_models now creates missingness indicators.",
    )
    parser.add_argument(
        "--diagnosis-occurrence-threshold-enabled",
        action="store_true",
        help="Pass through diagnosis occurrence threshold toggle to build_features",
    )
    parser.add_argument(
        "--diagnosis-occurrence-threshold",
        type=int,
        default=10,
        help="Pass through diagnosis occurrence threshold value to build_features",
    )
    parser.add_argument(
        "--recency-policy-csv",
        default=None,
        help="Optional path to recency policy CSV passed through to build_features",
    )
    parser.add_argument(
        "--recency-policy-id",
        default=None,
        help="Optional recency policy id passed through to build_features",
    )
    parser.add_argument(
        "--preprocessing-policy-json",
        default=None,
        help="Optional preprocessing policy JSON passed through to build_features",
    )
    parser.add_argument(
        "--icd-capture-gate-mode",
        choices=["off", "warn", "fail"],
        default="warn",
        help="Gate mode for ICD capture reconciliation severity",
    )
    parser.add_argument(
        "--icd-capture-warn-threshold",
        type=float,
        default=0.005,
        help="Warn threshold for ICD capture mismatch ratios",
    )
    parser.add_argument(
        "--icd-capture-fail-threshold",
        type=float,
        default=0.02,
        help="Fail threshold for ICD capture mismatch ratios",
    )

    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip build_features execution and run audits only",
    )
    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="Skip audit stage and run build_features only",
    )
    parser.add_argument(
        "--patch-legacy-pandas",
        action="store_true",
        help="Apply legacy pandas aggregation patch to build_features.py before execution",
    )

    parser.add_argument(
        "--max-transform-diff",
        type=float,
        default=1e-6,
        help="Deprecated audit argument retained for compatibility; build-stage transform-rebuild audit was removed.",
    )
    parser.add_argument(
        "--soft-fail",
        action="store_true",
        help="Write report but do not raise non-zero on audit failures",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# STEP 0 helpers: run-folder and input resolution
# ---------------------------------------------------------------------------
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


def infer_stamp_from_cohort(run_dir: Path, stamp_arg: str | None) -> tuple[str, Path]:
    if stamp_arg:
        cohort = run_dir / f"cohort_basic_with_haplotype_{stamp_arg}.csv"
        if not cohort.exists():
            raise FileNotFoundError(f"Missing cohort file for stamp={stamp_arg}: {cohort}")
        return stamp_arg, cohort

    cohort_files = sorted(
        run_dir.glob("cohort_basic_with_haplotype_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cohort_files:
        raise FileNotFoundError(f"No cohort_basic_with_haplotype_*.csv found in {run_dir}")

    cohort = cohort_files[0]
    match = re.match(r"cohort_basic_with_haplotype_(\d{4}-\d{2}-\d{2})\.csv$", cohort.name)
    if not match:
        raise RuntimeError(f"Could not parse stamp from cohort filename: {cohort.name}")
    return match.group(1), cohort


def ensure_inputs_for_stamp(run_dir: Path, stamp: str) -> dict[str, Path]:
    paths = {
        "cohort": run_dir / f"cohort_basic_with_haplotype_{stamp}.csv",
        "hes_apc": run_dir / f"hes_apc_censored_{stamp}.csv",
        "hes_op": run_dir / f"hes_op_censored_{stamp}.csv",
        "hes_ae": run_dir / f"hes_ae_censored_{stamp}.csv",
    }
    missing = [label for label, path in paths.items() if not path.exists()]
    if missing:
        detail = ", ".join([f"{m}:{paths[m]}" for m in missing])
        raise FileNotFoundError(f"Missing required inputs for stamp={stamp}: {detail}")
    return paths


# ---------------------------------------------------------------------------
# STEP 1 helpers: build-script resolution and optional notebook conversion
# ---------------------------------------------------------------------------
def convert_notebook_to_script(notebook_path: Path, output_path: Path) -> Path:
    """Convert code cells in an .ipynb into a plain .py script.

    This avoids external nbconvert dependency in constrained secure research environment environments.
    """
    if not notebook_path.exists():
        raise FileNotFoundError(f"Notebook not found: {notebook_path}")

    nb = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells = nb.get("cells", [])

    lines: list[str] = []
    lines.append('"""Auto-generated from notebook for secure research environment execution fallback."""\n')

    code_cell_idx = 0
    for cell in cells:
        if cell.get("cell_type") != "code":
            continue
        code_cell_idx += 1
        lines.append(f"\n# %% Notebook Cell {code_cell_idx}\n")

        source = cell.get("source", [])
        if isinstance(source, str):
            source_lines = [source]
        else:
            source_lines = [str(s) for s in source]

        for src_line in source_lines:
            if src_line.endswith("\n"):
                lines.append(src_line)
            else:
                lines.append(src_line + "\n")

    if code_cell_idx == 0:
        raise RuntimeError(f"Notebook has no code cells: {notebook_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path


def resolve_build_script(
    run_root: Path,
    build_script_arg: str | None,
    build_notebook_arg: str | None,
    convert_notebook: bool,
    converted_script_out: str | None,
) -> Path:
    if build_script_arg:
        path = Path(build_script_arg)
        if not path.exists():
            raise FileNotFoundError(f"build_features.py not found: {path}")
        return path

    if build_notebook_arg:
        notebook_path = Path(build_notebook_arg)
        if not notebook_path.exists():
            raise FileNotFoundError(f"Notebook not found: {notebook_path}")

        if convert_notebook:
            out_path = Path(converted_script_out) if converted_script_out else notebook_path.with_suffix(".py")
            return convert_notebook_to_script(notebook_path, out_path)

        sibling_script = notebook_path.with_suffix(".py")
        if sibling_script.exists():
            return sibling_script
        raise FileNotFoundError(
            "Notebook provided but no .py sibling found. Use --convert-notebook or pass --build-script."
        )

    local_candidate = Path(__file__).resolve().parent / "build_features.py"
    run_root_feature_engineering = run_root / "fyp_scripts" / "feature_engineering" / "build_features.py"
    legacy_candidate = run_root / "fyp_scripts" / "build_features.py"

    for candidate in [local_candidate, run_root_feature_engineering, legacy_candidate]:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not locate build_features.py in expected locations. "
        "Pass --build-script explicitly."
    )


def resolve_icd_policy_csv(
    run_root: Path,
    build_script: Path,
    policy_arg: str | None,
) -> str | None:
    if policy_arg:
        path = Path(policy_arg)
        if not path.exists():
            raise FileNotFoundError(f"ICD policy CSV not found: {path}")
        return str(path)

    candidates = [
        build_script.parent / "config" / "icd_group_policy.csv",
        run_root / "fyp_scripts" / "feature_engineering" / "config" / "icd_group_policy.csv",
        run_root / "fyp_scripts" / "config" / "icd_group_policy.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


# ---------------------------------------------------------------------------
# STEP 2 helper: optional legacy pandas patching
# ---------------------------------------------------------------------------
def patch_legacy_pandas_aggregations(build_script: Path) -> int:
    text = build_script.read_text(encoding="utf-8")
    replacements = [
        (
            '.agg(size="size", min="min", max="max").reset_index()',
            '.agg(["size", "min", "max"]).reset_index()',
        ),
        (
            '.agg(size="size", min="min", max="max")',
            '.agg(["size", "min", "max"]).reset_index()',
        ),
        (
            '.agg(sum="sum", mean="mean", max="max").reset_index()',
            '.agg(["sum", "mean", "max"]).reset_index()',
        ),
        (
            '.agg(min="min", max="max").reset_index()',
            '.agg(["min", "max"]).reset_index()',
        ),
    ]

    changed = 0
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            changed += 1

    if changed > 0:
        build_script.write_text(text, encoding="utf-8")
    return changed


# ---------------------------------------------------------------------------
# STEP 3 helper: execute build_features
# ---------------------------------------------------------------------------
def run_build_features(
    build_script: Path,
    run_dir: Path,
    stamp: str,
    inputs: dict[str, Path],
    icd_group_policy_csv: str | None,
    include_missingness_indicators: bool,
    diagnosis_occurrence_threshold_enabled: bool,
    diagnosis_occurrence_threshold: int,
    recency_policy_csv: str | None,
    recency_policy_id: str | None,
    preprocessing_policy_json: str | None,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(build_script),
        "--cohort",
        str(inputs["cohort"]),
        "--hes-apc",
        str(inputs["hes_apc"]),
        "--hes-op",
        str(inputs["hes_op"]),
        "--hes-ae",
        str(inputs["hes_ae"]),
        "--out-dir",
        str(run_dir),
        "--stamp",
        stamp,
    ]
    if icd_group_policy_csv:
        cmd.extend(["--icd-group-policy-csv", icd_group_policy_csv])
    if include_missingness_indicators:
        cmd.append("--include-missingness-indicators")
    if diagnosis_occurrence_threshold_enabled:
        cmd.extend(
            [
                "--diagnosis-occurrence-threshold-enabled",
                "--diagnosis-occurrence-threshold",
                str(int(diagnosis_occurrence_threshold)),
            ]
        )
    if recency_policy_csv:
        cmd.extend(["--recency-policy-csv", recency_policy_csv])
    if recency_policy_id:
        cmd.extend(["--recency-policy-id", recency_policy_id])
    if preprocessing_policy_json:
        cmd.extend(["--preprocessing-policy-json", preprocessing_policy_json])

    print("Running build_features command:")
    print(" ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)

    print("STDOUT:\n", res.stdout)
    print("STDERR:\n", res.stderr)
    print("EXIT:", res.returncode)

    if res.returncode != 0:
        raise RuntimeError("build_features execution failed")

    return {
        "command": cmd,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "exit_code": res.returncode,
    }


def extract_icd_codes(value: Any) -> set[str]:
    raw = str(value).strip().upper()
    if not raw or raw in {"NAN", "<NA>", "NONE", "NULL"}:
        return set()
    raw = raw.replace(".", "")
    tokens = ICD_TOKEN_RE.findall(raw)
    return {tok for tok in tokens if ICD_VALID_RE.match(tok)}


def collect_diag_numbered_cols(df: pd.DataFrame) -> list[str]:
    cols: list[tuple[int, str]] = []
    for col in df.columns:
        match = re.match(r"^diag_(\d+)$", str(col).lower())
        if match:
            cols.append((int(match.group(1)), col))
    return [name for _, name in sorted(cols, key=lambda x: x[0])]


def run_icd_code_capture_audit(
    inputs: dict[str, Path],
    warn_threshold: float,
    fail_threshold: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    table_sources = {
        "hes_apc": inputs["hes_apc"],
        "hes_op": inputs["hes_op"],
        "hes_ae": inputs["hes_ae"],
    }
    rows: list[dict[str, Any]] = []

    for table_name, table_path in table_sources.items():
        df = pd.read_csv(table_path)
        diag_all_col = "diag_all" if "diag_all" in df.columns else None
        diag_cols = collect_diag_numbered_cols(df)

        all_token_total = 0
        xx_token_total = 0
        unique_all: set[str] = set()
        unique_xx: set[str] = set()
        rows_with_diag_all = 0
        rows_with_diag_xx = 0

        for row in df.itertuples(index=False):
            row_dict = row._asdict()
            all_tokens: set[str] = set()
            xx_tokens: set[str] = set()

            if diag_all_col:
                all_tokens = extract_icd_codes(row_dict.get(diag_all_col))
            if all_tokens:
                rows_with_diag_all += 1

            for col in diag_cols:
                xx_tokens.update(extract_icd_codes(row_dict.get(col)))
            if xx_tokens:
                rows_with_diag_xx += 1

            all_token_total += len(all_tokens)
            xx_token_total += len(xx_tokens)
            unique_all.update(all_tokens)
            unique_xx.update(xx_tokens)

        only_in_xx = sorted(unique_xx.difference(unique_all))
        only_in_all = sorted(unique_all.difference(unique_xx))
        xx_missing_ratio = (
            float(len(only_in_xx) / len(unique_xx)) if unique_xx else 0.0
        )
        all_missing_ratio = (
            float(len(only_in_all) / len(unique_all)) if unique_all else 0.0
        )

        rows.append(
            {
                "table_name": table_name,
                "source_path": str(table_path),
                "rows_total": int(len(df)),
                "diag_all_present": int(diag_all_col is not None),
                "diag_xx_columns_count": int(len(diag_cols)),
                "diag_xx_columns": "|".join(diag_cols),
                "rows_with_diag_all_codes": int(rows_with_diag_all),
                "rows_with_diag_xx_codes": int(rows_with_diag_xx),
                "diag_all_token_total": int(all_token_total),
                "diag_xx_token_total": int(xx_token_total),
                "diag_all_unique_codes": int(len(unique_all)),
                "diag_xx_unique_codes": int(len(unique_xx)),
                "diag_xx_unique_missing_from_diag_all_n": int(len(only_in_xx)),
                "diag_all_unique_missing_from_diag_xx_n": int(len(only_in_all)),
                "diag_xx_unique_missing_from_diag_all_ratio": xx_missing_ratio,
                "diag_all_unique_missing_from_diag_xx_ratio": all_missing_ratio,
                "diag_xx_unique_missing_from_diag_all_examples": "|".join(only_in_xx[:25]),
                "diag_all_unique_missing_from_diag_xx_examples": "|".join(only_in_all[:25]),
            }
        )

    audit_df = pd.DataFrame(rows)
    warn_rows: list[dict[str, Any]] = []
    fail_rows: list[dict[str, Any]] = []
    warning_reasons: list[str] = []
    failure_reasons: list[str] = []
    max_missing_from_diag_all = 0.0
    max_missing_from_diag_xx = 0.0

    for row in audit_df.to_dict(orient="records"):
        table_name = str(row["table_name"])
        row_warn = False
        row_fail = False

        missing_from_all_ratio = float(row["diag_xx_unique_missing_from_diag_all_ratio"])
        missing_from_xx_ratio = float(row["diag_all_unique_missing_from_diag_xx_ratio"])
        max_missing_from_diag_all = max(max_missing_from_diag_all, missing_from_all_ratio)
        max_missing_from_diag_xx = max(max_missing_from_diag_xx, missing_from_xx_ratio)

        if int(row["diag_all_present"]) == 0:
            row_fail = True
            failure_reasons.append(f"{table_name}: diag_all column missing")
        if int(row["diag_xx_columns_count"]) == 0:
            row_fail = True
            failure_reasons.append(f"{table_name}: no diag_xx columns available")

        if missing_from_all_ratio >= float(fail_threshold):
            row_fail = True
            failure_reasons.append(
                f"{table_name}: diag_xx_missing_from_diag_all_ratio={missing_from_all_ratio:.6f} >= fail_threshold={fail_threshold:.6f}"
            )
        elif missing_from_all_ratio >= float(warn_threshold):
            row_warn = True
            warning_reasons.append(
                f"{table_name}: diag_xx_missing_from_diag_all_ratio={missing_from_all_ratio:.6f} >= warn_threshold={warn_threshold:.6f}"
            )

        if missing_from_xx_ratio >= float(fail_threshold):
            row_fail = True
            failure_reasons.append(
                f"{table_name}: diag_all_missing_from_diag_xx_ratio={missing_from_xx_ratio:.6f} >= fail_threshold={fail_threshold:.6f}"
            )
        elif missing_from_xx_ratio >= float(warn_threshold):
            row_warn = True
            warning_reasons.append(
                f"{table_name}: diag_all_missing_from_diag_xx_ratio={missing_from_xx_ratio:.6f} >= warn_threshold={warn_threshold:.6f}"
            )

        if row_fail:
            fail_rows.append(row)
        elif row_warn:
            warn_rows.append(row)

    severity = "pass"
    if fail_rows:
        severity = "fail"
    elif warn_rows:
        severity = "warn"

    payload = {
        "audit_type": "icd_diag_capture_reconciliation",
        "status": severity,
        "table_count": int(len(audit_df)),
        "warn_threshold": float(warn_threshold),
        "fail_threshold": float(fail_threshold),
        "warn_table_count": int(len(warn_rows)),
        "fail_table_count": int(len(fail_rows)),
        "warn_tables": [str(row["table_name"]) for row in warn_rows],
        "fail_tables": [str(row["table_name"]) for row in fail_rows],
        "warning_reasons": warning_reasons,
        "failure_reasons": failure_reasons,
        "max_diag_xx_unique_missing_from_diag_all_ratio": float(max_missing_from_diag_all),
        "max_diag_all_unique_missing_from_diag_xx_ratio": float(max_missing_from_diag_xx),
        "rows": audit_df.to_dict(orient="records"),
    }
    return audit_df, payload


# ---------------------------------------------------------------------------
# STEP 4 helper: load expected build outputs
# ---------------------------------------------------------------------------
def load_artifacts(run_dir: Path, stamp: str) -> dict[str, Any]:
    meta_path = run_dir / f"features_matrix_metadata_{stamp}.json"
    raw_path = run_dir / f"features_matrix_raw_{stamp}.csv"
    preprocessing_spec_path = run_dir / f"feature_preprocessing_spec_{stamp}.json"

    required = [meta_path, raw_path, preprocessing_spec_path]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing expected build_features outputs: " + ", ".join(missing))

    meta = json.loads(meta_path.read_text())
    outputs_meta = meta.get("outputs", {})
    signal_paths: dict[str, Path] = {}
    signal_discovery_expected = bool(meta.get("signal_discovery_meta")) or any(
        (run_dir / filename.format(stamp=stamp)).exists()
        for filename in SIGNAL_DISCOVERY_OUTPUT_FILENAMES.values()
    ) or any(key in outputs_meta for key in SIGNAL_DISCOVERY_OUTPUT_FILENAMES)

    signal_missing: list[str] = []
    signal_frames: dict[str, Any] = {
        "enabled": signal_discovery_expected,
    }
    if signal_discovery_expected:
        for key, filename_tmpl in SIGNAL_DISCOVERY_OUTPUT_FILENAMES.items():
            candidate = outputs_meta.get(key)
            path = Path(candidate) if candidate else (run_dir / filename_tmpl.format(stamp=stamp))
            signal_paths[key] = path
            if not path.exists():
                signal_missing.append(str(path))
        if signal_missing:
            raise FileNotFoundError(
                "Missing expected signal-discovery build outputs: " + ", ".join(signal_missing)
            )
        signal_frames.update(
            {
                "paths": {k: str(v) for k, v in signal_paths.items()},
                "raw_code_discovery_matrix": pd.read_csv(signal_paths["icd_raw_discovery_matrix"]),
                "raw_code_dictionary": pd.read_csv(signal_paths["icd_raw_code_dictionary"]),
                "stage_a_preparation": pd.read_csv(signal_paths["icd_raw_stage_a_preparation"]),
                "grouped_anchor_comparison": pd.read_csv(signal_paths["icd_group_anchor_comparison"]),
            }
        )
    else:
        signal_frames["paths"] = {}

    return {
        "meta_path": meta_path,
        "raw_path": raw_path,
        "preprocessing_spec_path": preprocessing_spec_path,
        "meta": meta,
        "raw": pd.read_csv(raw_path),
        "preprocessing_spec": json.loads(preprocessing_spec_path.read_text(encoding="utf-8")),
        "signal_discovery": signal_frames,
    }


# ---------------------------------------------------------------------------
# STEP 5 helpers: structural and governance checks
# ---------------------------------------------------------------------------
def resolve_target_columns(meta: dict[str, Any], raw: pd.DataFrame) -> list[str]:
    target_cols = meta.get("preprocessing_meta", {}).get("target_columns", [])
    if not target_cols:
        target_cols = [c for c in DEFAULT_TARGET_COLUMNS if c in raw.columns]

    resolved: list[str] = []
    seen: set[str] = set()
    for col in target_cols:
        name = str(col)
        if name in raw.columns and name not in seen:
            resolved.append(name)
            seen.add(name)
    return resolved


def run_structural_checks(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    raw = data["raw"]
    meta = data["meta"]
    preprocessing_spec = data["preprocessing_spec"]
    target_cols = resolve_target_columns(data["meta"], raw)
    outputs_meta = meta.get("outputs", {})
    forbidden_output_keys_present = sorted(
        FORBIDDEN_GLOBAL_PREPROCESSING_OUTPUT_KEYS.intersection(set(outputs_meta))
    )
    legacy_output_files_present = sorted(
        [
            str(path.name)
            for path in [
                data["raw_path"].parent / f"features_model_hes_only_linear_{data['raw_path'].stem.split('_')[-1]}.csv",
                data["raw_path"].parent / f"features_model_hes_only_tree_{data['raw_path'].stem.split('_')[-1]}.csv",
                data["raw_path"].parent / f"features_matrix_{data['raw_path'].stem.split('_')[-1]}.csv",
            ]
            if path.exists()
        ]
    )

    checks: dict[str, Any] = {
        "raw_rows": int(raw.shape[0]),
        "raw_cols": int(raw.shape[1]),
        "raw_unique_pid": int(raw["participant_id"].nunique()),
        "preprocessing_spec_predictor_count": int(len(preprocessing_spec.get("predictor_columns", []))),
        "preprocessing_spec_target_count": int(len(preprocessing_spec.get("target_columns", []))),
        "forbidden_output_keys_present": forbidden_output_keys_present,
        "legacy_global_matrix_files_present": legacy_output_files_present,
        "target_columns_checked": target_cols,
    }

    issues: list[str] = []
    if forbidden_output_keys_present:
        issues.append(
            "Metadata outputs still reference forbidden globally fitted model matrices: "
            f"{forbidden_output_keys_present}"
        )
    if preprocessing_spec.get("predictor_columns") != meta.get("preprocessing_meta", {}).get("predictor_columns", []):
        issues.append("Preprocessing spec predictor columns differ from preprocessing_meta predictor columns")
    if not target_cols:
        issues.append("No target columns available for structural alignment checks")
    for col in target_cols:
        if col not in raw.columns:
            issues.append(f"{col} missing from raw governed feature store")
        if col not in preprocessing_spec.get("target_columns", []):
            issues.append(f"{col} missing from preprocessing spec target columns")

    print("Structural checks:")
    for k in sorted(checks):
        print(f"- {k}: {checks[k]}")
    if issues:
        print("Structural issues:")
        for issue in issues:
            print("-", issue)

    return checks, issues


def run_signal_discovery_checks(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    signal = data.get("signal_discovery", {})
    meta = data.get("meta", {})
    signal_meta = meta.get("signal_discovery_meta", {})

    payload: dict[str, Any] = {
        "artifacts_present": bool(signal.get("enabled", False)),
        "status": "not_applicable",
        "artifact_paths": signal.get("paths", {}),
        "authoritative_source": signal_meta.get("authoritative_source"),
        "source_columns_by_table": signal_meta.get("source_columns_by_table", {}),
        "dosage_manifest_provenance_fields": signal_meta.get("dosage_manifest_provenance_fields", []),
        "raw_code_feature_column_count": 0,
        "stage_a_row_count": 0,
        "group_anchor_row_count": 0,
        "forbidden_stage_a_columns": [],
        "stage_a_preparation_only_all_rows": True,
    }
    if not signal.get("enabled", False):
        return payload, []

    issues: list[str] = []
    raw_matrix = signal["raw_code_discovery_matrix"]
    raw_dictionary = signal["raw_code_dictionary"]
    stage_a = signal["stage_a_preparation"]
    grouped_anchor = signal["grouped_anchor_comparison"]

    raw_matrix_cols = raw_matrix.columns.tolist()
    raw_feature_cols = [c for c in raw_matrix_cols if c != "participant_id"]
    stage_a_cols = stage_a.columns.tolist()
    dict_cols = raw_dictionary.columns.tolist()
    anchor_cols = grouped_anchor.columns.tolist()

    payload["status"] = "pass"
    payload["raw_code_feature_column_count"] = int(len(raw_feature_cols))
    payload["stage_a_row_count"] = int(stage_a.shape[0])
    payload["group_anchor_row_count"] = int(grouped_anchor.shape[0])
    payload["raw_code_feature_column_sample"] = raw_feature_cols[:10]

    missing_dict_cols = sorted(set(EXPECTED_SIGNAL_DISCOVERY_DICTIONARY_COLUMNS).difference(dict_cols))
    missing_stage_a_cols = sorted(set(EXPECTED_SIGNAL_DISCOVERY_STAGE_A_COLUMNS).difference(stage_a_cols))
    missing_anchor_cols = sorted(set(EXPECTED_SIGNAL_DISCOVERY_GROUP_ANCHOR_COLUMNS).difference(anchor_cols))
    if missing_dict_cols:
        issues.append(f"signal-discovery raw code dictionary missing columns: {missing_dict_cols}")
    if missing_stage_a_cols:
        issues.append(f"signal-discovery Stage A preparation missing columns: {missing_stage_a_cols}")
    if missing_anchor_cols:
        issues.append(f"signal-discovery grouped-anchor comparison missing columns: {missing_anchor_cols}")

    forbidden_stage_a_cols = sorted(
        {
            col
            for col in stage_a_cols
            if col in FORBIDDEN_STAGE_A_EXACT_COLUMNS
            or any(token in str(col).lower() for token in FORBIDDEN_STAGE_A_SUBSTRINGS)
        }
    )
    payload["forbidden_stage_a_columns"] = forbidden_stage_a_cols
    if forbidden_stage_a_cols:
        issues.append(
            "signal-discovery Stage A preparation contains forbidden target-aware or retain/drop columns: "
            f"{forbidden_stage_a_cols}"
        )

    if "stage_a_preparation_only" in stage_a.columns:
        try:
            prep_only_ok = bool(
                stage_a["stage_a_preparation_only"].dropna().astype(int).isin([1]).all()
            )
        except Exception:
            prep_only_ok = False
        payload["stage_a_preparation_only_all_rows"] = prep_only_ok
        if not prep_only_ok:
            issues.append("signal-discovery Stage A preparation contains rows not marked stage_a_preparation_only=1")
    else:
        payload["stage_a_preparation_only_all_rows"] = False

    if "participant_id" not in raw_matrix.columns:
        issues.append("signal-discovery raw-code discovery matrix missing participant_id")
    if any(col.startswith("icd_grp_") or col.startswith("opcs_grp_") for col in raw_feature_cols):
        issues.append("grouped-feature columns leaked into the raw-code discovery matrix")
    if any(col in set(EXPECTED_SIGNAL_DISCOVERY_GROUP_ANCHOR_COLUMNS) for col in raw_feature_cols):
        issues.append("grouped-anchor comparison columns leaked into the raw-code discovery matrix")
    if "participant_id" in grouped_anchor.columns:
        issues.append("grouped-anchor comparison output is participant-level and may be treated as discovery input")

    if "feature_column" in stage_a.columns:
        stage_a_feature_cols = set(stage_a["feature_column"].dropna().astype(str).tolist())
        if not stage_a_feature_cols.issubset(set(raw_feature_cols)):
            issues.append("Stage A preparation references feature columns missing from the raw-code discovery matrix")
    if "feature_column" in grouped_anchor.columns:
        anchor_feature_cols = set(grouped_anchor["feature_column"].dropna().astype(str).tolist())
        if not anchor_feature_cols.issubset(set(raw_feature_cols)):
            issues.append("Grouped-anchor comparison references feature columns missing from the raw-code discovery matrix")

    authoritative_source = str(signal_meta.get("authoritative_source", "")).strip()
    if authoritative_source != "diag_all":
        issues.append(
            f"signal-discovery authoritative source is {authoritative_source!r}, expected 'diag_all'"
        )
    source_columns_by_table = signal_meta.get("source_columns_by_table", {})
    if not source_columns_by_table:
        issues.append("signal-discovery metadata missing source_columns_by_table")
    else:
        for table_name, cols in source_columns_by_table.items():
            normalized = [str(col) for col in cols]
            if normalized != ["diag_all"]:
                issues.append(
                    f"signal-discovery source columns for {table_name} are {normalized}, expected ['diag_all'] only"
                )

    provenance_fields = [str(v) for v in signal_meta.get("dosage_manifest_provenance_fields", [])]
    missing_provenance = sorted(
        set(EXPECTED_DOSAGE_PROVENANCE_SUPPORT_FIELDS).difference(provenance_fields)
    )
    payload["missing_dosage_provenance_fields"] = missing_provenance
    if missing_provenance:
        issues.append(
            f"signal-discovery metadata missing dosage provenance-support fields: {missing_provenance}"
        )

    if issues:
        payload["status"] = "fail"
    return payload, issues


def run_training_artifact_checks(run_dir: Path, stamp: str) -> tuple[dict[str, Any], list[str]]:
    manifest_paths = sorted(run_dir.glob(f"model_run_manifest_*{stamp}*.json"))
    payload: dict[str, Any] = {
        "status": "not_applicable_no_model_runs_present",
        "manifest_count": int(len(manifest_paths)),
        "rows": [],
    }
    if not manifest_paths:
        return payload, []

    issues: list[str] = []
    rows: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs = manifest.get("outputs", {})
        preprocessing_path = outputs.get("preprocessing_artifacts")
        threshold_oof_path = outputs.get("train_threshold_oof")
        is_refactored_manifest = bool(
            manifest.get("preprocessing_policy_id")
            or manifest.get("preprocessing_spec_path")
            or preprocessing_path
            or threshold_oof_path
        )
        row = {
            "manifest": str(manifest_path),
            "run_tag": manifest.get("run_tag"),
            "model_type": manifest.get("model_type"),
            "legacy_manifest_skipped": bool(not is_refactored_manifest),
            "preprocessing_artifacts_present": False,
            "train_threshold_oof_present": False,
        }
        if not is_refactored_manifest:
            row["status"] = "legacy_manifest_not_subject_to_refactored_artifact_contract"
            rows.append(row)
            continue
        if preprocessing_path:
            resolved = Path(preprocessing_path)
            row["preprocessing_artifacts_present"] = bool(resolved.exists())
            row["preprocessing_artifacts"] = str(resolved)
            if not resolved.exists():
                issues.append(f"training manifest missing preprocessing_artifacts file: {manifest_path.name}")
        else:
            issues.append(f"training manifest missing preprocessing_artifacts output key: {manifest_path.name}")
        if threshold_oof_path:
            resolved = Path(threshold_oof_path)
            row["train_threshold_oof_present"] = bool(resolved.exists())
            row["train_threshold_oof"] = str(resolved)
            if not resolved.exists():
                issues.append(f"training manifest missing train_threshold_oof file: {manifest_path.name}")
        else:
            issues.append(f"training manifest missing train_threshold_oof output key: {manifest_path.name}")
        row["status"] = "pass" if row["preprocessing_artifacts_present"] and row["train_threshold_oof_present"] else "fail"
        rows.append(row)

    payload["rows"] = rows
    payload["status"] = "fail" if issues else "pass"
    return payload, issues


def run_governance_checks(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    meta = data["meta"]
    pre = meta.get("preprocessing_meta", {})
    preprocessing_spec = data["preprocessing_spec"]
    predictors = preprocessing_spec.get("predictor_columns", [])
    excluded_secondary = set(preprocessing_spec.get("default_excluded_secondary_genetics", []))
    excluded_vcf = set(preprocessing_spec.get("default_excluded_legacy_vcf_fields", []))
    unexpected_missing_indicators = sorted([c for c in predictors if str(c).endswith("_is_missing")])
    unexpected_prebuilt_onehot = sorted([c for c in predictors if "__" in str(c)])

    unexpected_secondary = sorted([c for c in predictors if c in excluded_secondary])
    unexpected_vcf = sorted([c for c in predictors if c in excluded_vcf])

    signal_discovery_payload, signal_discovery_issues = run_signal_discovery_checks(data)
    stamp_match = re.search(r"(\d{4}-\d{2}-\d{2})", data["meta_path"].name)
    stamp = stamp_match.group(1) if stamp_match else ""
    training_artifact_payload, training_artifact_issues = run_training_artifact_checks(
        run_dir=data["meta_path"].parent,
        stamp=stamp,
    )

    payload = {
        "predictor_count": len(predictors),
        "numeric_predictor_count": len(preprocessing_spec.get("numeric_predictor_columns", [])),
        "categorical_predictor_count": len(preprocessing_spec.get("categorical_predictor_columns", [])),
        "feature_class_counts": pre.get("feature_class_counts", {}),
        "preprocessing_policy_id": preprocessing_spec.get("policy_id"),
        "unexpected_missing_indicator_predictors": unexpected_missing_indicators,
        "unexpected_prebuilt_onehot_predictors": unexpected_prebuilt_onehot,
        "unexpected_secondary_in_predictors": unexpected_secondary,
        "unexpected_legacy_vcf_in_predictors": unexpected_vcf,
        "training_artifact_checks": training_artifact_payload,
        "signal_discovery_checks": signal_discovery_payload,
    }

    issues: list[str] = []
    if unexpected_secondary:
        issues.append("Secondary genetics fields leaked into predictor_columns")
    if unexpected_vcf:
        issues.append("Legacy VCF fields leaked into predictor_columns")
    if unexpected_missing_indicators:
        issues.append("Build-stage predictor columns contain prebuilt missingness indicators")
    if unexpected_prebuilt_onehot:
        issues.append("Build-stage predictor columns contain prebuilt one-hot columns")
    issues.extend([f"TRAINING_ARTIFACTS: {msg}" for msg in training_artifact_issues])
    issues.extend([f"SIGNAL_DISCOVERY: {msg}" for msg in signal_discovery_issues])

    print("Predictor governance checks:")
    for k, v in payload.items():
        print(f"- {k}: {v}")
    if issues:
        print("Governance issues:")
        for issue in issues:
            print("-", issue)

    return payload, issues


# ---------------------------------------------------------------------------
# STEP 6 helpers: preprocessing-contract and missingness audits
# ---------------------------------------------------------------------------
def build_column_dictionary(data: dict[str, Any]) -> pd.DataFrame:
    raw = data["raw"]
    meta = data["meta"]
    preprocessing_spec = data["preprocessing_spec"]

    feature_meta = meta.get("feature_meta", {})
    column_policies = preprocessing_spec.get("column_policies", {})
    feature_set = set(feature_meta.get("feature_cols", []))
    categorical_set = set(feature_meta.get("categorical_context_cols", []))
    count_set = set(feature_meta.get("count_cols", []))
    duration_set = set(feature_meta.get("duration_cols", []))
    ratio_set = set(feature_meta.get("ratio_cols", []))
    recency_set = set(feature_meta.get("recency_cols", []))
    density_set = set(feature_meta.get("density_cols", []))
    icd_set = set(feature_meta.get("icd_group_feature_cols", []))
    opcs_set = set(feature_meta.get("opcs_group_feature_cols", []))

    def infer_family(col: str) -> str:
        if col in icd_set:
            return "icd_group_feature"
        if col in opcs_set:
            return "opcs_group_feature"
        if col in count_set:
            return "count"
        if col in duration_set:
            return "duration"
        if col in ratio_set:
            return "ratio"
        if col in recency_set:
            return "recency"
        if col in density_set:
            return "density"
        if col in categorical_set:
            return "categorical_context"
        if col in feature_set:
            return "engineered_other"
        return "non_feature_or_output"

    rows = [
        {
            "column": c,
            "family": infer_family(c),
            "feature_class": column_policies.get(c, {}).get("feature_class"),
            "missingness_policy_class": column_policies.get(c, {}).get("missingness_policy_class"),
            "clinically_central": column_policies.get(c, {}).get("clinically_central"),
        }
        for c in sorted(raw.columns)
    ]
    return pd.DataFrame(rows)


def run_preprocessing_contract_audit(data: dict[str, Any]) -> pd.DataFrame:
    preprocessing_spec = data["preprocessing_spec"]
    meta = data["meta"]
    raw = data["raw"]
    predictors = preprocessing_spec.get("predictor_columns", [])
    column_policies = preprocessing_spec.get("column_policies", {})
    outputs = meta.get("outputs", {})

    rows: list[dict[str, Any]] = [
        {
            "check_name": "no_forbidden_global_matrix_output_keys",
            "status": "pass"
            if not FORBIDDEN_GLOBAL_PREPROCESSING_OUTPUT_KEYS.intersection(set(outputs))
            else "fail",
            "detail": sorted(FORBIDDEN_GLOBAL_PREPROCESSING_OUTPUT_KEYS.intersection(set(outputs))),
        },
        {
            "check_name": "preprocessing_spec_predictor_columns_match_meta",
            "status": "pass"
            if predictors == meta.get("preprocessing_meta", {}).get("predictor_columns", [])
            else "fail",
            "detail": {
                "spec_predictor_count": len(predictors),
                "meta_predictor_count": len(meta.get("preprocessing_meta", {}).get("predictor_columns", [])),
            },
        },
    ]
    for column in predictors:
        policy = column_policies.get(column, {})
        rows.append(
            {
                "check_name": f"column_contract::{column}",
                "status": "pass" if column in raw.columns else "fail",
                "detail": {
                    "feature_class": policy.get("feature_class"),
                    "missingness_policy_class": policy.get("missingness_policy_class"),
                    "protected_from_scaling": policy.get("protected_from_scaling"),
                    "protected_from_log": policy.get("protected_from_log"),
                    "clinically_central": policy.get("clinically_central"),
                },
            }
        )
    return pd.DataFrame(rows)


def build_missingness_summary(data: dict[str, Any]) -> pd.DataFrame:
    raw = data["raw"]
    rows: list[dict[str, Any]] = []

    for col in raw.columns:
        s = raw[col]
        row: dict[str, Any] = {
            "column": col,
            "dtype": str(s.dtype),
            "missing_n": int(s.isna().sum()),
            "missing_pct": float(s.isna().mean() * 100.0),
        }
        if pd.api.types.is_numeric_dtype(s):
            if s.notna().any():
                row["min"] = float(np.nanmin(s))
                row["max"] = float(np.nanmax(s))
                row["mean"] = float(np.nanmean(s))
            else:
                row["min"] = np.nan
                row["max"] = np.nan
                row["mean"] = np.nan
        else:
            row["n_unique_non_null"] = int(s.dropna().nunique())

        rows.append(row)

    return pd.DataFrame(rows).sort_values(["missing_pct", "column"], ascending=[False, True])


# ---------------------------------------------------------------------------
# STEP 7 helpers: pass/fail evaluation and artifact/report writing
# ---------------------------------------------------------------------------
def evaluate_audit_status(
    structural_issues: list[str],
    governance_issues: list[str],
    contract_df: pd.DataFrame,
    icd_capture_payload: dict[str, Any],
    icd_capture_gate_mode: str,
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []

    if structural_issues:
        failures.extend([f"STRUCTURAL: {msg}" for msg in structural_issues])
    if governance_issues:
        failures.extend([f"GOVERNANCE: {msg}" for msg in governance_issues])

    contract_failures = contract_df.loc[contract_df["status"] == "fail"].copy() if not contract_df.empty else pd.DataFrame()
    if not contract_failures.empty:
        failures.extend(
            [f"PREPROCESSING_CONTRACT: {row['check_name']}" for row in contract_failures.to_dict(orient="records")]
        )

    icd_status = str(icd_capture_payload.get("status", "pass")).strip().lower()
    icd_gate_mode = str(icd_capture_gate_mode).strip().lower()
    icd_gate_triggered = False
    if icd_gate_mode == "fail" and icd_status == "fail":
        failures.append("ICD_CAPTURE: status=fail and gate-mode=fail")
        icd_gate_triggered = True

    status = {
        "pass": len(failures) == 0,
        "failure_count": len(failures),
        "preprocessing_contract_failures": int(len(contract_failures)),
        "icd_capture_status": icd_status,
        "icd_capture_gate_mode": icd_gate_mode,
        "icd_capture_gate_triggered": icd_gate_triggered,
    }
    return status, failures


def render_report_markdown(
    run_dir: Path,
    stamp: str,
    build_script: Path,
    policy_csv: str | None,
    build_result: dict[str, Any] | None,
    structural_checks: dict[str, Any],
    structural_issues: list[str],
    governance_payload: dict[str, Any],
    governance_issues: list[str],
    contract_df: pd.DataFrame,
    missingness_df: pd.DataFrame,
    icd_capture_payload: dict[str, Any],
    status: dict[str, Any],
    failures: list[str],
) -> str:
    lines: list[str] = []
    lines.append("# Feature Build + Audit Report")
    lines.append("")
    lines.append(f"Generated at (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Run directory: `{run_dir}`")
    lines.append(f"Stamp: `{stamp}`")
    lines.append(f"Build script: `{build_script}`")
    lines.append(f"ICD policy CSV: `{policy_csv}`" if policy_csv else "ICD policy CSV: `<build_features default resolution>`")
    lines.append("")

    lines.append("## Step Coverage")
    lines.append("1. Resolve inputs from `testing_<n>`")
    lines.append("2. Resolve/convert build script")
    lines.append("3. Execute build_features")
    lines.append("4. Load build artifacts")
    lines.append("5. Structural + governance checks")
    lines.append("6. Preprocessing-contract + missingness audits")
    lines.append("7. Persist outputs + pass/fail decision")
    lines.append("")

    if build_result is not None:
        lines.append("## Build Execution")
        lines.append(f"- Exit code: `{build_result.get('exit_code')}`")
        lines.append(f"- Command: `{ ' '.join(build_result.get('command', [])) }`")
        lines.append("")

    lines.append("## Structural Checks")
    for k in sorted(structural_checks):
        lines.append(f"- `{k}`: `{structural_checks[k]}`")
    if structural_issues:
        lines.append("- Issues:")
        for issue in structural_issues:
            lines.append(f"  - {issue}")
    else:
        lines.append("- Issues: none")
    lines.append("")

    lines.append("## Governance Checks")
    for k, v in governance_payload.items():
        lines.append(f"- `{k}`: `{v}`")
    if governance_issues:
        lines.append("- Issues:")
        for issue in governance_issues:
            lines.append(f"  - {issue}")
    else:
        lines.append("- Issues: none")
    lines.append("")

    signal_discovery_payload = governance_payload.get("signal_discovery_checks", {})
    lines.append("## Signal-Discovery Artifact Checks")
    if signal_discovery_payload:
        for k, v in signal_discovery_payload.items():
            lines.append(f"- `{k}`: `{v}`")
    else:
        lines.append("- Signal-discovery artifact checks unavailable.")
    lines.append("")

    lines.append("## Preprocessing Contract Audit")
    if contract_df.empty:
        lines.append("- Preprocessing contract audit unavailable.")
    else:
        lines.append(f"- Contract rows audited: `{len(contract_df)}`")
        failing_rows = contract_df.loc[contract_df["status"] == "fail"].head(10)
        if failing_rows.empty:
            lines.append("- Failing contract rows: none")
        else:
            lines.append("- Failing contract rows:")
            for row in failing_rows.itertuples(index=False):
                lines.append(f"  - `{row.check_name}`: `{row.detail}`")
    lines.append("")

    lines.append("## Missingness Snapshot")
    if missingness_df.empty:
        lines.append("- Missingness summary unavailable.")
    else:
        top_missing = missingness_df.head(10)[["column", "missing_pct", "missing_n"]]
        lines.append("- Top 10 columns by missing %:")
        for row in top_missing.itertuples(index=False):
            lines.append(f"  - `{row.column}`: `{row.missing_pct:.2f}%` ({row.missing_n} rows)")
    lines.append("")

    lines.append("## ICD Capture Reconciliation (diag_all vs diag_xx)")
    lines.append(f"- Status: `{icd_capture_payload.get('status')}`")
    lines.append(f"- Gate mode: `{icd_capture_payload.get('gate_mode')}`")
    lines.append(f"- Warn threshold: `{icd_capture_payload.get('warn_threshold')}`")
    lines.append(f"- Fail threshold: `{icd_capture_payload.get('fail_threshold')}`")
    lines.append(f"- Tables audited: `{icd_capture_payload.get('table_count')}`")
    lines.append(f"- Warn tables: `{icd_capture_payload.get('warn_table_count')}`")
    lines.append(f"- Fail tables: `{icd_capture_payload.get('fail_table_count')}`")
    warn_tables = icd_capture_payload.get("warn_tables", [])
    if warn_tables:
        lines.append(f"- Warn table ids: `{warn_tables}`")
    fail_tables = icd_capture_payload.get("fail_tables", [])
    if fail_tables:
        lines.append(f"- Fail table ids: `{fail_tables}`")
    lines.append("")

    lines.append("## Final Status")
    lines.append(f"- PASS: `{status['pass']}`")
    lines.append(f"- Failure count: `{status['failure_count']}`")
    lines.append(f"- Preprocessing contract failures: `{status['preprocessing_contract_failures']}`")
    if failures:
        lines.append("- Failure reasons:")
        for reason in failures:
            lines.append(f"  - {reason}")
    else:
        lines.append("- Failure reasons: none")

    return "\n".join(lines) + "\n"


def write_audit_outputs(
    run_dir: Path,
    stamp: str,
    structural_checks: dict[str, Any],
    governance_payload: dict[str, Any],
    dict_df: pd.DataFrame,
    contract_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    icd_capture_df: pd.DataFrame,
    icd_capture_payload: dict[str, Any],
    status: dict[str, Any],
    failures: list[str],
    report_md: str,
) -> dict[str, str]:
    out_dict = run_dir / f"feature_dictionary_audit_{stamp}.csv"
    out_contract = run_dir / f"feature_preprocessing_contract_audit_{stamp}.csv"
    out_summary = run_dir / f"feature_missingness_summary_{stamp}.csv"
    out_governance = run_dir / f"feature_governance_checks_{stamp}.json"
    out_icd_capture_csv = run_dir / f"icd_code_capture_audit_{stamp}.csv"
    out_icd_capture_json = run_dir / f"icd_code_capture_audit_{stamp}.json"
    out_manifest = run_dir / f"feature_audit_manifest_{stamp}.json"
    out_report = run_dir / f"feature_audit_report_{stamp}.md"

    dict_df.to_csv(out_dict, index=False)
    contract_df.to_csv(out_contract, index=False)
    summary_df.to_csv(out_summary, index=False)
    icd_capture_df.to_csv(out_icd_capture_csv, index=False)

    governance_payload_with_status = {
        **governance_payload,
        "audit_status": status,
        "audit_failures": failures,
    }
    out_governance.write_text(json.dumps(governance_payload_with_status, indent=2))
    out_icd_capture_json.write_text(json.dumps(icd_capture_payload, indent=2))
    out_report.write_text(report_md)

    manifest = {
        "stamp": stamp,
        "run_dir": str(run_dir),
        "status": status,
        "failures": failures,
        "structural_checks": structural_checks,
        "outputs": {
            "feature_dictionary_audit": str(out_dict),
            "feature_preprocessing_contract_audit": str(out_contract),
            "feature_missingness_summary": str(out_summary),
            "feature_governance_checks": str(out_governance),
            "icd_code_capture_audit_csv": str(out_icd_capture_csv),
            "icd_code_capture_audit_json": str(out_icd_capture_json),
            "feature_audit_report": str(out_report),
        },
    }
    out_manifest.write_text(json.dumps(manifest, indent=2))

    print("Wrote audit artifacts:")
    for p in [
        out_dict,
        out_contract,
        out_summary,
        out_governance,
        out_icd_capture_csv,
        out_icd_capture_json,
        out_report,
        out_manifest,
    ]:
        print("-", p)

    return {
        "feature_dictionary_audit": str(out_dict),
        "feature_preprocessing_contract_audit": str(out_contract),
        "feature_missingness_summary": str(out_summary),
        "feature_governance_checks": str(out_governance),
        "icd_code_capture_audit_csv": str(out_icd_capture_csv),
        "icd_code_capture_audit_json": str(out_icd_capture_json),
        "feature_audit_report": str(out_report),
        "feature_audit_manifest": str(out_manifest),
    }


def main() -> None:
    args = parse_args()
    if float(args.icd_capture_fail_threshold) < float(args.icd_capture_warn_threshold):
        raise ValueError("--icd-capture-fail-threshold must be >= --icd-capture-warn-threshold")

    print("=== STEP 0: Resolve run folder and input artifacts ===")
    run_root = Path(args.run_root)
    run_dir = find_run_dir(run_root, args.run_dir)
    stamp, _ = infer_stamp_from_cohort(run_dir, args.stamp)
    inputs = ensure_inputs_for_stamp(run_dir, stamp)
    print("RUN_DIR:", run_dir)
    print("STAMP:", stamp)
    print("INPUTS:", {k: str(v) for k, v in inputs.items()})

    print("\n=== STEP 1: Resolve build script and policy configuration ===")
    build_script = resolve_build_script(
        run_root=run_root,
        build_script_arg=args.build_script,
        build_notebook_arg=args.build_notebook,
        convert_notebook=args.convert_notebook,
        converted_script_out=args.converted_script_out,
    )
    icd_policy_csv = resolve_icd_policy_csv(run_root, build_script, args.icd_group_policy_csv)
    print("BUILD_SCRIPT:", build_script)
    print("ICD_POLICY_CSV:", icd_policy_csv if icd_policy_csv else "<build_features default>")

    print("\n=== STEP 2: Optional legacy pandas patch ===")
    if args.patch_legacy_pandas and not args.skip_build:
        changed = patch_legacy_pandas_aggregations(build_script)
        print(f"Applied legacy pandas patch replacements: {changed}")
    else:
        print("Legacy pandas patch skipped")

    build_result: dict[str, Any] | None = None
    print("\n=== STEP 3: Execute build_features ===")
    if not args.skip_build:
        build_result = run_build_features(
            build_script=build_script,
            run_dir=run_dir,
            stamp=stamp,
            inputs=inputs,
            icd_group_policy_csv=icd_policy_csv,
            include_missingness_indicators=bool(args.include_missingness_indicators),
            diagnosis_occurrence_threshold_enabled=bool(args.diagnosis_occurrence_threshold_enabled),
            diagnosis_occurrence_threshold=int(args.diagnosis_occurrence_threshold),
            recency_policy_csv=args.recency_policy_csv,
            recency_policy_id=args.recency_policy_id,
            preprocessing_policy_json=args.preprocessing_policy_json,
        )
    else:
        print("Build execution skipped (--skip-build)")

    if args.skip_audit:
        print("\n=== STEP 4-7: Audit skipped (--skip-audit) ===")
        return

    print("\n=== STEP 4: Load build artifacts ===")
    data = load_artifacts(run_dir, stamp)

    print("\n=== STEP 5: Structural and governance checks ===")
    structural_checks, structural_issues = run_structural_checks(data)
    governance_payload, governance_issues = run_governance_checks(data)

    print("\n=== STEP 6: Preprocessing contract and missingness audits ===")
    dict_df = build_column_dictionary(data)
    contract_df = run_preprocessing_contract_audit(data)
    missingness_df = build_missingness_summary(data)
    icd_capture_df, icd_capture_payload = run_icd_code_capture_audit(
        inputs,
        warn_threshold=float(args.icd_capture_warn_threshold),
        fail_threshold=float(args.icd_capture_fail_threshold),
    )
    icd_capture_payload["gate_mode"] = str(args.icd_capture_gate_mode)

    status, failures = evaluate_audit_status(
        structural_issues=structural_issues,
        governance_issues=governance_issues,
        contract_df=contract_df,
        icd_capture_payload=icd_capture_payload,
        icd_capture_gate_mode=str(args.icd_capture_gate_mode),
    )

    print("\n=== STEP 7: Write audit outputs and report ===")
    report_md = render_report_markdown(
        run_dir=run_dir,
        stamp=stamp,
        build_script=build_script,
        policy_csv=icd_policy_csv,
        build_result=build_result,
        structural_checks=structural_checks,
        structural_issues=structural_issues,
        governance_payload=governance_payload,
        governance_issues=governance_issues,
        contract_df=contract_df,
        missingness_df=missingness_df,
        icd_capture_payload=icd_capture_payload,
        status=status,
        failures=failures,
    )

    _ = write_audit_outputs(
        run_dir=run_dir,
        stamp=stamp,
        structural_checks=structural_checks,
        governance_payload=governance_payload,
        dict_df=dict_df,
        contract_df=contract_df,
        summary_df=missingness_df,
        icd_capture_df=icd_capture_df,
        icd_capture_payload=icd_capture_payload,
        status=status,
        failures=failures,
        report_md=report_md,
    )

    print("\nFINAL STATUS:")
    print("- PASS:", status["pass"])
    print("- Failure count:", status["failure_count"])
    print("- Preprocessing contract failures:", status["preprocessing_contract_failures"])

    if not status["pass"] and not args.soft_fail:
        raise RuntimeError(
            "Audit failed strict checks. See feature_audit_report and feature_audit_manifest for details."
        )


if __name__ == "__main__":
    main()
