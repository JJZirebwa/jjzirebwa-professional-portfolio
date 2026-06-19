"""Portfolio copy of the authored final-year project pipeline.

Private run roots and account-specific paths have been replaced with placeholders.
The method structure is preserved for technical review.
"""

from __future__ import annotations

# %% Cell 1: Environment and paths
# This cell defines immutable runtime paths and path-candidates used by downstream cells.
import ast
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd


# Default secure research environment root remains unchanged; ORION_RUN_ROOT supports local simulation and tests.
RUN_ROOT = Path(
    os.environ.get(
        "ORION_RUN_ROOT",
        "data/example_run",
    )
)
FE_DIR = RUN_ROOT / "fyp_scripts" / "feature_engineering"

PY_BUILD = FE_DIR / "build_features.py"
PY_EXEC_AUDIT = FE_DIR / "build_features_execute_and_audit.py"
PY_TRAIN = FE_DIR / "train_models.py"
PY_EDA = FE_DIR / "eda_plots.py"
ICD_POLICY = FE_DIR / "config" / "icd_group_policy.csv"
FEATURE_PROFILE_CSV = FE_DIR / "config" / "feature_family_profiles.csv"
TARGET_PROFILE_CSV = FE_DIR / "config" / "target_profile_mappings.csv"
INVESTIGATION_CONTROL_CSV = FE_DIR / "config" / "investigation_controls.csv"
RECENCY_POLICY_CSV = FE_DIR / "config" / "recency_policy.csv"
SCREENING_SCENARIO_CSV = FE_DIR / "config" / "screening_scenarios.csv"
PREPROCESSING_POLICY_JSON = FE_DIR / "config" / "preprocessing_policy_v1.json"
LOCKED_BASELINE_REFERENCE = "projects/fyp_orion/run_reports/20260223_first_modeling_baseline_run.md"
# Investigation selectors:
# - Set INVESTIGATION_ID for one row, OR
# - set INVESTIGATION_IDS for a controlled list.
INVESTIGATION_ID = ""
INVESTIGATION_IDS = [
    "EG_homozygous_vs_noncarrier_excl_tier12_grouped_burden_compact_primary_v1_lrrf_specguard",
]
BUILD_DIAG_THRESHOLD_ENABLED = True
BUILD_DIAG_THRESHOLD_VALUE = 10
ICD_CAPTURE_GATE_MODE = "warn"
ICD_CAPTURE_WARN_THRESHOLD = 0.005
ICD_CAPTURE_FAIL_THRESHOLD = 0.02
RANDOM_STATES = [42, 52, 62, 72, 82]
THRESHOLD_POLICY = "train_balanced_accuracy_min_specificity"
MIN_SPECIFICITY_FLOOR = 0.55
NN_HIDDEN_LAYERS = "32,16"
NN_ALPHA = 0.001
NN_LEARNING_RATE_INIT = 0.0005
NN_MAX_ITER = 1200
NN_EARLY_STOPPING = True
NN_PERMUTATION_REPEATS = 30
NN_PERMUTATION_MAX_ROWS = 0
# Optional manual signal-discovery execution after Cell 9A.
# Keep this disabled unless you explicitly want the notebook to launch the opt-in branch.
RUN_SIGNAL_DISCOVERY_AFTER_9A = False
SIGNAL_DISCOVERY_MODEL_TYPES = ["lr"]
SIGNAL_DISCOVERY_RANDOM_STATE = 42
SIGNAL_DISCOVERY_RUN_TAG_SUFFIX = "seed42"

NB_CANDIDATES = {
    "build_features": [FE_DIR / "build_features.ipynb", FE_DIR / "build_feature.ipynb"],
    "exec_audit": [
        FE_DIR / "build_features_execute_and_audit.ipynb",
        FE_DIR / "feature_engineering_execute_and_audit.ipynb",
    ],
    "train_models": [FE_DIR / "train_models.ipynb"],
    "eda_plots": [FE_DIR / "eda_plots.ipynb"],
}

print("Interpreter:", sys.executable)
print("RUN_ROOT:", RUN_ROOT)
print("FE_DIR:", FE_DIR)


# %% Cell 2: Validate expected secure research environment files exist
# This cell checks static preconditions before any run-specific logic is attempted.
required_static = [
    RUN_ROOT,
    FE_DIR,
    ICD_POLICY,
    FEATURE_PROFILE_CSV,
    TARGET_PROFILE_CSV,
    INVESTIGATION_CONTROL_CSV,
    RECENCY_POLICY_CSV,
    PREPROCESSING_POLICY_JSON,
]
missing_static = [str(p) for p in required_static if not p.exists()]
if missing_static:
    raise FileNotFoundError("Missing required static paths:\n" + "\n".join(missing_static))

for logical_name, candidates in NB_CANDIDATES.items():
    exists_any = any(p.exists() for p in candidates)
    if not exists_any:
        tried = "\n".join(str(p) for p in candidates)
        raise FileNotFoundError(
            f"Notebook not found for '{logical_name}'. Tried:\n{tried}"
        )

print("Static path checks passed.")


# %% Cell 3: Helpers
# Helper functions are centralized here so each execution phase remains concise and auditable.
def first_existing(candidates: list[Path], label: str) -> Path:
    for p in candidates:
        if p.exists():
            return p
    tried = "\n".join(str(p) for p in candidates)
    raise FileNotFoundError(f"No path found for {label}. Tried:\n{tried}")


def slug_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    return cleaned.strip("_") or "unset"


def build_train_run_tag(
    model_type: str,
    feature_token: str,
    stamp: str,
    target_col: str,
    target_profile: str,
    investigation_id: str = "",
    target_name: str = "",
    recency_policy_id: str = "",
    run_tag_suffix: str = "",
) -> str:
    feature_tag = slug_token(feature_token)
    if investigation_id:
        inv_tag = slug_token(investigation_id)
        target_name_tag = slug_token(target_name or target_col)
        recency_tag = slug_token(recency_policy_id or "unset")
        base = f"{model_type}_{feature_tag}_inv_{inv_tag}_{target_name_tag}_{recency_tag}_{stamp}"
        if run_tag_suffix:
            return f"{base}_{slug_token(run_tag_suffix)}"
        return base
    if target_profile:
        base = f"{model_type}_{feature_tag}_profile_{slug_token(target_profile)}_{stamp}"
        if run_tag_suffix:
            return f"{base}_{slug_token(run_tag_suffix)}"
        return base
    if target_col == "promoter_carrier":
        base = f"{model_type}_{feature_tag}_{stamp}"
        if run_tag_suffix:
            return f"{base}_{slug_token(run_tag_suffix)}"
        return base
    base = f"{model_type}_{feature_tag}_{slug_token(target_col)}_{stamp}"
    if run_tag_suffix:
        return f"{base}_{slug_token(run_tag_suffix)}"
    return base


