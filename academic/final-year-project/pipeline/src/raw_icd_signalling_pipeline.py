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
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_MPL_CACHE_DIR = Path(tempfile.gettempdir()) / "orion_matplotlib_cache"
_MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CACHE_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(_MPL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import fisher_exact
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold

from train_models import (
    apply_cohort_filter,
    build_model,
    evaluate_binary_predictions,
    load_target_profile_mappings,
    resolve_target_definition,
    select_threshold_from_policy,
    split_dataset,
)


DEFAULT_CONTROL_CSV = Path(__file__).resolve().parent / "config" / "raw_icd_signalling_investigations.csv"
DEFAULT_POLICY_JSON = Path(__file__).resolve().parent / "config" / "raw_icd_signalling_policy_v1.json"
DEFAULT_TARGET_PROFILE_CSV = Path(__file__).resolve().parent / "config" / "target_profile_mappings.csv"


# %% ---------------------------------------------------------------------------
# CLI and config helpers
# -----------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the raw ICD signalling exploratory pipeline.")
    parser.add_argument("--work-root", default=".", help="Root directory used to resolve relative input paths.")
    parser.add_argument("--output-root", default=None, help="Root directory for signalling_<n> outputs.")
    parser.add_argument("--investigation-id", default="", help="Investigation id from raw_icd_signalling_investigations.csv.")
    parser.add_argument("--investigation-control-csv", default=str(DEFAULT_CONTROL_CSV))
    parser.add_argument("--policy-json", default=str(DEFAULT_POLICY_JSON))
    parser.add_argument("--target-profile-csv", default=str(DEFAULT_TARGET_PROFILE_CSV))
    parser.add_argument("--force-run-dir", default="", help="Optional explicit signalling_<n> directory path.")
    return parser.parse_args(argv)


def clean_token(value: Any) -> str:
    if pd.isna(value):
        return ""
    cleaned = str(value).strip()
    if cleaned.lower() in {"", "nan", "<na>", "none", "null"}:
        return ""
    return cleaned


def slug_token(value: Any) -> str:
    token = clean_token(value).lower()
    if token == "":
        return "na"
    chars = [ch if ch.isalnum() else "_" for ch in token]
    slug = "".join(chars)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "na"


def resolve_path(path_like: str, base_dir: Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def next_indexed_dir(root: Path, prefix: str) -> Path:
    root = root.resolve()
    ensure_dir(root)
    existing: list[int] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith(f"{prefix}_"):
            continue
        suffix = name[len(prefix) + 1 :]
        if suffix.isdigit():
            existing.append(int(suffix))
    next_idx = max(existing, default=0) + 1
    return root / f"{prefix}_{next_idx}"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_signalling_controls(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Raw ICD signalling control CSV not found: {path}")
    df = pd.read_csv(path)
    required = {
        "investigation_id",
        "analysis_mode",
        "target_profile",
        "cohort_filter",
        "label_source_csv",
        "stage_a_preparation_csv",
        "discovery_matrix_csv",
        "participant_id_col",
        "code_col_prefix",
        "support_score_formula_id",
        "support_threshold_policy_id",
        "grouping_policy_id",
        "run_lr",
        "run_rf",
        "run_nn",
        "notes",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Raw ICD signalling control CSV missing columns: {sorted(missing)}")
    cleaned = df.copy()
    for col in required.difference({"run_lr", "run_rf", "run_nn"}):
        cleaned[col] = cleaned[col].astype(str).str.strip().replace({"nan": "", "None": ""})
    for col in ("run_lr", "run_rf", "run_nn"):
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").fillna(0).astype(int)
    cleaned = cleaned.loc[cleaned["investigation_id"] != ""].reset_index(drop=True)
    return cleaned


def resolve_signalling_row(controls: pd.DataFrame, investigation_id: str) -> dict[str, Any]:
    if investigation_id:
        rows = controls.loc[controls["investigation_id"] == investigation_id].copy()
        if rows.empty:
            available = sorted(controls["investigation_id"].astype(str).tolist())
            raise ValueError(f"Unknown signalling investigation_id '{investigation_id}'. Available: {available}")
    else:
        rows = controls.loc[(controls["run_lr"] + controls["run_rf"] + controls["run_nn"]) > 0].copy()
        if rows.empty:
            raise ValueError("No runnable raw ICD signalling investigation rows found.")
        rows = rows.iloc[[0]].copy()
    if len(rows) != 1:
        ids = rows["investigation_id"].astype(str).tolist()
        raise ValueError(f"Expected exactly one signalling investigation row. Found: {ids}")
    row = rows.iloc[0].to_dict()
    if clean_token(row.get("analysis_mode")) != "raw_icd_signalling":
        raise ValueError(f"Invalid analysis_mode for signalling row: {row.get('analysis_mode')!r}")
    return row


# %% ---------------------------------------------------------------------------
# Input preparation
# -----------------------------------------------------------------------------
def load_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Raw ICD signalling policy JSON not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if clean_token(payload.get("analysis_mode")) != "raw_icd_signalling":
        raise ValueError("Raw ICD signalling policy has invalid analysis_mode.")
    return payload


def load_inputs(
    *,
    work_root: Path,
    row: dict[str, Any],
    target_profile_csv: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, dict[str, Any]]:
    label_source_path = resolve_path(str(row["label_source_csv"]), work_root)
    stage_a_path = resolve_path(str(row["stage_a_preparation_csv"]), work_root)
    discovery_path = resolve_path(str(row["discovery_matrix_csv"]), work_root)

    for path in (label_source_path, stage_a_path, discovery_path):
        if not path.exists():
            raise FileNotFoundError(f"Required signalling input not found: {path}")

    label_df = pd.read_csv(label_source_path)
    participant_id_col = clean_token(row.get("participant_id_col")) or "participant_id"
    if participant_id_col not in label_df.columns:
        raise RuntimeError(f"Label source CSV missing participant id column: {participant_id_col}")

    filtered_df, cohort_meta = apply_cohort_filter(label_df, clean_token(row.get("cohort_filter")) or "all")
    target_profile_mappings = load_target_profile_mappings(target_profile_csv, required=True)
    resolved_matrix, target_values, resolved_target_col, _, target_meta = resolve_target_definition(
        matrix=filtered_df,
        target_col=None,
        target_profile=clean_token(row.get("target_profile")),
        target_profile_mappings=target_profile_mappings,
    )
    resolved_matrix = resolved_matrix.copy()
    resolved_matrix[participant_id_col] = pd.to_numeric(
        resolved_matrix[participant_id_col], errors="coerce"
    ).astype("Int64")
    resolved_matrix = resolved_matrix.dropna(subset=[participant_id_col]).copy()
    resolved_matrix[participant_id_col] = resolved_matrix[participant_id_col].astype(int)

    discovery_df = pd.read_csv(discovery_path)
    if participant_id_col not in discovery_df.columns:
        raise RuntimeError(f"Discovery matrix missing participant id column: {participant_id_col}")
    discovery_df[participant_id_col] = pd.to_numeric(discovery_df[participant_id_col], errors="coerce").astype("Int64")
    discovery_df = discovery_df.dropna(subset=[participant_id_col]).copy()
    discovery_df[participant_id_col] = discovery_df[participant_id_col].astype(int)

    code_prefix = clean_token(row.get("code_col_prefix")) or "icd_raw_"
    code_columns = [c for c in discovery_df.columns if c != participant_id_col and str(c).startswith(code_prefix)]
    if not code_columns:
        raise RuntimeError(f"Discovery matrix does not contain any code columns with prefix '{code_prefix}'.")
    bad_cols = [c for c in discovery_df.columns if c != participant_id_col and c not in code_columns]
    if bad_cols:
        raise RuntimeError(
            "Discovery matrix contains non-code columns outside the configured participant id column: "
            f"{bad_cols[:10]}"
        )

    merged = resolved_matrix[[participant_id_col]].copy().merge(discovery_df, on=participant_id_col, how="left")
    merged[code_columns] = merged[code_columns].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)

    stage_a_df = pd.read_csv(stage_a_path)
    stage_required = {
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
    missing = stage_required.difference(stage_a_df.columns)
    if missing:
        raise RuntimeError(f"Stage A preparation CSV missing required columns: {sorted(missing)}")
    stage_a_df = stage_a_df.copy()
    stage_a_df["feature_column"] = stage_a_df["feature_column"].astype(str).str.strip()
    stage_a_df = stage_a_df.loc[stage_a_df["feature_column"].isin(code_columns)].copy()
    if stage_a_df.empty:
        raise RuntimeError("Stage A preparation table does not overlap the configured discovery matrix columns.")
    lookup_missing = sorted(set(code_columns).difference(set(stage_a_df["feature_column"].tolist())))
    if lookup_missing:
        raise RuntimeError(
            "Stage A preparation table is missing discovery-matrix columns required for signalling: "
            f"{lookup_missing[:10]}"
        )

    y = pd.to_numeric(target_values.loc[resolved_matrix.index], errors="coerce").astype(int).reset_index(drop=True)
    pid = merged[participant_id_col].astype(int).reset_index(drop=True)
    X = merged[code_columns].reset_index(drop=True)
    input_meta = {
        "label_source_path": str(label_source_path),
        "stage_a_preparation_path": str(stage_a_path),
        "discovery_matrix_path": str(discovery_path),
        "resolved_target_col": resolved_target_col,
        "target_profile": clean_token(row.get("target_profile")),
        "participant_id_col": participant_id_col,
        "code_col_prefix": code_prefix,
        "cohort_filter": cohort_meta,
        "target_resolution": target_meta,
        "n_rows_after_target_resolution": int(len(X)),
        "n_code_columns": int(len(code_columns)),
    }
    return X, stage_a_df.reset_index(drop=True), pid, y, input_meta


# %% ---------------------------------------------------------------------------
# Support, phi, and grouping helpers
# -----------------------------------------------------------------------------
def build_model_from_policy(model_type: str, seed: int, policy: dict[str, Any]):
    model_defaults = policy.get("model_family_order", {})
    nn_cfg = model_defaults.get("nn", {})
    return build_model(
        model_type=model_type,
        random_state=int(seed),
        target_type="binary",
        nn_hidden_layers=tuple(int(v) for v in nn_cfg.get("hidden_layers", [32, 16])),
        nn_alpha=float(nn_cfg.get("alpha", 0.001)),
        nn_learning_rate_init=float(nn_cfg.get("learning_rate_init", 0.0005)),
        nn_max_iter=int(nn_cfg.get("max_iter", 1200)),
        nn_early_stopping=bool(nn_cfg.get("early_stopping", True)),
        class_weight_mode=str(model_defaults.get("class_weight_mode", "none")),
    )


def compute_support_summary(
    X_train: pd.DataFrame,
    stage_a_df: pd.DataFrame,
    zero_offset: float,
    event_volume_mode: str,
) -> pd.DataFrame:
    stage_lookup = stage_a_df.set_index("feature_column")
    rows: list[dict[str, Any]] = []
    for feature_column in X_train.columns:
        train_support = int(pd.to_numeric(X_train[feature_column], errors="coerce").fillna(0).astype(int).sum())
        stage_row = stage_lookup.loc[feature_column]
        global_support = float(pd.to_numeric(pd.Series([stage_row["participant_support_n"]]), errors="coerce").iloc[0])
        global_events = float(pd.to_numeric(pd.Series([stage_row["event_occurrence_n"]]), errors="coerce").iloc[0])
        if global_support > 0:
            train_event_proxy = float(global_events * (train_support / global_support))
        else:
            train_event_proxy = 0.0
        support_score = math.log10((train_support + zero_offset) * (train_event_proxy + zero_offset))
        rows.append(
            {
                "feature_column": feature_column,
                "normalized_code": clean_token(stage_row["normalized_code"]),
                "icd_chapter": clean_token(stage_row["normalized_code"])[:1] or "na",
                "participant_support_n_train": train_support,
                "participant_support_n_stage_a_global": int(global_support),
                "event_occurrence_n_stage_a_global": float(global_events),
                "event_occurrence_n_train_proxy": float(train_event_proxy),
                "event_volume_source_mode": event_volume_mode,
                "support_score": float(support_score),
            }
        )
    return pd.DataFrame(rows).sort_values(["support_score", "feature_column"], ascending=[False, True]).reset_index(drop=True)


def score_support_candidate(X: pd.DataFrame, y: pd.Series, seed: int, policy: dict[str, Any]) -> tuple[float, float, int]:
    if X.shape[1] == 0:
        return float("nan"), float("nan"), 0
    class_counts = y.value_counts().sort_index()
    min_class_n = int(class_counts.min()) if not class_counts.empty else 0
    n_splits = min(int(policy["support_threshold_policy"].get("inner_cv_folds", 3)), min_class_n)
    if n_splits < 2:
        model = build_model_from_policy("lr", seed, policy)
        model.fit(X, y)
        y_pred = model.predict(X)
        score = float(balanced_accuracy_score(y, y_pred))
        return score, 0.0, 1

    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=int(seed))
    scores: list[float] = []
    for fold_id, (fit_idx, val_idx) in enumerate(splitter.split(X, y)):
        model = build_model_from_policy("lr", seed + fold_id + 1, policy)
        X_fit = X.iloc[fit_idx].reset_index(drop=True)
        y_fit = y.iloc[fit_idx].reset_index(drop=True)
        X_val = X.iloc[val_idx].reset_index(drop=True)
        y_val = y.iloc[val_idx].reset_index(drop=True)
        model.fit(X_fit, y_fit)
        y_pred = model.predict(X_val)
        scores.append(float(balanced_accuracy_score(y_val, y_pred)))
    arr = np.asarray(scores, dtype=float)
    se = float(arr.std(ddof=1) / math.sqrt(len(arr))) if len(arr) > 1 else 0.0
    return float(arr.mean()), se, int(len(arr))


def tune_support_threshold(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    support_df: pd.DataFrame,
    seed: int,
    policy: dict[str, Any],
) -> tuple[pd.DataFrame, float, list[str], dict[str, Any]]:
    quantiles = [float(v) for v in policy["support_threshold_policy"]["quantile_grid"]]
    rows: list[dict[str, Any]] = []
    best_mean = -float("inf")
    best_se = 0.0
    for q in quantiles:
        tau = float(support_df["support_score"].quantile(q))
        retained = support_df.loc[support_df["support_score"] >= tau, "feature_column"].astype(str).tolist()
        mean_score, se_score, fold_count = score_support_candidate(
            X_train[retained].copy(),
            y_train,
            seed=int(seed + round(q * 100)),
            policy=policy,
        )
        rows.append(
            {
                "support_quantile": float(q),
                "support_threshold": tau,
                "retained_code_count": int(len(retained)),
                "inner_cv_balanced_accuracy_mean": float(mean_score),
                "inner_cv_balanced_accuracy_se": float(se_score),
                "inner_cv_fold_count": int(fold_count),
            }
        )
        if not math.isnan(mean_score) and mean_score > best_mean:
            best_mean = float(mean_score)
            best_se = float(se_score)

    tuning_df = pd.DataFrame(rows).sort_values("support_quantile").reset_index(drop=True)
    acceptable = tuning_df.loc[
        tuning_df["inner_cv_balanced_accuracy_mean"] >= float(best_mean - best_se)
    ].copy()
    acceptable = acceptable.sort_values(
        ["support_quantile", "retained_code_count", "support_threshold"],
        ascending=[False, True, False],
    )
    selected_row = acceptable.iloc[0].to_dict()
    selected_quantile = float(selected_row["support_quantile"])
    selected_threshold = float(selected_row["support_threshold"])
    selected_codes = support_df.loc[
        support_df["support_score"] >= selected_threshold, "feature_column"
    ].astype(str).tolist()
    tuning_df["selected_flag"] = tuning_df["support_quantile"].eq(selected_quantile).astype(int)
    support_df = support_df.copy()
    support_df["selected_support_quantile"] = selected_quantile
    support_df["selected_support_threshold"] = selected_threshold
    support_df["retained_after_support_threshold"] = support_df["feature_column"].isin(selected_codes).astype(int)
    selection_meta = {
        "selection_rule": policy["support_threshold_policy"]["selection_rule"],
        "score_metric": policy["support_threshold_policy"]["score_metric"],
        "selected_support_quantile": selected_quantile,
        "selected_support_threshold": selected_threshold,
        "best_inner_cv_balanced_accuracy_mean": float(best_mean),
        "best_inner_cv_balanced_accuracy_se": float(best_se),
    }
    return support_df, selected_threshold, selected_codes, selection_meta


def compute_phi_table(X_train: pd.DataFrame, y_train: pd.Series, support_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    support_lookup = support_df.set_index("feature_column")
    for feature_column in support_df.loc[support_df["retained_after_support_threshold"] == 1, "feature_column"]:
        x = pd.to_numeric(X_train[feature_column], errors="coerce").fillna(0).astype(int)
        a = float(((x == 1) & (y_train == 1)).sum())
        b = float(((x == 1) & (y_train == 0)).sum())
        c = float(((x == 0) & (y_train == 1)).sum())
        d = float(((x == 0) & (y_train == 0)).sum())
        corrected = False
        a_corr, b_corr, c_corr, d_corr = a, b, c, d
        if min(a, b, c, d) == 0:
            corrected = True
            a_corr += 0.5
            b_corr += 0.5
            c_corr += 0.5
            d_corr += 0.5
        denom = math.sqrt((a_corr + b_corr) * (c_corr + d_corr) * (a_corr + c_corr) * (b_corr + d_corr))
        phi = float(((a_corr * d_corr) - (b_corr * c_corr)) / denom) if denom > 0 else 0.0
        fisher_p = float(fisher_exact([[a, b], [c, d]])[1])
        phi_sign = "positive" if phi >= 0 else "negative"
        support_row = support_lookup.loc[feature_column]
        rows.append(
            {
                "feature_column": feature_column,
                "normalized_code": clean_token(support_row["normalized_code"]),
                "icd_chapter": clean_token(support_row["icd_chapter"]) or "na",
                "participant_support_n_train": int(support_row["participant_support_n_train"]),
                "event_occurrence_n_train_proxy": float(support_row["event_occurrence_n_train_proxy"]),
                "support_score": float(support_row["support_score"]),
                "a_present_target1": a,
                "b_present_target0": b,
                "c_absent_target1": c,
                "d_absent_target0": d,
                "continuity_corrected": bool(corrected),
                "phi": phi,
                "phi_abs": float(abs(phi)),
                "phi_sign": phi_sign,
                "fisher_p_value": fisher_p,
            }
        )
    return pd.DataFrame(rows).sort_values(["phi_abs", "feature_column"], ascending=[False, True]).reset_index(drop=True)


def build_weighted_similarity_matrix(
    X_train: pd.DataFrame,
    phi_df: pd.DataFrame,
) -> pd.DataFrame:
    cols = phi_df["feature_column"].astype(str).tolist()
    X_bin = X_train[cols].astype(int)
    support = X_bin.sum(axis=0).astype(float)
    inter = X_bin.T.dot(X_bin).astype(float)
    union = support.values[:, None] + support.values[None, :] - inter.values
    with np.errstate(divide="ignore", invalid="ignore"):
        jaccard = np.where(union > 0, inter.values / union, 0.0)
    phi_abs = phi_df["phi_abs"].astype(float).to_numpy()
    weighted = jaccard * np.sqrt(np.outer(phi_abs, phi_abs))
    np.fill_diagonal(weighted, 1.0)
    return pd.DataFrame(weighted, index=cols, columns=cols)


def cluster_partition(
    investigation_id: str,
    seed: int,
    chapter: str,
    sign: str,
    phi_df: pd.DataFrame,
    X_train: pd.DataFrame,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    cols = phi_df["feature_column"].astype(str).tolist()
    if len(cols) == 1:
        group_id = f"{slug_token(investigation_id)}__seed{seed}__ch{slug_token(chapter)}__{slug_token(sign)}__grp01"
        return ([{"group_id": group_id, "member_columns": cols, "chapter": chapter, "sign": sign}], pd.DataFrame([[1.0]], index=cols, columns=cols))

    weighted_df = build_weighted_similarity_matrix(X_train=X_train, phi_df=phi_df)
    if len(cols) == 2:
        similarity = float(weighted_df.iloc[0, 1])
        if similarity > 0:
            group_id = f"{slug_token(investigation_id)}__seed{seed}__ch{slug_token(chapter)}__{slug_token(sign)}__grp01"
            return ([{"group_id": group_id, "member_columns": cols, "chapter": chapter, "sign": sign}], weighted_df)
        groups = []
        for idx, col in enumerate(cols, start=1):
            group_id = f"{slug_token(investigation_id)}__seed{seed}__ch{slug_token(chapter)}__{slug_token(sign)}__grp{idx:02d}"
            groups.append({"group_id": group_id, "member_columns": [col], "chapter": chapter, "sign": sign})
        return groups, weighted_df

    distance = 1.0 - weighted_df.to_numpy(dtype=float)
    distance = np.clip((distance + distance.T) / 2.0, 0.0, 1.0)
    np.fill_diagonal(distance, 0.0)
    linkage_matrix = linkage(squareform(distance, checks=False), method="average")
    heights = linkage_matrix[:, 2]
    gaps = np.diff(heights)
    gap_idx = int(np.argmax(gaps)) if len(gaps) else 0
    if len(gaps):
        cut_height = float(heights[gap_idx] + (gaps[gap_idx] / 2.0))
    else:
        cut_height = float(heights[0])
    cluster_ids = fcluster(linkage_matrix, t=cut_height, criterion="distance")
    groups: list[dict[str, Any]] = []
    for group_idx, cluster_id in enumerate(sorted(set(cluster_ids)), start=1):
        member_columns = sorted([col for col, cid in zip(cols, cluster_ids) if cid == cluster_id])
        group_id = f"{slug_token(investigation_id)}__seed{seed}__ch{slug_token(chapter)}__{slug_token(sign)}__grp{group_idx:02d}"
        groups.append(
            {
                "group_id": group_id,
                "member_columns": member_columns,
                "chapter": chapter,
                "sign": sign,
                "cut_height": cut_height,
            }
        )
    return groups, weighted_df


def build_groups_for_seed(
    investigation_id: str,
    seed: int,
    phi_df: pd.DataFrame,
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    mapping_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    heatmaps: dict[str, pd.DataFrame] = {}

    for (chapter, sign), part_df in phi_df.groupby(["icd_chapter", "phi_sign"], dropna=False):
        groups, weighted_df = cluster_partition(
            investigation_id=investigation_id,
            seed=seed,
            chapter=str(chapter),
            sign=str(sign),
            phi_df=part_df.reset_index(drop=True),
            X_train=X_train,
        )
        heatmaps[f"{slug_token(chapter)}__{slug_token(sign)}"] = weighted_df
        for group in groups:
            member_columns = list(group["member_columns"])
            group_ever = X_train[member_columns].max(axis=1).astype(int)
            a = float(((group_ever == 1) & (y_train == 1)).sum())
            b = float(((group_ever == 1) & (y_train == 0)).sum())
            c = float(((group_ever == 0) & (y_train == 1)).sum())
            d = float(((group_ever == 0) & (y_train == 0)).sum())
            if min(a, b, c, d) == 0:
                a += 0.5
                b += 0.5
                c += 0.5
                d += 0.5
            denom = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
            group_phi = float(((a * d) - (b * c)) / denom) if denom > 0 else 0.0
            member_phi = part_df.loc[part_df["feature_column"].isin(member_columns)].copy()
            member_phi = member_phi.sort_values(["phi_abs", "normalized_code"], ascending=[False, True])
            group_rows.append(
                {
                    "seed": int(seed),
                    "group_id": group["group_id"],
                    "group_feature_column": group["group_id"],
                    "icd_chapter": str(chapter),
                    "phi_sign": str(sign),
                    "member_code_count": int(len(member_columns)),
                    "member_codes": "|".join(member_phi["normalized_code"].astype(str).tolist()),
                    "member_feature_columns": "|".join(member_columns),
                    "participant_support_n_train": int(group_ever.sum()),
                    "event_occurrence_n_train_proxy": float(member_phi["event_occurrence_n_train_proxy"].sum()),
                    "group_phi": group_phi,
                    "top_member_codes_by_abs_phi": "|".join(member_phi["normalized_code"].astype(str).head(5).tolist()),
                }
            )
            for _, row in member_phi.iterrows():
                mapping_rows.append(
                    {
                        "seed": int(seed),
                        "group_id": group["group_id"],
                        "group_feature_column": group["group_id"],
                        "icd_chapter": str(chapter),
                        "phi_sign": str(sign),
                        "feature_column": clean_token(row["feature_column"]),
                        "normalized_code": clean_token(row["normalized_code"]),
                        "phi": float(row["phi"]),
                        "phi_abs": float(row["phi_abs"]),
                        "support_score": float(row["support_score"]),
                    }
                )

    mapping_df = pd.DataFrame(mapping_rows).sort_values(
        ["group_id", "phi_abs", "normalized_code"], ascending=[True, False, True]
    ).reset_index(drop=True)
    group_df = pd.DataFrame(group_rows).sort_values(["group_id"]).reset_index(drop=True)
    if group_df.empty:
        raise RuntimeError("Grouping produced no groups for the seed.")
    return group_df, mapping_df, heatmaps


def build_group_feature_matrix(
    source_matrix: pd.DataFrame,
    pid: pd.Series,
    y: pd.Series,
    mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    group_to_members = mapping_df.groupby("group_feature_column")["feature_column"].apply(list).to_dict()
    out = pd.DataFrame({"participant_id": pid.astype(int), "y_true": y.astype(int)})
    for group_feature, members in group_to_members.items():
        out[group_feature] = source_matrix[members].max(axis=1).astype(int)
    return out


# %% ---------------------------------------------------------------------------
# Model fitting, evaluation, and plots
# -----------------------------------------------------------------------------
def generate_training_oof_probabilities(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_type: str,
    seed: int,
    policy: dict[str, Any],
) -> tuple[np.ndarray | None, dict[str, Any]]:
    class_counts = y_train.value_counts().sort_index()
    min_class_n = int(class_counts.min()) if not class_counts.empty else 0
    n_splits = min(5, min_class_n)
    if n_splits < 2:
        return None, {"selection_scope": "fallback_fixed_threshold_due_to_insufficient_inner_cv_support"}
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=int(seed))
    oof = np.full(len(X_train), np.nan, dtype=float)
    for fold_id, (fit_idx, val_idx) in enumerate(splitter.split(X_train, y_train)):
        model = build_model_from_policy(model_type, seed + fold_id + 1, policy)
        X_fit = X_train.iloc[fit_idx].reset_index(drop=True)
        y_fit = y_train.iloc[fit_idx].reset_index(drop=True)
        X_val = X_train.iloc[val_idx].reset_index(drop=True)
        model.fit(X_fit, y_fit)
        class_values = list(getattr(model, "classes_", [0, 1]))
        pos_idx = class_values.index(1)
        oof[val_idx] = model.predict_proba(X_val)[:, pos_idx]
    if np.isnan(oof).any():
        raise RuntimeError("Training OOF probabilities contain NaN values.")
    return oof, {"selection_scope": "training_only_oof_inner_cv", "inner_cv_folds": int(n_splits)}


def fit_and_score_model(
    model_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    seed: int,
    policy: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame | None, np.ndarray]:
    model = build_model_from_policy(model_type, seed, policy)
    model.fit(X_train, y_train)
    class_values = list(getattr(model, "classes_", [0, 1]))
    if 1 not in class_values:
        raise RuntimeError(f"Model '{model_type}' did not learn positive class label 1.")
    pos_idx = class_values.index(1)
    y_proba_test = model.predict_proba(X_test)[:, pos_idx]

    oof_train, oof_meta = generate_training_oof_probabilities(
        X_train=X_train,
        y_train=y_train,
        model_type=model_type,
        seed=seed,
        policy=policy,
    )
    threshold_policy = clean_token(policy["evaluation_defaults"].get("threshold_policy")) or "train_balanced_accuracy_min_specificity"
    min_specificity_floor = float(policy["evaluation_defaults"].get("min_specificity_floor", 0.55))
    if oof_train is None:
        selected_threshold = 0.5
        threshold_sweep = pd.DataFrame()
        selection_meta = {
            "policy": "fixed_fallback",
            "selected_threshold": float(selected_threshold),
            "fallback_used": True,
            **oof_meta,
        }
    else:
        selected_threshold, threshold_sweep, selection_meta = select_threshold_from_policy(
            policy=threshold_policy,
            fixed_threshold=0.5,
            y_train=y_train,
            y_train_proba=oof_train,
            min_specificity_floor=min_specificity_floor,
        )
        selection_meta = {**selection_meta, **oof_meta}

    y_pred_test = (y_proba_test >= float(selected_threshold)).astype(int)
    metrics = evaluate_binary_predictions(y_test, y_pred_test, y_proba_test)
    metrics.update(
        {
            "model": model_type,
            "selected_threshold": float(selected_threshold),
            "threshold_fallback_used": bool(selection_meta.get("fallback_used", False)),
            "threshold_selection": selection_meta,
        }
    )

    coefficients_df = None
    if model_type == "lr":
        coefs = np.asarray(getattr(model, "coef_", [[0.0] * X_train.shape[1]]))[0]
        coefficients_df = pd.DataFrame(
            {
                "group_feature_column": X_train.columns.astype(str),
                "coefficient": coefs,
                "abs_coefficient": np.abs(coefs),
                "odds_ratio": np.exp(coefs),
            }
        ).sort_values(["abs_coefficient", "group_feature_column"], ascending=[False, True]).reset_index(drop=True)
    return metrics, coefficients_df, y_proba_test


def plot_support_histogram(path: Path, support_df: pd.DataFrame, threshold: float) -> None:
    plt.figure(figsize=(7, 4))
    plt.hist(support_df["support_score"].astype(float), bins=min(20, max(5, len(support_df))), color="#4c72b0", alpha=0.8)
    plt.axvline(float(threshold), color="#c44e52", linestyle="--", linewidth=2)
    plt.xlabel("Support score")
    plt.ylabel("Code count")
    plt.title("Support-score histogram")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def plot_support_tuning(path: Path, tuning_df: pd.DataFrame) -> None:
    plt.figure(figsize=(7, 4))
    plt.errorbar(
        tuning_df["support_quantile"].astype(float),
        tuning_df["inner_cv_balanced_accuracy_mean"].astype(float),
        yerr=tuning_df["inner_cv_balanced_accuracy_se"].astype(float),
        marker="o",
        color="#4c72b0",
    )
    selected_rows = tuning_df.loc[tuning_df["selected_flag"] == 1]
    if not selected_rows.empty:
        plt.scatter(
            selected_rows["support_quantile"].astype(float),
            selected_rows["inner_cv_balanced_accuracy_mean"].astype(float),
            color="#c44e52",
            s=50,
            zorder=3,
        )
    plt.xlabel("Support quantile")
    plt.ylabel("Inner-CV balanced accuracy")
    plt.title("Support-threshold tuning")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def plot_top_phi(path: Path, phi_df: pd.DataFrame) -> None:
    top_df = phi_df.head(20).iloc[::-1].copy()
    plt.figure(figsize=(8, max(4, 0.3 * len(top_df))))
    colors = ["#4c72b0" if v >= 0 else "#c44e52" for v in top_df["phi"].astype(float)]
    plt.hlines(top_df["normalized_code"], 0, top_df["phi"], color=colors, linewidth=2)
    plt.scatter(top_df["phi"], top_df["normalized_code"], color=colors, s=30)
    plt.xlabel("Phi")
    plt.ylabel("Code")
    plt.title("Top codes by phi")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def plot_weighted_heatmaps(plots_dir: Path, heatmaps: dict[str, pd.DataFrame]) -> None:
    for token, matrix in heatmaps.items():
        if matrix.shape[0] < 2:
            continue
        plt.figure(figsize=(max(4, 0.45 * matrix.shape[0]), max(4, 0.45 * matrix.shape[0])))
        plt.imshow(matrix.to_numpy(dtype=float), cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        plt.xticks(range(matrix.shape[1]), matrix.columns, rotation=90, fontsize=6)
        plt.yticks(range(matrix.shape[0]), matrix.index, fontsize=6)
        plt.colorbar(label="Weighted similarity")
        plt.title(f"Weighted similarity heatmap: {token}")
        plt.tight_layout()
        plt.savefig(plots_dir / f"weighted_similarity_heatmap_{token}.png", dpi=160)
        plt.close()


def plot_group_prevalence(path: Path, group_train_df: pd.DataFrame) -> None:
    group_cols = [c for c in group_train_df.columns if c not in {"participant_id", "y_true"}]
    prevalence = group_train_df[group_cols].mean(axis=0).sort_values(ascending=False)
    plt.figure(figsize=(8, max(4, 0.25 * len(prevalence))))
    plt.barh(prevalence.index[::-1], prevalence.values[::-1], color="#55a868")
    plt.xlabel("Training prevalence")
    plt.ylabel("Grouped feature")
    plt.title("Grouped-feature prevalence")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def plot_roc_pr_calibration(
    plots_dir: Path,
    y_test: pd.Series,
    model_outputs: dict[str, dict[str, Any]],
) -> None:
    plt.figure(figsize=(6, 5))
    for model_name, payload in model_outputs.items():
        y_proba = np.asarray(payload["y_proba"], dtype=float)
        fpr, tpr, _ = roc_curve(y_test, y_proba)
        auc_val = roc_auc_score(y_test, y_proba)
        plt.plot(fpr, tpr, label=f"{model_name.upper()} (AUC={auc_val:.3f})")
    plt.plot([0, 1], [0, 1], linestyle="--", color="grey")
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate")
    plt.title("ROC curves")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "roc_curves.png", dpi=160)
    plt.close()

    plt.figure(figsize=(6, 5))
    for model_name, payload in model_outputs.items():
        y_proba = np.asarray(payload["y_proba"], dtype=float)
        precision, recall, _ = precision_recall_curve(y_test, y_proba)
        ap = average_precision_score(y_test, y_proba)
        plt.plot(recall, precision, label=f"{model_name.upper()} (AP={ap:.3f})")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-recall curves")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "pr_curves.png", dpi=160)
    plt.close()

    plt.figure(figsize=(6, 5))
    for model_name, payload in model_outputs.items():
        y_proba = np.asarray(payload["y_proba"], dtype=float)
        frac_pos, mean_pred = calibration_curve(y_test, y_proba, n_bins=5, strategy="quantile")
        plt.plot(mean_pred, frac_pos, marker="o", label=model_name.upper())
    plt.plot([0, 1], [0, 1], linestyle="--", color="grey")
    plt.xlabel("Mean predicted probability")
    plt.ylabel("Observed fraction positive")
    plt.title("Calibration curves")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "calibration_curves.png", dpi=160)
    plt.close()


# %% ---------------------------------------------------------------------------
# Summary helpers
# -----------------------------------------------------------------------------
def median_iqr(series: pd.Series) -> tuple[float | None, float | None]:
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if vals.empty:
        return None, None
    return float(vals.median()), float(vals.quantile(0.75) - vals.quantile(0.25))


def build_aggregate_metrics(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model_name, model_df in summary_df.groupby("model", dropna=False):
        row = {"model": model_name, "seed_count": int(len(model_df))}
        for metric in ("balanced_accuracy", "roc_auc", "pr_auc", "sensitivity", "specificity", "brier"):
            med, iqr = median_iqr(model_df[metric])
            row[f"{metric}_median"] = med
            row[f"{metric}_iqr"] = iqr
        rows.append(row)
    return pd.DataFrame(rows).sort_values("model").reset_index(drop=True)


def build_best_seed_appendix(summary_df: pd.DataFrame, investigation_id: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model_name, model_df in summary_df.groupby("model", dropna=False):
        record = {"investigation_id": investigation_id, "model": model_name}
        for metric in ("roc_auc", "balanced_accuracy", "pr_auc"):
            best_val = float(model_df[metric].max())
            best_seeds = sorted(model_df.loc[model_df[metric] == best_val, "seed"].astype(int).tolist())
            record[f"best_seed_by_{metric}"] = "|".join(str(v) for v in best_seeds)
            record[f"best_{metric}"] = best_val
        rows.append(record)
    return pd.DataFrame(rows).sort_values("model").reset_index(drop=True)


def write_run_summary(path: Path, manifest: dict[str, Any], aggregate_df: pd.DataFrame, appendix_df: pd.DataFrame) -> None:
    lines = [
        "# Raw ICD Signalling Run Summary",
        "",
        f"- investigation_id: `{manifest['investigation_id']}`",
        f"- policy_id: `{manifest['policy_id']}`",
        f"- output_dir: `{manifest['run_dir']}`",
        f"- event_volume_operationalisation_v1: `{manifest['event_volume_operationalisation_v1']}`",
        "",
        "## Aggregate metrics",
    ]
    if aggregate_df.empty:
        lines.append("- none")
    else:
        for _, row in aggregate_df.iterrows():
            lines.append(
                f"- {row['model']}: balanced_accuracy {row['balanced_accuracy_median']:.4f} / {row['balanced_accuracy_iqr']:.4f}, "
                f"roc_auc {row['roc_auc_median']:.4f} / {row['roc_auc_iqr']:.4f}, "
                f"pr_auc {row['pr_auc_median']:.4f} / {row['pr_auc_iqr']:.4f}"
            )
    lines.extend(["", "## Appendix-only best seeds"])
    if appendix_df.empty:
        lines.append("- none")
    else:
        for _, row in appendix_df.iterrows():
            lines.append(
                f"- {row['model']}: best ROC AUC seed(s) `{row['best_seed_by_roc_auc']}`, "
                f"best balanced accuracy seed(s) `{row['best_seed_by_balanced_accuracy']}`, "
                f"best PR AUC seed(s) `{row['best_seed_by_pr_auc']}`"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# %% ---------------------------------------------------------------------------
# Main execution
# -----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    work_root = Path(args.work_root).resolve()
    output_root = Path(args.output_root).resolve() if args.output_root else work_root
    controls = load_signalling_controls(Path(args.investigation_control_csv))
    row = resolve_signalling_row(controls, clean_token(args.investigation_id))
    policy = load_policy(Path(args.policy_json))

    if clean_token(row["support_score_formula_id"]) != clean_token(policy["support_score"]["formula_id"]):
        raise ValueError("Signalling investigation row and policy JSON disagree on support_score_formula_id.")
    if clean_token(row["support_threshold_policy_id"]) != clean_token(policy["support_threshold_policy"]["policy_id"]):
        raise ValueError("Signalling investigation row and policy JSON disagree on support_threshold_policy_id.")
    if clean_token(row["grouping_policy_id"]) != clean_token(policy["grouping_policy"]["policy_id"]):
        raise ValueError("Signalling investigation row and policy JSON disagree on grouping_policy_id.")

    X_all, stage_a_df, pid_all, y_all, input_meta = load_inputs(
        work_root=work_root,
        row=row,
        target_profile_csv=Path(args.target_profile_csv),
    )

    if clean_token(args.force_run_dir):
        run_dir = ensure_dir(Path(args.force_run_dir).resolve())
    else:
        run_dir = ensure_dir(next_indexed_dir(output_root, "signalling"))

    write_json(run_dir / "investigation_control_snapshot.json", row)
    write_json(run_dir / "policy_snapshot.json", policy)

    summary_rows: list[dict[str, Any]] = []
    all_group_rows: list[pd.DataFrame] = []
    all_code_rows: list[pd.DataFrame] = []
    seeds = [int(v) for v in policy["outer_resampling"]["default_seeds"]]
    zero_offset = float(policy["support_score"].get("zero_offset", 0.5))
    event_volume_mode = clean_token(policy["support_score"].get("event_volume_operationalisation_v1"))

    for seed in seeds:
        seed_dir = ensure_dir(run_dir / f"seed_{seed}")
        plots_dir = ensure_dir(seed_dir / "plots")
        X_train, X_test, y_train, y_test, pid_train, pid_test, split_meta = split_dataset(
            X=X_all,
            y=y_all,
            pid=pid_all,
            test_size=float(policy["outer_resampling"].get("test_size", 0.25)),
            random_state=int(seed),
        )

        split_membership = pd.DataFrame(
            {
                "participant_id": pd.concat([pid_train, pid_test], ignore_index=True).astype(int),
                "split": ["train"] * len(pid_train) + ["test"] * len(pid_test),
                "seed": int(seed),
                "y_true": pd.concat([y_train, y_test], ignore_index=True).astype(int),
            }
        )
        split_membership.to_csv(seed_dir / "train_test_split_membership.csv", index=False)

        support_df = compute_support_summary(
            X_train=X_train.reset_index(drop=True),
            stage_a_df=stage_a_df,
            zero_offset=zero_offset,
            event_volume_mode=event_volume_mode,
        )
        support_df, selected_threshold, retained_codes, support_meta = tune_support_threshold(
            X_train=X_train.reset_index(drop=True),
            y_train=y_train.reset_index(drop=True),
            support_df=support_df,
            seed=int(seed),
            policy=policy,
        )
        support_df.to_csv(seed_dir / "support_summary.csv", index=False)
        tuning_df = support_df[[]].copy()
        tuning_df = pd.DataFrame()  # placeholder; replaced below
        support_tuning_df = pd.DataFrame()
        # Recompute the persisted tuning table to avoid returning a second large object from the tuner.
        tuning_rows: list[dict[str, Any]] = []
        for q in [float(v) for v in policy["support_threshold_policy"]["quantile_grid"]]:
            tau = float(support_df["support_score"].quantile(q))
            retained = support_df.loc[support_df["support_score"] >= tau, "feature_column"].astype(str).tolist()
            mean_score, se_score, fold_count = score_support_candidate(
                X_train.reset_index(drop=True)[retained].copy(),
                y_train.reset_index(drop=True),
                seed=int(seed + round(q * 100)),
                policy=policy,
            )
            tuning_rows.append(
                {
                    "support_quantile": q,
                    "support_threshold": tau,
                    "retained_code_count": int(len(retained)),
                    "inner_cv_balanced_accuracy_mean": mean_score,
                    "inner_cv_balanced_accuracy_se": se_score,
                    "inner_cv_fold_count": fold_count,
                    "selected_flag": int(math.isclose(q, support_meta["selected_support_quantile"])),
                }
            )
        support_tuning_df = pd.DataFrame(tuning_rows).sort_values("support_quantile").reset_index(drop=True)
        support_tuning_df.to_csv(seed_dir / "support_threshold_tuning.csv", index=False)

        plot_support_histogram(plots_dir / "support_score_histogram.png", support_df, selected_threshold)
        plot_support_tuning(plots_dir / "support_threshold_tuning.png", support_tuning_df)

        phi_df = compute_phi_table(
            X_train=X_train.reset_index(drop=True),
            y_train=y_train.reset_index(drop=True),
            support_df=support_df,
        )
        phi_df.to_csv(seed_dir / "code_phi_summary.csv", index=False)
        plot_top_phi(plots_dir / "top_phi_lollipop.png", phi_df)

        group_df, mapping_df, heatmaps = build_groups_for_seed(
            investigation_id=clean_token(row["investigation_id"]),
            seed=int(seed),
            phi_df=phi_df,
            X_train=X_train.reset_index(drop=True),
            y_train=y_train.reset_index(drop=True),
        )
        group_df.to_csv(seed_dir / "group_definition_table.csv", index=False)
        mapping_df.to_csv(seed_dir / "code_to_group_mapping.csv", index=False)
        plot_weighted_heatmaps(plots_dir, heatmaps)

        code_long_df = support_df.merge(
            phi_df.drop(columns=["participant_support_n_train", "event_occurrence_n_train_proxy", "support_score"], errors="ignore"),
            on=["feature_column", "normalized_code", "icd_chapter"],
            how="left",
        ).merge(
            mapping_df[["feature_column", "group_id", "group_feature_column"]],
            on="feature_column",
            how="left",
        )
        code_long_df["seed"] = int(seed)
        all_code_rows.append(code_long_df)

        X_group_train = build_group_feature_matrix(
            source_matrix=X_train.reset_index(drop=True),
            pid=pid_train.reset_index(drop=True),
            y=y_train.reset_index(drop=True),
            mapping_df=mapping_df,
        )
        X_group_test = build_group_feature_matrix(
            source_matrix=X_test.reset_index(drop=True),
            pid=pid_test.reset_index(drop=True),
            y=y_test.reset_index(drop=True),
            mapping_df=mapping_df,
        )
        X_group_train.to_csv(seed_dir / "group_feature_matrix_train.csv", index=False)
        X_group_test.to_csv(seed_dir / "group_feature_matrix_test.csv", index=False)
        plot_group_prevalence(plots_dir / "group_feature_prevalence.png", X_group_train)

        feature_cols = [c for c in X_group_train.columns if c not in {"participant_id", "y_true"}]
        model_outputs: dict[str, dict[str, Any]] = {}
        for model_type, run_flag in (
            ("lr", int(row.get("run_lr", 0))),
            ("rf", int(row.get("run_rf", 0))),
            ("nn", int(row.get("run_nn", 0))),
        ):
            metrics_path = seed_dir / f"{model_type}_metrics.json"
            if not run_flag:
                write_json(metrics_path, {"model": model_type, "skipped": True})
                continue
            metrics, coefficients_df, y_proba_test = fit_and_score_model(
                model_type=model_type,
                X_train=X_group_train[feature_cols].copy(),
                y_train=X_group_train["y_true"].astype(int).copy(),
                X_test=X_group_test[feature_cols].copy(),
                y_test=X_group_test["y_true"].astype(int).copy(),
                seed=int(seed),
                policy=policy,
            )
            metrics_payload = {
                **metrics,
                "seed": int(seed),
                "n_train": int(len(X_group_train)),
                "n_test": int(len(X_group_test)),
                "n_group_features": int(len(feature_cols)),
                "n_codes_retained": int(len(retained_codes)),
            }
            write_json(metrics_path, metrics_payload)
            if model_type == "lr" and coefficients_df is not None:
                coefficients_df.to_csv(seed_dir / "lr_coefficients.csv", index=False)
            model_outputs[model_type] = {"metrics": metrics_payload, "y_proba": y_proba_test}
            summary_rows.append(
                {
                    "investigation_id": clean_token(row["investigation_id"]),
                    "model": model_type,
                    "seed": int(seed),
                    "balanced_accuracy": float(metrics["balanced_accuracy"]),
                    "roc_auc": float(metrics["roc_auc"]),
                    "pr_auc": float(metrics["pr_auc"]),
                    "sensitivity": float(metrics["sensitivity"]),
                    "specificity": float(metrics["specificity"]),
                    "brier": float(metrics["brier"]),
                    "selected_threshold": float(metrics["selected_threshold"]),
                    "threshold_fallback_used": bool(metrics["threshold_fallback_used"]),
                    "n_train": int(len(X_group_train)),
                    "n_test": int(len(X_group_test)),
                    "n_group_features": int(len(feature_cols)),
                    "n_codes_retained": int(len(retained_codes)),
                    "train_class_dist": json.dumps(
                        {str(k): int(v) for k, v in X_group_train["y_true"].value_counts().sort_index().items()},
                        sort_keys=True,
                    ),
                    "test_class_dist": json.dumps(
                        {str(k): int(v) for k, v in X_group_test["y_true"].value_counts().sort_index().items()},
                        sort_keys=True,
                    ),
                }
            )
        if "lr" in model_outputs and not (seed_dir / "lr_coefficients.csv").exists():
            pd.DataFrame(columns=["group_feature_column", "coefficient", "abs_coefficient", "odds_ratio"]).to_csv(
                seed_dir / "lr_coefficients.csv", index=False
            )
        plot_roc_pr_calibration(plots_dir, X_group_test["y_true"].astype(int), model_outputs)

        seed_manifest = {
            "seed": int(seed),
            "investigation_id": clean_token(row["investigation_id"]),
            "selected_support_threshold": float(selected_threshold),
            "support_selection_meta": support_meta,
            "event_volume_source_mode": event_volume_mode,
            "split_meta": split_meta,
            "n_codes_retained": int(len(retained_codes)),
            "n_group_features": int(len(feature_cols)),
            "stage_a_preparation_path": input_meta["stage_a_preparation_path"],
            "discovery_matrix_path": input_meta["discovery_matrix_path"],
            "label_source_path": input_meta["label_source_path"],
        }
        write_json(seed_dir / "seed_manifest.json", seed_manifest)
        all_group_rows.append(group_df.assign(seed=int(seed)))

    summary_df = pd.DataFrame(summary_rows).sort_values(["model", "seed"]).reset_index(drop=True)
    summary_df.to_csv(run_dir / "summary_metrics_by_seed.csv", index=False)
    aggregate_df = build_aggregate_metrics(summary_df)
    aggregate_df.to_csv(run_dir / "summary_metrics_aggregate.csv", index=False)
    appendix_df = build_best_seed_appendix(summary_df, clean_token(row["investigation_id"]))
    appendix_df.to_csv(run_dir / "best_seed_appendix_summary.csv", index=False)
    pd.concat(all_group_rows, ignore_index=True).to_csv(run_dir / "all_groups_long.csv", index=False)
    pd.concat(all_code_rows, ignore_index=True).to_csv(run_dir / "all_codes_long.csv", index=False)

    run_manifest = {
        "run_dir": str(run_dir),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "investigation_id": clean_token(row["investigation_id"]),
        "analysis_mode": clean_token(row["analysis_mode"]),
        "policy_id": clean_token(policy["policy_id"]),
        "policy_version": clean_token(policy["policy_version"]),
        "output_root": str(output_root),
        "input_meta": input_meta,
        "seeds": seeds,
        "event_volume_operationalisation_v1": event_volume_mode,
        "root_outputs": policy["required_root_outputs"],
        "seed_outputs": policy["required_seed_outputs"],
        "plot_outputs": policy["required_plot_outputs"],
    }
    write_json(run_dir / "run_manifest.json", run_manifest)
    write_run_summary(run_dir / "README_run_summary.md", run_manifest, aggregate_df, appendix_df)
    print(f"Raw ICD signalling run written to: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