def summarize_metrics_row(model_type: str, payload: dict, investigation_id: str) -> dict:
    m = payload.get("metrics", {})
    return {
        "investigation_id": investigation_id,
        "model": model_type,
        "run_tag": payload.get("run_tag"),
        "seed": payload.get("args", {}).get("random_state"),
        "threshold_policy": payload.get("args", {}).get("threshold_policy"),
        "selected_threshold": payload.get("threshold_selection", {}).get("selected_threshold"),
        "target_col": payload.get("target_col"),
        "target_type": payload.get("target_type"),
        "accuracy": m.get("accuracy"),
        "balanced_accuracy": m.get("balanced_accuracy"),
        "roc_auc": m.get("roc_auc"),
        "pr_auc": m.get("pr_auc"),
        "roc_auc_macro_ovr": m.get("roc_auc_macro_ovr"),
        "pr_auc_macro_ovr": m.get("pr_auc_macro_ovr"),
        "brier": m.get("brier"),
        "sensitivity": m.get("sensitivity"),
        "specificity": m.get("specificity"),
        "precision": m.get("precision"),
        "macro_precision": m.get("macro_precision"),
        "macro_f1": m.get("macro_f1"),
    }


def load_investigation_controls(path: Path) -> pd.DataFrame:
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
        "feature_profile",
        "recency_policy_id",
        "run_lr",
        "run_rf",
        "run_nn",
        "screening_enabled",
        "screening_scenario_id",
        "screening_mode",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Investigation controls CSV missing columns: {sorted(missing)}")

    cleaned = df.copy()
    for col in (
        "investigation_id",
        "target_name",
        "target_column",
        "target_profile",
        "feature_profile",
        "recency_policy_id",
        "screening_scenario_id",
        "screening_mode",
    ):
        cleaned[col] = cleaned[col].astype(str).str.strip().replace({"nan": "", "None": ""})
    for col in ("run_lr", "run_rf", "run_nn", "screening_enabled"):
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").fillna(0).astype(int)
    cleaned = cleaned[cleaned["investigation_id"] != ""].copy()
    cleaned["target_profile"] = cleaned["target_profile"].replace({"": pd.NA}).fillna("")
    cleaned["target_column"] = cleaned["target_column"].replace({"": pd.NA})
    direct_target_mask = cleaned["target_profile"] == ""
    cleaned.loc[direct_target_mask, "target_column"] = cleaned.loc[
        direct_target_mask, "target_column"
    ].fillna(cleaned.loc[direct_target_mask, "target_name"].replace({"": pd.NA}))
    cleaned["target_column"] = cleaned["target_column"].fillna("")
    cleaned["recency_policy_id"] = cleaned["recency_policy_id"].replace({"": "minimal"})

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


def resolve_latest_run(require_stage1_inputs: bool = True) -> tuple[Path, str]:
    run_dirs = sorted(RUN_ROOT.glob("testing_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not run_dirs:
        raise RuntimeError(f"No testing_* folders found in {RUN_ROOT}")
    run_dir = run_dirs[0]

    cohort_files = sorted(
        run_dir.glob("cohort_basic_with_haplotype_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cohort_files:
        raise RuntimeError(f"No cohort_basic_with_haplotype_*.csv found in {run_dir}")

    m = re.search(r"(\d{4}-\d{2}-\d{2})", cohort_files[0].name)
    if not m:
        raise RuntimeError(f"Could not parse stamp from {cohort_files[0].name}")
    stamp = m.group(1)

    if require_stage1_inputs:
        needed = [
            run_dir / f"cohort_basic_with_haplotype_{stamp}.csv",
            run_dir / f"hes_apc_censored_{stamp}.csv",
            run_dir / f"hes_op_censored_{stamp}.csv",
            run_dir / f"hes_ae_censored_{stamp}.csv",
        ]
        missing = [str(p) for p in needed if not p.exists()]
        if missing:
            raise FileNotFoundError("Missing required stage-1 inputs:\n" + "\n".join(missing))

    return run_dir, stamp


def run_cmd(
    cmd: list[str],
    run_dir: Path,
    label: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run subprocess and persist stdout/stderr logs for deterministic debugging."""
    stdout_path = run_dir / f"{label}_stdout.log"
    stderr_path = run_dir / f"{label}_stderr.log"

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
    )
    stdout_path.write_text(res.stdout or "", encoding="utf-8")
    stderr_path.write_text(res.stderr or "", encoding="utf-8")

    print("Label:", label)
    print("Exit code:", res.returncode)
    print("CWD:", cwd if cwd is not None else Path.cwd())
    print("STDOUT log:", stdout_path)
    print("STDERR log:", stderr_path)

    if res.returncode != 0:
        tail = (res.stderr or "").splitlines()[-40:]
        raise RuntimeError("Command failed.\nLast stderr lines:\n" + "\n".join(tail))
    return res


def convert_notebook_to_script(nb_path: Path, py_path: Path) -> tuple[int, int]:
    """Convert notebook code cells to `.py`, skipping shell/magic lines and malformed cells."""
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    kept_cells = 0
    skipped_cells = 0
    out_lines = [f'"""Auto-generated from {nb_path.name} (code cells only)."""\n']

    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue

        raw_src = "".join(cell.get("source", []))
        cleaned_lines: list[str] = []
        for line in raw_src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("%") or stripped.startswith("!"):
                continue
            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines).strip()
        if not cleaned:
            skipped_cells += 1
            continue

        try:
            ast.parse(cleaned)
        except SyntaxError:
            skipped_cells += 1
            continue

        kept_cells += 1
        out_lines.append(f"\n# %% Notebook Cell {kept_cells}\n")
        out_lines.append(cleaned + "\n")

    py_path.write_text("".join(out_lines), encoding="utf-8")
    return kept_cells, skipped_cells


def patch_exec_audit_variable_drift(py_exec_audit: Path) -> int:
    """Patch legacy notebook-conversion drift in the executable audit runner."""
    txt = py_exec_audit.read_text(encoding="utf-8")
    replacements = 0

    if "transform_audit" in txt:
        txt = txt.replace("transform_audit", "transform_df")
        replacements += 1

    # Remove accidental notebook display calls that can break script-mode execution.
    for bad in ("transform_df.head(", "transform_audit.head("):
        if bad in txt:
            lines = []
            for line in txt.splitlines():
                if bad in line and line.strip().startswith(("transform_df.head(", "transform_audit.head(")):
                    continue
                lines.append(line)
            txt = "\n".join(lines) + "\n"
            replacements += 1

    py_exec_audit.write_text(txt, encoding="utf-8")
    return replacements


def compile_check(py_files: list[Path]) -> None:
    cmd = [sys.executable, "-m", "py_compile", *[str(p) for p in py_files]]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            "py_compile failed.\nSTDOUT:\n"
            + (res.stdout or "")
            + "\nSTDERR:\n"
            + (res.stderr or "")
        )
    print("py_compile rc:", res.returncode)


def find_top_level_head_calls(script_text: str) -> list[int]:
    """Return line numbers of true top-level legacy transform audit `.head(...)` calls."""
    try:
        tree = ast.parse(script_text)
    except SyntaxError:
        return []

    line_numbers: list[int] = []
    for node in tree.body:
        if not isinstance(node, ast.Expr):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "head":
            continue
        if not isinstance(func.value, ast.Name):
            continue
        if func.value.id in {"transform_df", "transform_audit"}:
            line_numbers.append(int(getattr(node, "lineno", -1)))
    return line_numbers


# %% Cell 4: Confirm latest testing run and stamp
# This cell pins the run to one exact `testing_*` folder and one exact date-stamp.
RUN_DIR, STAMP = resolve_latest_run(require_stage1_inputs=True)
print("RUN_DIR:", RUN_DIR)
print("STAMP:", STAMP)

INVESTIGATION_ID_ARG = INVESTIGATION_ID.strip()
INVESTIGATION_ID_LIST_ARG = [str(v).strip() for v in INVESTIGATION_IDS if str(v).strip()]
if INVESTIGATION_ID_ARG and INVESTIGATION_ID_LIST_ARG:
    raise ValueError("Set either INVESTIGATION_ID or INVESTIGATION_IDS, not both.")
investigation_controls_df = load_investigation_controls(INVESTIGATION_CONTROL_CSV)
if INVESTIGATION_ID_ARG:
    investigation_controls_df = investigation_controls_df.loc[
        investigation_controls_df["investigation_id"] == INVESTIGATION_ID_ARG
    ].copy()
    if investigation_controls_df.empty:
        raise ValueError(f"Investigation id not found in controls CSV: {INVESTIGATION_ID_ARG}")
elif INVESTIGATION_ID_LIST_ARG:
    requested_ids = set(INVESTIGATION_ID_LIST_ARG)
    investigation_controls_df = investigation_controls_df.loc[
        investigation_controls_df["investigation_id"].isin(requested_ids)
    ].copy()
    found_ids = set(investigation_controls_df["investigation_id"].astype(str).tolist())
    missing_ids = sorted(requested_ids.difference(found_ids))
    if missing_ids:
        raise ValueError(f"Investigation ids not found in controls CSV: {missing_ids}")

INVESTIGATION_ROWS = investigation_controls_df.to_dict(orient="records")
if not INVESTIGATION_ROWS:
    raise RuntimeError("No investigation rows selected for execution.")

print("Investigation rows selected:", len(INVESTIGATION_ROWS))
print("Investigation ids:", [r.get("investigation_id") for r in INVESTIGATION_ROWS])


def load_screening_scenarios(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing screening scenarios CSV: {path}")
    df = pd.read_csv(path)
    required = {"screening_scenario_id"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Screening scenarios CSV missing columns: {sorted(missing)}")
    cleaned = df.copy()
    cleaned["screening_scenario_id"] = cleaned["screening_scenario_id"].astype(str).str.strip()
    cleaned = cleaned[cleaned["screening_scenario_id"] != ""].copy()
    if cleaned["screening_scenario_id"].duplicated().any():
        dups = sorted(cleaned.loc[cleaned["screening_scenario_id"].duplicated(), "screening_scenario_id"].unique().tolist())
        raise ValueError(f"Duplicate screening_scenario_id rows found: {dups}")
    return cleaned.reset_index(drop=True)


def load_feature_build_metadata(run_dir: Path, stamp: str) -> dict:
    metadata_path = run_dir / f"features_matrix_metadata_{stamp}.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing feature-build metadata for screening context resolution: {metadata_path}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def resolve_output_path_from_metadata(
    metadata: dict,
    run_dir: Path,
    stamp: str,
    output_key: str,
    filename_template: str,
) -> Path:
    outputs = metadata.get("outputs", {})
    candidate = outputs.get(output_key)
    path = Path(str(candidate)) if candidate else run_dir / filename_template.format(stamp=stamp)
    if not path.exists():
        raise FileNotFoundError(f"Missing required signal-discovery artifact for {output_key}: {path}")
    return path


def build_signal_discovery_context(
    investigation_row: dict,
    run_dir: Path,
    stamp: str,
    screening_scenarios_df: pd.DataFrame,
) -> dict:
    investigation_id = str(investigation_row.get("investigation_id", "")).strip()
    screening_scenario_id = str(investigation_row.get("screening_scenario_id", "")).strip()
    screening_mode = str(investigation_row.get("screening_mode", "")).strip()
    if not screening_scenario_id:
        raise ValueError(
            f"{investigation_id}: screening_enabled=1 but screening_scenario_id is missing"
        )
    if screening_mode != "raw_icd_signal_discovery":
        raise ValueError(
            f"{investigation_id}: screening_enabled=1 but screening_mode={screening_mode!r} is invalid"
        )
    if screening_scenarios_df.empty:
        raise ValueError(f"{investigation_id}: screening_enabled=1 but no screening scenarios are loaded")
    scenario_match = screening_scenarios_df.loc[
        screening_scenarios_df["screening_scenario_id"] == screening_scenario_id
    ]
    if scenario_match.empty:
        raise ValueError(
            f"{investigation_id}: screening_scenario_id not found in screening_scenarios.csv: {screening_scenario_id}"
        )

    metadata = load_feature_build_metadata(run_dir, stamp)
    signal_meta = metadata.get("signal_discovery_meta", {})
    authoritative_source = str(signal_meta.get("authoritative_source", "")).strip()
    source_columns_by_table = signal_meta.get("source_columns_by_table", {})
    if authoritative_source != "diag_all":
        raise ValueError(
            f"{investigation_id}: signal-discovery metadata authoritative_source={authoritative_source!r}; expected 'diag_all'"
        )
    for table_name, cols in source_columns_by_table.items():
        normalized_cols = [str(col) for col in cols]
        if normalized_cols != ["diag_all"]:
            raise ValueError(
                f"{investigation_id}: signal-discovery source columns for {table_name} are {normalized_cols}; expected ['diag_all']"
            )

    raw_code_matrix_path = resolve_output_path_from_metadata(
        metadata,
        run_dir,
        stamp,
        "icd_raw_discovery_matrix",
        "icd_raw_discovery_matrix_{stamp}.csv",
    )
    stage_a_path = resolve_output_path_from_metadata(
        metadata,
        run_dir,
        stamp,
        "icd_raw_stage_a_preparation",
        "icd_raw_stage_a_preparation_{stamp}.csv",
    )
    grouped_anchor_path = resolve_output_path_from_metadata(
        metadata,
        run_dir,
        stamp,
        "icd_group_anchor_comparison",
        "icd_group_anchor_comparison_{stamp}.csv",
    )

    return {
        "investigation_id": investigation_id,
        "target_name": str(investigation_row.get("target_name", "")).strip(),
        "branch_mode": "signal_discovery_opt_in",
        "screening_enabled": True,
        "screening_mode": screening_mode,
        "screening_scenario_id": screening_scenario_id,
        "baseline_reference": LOCKED_BASELINE_REFERENCE,
        "discovery_inputs": {
            "raw_code_matrix_path": str(raw_code_matrix_path),
            "stage_a_preparation_path": str(stage_a_path),
        },
        "comparison_only_grouped_anchor_artifacts": {
            "grouped_anchor_comparison_path": str(grouped_anchor_path),
            "comparison_only": True,
            "not_model_input": True,
        },
        "signal_discovery_constraints": {
            "authoritative_source": authoritative_source,
            "source_columns_by_table": source_columns_by_table,
            "no_stage_a_or_b_screening_in_driver": True,
        },
        "downstream_handoff": {
            "context_only": True,
            "model_training_deferred_until_stage_6_5": True,
        },
    }


SCREENING_ROWS = [row for row in INVESTIGATION_ROWS if int(row.get("screening_enabled", 0)) == 1]
LEGACY_INVESTIGATION_ROWS = [row for row in INVESTIGATION_ROWS if int(row.get("screening_enabled", 0)) != 1]
SCREENING_SCENARIOS_DF = load_screening_scenarios(SCREENING_SCENARIO_CSV) if SCREENING_ROWS else pd.DataFrame()


# %% Cell 5: Notebook-to-PY conversion plus PY compile validation
# This merged cell replaces earlier split conversion/compile cells and is now canonical.
NB_BUILD = first_existing(NB_CANDIDATES["build_features"], "build_features notebook")
NB_EXEC_AUDIT = first_existing(NB_CANDIDATES["exec_audit"], "feature_engineering_execute_and_audit notebook")
NB_TRAIN = first_existing(NB_CANDIDATES["train_models"], "train_models notebook")
NB_EDA = first_existing(NB_CANDIDATES["eda_plots"], "eda_plots notebook")

conversions = [
    (NB_BUILD, PY_BUILD),
    (NB_EXEC_AUDIT, PY_EXEC_AUDIT),
    (NB_TRAIN, PY_TRAIN),
    (NB_EDA, PY_EDA),
]

for nb_path, py_path in conversions:
    should_convert = (not py_path.exists()) or (nb_path.stat().st_mtime > py_path.stat().st_mtime)
    if should_convert:
        kept, skipped = convert_notebook_to_script(nb_path, py_path)
        print(f"Converted {nb_path.name} -> {py_path.name} | kept={kept}, skipped={skipped}")
    else:
        print(f"Skipped conversion for {py_path.name}; script is newer than notebook.")

patched = patch_exec_audit_variable_drift(PY_EXEC_AUDIT)
if patched:
    print("Patched converted audit runner drift edits:", patched)

txt = PY_EXEC_AUDIT.read_text(encoding="utf-8")
legacy_transform_markers = [
    marker
    for marker in (
        "run_transform_rebuild_audit(",
        "feature_transform_rebuild_audit_",
        "transform_df = run_transform_rebuild_audit(data)",
    )
    if marker in txt
]
if legacy_transform_markers:
    raise RuntimeError(
        "Preflight failed: converted audit runner still contains retired transform-rebuild logic: "
        + ", ".join(repr(marker) for marker in legacy_transform_markers)
    )
required_contract_markers = [
    marker
    for marker in (
        "run_preprocessing_contract_audit(",
        "feature_preprocessing_contract_audit_",
        "feature_audit_manifest_",
    )
    if marker not in txt
]
if required_contract_markers:
    raise RuntimeError(
        "Preflight failed: converted audit runner is missing preprocessing-contract markers: "
        + ", ".join(repr(marker) for marker in required_contract_markers)
    )
head_call_lines = find_top_level_head_calls(txt)
if head_call_lines:
    raise RuntimeError(
        "Preflight failed: leftover top-level legacy transform .head(...) call found in converted audit runner "
        f"at lines {head_call_lines}"
    )

compile_check([PY_BUILD, PY_EXEC_AUDIT, PY_TRAIN, PY_EDA])


# %% Cell 7: Run build + audit (RUN_DIR, STAMP pinned)
# This is the execution cell that produces/refreshes features and writes audit artifacts.
cmd_build_audit = [
    sys.executable,
    str(PY_EXEC_AUDIT),
    "--run-root",
    str(RUN_ROOT),
    "--run-dir",
    str(RUN_DIR),
    "--stamp",
    STAMP,
    "--build-script",
    str(PY_BUILD),
    "--icd-group-policy-csv",
    str(ICD_POLICY),
    "--preprocessing-policy-json",
    str(PREPROCESSING_POLICY_JSON),
    "--icd-capture-gate-mode",
    ICD_CAPTURE_GATE_MODE,
    "--icd-capture-warn-threshold",
    str(ICD_CAPTURE_WARN_THRESHOLD),
    "--icd-capture-fail-threshold",
    str(ICD_CAPTURE_FAIL_THRESHOLD),
]
if BUILD_DIAG_THRESHOLD_ENABLED:
    cmd_build_audit.extend(
        [
            "--diagnosis-occurrence-threshold-enabled",
            "--diagnosis-occurrence-threshold",
            str(BUILD_DIAG_THRESHOLD_VALUE),
        ]
    )
# In secure research environment, older pandas may reject named aggregation signatures in build_features; keep compatibility patch enabled.
cmd_build_audit.append("--patch-legacy-pandas")
run_cmd(cmd_build_audit, RUN_DIR, "step4_build_audit")


# %% Cell 9: Gate cell after running feature_engineering_execute_and_audit.ipynb
# This gate enforces audit pass before model training.
manifest_path = RUN_DIR / f"feature_audit_manifest_{STAMP}.json"
if not manifest_path.exists():
    raise FileNotFoundError(f"Missing audit manifest: {manifest_path}")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
status = manifest.get("status", {})
if not status.get("pass", False) or int(status.get("failure_count", 1)) != 0:
    raise RuntimeError(
        "Audit gate failed.\n"
        f"pass={status.get('pass')} failure_count={status.get('failure_count')}\n"
        f"manifest={manifest_path}"
    )

required_audit_outputs = [
    RUN_DIR / f"feature_dictionary_audit_{STAMP}.csv",
    RUN_DIR / f"feature_preprocessing_contract_audit_{STAMP}.csv",
    RUN_DIR / f"feature_missingness_summary_{STAMP}.csv",
]
missing = [str(p) for p in required_audit_outputs if not p.exists()]
if missing:
    raise FileNotFoundError("Missing audit outputs:\n" + "\n".join(missing))

contract_df = pd.read_csv(RUN_DIR / f"feature_preprocessing_contract_audit_{STAMP}.csv")
contract_failures = int((contract_df["status"] == "fail").sum()) if len(contract_df) else 0
print("Audit gate PASS")
print("preprocessing_contract_failures:", contract_failures)


# %% Cell 9A: Build driver branch manifest and signal-discovery handoff context
# This cell resolves branch mode per investigation row without performing any screening in the driver.
driver_manifest_path = RUN_DIR / f"feature_engineering_driver_manifest_{STAMP}.json"
driver_context_rows: list[dict[str, object]] = []
signal_discovery_context_rows: list[dict[str, object]] = []
legacy_training_rows: list[dict[str, object]] = []

for inv in INVESTIGATION_ROWS:
    investigation_id = str(inv.get("investigation_id", "")).strip()
    screening_enabled = int(inv.get("screening_enabled", 0)) == 1
    if screening_enabled:
        context = build_signal_discovery_context(
            investigation_row=inv,
            run_dir=RUN_DIR,
            stamp=STAMP,
            screening_scenarios_df=SCREENING_SCENARIOS_DF,
        )
        signal_discovery_context_rows.append(context)
        driver_context_rows.append(context)
        print(
            f"Prepared signal-discovery context for {investigation_id}; "
            "downstream model execution deferred until Stage 6.5."
        )
        continue

    legacy_context = {
        "investigation_id": investigation_id,
        "target_name": str(inv.get("target_name", "")).strip(),
        "branch_mode": "legacy_grouped_feature_default",
        "screening_enabled": False,
        "screening_mode": "",
        "screening_scenario_id": "",
        "baseline_reference": LOCKED_BASELINE_REFERENCE,
    }
    driver_context_rows.append(legacy_context)
    legacy_training_rows.append(inv)

driver_manifest = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_dir": str(RUN_DIR),
    "stamp": STAMP,
    "baseline_reference": LOCKED_BASELINE_REFERENCE,
    "branch_summary": {
        "legacy_grouped_feature_default_count": int(len(legacy_training_rows)),
        "signal_discovery_opt_in_count": int(len(signal_discovery_context_rows)),
    },
    "investigations": driver_context_rows,
}
driver_manifest_path.write_text(json.dumps(driver_manifest, indent=2), encoding="utf-8")
print("Driver manifest:", driver_manifest_path)


# %% Cell 9B: Optional signal-discovery model execution from the notebook
# This cell is off by default because the signal branch must remain opt-in.
signal_metrics_files: list[dict[str, str | Path]] = []
signal_baseline_reference_path = RUN_ROOT / LOCKED_BASELINE_REFERENCE
print("Signal-discovery baseline reference expected at:", signal_baseline_reference_path)

if signal_discovery_context_rows and not RUN_SIGNAL_DISCOVERY_AFTER_9A:
    print(
        "Signal-discovery notebook execution is disabled. "
        "Set RUN_SIGNAL_DISCOVERY_AFTER_9A = True and rerun this cell to launch "
        "train_models.py for the selected screening-enabled investigations."
    )
elif signal_discovery_context_rows:
    if not signal_baseline_reference_path.exists():
        raise FileNotFoundError(
            "Signal-discovery baseline reference not found at the notebook-run location: "
            f"{signal_baseline_reference_path}"
        )

    screening_rows_by_id = {
        str(row.get("investigation_id", "")).strip(): row for row in SCREENING_ROWS
    }

    for context in signal_discovery_context_rows:
        investigation_id = str(context.get("investigation_id", "")).strip()
        inv = screening_rows_by_id.get(investigation_id)
        if inv is None:
            raise RuntimeError(
                f"Could not resolve screening investigation row for context: {investigation_id}"
            )

        feature_token = str(inv.get("feature_profile", "")).strip() or "raw_icd_signal_discovery"
        target_profile = str(inv.get("target_profile", "")).strip()
        target_col = str(inv.get("target_column", "")).strip() or str(inv.get("target_name", "")).strip()
        target_name = str(inv.get("target_name", "")).strip() or target_col
        recency_policy_id = str(inv.get("recency_policy_id", "")).strip() or "minimal"

        for model_type in SIGNAL_DISCOVERY_MODEL_TYPES:
            run_key = f"run_{model_type}"
            if int(inv.get(run_key, 0)) != 1:
                print(f"Skipping {investigation_id} {model_type}: {run_key}=0")
                continue

            cmd_train = [
                sys.executable,
                str(PY_TRAIN),
                "--run-root",
                str(RUN_ROOT),
                "--run-dir",
                str(RUN_DIR),
                "--stamp",
                STAMP,
                "--model-type",
                model_type,
                "--feature-profile-csv",
                str(FEATURE_PROFILE_CSV),
                "--preprocessing-policy-json",
                str(PREPROCESSING_POLICY_JSON),
                "--target-profile-csv",
                str(TARGET_PROFILE_CSV),
                "--icd-group-policy-csv",
                str(ICD_POLICY),
                "--investigation-id",
                investigation_id,
                "--investigation-control-csv",
                str(INVESTIGATION_CONTROL_CSV),
                "--recency-policy-csv",
                str(RECENCY_POLICY_CSV),
                "--screening-scenario-csv",
                str(SCREENING_SCENARIO_CSV),
                "--driver-manifest",
                str(driver_manifest_path),
                "--random-state",
                str(int(SIGNAL_DISCOVERY_RANDOM_STATE)),
                "--threshold-policy",
                THRESHOLD_POLICY,
                "--min-specificity-floor",
                str(MIN_SPECIFICITY_FLOOR),
                "--class-weight-mode",
                "none",
                "--calibration-mode",
                "none",
            ]
            if SIGNAL_DISCOVERY_RUN_TAG_SUFFIX:
                cmd_train.extend(["--run-tag-suffix", SIGNAL_DISCOVERY_RUN_TAG_SUFFIX])
            if model_type == "nn":
                cmd_train.extend(
                    [
                        "--nn-hidden-layers",
                        NN_HIDDEN_LAYERS,
                        "--nn-alpha",
                        str(NN_ALPHA),
                        "--nn-learning-rate-init",
                        str(NN_LEARNING_RATE_INIT),
                        "--nn-max-iter",
                        str(NN_MAX_ITER),
                        "--nn-permutation-repeats",
                        str(NN_PERMUTATION_REPEATS),
                        "--nn-permutation-max-rows",
                        str(NN_PERMUTATION_MAX_ROWS),
                    ]
                )
                if NN_EARLY_STOPPING:
                    cmd_train.append("--nn-early-stopping")

            run_cmd(
                cmd_train,
                RUN_DIR,
                f"step5_signal_{investigation_id}_{model_type}_seed{int(SIGNAL_DISCOVERY_RANDOM_STATE)}",
                cwd=RUN_ROOT,
            )

            run_tag = build_train_run_tag(
                model_type=model_type,
                feature_token=feature_token,
                stamp=STAMP,
                target_col=target_col,
                target_profile=target_profile,
                investigation_id=investigation_id,
                target_name=target_name,
                recency_policy_id=recency_policy_id,
                run_tag_suffix=SIGNAL_DISCOVERY_RUN_TAG_SUFFIX,
            )
            metrics_path = RUN_DIR / f"model_metrics_{run_tag}.json"
            if not metrics_path.exists():
                raise FileNotFoundError(f"Missing signal-discovery model metrics file: {metrics_path}")
            signal_metrics_files.append(
                {
                    "investigation_id": investigation_id,
                    "model_type": model_type,
                    "random_state": int(SIGNAL_DISCOVERY_RANDOM_STATE),
                    "path": metrics_path,
                }
            )
else:
    print("No signal-discovery investigations selected for Cell 9B.")


# %% Cell 10: Train models for LR, RF and NN
# This cell runs model families per investigation-control row for reproducible A/B/C orchestration.
summary_rows = []
metrics_files: list[dict[str, str | Path]] = []
for inv in legacy_training_rows:
    investigation_id = str(inv.get("investigation_id", "")).strip()
    feature_token = str(inv.get("feature_profile", "")).strip() or "icd_relevant_only"
    target_profile = str(inv.get("target_profile", "")).strip()
    target_col = str(inv.get("target_column", "")).strip() or str(inv.get("target_name", "")).strip()
    target_name = str(inv.get("target_name", "")).strip() or target_col
    recency_policy_id = str(inv.get("recency_policy_id", "")).strip() or "minimal"

    for model_type in ("lr", "rf", "nn"):
        run_key = f"run_{model_type}"
        if int(inv.get(run_key, 0)) != 1:
            print(f"Skipping {investigation_id} {model_type}: {run_key}=0")
            continue
        for random_state in RANDOM_STATES:
            run_tag_suffix = f"seed{int(random_state)}"
            cmd_train = [
                sys.executable,
                str(PY_TRAIN),
                "--run-root",
                str(RUN_ROOT),
                "--run-dir",
                str(RUN_DIR),
                "--stamp",
                STAMP,
                "--model-type",
                model_type,
                "--feature-profile-csv",
                str(FEATURE_PROFILE_CSV),
                "--preprocessing-policy-json",
                str(PREPROCESSING_POLICY_JSON),
                "--target-profile-csv",
                str(TARGET_PROFILE_CSV),
                "--icd-group-policy-csv",
                str(ICD_POLICY),
                "--investigation-id",
                investigation_id,
                "--investigation-control-csv",
                str(INVESTIGATION_CONTROL_CSV),
                "--recency-policy-csv",
                str(RECENCY_POLICY_CSV),
                "--random-state",
                str(int(random_state)),
                "--threshold-policy",
                THRESHOLD_POLICY,
                "--min-specificity-floor",
                str(MIN_SPECIFICITY_FLOOR),
                "--class-weight-mode",
                "none",
                "--calibration-mode",
                "none",
                "--run-tag-suffix",
                run_tag_suffix,
            ]
            if model_type == "nn":
                cmd_train.extend(
                    [
                        "--nn-hidden-layers",
                        NN_HIDDEN_LAYERS,
                        "--nn-alpha",
                        str(NN_ALPHA),
                        "--nn-learning-rate-init",
                        str(NN_LEARNING_RATE_INIT),
                        "--nn-max-iter",
                        str(NN_MAX_ITER),
                        "--nn-permutation-repeats",
                        str(NN_PERMUTATION_REPEATS),
                        "--nn-permutation-max-rows",
                        str(NN_PERMUTATION_MAX_ROWS),
                    ]
                )
                if NN_EARLY_STOPPING:
                    cmd_train.append("--nn-early-stopping")

            run_cmd(
                cmd_train,
                RUN_DIR,
                f"step5_train_{investigation_id}_{model_type}_seed{int(random_state)}",
            )
            run_tag = build_train_run_tag(
                model_type=model_type,
                feature_token=feature_token,
                stamp=STAMP,
                target_col=target_col,
                target_profile=target_profile,
                investigation_id=investigation_id,
                target_name=target_name,
                recency_policy_id=recency_policy_id,
                run_tag_suffix=run_tag_suffix,
            )
            metrics_path = RUN_DIR / f"model_metrics_{run_tag}.json"
            if not metrics_path.exists():
                raise FileNotFoundError(f"Missing model metrics file: {metrics_path}")
            metrics_files.append(
                {
                    "investigation_id": investigation_id,
                    "model_type": model_type,
                    "random_state": int(random_state),
                    "path": metrics_path,
                }
            )

for metrics_item in metrics_files:
    metrics_path = Path(str(metrics_item["path"]))
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    summary_rows.append(
        summarize_metrics_row(
            model_type=str(metrics_item["model_type"]),
            payload=payload,
            investigation_id=str(metrics_item["investigation_id"]),
        )
    )

if summary_rows:
    summary_df = pd.DataFrame(summary_rows).sort_values(["investigation_id", "model", "seed"])
    print(summary_df.to_string(index=False))
else:
    summary_df = pd.DataFrame(columns=["investigation_id", "model", "seed"])
    print("No legacy model-training rows were executed in this driver run.")

agg_rows: list[dict[str, object]] = []
if not summary_df.empty:
    metric_cols = [
        "balanced_accuracy",
        "roc_auc",
        "pr_auc",
        "sensitivity",
        "specificity",
        "brier",
    ]
    for (investigation_id, model), sub_df in summary_df.groupby(["investigation_id", "model"]):
        row: dict[str, object] = {
            "investigation_id": investigation_id,
            "model": model,
            "n_runs": int(len(sub_df)),
        }
        for metric_col in metric_cols:
            vals = pd.to_numeric(sub_df[metric_col], errors="coerce").dropna()
            if vals.empty:
                row[f"{metric_col}_median"] = pd.NA
                row[f"{metric_col}_iqr"] = pd.NA
            else:
                q1 = float(vals.quantile(0.25))
                q3 = float(vals.quantile(0.75))
                row[f"{metric_col}_median"] = float(vals.median())
                row[f"{metric_col}_iqr"] = float(q3 - q1)
        agg_rows.append(row)

agg_df = pd.DataFrame(agg_rows).sort_values(["investigation_id", "model"])
if not agg_df.empty:
    agg_path = RUN_DIR / f"model_metrics_seed_aggregate_{STAMP}.csv"
    agg_df.to_csv(agg_path, index=False)
    print("\nSeed-aggregate summary (median / IQR):")
    print(agg_df.to_string(index=False))
    print("Seed-aggregate CSV:", agg_path)


# %% Cell 10A: Export interpretation-facing summaries
# This cell reads the completed run artefacts and writes a compact interpretation bundle.
INTERPRET_DIR = RUN_DIR / "interpretation_exports"
INTERPRET_DIR.mkdir(parents=True, exist_ok=True)
INTERPRET_SUMMARY_PATH = INTERPRET_DIR / f"model_run_interpretation_summary_{STAMP}.csv"
INTERPRET_SEED_PATH = INTERPRET_DIR / f"model_run_interpretation_seed_detail_{STAMP}.csv"


def safe_read_json(path: Path) -> tuple[dict[str, object] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:  # pragma: no cover - defensive runtime path
        return None, str(exc)


def to_float_or_na(value: object) -> object:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return pd.NA if pd.isna(numeric) else float(numeric)


def to_int_or_na(value: object) -> object:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return pd.NA if pd.isna(numeric) else int(numeric)


def text_or_blank(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text in {"", "None", "nan", "<NA>"}:
        return ""
    return text


def serialise_mapping(value: object) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return text_or_blank(value)


def median_or_na(series: pd.Series) -> object:
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if vals.empty:
        return pd.NA
    return float(vals.median())


def iqr_or_na(series: pd.Series) -> object:
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if vals.empty:
        return pd.NA
    return float(vals.quantile(0.75) - vals.quantile(0.25))


def any_true(series: pd.Series) -> bool:
    return bool(series.fillna(False).astype(bool).any())


def warning_level_summary(series: pd.Series) -> str:
    values = sorted({text_or_blank(v) for v in series.tolist() if text_or_blank(v)})
    return "|".join(values)


audit_manifest_payload, audit_manifest_error = safe_read_json(RUN_DIR / f"feature_audit_manifest_{STAMP}.json")
audit_status = dict((audit_manifest_payload or {}).get("status", {}))
aggregate_metrics_path = RUN_DIR / f"model_metrics_seed_aggregate_{STAMP}.csv"

seed_detail_columns = [
    "investigation_id",
    "target_col",
    "target_profile",
    "feature_profile",
    "model",
    "seed",
    "run_tag",
    "selected_predictor_count",
    "n_train",
    "n_test",
    "train_prevalence",
    "test_prevalence",
    "class_dist_train",
    "class_dist_test",
    "balanced_accuracy",
    "roc_auc",
    "pr_auc",
    "sensitivity",
    "specificity",
    "brier",
    "selected_threshold",
    "threshold_fallback_used",
    "split_fallback_reason",
    "epv_estimate",
    "epv_warning_level",
    "epv_warning_reason",
    "run_completed_successfully",
    "stdout_log_path",
    "stderr_log_path",
    "metrics_json_path",
    "model_run_manifest_path",
]
seed_detail_rows: list[dict[str, object]] = []

for inv in legacy_training_rows:
    investigation_id = text_or_blank(inv.get("investigation_id"))
    feature_token = text_or_blank(inv.get("feature_profile")) or "icd_relevant_only"
    target_profile = text_or_blank(inv.get("target_profile"))
    target_col = text_or_blank(inv.get("target_column")) or text_or_blank(inv.get("target_name"))
    target_name = text_or_blank(inv.get("target_name")) or target_col
    recency_policy_id = text_or_blank(inv.get("recency_policy_id")) or "minimal"

    for model_type in ("lr", "rf", "nn"):
        if int(inv.get(f"run_{model_type}", 0)) != 1:
            continue
        for random_state in RANDOM_STATES:
            run_tag = build_train_run_tag(
                model_type=model_type,
                feature_token=feature_token,
                stamp=STAMP,
                target_col=target_col,
                target_profile=target_profile,
                investigation_id=investigation_id,
                target_name=target_name,
                recency_policy_id=recency_policy_id,
                run_tag_suffix=f"seed{int(random_state)}",
            )
            metrics_path = RUN_DIR / f"model_metrics_{run_tag}.json"
            model_manifest_path = RUN_DIR / f"model_run_manifest_{run_tag}.json"
            stdout_log_path = RUN_DIR / f"step5_train_{investigation_id}_{model_type}_seed{int(random_state)}_stdout.log"
            stderr_log_path = RUN_DIR / f"step5_train_{investigation_id}_{model_type}_seed{int(random_state)}_stderr.log"

            metrics_payload, metrics_error = safe_read_json(metrics_path)
            model_manifest_payload, model_manifest_error = safe_read_json(model_manifest_path)
            split_summary = dict((metrics_payload or {}).get("split_summary", {}))
            feature_selection = dict((metrics_payload or {}).get("feature_selection", {}))
            threshold_selection = dict((metrics_payload or {}).get("threshold_selection", {}))
            epv_diagnostics = dict((metrics_payload or {}).get("epv_diagnostics", {}))
            metric_block = dict((metrics_payload or {}).get("metrics", {}))
            args_block = dict((metrics_payload or {}).get("args", {}))

            run_completed_successfully = metrics_payload is not None and metrics_error == ""
            if not run_completed_successfully and model_manifest_payload is not None and model_manifest_error == "":
                target_col_value = text_or_blank(model_manifest_payload.get("target_col")) or target_col
                target_profile_value = text_or_blank(model_manifest_payload.get("target_profile")) or target_profile
                feature_profile_value = text_or_blank(model_manifest_payload.get("feature_profile")) or feature_token
            else:
                target_col_value = text_or_blank((metrics_payload or {}).get("target_col")) or target_col
                target_profile_value = text_or_blank((metrics_payload or {}).get("target_profile")) or target_profile
                feature_profile_value = text_or_blank(args_block.get("feature_profile")) or feature_token

            seed_detail_rows.append(
                {
                    "investigation_id": investigation_id,
                    "target_col": target_col_value,
                    "target_profile": target_profile_value,
                    "feature_profile": feature_profile_value,
                    "model": model_type,
                    "seed": int(random_state),
                    "run_tag": run_tag,
                    "selected_predictor_count": to_int_or_na(feature_selection.get("selected_predictor_count")),
                    "n_train": to_int_or_na(split_summary.get("n_train")),
                    "n_test": to_int_or_na(split_summary.get("n_test")),
                    "train_prevalence": to_float_or_na(split_summary.get("prevalence_train")),
                    "test_prevalence": to_float_or_na(split_summary.get("prevalence_test")),
                    "class_dist_train": serialise_mapping(split_summary.get("class_dist_train")),
                    "class_dist_test": serialise_mapping(split_summary.get("class_dist_test")),
                    "balanced_accuracy": to_float_or_na(metric_block.get("balanced_accuracy")),
                    "roc_auc": to_float_or_na(metric_block.get("roc_auc")),
                    "pr_auc": to_float_or_na(metric_block.get("pr_auc")),
                    "sensitivity": to_float_or_na(metric_block.get("sensitivity")),
                    "specificity": to_float_or_na(metric_block.get("specificity")),
                    "brier": to_float_or_na(metric_block.get("brier")),
                    "selected_threshold": to_float_or_na(threshold_selection.get("selected_threshold")),
                    "threshold_fallback_used": bool(threshold_selection.get("fallback_used", False))
                    if run_completed_successfully
                    else pd.NA,
                    "split_fallback_reason": text_or_blank(split_summary.get("stratify_fallback_reason")),
                    "epv_estimate": to_float_or_na(epv_diagnostics.get("epv_estimate")),
                    "epv_warning_level": text_or_blank(epv_diagnostics.get("warning_level")),
                    "epv_warning_reason": text_or_blank(epv_diagnostics.get("warning_reason")),
                    "run_completed_successfully": bool(run_completed_successfully),
                    "stdout_log_path": str(stdout_log_path),
                    "stderr_log_path": str(stderr_log_path),
                    "metrics_json_path": str(metrics_path),
                    "model_run_manifest_path": str(model_manifest_path),
                }
            )

seed_detail_df = pd.DataFrame(seed_detail_rows, columns=seed_detail_columns)
seed_detail_df = seed_detail_df.sort_values(["investigation_id", "model", "seed"]).reset_index(drop=True)
seed_detail_df.to_csv(INTERPRET_SEED_PATH, index=False)

summary_columns = [
    "investigation_id",
    "target_col",
    "target_profile",
    "feature_profile",
    "model",
    "n_seeds_completed",
    "selected_predictor_count_median",
    "selected_predictor_count_iqr",
    "balanced_accuracy_median",
    "balanced_accuracy_iqr",
    "roc_auc_median",
    "roc_auc_iqr",
    "pr_auc_median",
    "pr_auc_iqr",
    "sensitivity_median",
    "sensitivity_iqr",
    "specificity_median",
    "specificity_iqr",
    "brier_median",
    "brier_iqr",
    "threshold_median",
    "threshold_fallback_any",
    "audit_pass",
    "audit_failure_count",
    "epv_warning_level_summary",
    "split_fallback_any",
    "aggregate_metrics_source_path",
]
summary_rows: list[dict[str, object]] = []
if not seed_detail_df.empty:
    for (investigation_id, model_type), sub_df in seed_detail_df.groupby(["investigation_id", "model"], dropna=False):
        completed_df = sub_df.loc[sub_df["run_completed_successfully"] == True].copy()
        summary_rows.append(
            {
                "investigation_id": investigation_id,
                "target_col": text_or_blank(sub_df["target_col"].iloc[0]),
                "target_profile": text_or_blank(sub_df["target_profile"].iloc[0]),
                "feature_profile": text_or_blank(sub_df["feature_profile"].iloc[0]),
                "model": model_type,
                "n_seeds_completed": int(completed_df.shape[0]),
                "selected_predictor_count_median": median_or_na(completed_df["selected_predictor_count"]),
                "selected_predictor_count_iqr": iqr_or_na(completed_df["selected_predictor_count"]),
                "balanced_accuracy_median": median_or_na(completed_df["balanced_accuracy"]),
                "balanced_accuracy_iqr": iqr_or_na(completed_df["balanced_accuracy"]),
                "roc_auc_median": median_or_na(completed_df["roc_auc"]),
                "roc_auc_iqr": iqr_or_na(completed_df["roc_auc"]),
                "pr_auc_median": median_or_na(completed_df["pr_auc"]),
                "pr_auc_iqr": iqr_or_na(completed_df["pr_auc"]),
                "sensitivity_median": median_or_na(completed_df["sensitivity"]),
                "sensitivity_iqr": iqr_or_na(completed_df["sensitivity"]),
                "specificity_median": median_or_na(completed_df["specificity"]),
                "specificity_iqr": iqr_or_na(completed_df["specificity"]),
                "brier_median": median_or_na(completed_df["brier"]),
                "brier_iqr": iqr_or_na(completed_df["brier"]),
                "threshold_median": median_or_na(completed_df["selected_threshold"]),
                "threshold_fallback_any": any_true(completed_df["threshold_fallback_used"]),
                "audit_pass": bool(audit_status.get("pass", False)) if audit_manifest_payload is not None else pd.NA,
                "audit_failure_count": to_int_or_na(audit_status.get("failure_count")),
                "epv_warning_level_summary": warning_level_summary(completed_df["epv_warning_level"]),
                "split_fallback_any": bool(
                    completed_df["split_fallback_reason"].fillna("").astype(str).str.strip().ne("").any()
                ),
                "aggregate_metrics_source_path": str(aggregate_metrics_path) if aggregate_metrics_path.exists() else "",
            }
        )

summary_df = pd.DataFrame(summary_rows, columns=summary_columns)
summary_df = summary_df.sort_values(["investigation_id", "model"]).reset_index(drop=True)
summary_df.to_csv(INTERPRET_SUMMARY_PATH, index=False)

print("\nInterpretation exports:")
print("- summary:", INTERPRET_SUMMARY_PATH)
print("- per-seed detail:", INTERPRET_SEED_PATH)


# %% Cell 11: Run EDA plots
# This cell generates seminar-facing figure/table artifacts from the current run outputs.
EDA_SKIPPED = False
EDA_SKIP_REASON = ""
if legacy_training_rows:
    cmd_eda = [
        sys.executable,
        str(PY_EDA),
        "--run-root",
        str(RUN_ROOT),
        "--run-dir",
        str(RUN_DIR),
        "--stamp",
        STAMP,
        "--top-n",
        "20",
    ]
    EDA_INVESTIGATION_ID = INVESTIGATION_ID_ARG if INVESTIGATION_ID_ARG else ""
    if EDA_INVESTIGATION_ID:
        cmd_eda.extend(["--investigation-id", EDA_INVESTIGATION_ID])
    run_cmd(cmd_eda, RUN_DIR, "step6_eda")

    EDA_DIR = (
        RUN_DIR / f"eda_plots_{STAMP}_{slug_token(EDA_INVESTIGATION_ID)}"
        if EDA_INVESTIGATION_ID
        else RUN_DIR / f"eda_plots_{STAMP}"
    )
    EDA_MANIFEST = EDA_DIR / "eda_plot_manifest.json"
    print("EDA directory:", EDA_DIR)
    print("EDA manifest:", EDA_MANIFEST)
else:
    EDA_SKIPPED = True
    EDA_SKIP_REASON = "No legacy grouped-feature investigations were executed; signal-discovery rows are context-only until Stage 6.5."
    EDA_DIR = RUN_DIR
    EDA_MANIFEST = RUN_DIR / f"eda_plot_manifest_skipped_{STAMP}.json"
    print("EDA skipped:", EDA_SKIP_REASON)


# %% Cell 12: Final summary
# Consolidated end-of-run checkpoint for build/audit/train/EDA artifacts.
audit_manifest_path = RUN_DIR / f"feature_audit_manifest_{STAMP}.json"
if not audit_manifest_path.exists():
    raise FileNotFoundError(f"Missing audit manifest at final summary: {audit_manifest_path}")

audit_manifest = json.loads(audit_manifest_path.read_text(encoding="utf-8"))
audit_status = audit_manifest.get("status", {})
print("Audit pass:", audit_status.get("pass"))
print("Audit failures:", audit_status.get("failure_count"))
print("Audit preprocessing contract failures:", audit_status.get("preprocessing_contract_failures"))

if not EDA_SKIPPED:
    if not EDA_MANIFEST.exists():
        raise FileNotFoundError(f"Missing EDA manifest: {EDA_MANIFEST}")
    eda_manifest = json.loads(EDA_MANIFEST.read_text(encoding="utf-8"))
else:
    eda_manifest = {"plots": {}, "tables": {}, "skipped": True, "reason": EDA_SKIP_REASON}

print("\nModel metrics files:")
for item in metrics_files:
    metrics_path = Path(str(item["path"]))
    print(
        f"- {item['investigation_id']} {item['model_type']}: "
        f"{metrics_path} | exists={metrics_path.exists()}"
    )

if signal_metrics_files:
    print("\nSignal-discovery model metrics files:")
    for item in signal_metrics_files:
        metrics_path = Path(str(item["path"]))
        print(
            f"- {item['investigation_id']} {item['model_type']}: "
            f"{metrics_path} | exists={metrics_path.exists()}"
        )

print("\nEDA plot outputs:")
for name, payload in eda_manifest.get("plots", {}).items():
    print(f"- {name}: generated={payload.get('generated')} path={payload.get('path')}")

print("\nEDA table outputs:")
for name, path in eda_manifest.get("tables", {}).items():
    print(f"- {name}: {path}")

if EDA_SKIPPED:
    print("\nEDA skipped reason:")
    print(EDA_SKIP_REASON)

print("\nSignal-discovery context rows:")
for row in signal_discovery_context_rows:
    print(
        f"- {row['investigation_id']}: branch_mode={row['branch_mode']} "
        f"scenario={row['screening_scenario_id']} "
        f"baseline={row['baseline_reference']}"
    )

print("\nRun complete for:")
print("RUN_DIR:", RUN_DIR)
print("STAMP:", STAMP)
