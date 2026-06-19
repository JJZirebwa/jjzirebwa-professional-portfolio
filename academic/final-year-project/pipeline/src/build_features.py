"""Portfolio copy of the authored final-year project pipeline.

Private run roots and account-specific paths have been replaced with placeholders.
The method structure is preserved for technical review.
"""

# %% Cell 0: Imports and runtime constants
from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd


SECONDS_PER_DAY = 24 * 60 * 60
DAYS_PER_YEAR = 365.25
DEFAULT_ICD_POLICY_CSV = Path(__file__).resolve().parent / "config" / "icd_group_policy.csv"
DEFAULT_TARGET_POLICY_CSV = Path(__file__).resolve().parent / "config" / "target_profile_mappings.csv"
DEFAULT_RECENCY_POLICY_CSV = Path(__file__).resolve().parent / "config" / "recency_policy.csv"
DEFAULT_PREPROCESSING_POLICY_JSON = Path(__file__).resolve().parent / "config" / "preprocessing_policy_v1.json"


# %% Cell 1: Generic data/cleaning helpers
def load_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return pd.read_csv(path)


def ensure_participant_id(df: pd.DataFrame, label: str) -> pd.DataFrame:
    if "participant_id" not in df.columns:
        raise KeyError(f"{label} missing required column: participant_id")
    out = df.copy()
    out["participant_id"] = pd.to_numeric(out["participant_id"], errors="coerce").astype("Int64")
    out = out.dropna(subset=["participant_id"])
    return out


def parse_date_col(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    return pd.to_datetime(df[col], errors="coerce")


def clean_token(value: Any) -> str:
    if pd.isna(value):
        return ""
    txt = str(value).strip()
    if not txt or txt.lower() in {"nan", "<na>", "none", "null"}:
        return ""
    return txt


def mode_nonempty(values: pd.Series, unknown: str = "Unknown") -> str:
    cleaned = [clean_token(v) for v in values]
    cleaned = [v for v in cleaned if v]
    if not cleaned:
        return unknown
    return pd.Series(cleaned).value_counts().index[0]


def percentile_cap(series: pd.Series, upper_q: float) -> tuple[pd.Series, float | None]:
    if series.dropna().empty:
        return series, None
    cap_value = float(series.quantile(upper_q))
    return series.clip(upper=cap_value), cap_value


def year_tag(years: float) -> str:
    if float(years).is_integer():
        return f"{int(years)}y"
    return f"{str(years).replace('.', 'p')}y"


# %% Cell 2: ICD/OPCS parsing and grouped-mapping helpers
ICD_TOKEN_RE = re.compile(r"[A-Z][0-9]{2}[A-Z0-9]{0,2}")
ICD_VALID_RE = re.compile(r"^[A-Z][0-9]{2}[A-Z0-9]{0,2}$")
OPCS_TOKEN_RE = re.compile(r"[A-Z][0-9]{2}[A-Z0-9]?")
OPCS_VALID_RE = re.compile(r"^[A-Z][0-9]{2}[A-Z0-9]?$")

ICD_CORE_GROUPS = [
    "ventricular_tachyarrhythmia",
    "ventricular_fibrillation_flutter",
    "cardiac_arrest_history",
    "syncope_collapse",
    "av_block_any",
    "bundle_branch_fascicular_iv_block",
    "sinus_node_dysfunction",
    "bradycardia_unspecified",
    "atrial_fibrillation_flutter",
]

ICD_OPTIONAL_GROUPS = [
    "brugada_or_specified_channelopathy",
    "premature_depolarisation",
    "palpitations_only",
    "abnormal_ecg_or_cardiac_tests",
    "device_presence_cardiac",
    "device_followup_management",
    "seizure_like",
    "chest_pain",
    "orthostatic_syncope",
    "structural_diff",
    "febrile_infective_trigger",
    "drug_toxicity_substance",
]

ICD_BURDEN_MODULE_GROUPS: dict[str, list[str]] = {
    "ventricular_severity_burden": [
        "ventricular_tachyarrhythmia",
        "ventricular_fibrillation_flutter",
        "cardiac_arrest_history",
    ],
    "conduction_system_burden": [
        "av_block_any",
        "bundle_branch_fascicular_iv_block",
        "sinus_node_dysfunction",
        "bradycardia_unspecified",
    ],
    "loc_mimic_burden": [
        "syncope_collapse",
        "orthostatic_syncope",
        "seizure_like",
        "palpitations_only",
    ],
    "pathway_proxy_burden": [
        "brugada_or_specified_channelopathy",
        "abnormal_ecg_or_cardiac_tests",
        "device_presence_cardiac",
        "device_followup_management",
    ],
}

OPCS_CORE_GROUPS = [
    "eps_no_ablation",
    "ablation_any",
    "ppm_any",
    "icd_crt_any",
    "ecg_diag_any",
    "conduction_any",
]

OPCS_OPTIONAL_GROUPS = [
    "icd_subcutaneous",
    "leadless_pacing",
    "device_revision",
    "advanced_hf_therapy",
    "ecg_holter",
    "ecg_exercise",
]

ICD_GROUP_COLUMNS_BY_TABLE = {
    "apc": ["diag_all", *[f"diag_{i:02d}" for i in range(1, 21)]],
    "op": ["diag_all", *[f"diag_{i:02d}" for i in range(1, 13)]],
    "ae": ["diag_all", *[f"diag_{i:02d}" for i in range(1, 13)]],
}

ICD_SIGNAL_DISCOVERY_COLUMNS_BY_TABLE = {
    "apc": ["diag_all"],
    "op": ["diag_all"],
    "ae": ["diag_all"],
}

OPCS_GROUP_COLUMNS_BY_TABLE = {
    "apc": ["opertn_all", "opertn_01", "opertn_02", "opertn_03"],
    "op": ["opertn_all", "opertn_01", "opertn_02", "opertn_03"],
}

OPCS_ABLATION_CODES = {"K521", "K571", "K622", "K623"}


def code3_in_range(code3: str, prefix: str, lo: int, hi: int) -> bool:
    if len(code3) != 3 or not code3.startswith(prefix):
        return False
    num = code3[1:]
    if not num.isdigit():
        return False
    value = int(num)
    return lo <= value <= hi


def extract_icd_codes(value: Any) -> set[str]:
    raw = clean_token(value).upper()
    if not raw:
        return set()
    raw = raw.replace(".", "")
    tokens = ICD_TOKEN_RE.findall(raw)
    return {tok for tok in tokens if ICD_VALID_RE.match(tok)}


def extract_opcs_codes(value: Any) -> set[str]:
    raw = clean_token(value).upper()
    if not raw:
        return set()
    raw = raw.replace(".", "")
    tokens = OPCS_TOKEN_RE.findall(raw)
    return {tok for tok in tokens if OPCS_VALID_RE.match(tok)}


def map_icd_groups(code: str) -> set[str]:
    """Return ICD groups for the dissertation-aligned refined signal map."""
    if not code:
        return set()

    code3 = code[:3]
    code4 = code[:4] if len(code) >= 4 else code3
    groups: set[str] = set()

    # Core groups: emphasise pre-diagnostic phenotype expression rather than direct diagnosis labels.
    if code4 == "I498":
        groups.add("brugada_or_specified_channelopathy")
    if code4 in {"I470", "I472"}:
        groups.add("ventricular_tachyarrhythmia")
    if code4 == "I490":
        groups.add("ventricular_fibrillation_flutter")
    if code3 == "I46":
        groups.add("cardiac_arrest_history")
    if code3 == "R55" or code4 == "I459":
        groups.add("syncope_collapse")
    if code3 == "I44":
        groups.add("av_block_any")
    if code3 == "I45":
        groups.add("bundle_branch_fascicular_iv_block")
    if code4 == "I495":
        groups.add("sinus_node_dysfunction")
    if code4 == "R001":
        groups.add("bradycardia_unspecified")
    if code3 == "I48":
        groups.add("atrial_fibrillation_flutter")

    # Optional context/sensitivity groups. These include direct diagnosis-pathway
    # and work-up or care-pathway proxies kept out of the default model profile.
    if code4 == "I951":
        groups.update({"syncope_collapse", "orthostatic_syncope"})
    if code4 in {"I491", "I492", "I493", "I494"}:
        groups.add("premature_depolarisation")
    if code4 == "R002":
        groups.add("palpitations_only")
    if code4 == "R943":
        groups.add("abnormal_ecg_or_cardiac_tests")
    if code4 == "Z950":
        groups.add("device_presence_cardiac")
    if code4 == "Z450":
        groups.add("device_followup_management")
    if code3 in {"G40", "G41", "R56"}:
        groups.add("seizure_like")
    if code3 in {"R07", "I20", "I24"}:
        groups.add("chest_pain")
    if code3 in {"I30", "I31", "I40", "I41", "I42", "I50"} or code4 in {"I514", "I517"}:
        groups.add("structural_diff")
    if code3 == "R50" or code3_in_range(code3, "J", 10, 18) or code3_in_range(code3, "A", 40, 41):
        groups.add("febrile_infective_trigger")
    if code3_in_range(code3, "T", 36, 50) or code3_in_range(code3, "F", 10, 19):
        groups.add("drug_toxicity_substance")

    return groups


def map_opcs_group(code: str) -> str | None:
    if not code:
        return None
    code3 = code[:3]
    code4 = code[:4] if len(code) >= 4 else code3

    # Core groups (hierarchical precedence).
    if code4 == "K582":
        return "eps_no_ablation"
    if code4 in OPCS_ABLATION_CODES:
        return "ablation_any"
    if code3 == "K60":
        return "ppm_any"
    if code3 == "K59" or code4 in {"K617", "K721", "K611"}:
        return "icd_crt_any"
    if code3 == "U19":
        return "ecg_diag_any"
    if code3 in {"K52", "K57", "K58", "K62"}:
        return "conduction_any"

    # Optional groups (sensitivity modules).
    if code4 == "K721":
        return "icd_subcutaneous"
    if code3 == "K70":
        return "leadless_pacing"
    if code4 == "K611":
        return "device_revision"
    if code4 == "K578":
        return "advanced_hf_therapy"
    if code4 == "U193":
        return "ecg_holter"
    if code4 == "U194":
        return "ecg_exercise"
    return None


def load_icd_group_policy(policy_path: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    """Load editable ICD group level policy (core vs optional) from CSV."""
    default_meta = {
        "policy_file": str(policy_path),
        "policy_loaded": False,
        "policy_reason": "fallback_to_builtin_defaults",
        "group_levels": {group: "core" for group in ICD_CORE_GROUPS} | {group: "optional" for group in ICD_OPTIONAL_GROUPS},
        "include_in_default_model": {group: int(group in ICD_CORE_GROUPS) for group in (ICD_CORE_GROUPS + ICD_OPTIONAL_GROUPS)},
        "include_in_lr_relevant_baseline": {group: int(group in ICD_CORE_GROUPS) for group in (ICD_CORE_GROUPS + ICD_OPTIONAL_GROUPS)},
        "min_positive_n_override": {group: None for group in (ICD_CORE_GROUPS + ICD_OPTIONAL_GROUPS)},
    }
    if not policy_path.exists():
        default_meta["policy_reason"] = "policy_file_missing"
        return ICD_CORE_GROUPS.copy(), ICD_OPTIONAL_GROUPS.copy(), default_meta

    policy = pd.read_csv(policy_path)
    required_cols = {"group_name", "group_level", "include_in_default_model", "include_in_lr_relevant_baseline"}
    missing_cols = required_cols.difference(policy.columns)
    if missing_cols:
        raise ValueError(
            f"ICD group policy CSV missing required columns: {sorted(missing_cols)} (file={policy_path})"
        )

    policy = policy.copy()
    policy["group_name"] = policy["group_name"].map(clean_token)
    policy["group_level"] = policy["group_level"].map(clean_token).str.lower()
    policy["include_in_default_model"] = pd.to_numeric(policy["include_in_default_model"], errors="coerce").fillna(0).astype(int)
    policy["include_in_lr_relevant_baseline"] = pd.to_numeric(
        policy["include_in_lr_relevant_baseline"], errors="coerce"
    ).fillna(0).astype(int)
    if "min_positive_n_override" in policy.columns:
        policy["min_positive_n_override"] = (
            pd.to_numeric(policy["min_positive_n_override"], errors="coerce")
            .where(lambda s: s > 0)
        )
    else:
        policy["min_positive_n_override"] = np.nan

    policy = policy[policy["group_name"] != ""]
    if policy["group_name"].duplicated().any():
        dups = sorted(policy.loc[policy["group_name"].duplicated(), "group_name"].unique().tolist())
        raise ValueError(f"ICD group policy has duplicate group_name rows: {dups} (file={policy_path})")

    invalid_levels = sorted(
        policy.loc[~policy["group_level"].isin({"core", "optional"}), "group_level"].unique().tolist()
    )
    if invalid_levels:
        raise ValueError(f"ICD group policy has invalid group_level values: {invalid_levels} (file={policy_path})")

    expected = set(ICD_CORE_GROUPS + ICD_OPTIONAL_GROUPS)
    found = set(policy["group_name"].tolist())
    missing_groups = sorted(expected.difference(found))
    extra_groups = sorted(found.difference(expected))
    if missing_groups:
        raise ValueError(f"ICD group policy missing known groups: {missing_groups} (file={policy_path})")
    if extra_groups:
        raise ValueError(f"ICD group policy contains unknown groups: {extra_groups} (file={policy_path})")

    # Preserve row ordering from the policy file for deterministic feature ordering.
    ordered_groups = policy["group_name"].tolist()
    level_map = dict(zip(policy["group_name"], policy["group_level"]))
    core_groups = [g for g in ordered_groups if level_map[g] == "core"]
    optional_groups = [g for g in ordered_groups if level_map[g] == "optional"]

    meta = {
        "policy_file": str(policy_path),
        "policy_loaded": True,
        "policy_reason": "loaded_from_csv",
        "group_levels": {row.group_name: row.group_level for row in policy.itertuples(index=False)},
        "include_in_default_model": {
            row.group_name: int(row.include_in_default_model) for row in policy.itertuples(index=False)
        },
        "include_in_lr_relevant_baseline": {
            row.group_name: int(row.include_in_lr_relevant_baseline) for row in policy.itertuples(index=False)
        },
        "min_positive_n_override": {
            row.group_name: (
                int(row.min_positive_n_override)
                if pd.notna(row.min_positive_n_override)
                else None
            )
            for row in policy.itertuples(index=False)
        },
    }
    return core_groups, optional_groups, meta


def load_target_policy_source_columns(policy_path: Path | None) -> list[str]:
    """Load target source-column names from target-policy CSV.

    Missing/invalid files are treated as no-op to preserve build stability.
    """
    if policy_path is None or not policy_path.exists():
        return []
    try:
        policy = pd.read_csv(policy_path)
    except Exception:
        return []
    if "source_column" not in policy.columns:
        return []
    cols = (
        policy["source_column"]
        .map(clean_token)
        .replace("", pd.NA)
        .dropna()
        .astype(str)
        .drop_duplicates()
        .tolist()
    )
    return sorted(cols)


def load_recency_policy(
    policy_path: Path | None,
    policy_id: str | None,
) -> tuple[set[str], set[str], dict[str, Any]]:
    """Load recency policy controls for ICD grouped recency columns.

    If policy cannot be loaded, the function returns empty include sets and metadata
    indicating policy was not applied. This preserves execution stability.
    """
    if policy_path is None or not policy_path.exists() or not policy_id:
        return set(), set(), {
            "recency_policy_loaded": False,
            "recency_policy_id": policy_id,
            "recency_policy_file": str(policy_path) if policy_path else None,
            "recency_policy_reason": "missing_policy_input",
        }

    try:
        policy = pd.read_csv(policy_path)
    except Exception:
        return set(), set(), {
            "recency_policy_loaded": False,
            "recency_policy_id": policy_id,
            "recency_policy_file": str(policy_path),
            "recency_policy_reason": "read_error",
        }

    required_cols = {
        "recency_policy_id",
        "icd_group_name",
        "include_days_since_last",
        "include_days_since_first",
    }
    missing_cols = required_cols.difference(set(policy.columns))
    if missing_cols:
        return set(), set(), {
            "recency_policy_loaded": False,
            "recency_policy_id": policy_id,
            "recency_policy_file": str(policy_path),
            "recency_policy_reason": f"missing_columns:{sorted(missing_cols)}",
        }

    subset = policy.loc[
        policy["recency_policy_id"].map(clean_token).str.lower() == clean_token(policy_id).lower()
    ].copy()
    if subset.empty:
        return set(), set(), {
            "recency_policy_loaded": False,
            "recency_policy_id": policy_id,
            "recency_policy_file": str(policy_path),
            "recency_policy_reason": "policy_id_not_found",
        }

    subset["icd_group_name"] = subset["icd_group_name"].map(clean_token)
    subset["include_days_since_last"] = pd.to_numeric(
        subset["include_days_since_last"], errors="coerce"
    ).fillna(0).astype(int)
    subset["include_days_since_first"] = pd.to_numeric(
        subset["include_days_since_first"], errors="coerce"
    ).fillna(0).astype(int)

    include_last = set(
        subset.loc[subset["include_days_since_last"] == 1, "icd_group_name"].tolist()
    )
    include_first = set(
        subset.loc[subset["include_days_since_first"] == 1, "icd_group_name"].tolist()
    )
    meta = {
        "recency_policy_loaded": True,
        "recency_policy_id": policy_id,
        "recency_policy_file": str(policy_path),
        "recency_policy_reason": "loaded_from_csv",
        "recency_include_last_groups": sorted(include_last),
        "recency_include_first_groups": sorted(include_first),
    }
    return include_last, include_first, meta


def parse_icd_recency_column(col: str) -> tuple[str, str] | None:
    """Parse icd recency columns: icd_grp_<group>_days_since_(last|first)_<tag>."""
    match = re.match(r"^icd_grp_(.+?)_days_since_(last|first)_[A-Za-z0-9_]+$", col)
    if not match:
        return None
    return match.group(1), match.group(2)


def load_preprocessing_policy(policy_path: Path | None) -> dict[str, Any]:
    resolved = policy_path if policy_path is not None else DEFAULT_PREPROCESSING_POLICY_JSON
    if not resolved.exists():
        raise FileNotFoundError(f"Missing preprocessing policy JSON: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    payload["policy_path"] = str(resolved.resolve())
    return payload


def matches_any_regex(value: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, value) for pattern in patterns)


def infer_binary_numeric(series: pd.Series) -> bool:
    vals = pd.to_numeric(series, errors="coerce").dropna().unique()
    if len(vals) == 0:
        return False
    return set(pd.Series(vals).astype(float).tolist()).issubset({0.0, 1.0})


def build_governed_preprocessing_spec(
    raw_store: pd.DataFrame,
    feature_meta: dict[str, Any],
    core_window_years: float,
    include_legacy_vcf_fields: bool,
    include_sequencing_missing_flag: bool,
    target_policy_csv: Path | None,
    preprocessing_policy: dict[str, Any],
    recency_sentinel_days: float,
) -> dict[str, Any]:
    deprecated_vcf_fields = ["has_scn5a_vcf", "scn5a_evidence_source"]
    secondary_genetics_fields = [
        "has_scn5a_any",
        "scn5a_plp_flag",
        "scn5a_tier3_flag",
        "scn5a_tier3_only_flag",
        "is_proband_scn5a",
        "n_scn5a_variants_total",
        "n_scn5a_tier1_2",
        "n_scn5a_tier3",
        "mixed_tier_flag",
        "best_scn5a_tier_num",
        "scn5a_best_tier",
        "scn5a_consequence_types",
        "scn5a_has_consequence",
        "any_het_scn5a",
        "any_hom_or_biallelic_scn5a",
        "any_AD_compatible",
        "any_AR_compatible",
        "any_de_novo_like",
        "monogenic_high",
        "modifier_only",
        "scn5a_negative",
        "burden_class",
        "architecture_label",
        "tiering_label_primary",
        "tiering_label_detail",
        "scn5a_conflict",
        "monogenic_scn5a",
        "promoter_only",
        "no_scn5a_signal",
    ]
    non_predictor_cols = [
        "participant_id",
        "sequencing_date",
        "sequencing_date_policy",
        "promoter_carrier",
        "promoter_zygosity",
        "promoter_dosage",
        "promoter_zygosity_inferred",
        "has_rs41310239",
        "label_primary",
        "label_detail",
        "label",
        "target_name",
    ] + secondary_genetics_fields
    if not include_legacy_vcf_fields:
        non_predictor_cols.extend(deprecated_vcf_fields)
    if not include_sequencing_missing_flag:
        non_predictor_cols.extend(["sequencing_date_missing", "sequencing_index_available"])

    candidate_predictors = [
        c for c in raw_store.columns
        if c not in set(non_predictor_cols) and c != "participant_id"
    ]
    preferred_predictors = set(feature_meta["feature_cols"] + feature_meta["categorical_context_cols"])
    predictors = [c for c in candidate_predictors if c in preferred_predictors]
    if include_sequencing_missing_flag and "sequencing_date_missing" in raw_store.columns:
        predictors.append("sequencing_date_missing")

    target_cols = [
        c
        for c in [
            "promoter_carrier",
            "promoter_dosage",
            "tier12_positive",
            "monogenic_high",
            "modifier_only",
            "scn5a_negative",
            "burden_class",
        ]
        if c in raw_store.columns
    ]
    target_source_cols_from_policy = load_target_policy_source_columns(target_policy_csv)
    for col in target_source_cols_from_policy:
        if col in raw_store.columns and col not in target_cols:
            target_cols.append(col)

    feature_family_map = {
        "count_cols": set(feature_meta.get("count_cols", [])),
        "duration_cols": set(feature_meta.get("duration_cols", [])),
        "ratio_cols": set(feature_meta.get("ratio_cols", [])),
        "recency_cols": set(feature_meta.get("recency_cols", [])),
        "density_cols": set(feature_meta.get("density_cols", [])),
        "icd_group_feature_cols": set(feature_meta.get("icd_group_feature_cols", [])),
        "burden_feature_cols": set(feature_meta.get("burden_feature_cols", [])),
        "opcs_group_feature_cols": set(feature_meta.get("opcs_group_feature_cols", [])),
        "categorical_context_cols": set(feature_meta.get("categorical_context_cols", [])),
        "observability_covariate_cols": set(feature_meta.get("observability_covariate_cols", [])),
        "index_dependent_cols": set(feature_meta.get("index_dependent_cols", [])),
    }
    class_rules = preprocessing_policy.get("feature_class_rules", {})
    central_policy = preprocessing_policy.get("clinically_central_retention", {})
    categorical_policy = preprocessing_policy.get("categorical_policy", {})
    recency_policy = preprocessing_policy.get("recency_policy", {})
    log_policy = preprocessing_policy.get("log_transform_policy", {})
    winsor_policy = preprocessing_policy.get("winsor_policy", {})
    scaling_policy = preprocessing_policy.get("scaling_policy", {})

    class_assignments: dict[str, list[str]] = {
        "binary": [],
        "low_card_categorical": [],
        "ordinal": [],
        "continuous": [],
        "count": [],
        "duration": [],
        "rate": [],
        "recency": [],
    }
    column_policies: dict[str, dict[str, Any]] = {}
    categorical_predictor_columns: list[str] = []
    numeric_predictor_columns: list[str] = []
    clinically_central_columns: list[str] = []
    log_eligible_columns: list[str] = []
    winsor_eligible_columns: list[str] = []
    scaling_eligible_columns: list[str] = []

    for col in predictors:
        series = raw_store[col]
        family_hits = sorted([name for name, members in feature_family_map.items() if col in members])
        is_binary = infer_binary_numeric(series) or matches_any_regex(
            col, class_rules.get("binary_regex", [])
        )
        is_categorical = (
            col in feature_family_map["categorical_context_cols"]
            or str(series.dtype) == "object"
        )

        if col in set(class_rules.get("ordinal_exact_columns", [])):
            feature_class = "ordinal"
        elif col in feature_family_map["recency_cols"]:
            feature_class = "recency"
        elif col in feature_family_map["duration_cols"] or col in set(class_rules.get("duration_exact_columns", [])):
            feature_class = "duration"
        elif matches_any_regex(col, class_rules.get("rate_regex", [])):
            feature_class = "rate"
        elif col in feature_family_map["count_cols"]:
            feature_class = "count"
        elif is_binary:
            feature_class = "binary"
        elif is_categorical:
            feature_class = "low_card_categorical"
        elif matches_any_regex(col, class_rules.get("continuous_regex", [])) or col in feature_family_map["ratio_cols"] or col in feature_family_map["density_cols"]:
            feature_class = "continuous"
        else:
            feature_class = "continuous"

        central_regex = central_policy.get("regex", [])
        central_families = set(central_policy.get("feature_meta_families", []))
        clinically_central = (
            col in set(central_policy.get("exact_columns", []))
            or matches_any_regex(col, central_regex)
            or bool(central_families.intersection(set(family_hits)))
        )
        if clinically_central:
            clinically_central_columns.append(col)

        missingness_policy_class = "numeric_selective"
        if feature_class == "low_card_categorical":
            missingness_policy_class = "categorical_unknown"
        elif feature_class == "binary":
            missingness_policy_class = "binary_passthrough"
        elif feature_class == "recency":
            missingness_policy_class = "recency_sentinel"

        log_eligible = (
            feature_class in set(log_policy.get("eligible_feature_classes", []))
            or matches_any_regex(col, log_policy.get("eligible_regex", []))
        ) and feature_class not in set(log_policy.get("exclude_feature_classes", []))
        winsor_eligible = (
            feature_class in set(winsor_policy.get("eligible_feature_classes", []))
            or matches_any_regex(col, winsor_policy.get("eligible_regex", []))
        ) and feature_class not in set(winsor_policy.get("exclude_feature_classes", []))
        scaling_eligible = (
            feature_class in set(scaling_policy.get("eligible_feature_classes", []))
        ) and feature_class not in set(scaling_policy.get("exclude_feature_classes", []))

        if feature_class == "recency":
            log_eligible = False
            winsor_eligible = not bool(recency_policy.get("protect_from_winsor", True))
            scaling_eligible = not bool(recency_policy.get("protect_from_scaling", True))
        if feature_class in {"binary", "low_card_categorical"}:
            log_eligible = False
            scaling_eligible = False

        non_null_levels = (
            sorted({clean_token(v) for v in series.dropna().tolist() if clean_token(v)})
            if feature_class == "low_card_categorical"
            else []
        )
        if feature_class == "low_card_categorical":
            categorical_predictor_columns.append(col)
        else:
            numeric_predictor_columns.append(col)
        if log_eligible:
            log_eligible_columns.append(col)
        if winsor_eligible:
            winsor_eligible_columns.append(col)
        if scaling_eligible:
            scaling_eligible_columns.append(col)
        class_assignments[feature_class].append(col)
        column_policies[col] = {
            "feature_class": feature_class,
            "source_families": family_hits,
            "binary_like": bool(is_binary),
            "categorical_like": bool(is_categorical),
            "clinically_central": bool(clinically_central),
            "missingness_policy_class": missingness_policy_class,
            "protected_from_scaling": bool(not scaling_eligible),
            "protected_from_log": bool(not log_eligible),
            "eligible_for_log": bool(log_eligible),
            "eligible_for_winsor": bool(winsor_eligible),
            "eligible_for_scaling": bool(scaling_eligible),
            "n_unique_non_null": int(series.dropna().nunique()),
            "non_null_category_levels": non_null_levels,
        }

    return {
        "policy_id": preprocessing_policy.get("policy_id"),
        "policy_version": preprocessing_policy.get("policy_version"),
        "policy_path": preprocessing_policy.get("policy_path"),
        "core_window_years": float(core_window_years),
        "default_recency_sentinel_days": float(recency_sentinel_days),
        "target_columns": target_cols,
        "target_source_columns_from_policy": target_source_cols_from_policy,
        "predictor_columns": predictors,
        "categorical_predictor_columns": sorted(categorical_predictor_columns),
        "numeric_predictor_columns": sorted(numeric_predictor_columns),
        "feature_class_assignments": {k: sorted(v) for k, v in class_assignments.items()},
        "column_policies": column_policies,
        "clinically_central_columns": sorted(clinically_central_columns),
        "log_eligible_columns": sorted(log_eligible_columns),
        "winsor_eligible_columns": sorted(winsor_eligible_columns),
        "scaling_eligible_columns": sorted(scaling_eligible_columns),
        "missingness_policy": preprocessing_policy.get("missingness_policy", {}),
        "categorical_policy": categorical_policy,
        "recency_policy": recency_policy,
        "log_transform_policy": log_policy,
        "winsor_policy": winsor_policy,
        "scaling_policy": scaling_policy,
        "model_defaults": preprocessing_policy.get("model_defaults", {}),
        "evaluation_defaults": preprocessing_policy.get("evaluation_defaults", {}),
        "default_excluded_secondary_genetics": secondary_genetics_fields,
        "default_excluded_legacy_vcf_fields": deprecated_vcf_fields if not include_legacy_vcf_fields else [],
        "include_legacy_vcf_fields": include_legacy_vcf_fields,
        "include_sequencing_missing_flag": include_sequencing_missing_flag,
        "categorical_unknown_token": categorical_policy.get("unknown_token", "Unknown"),
    }


def build_group_episode_events(
    tables: dict[str, pd.DataFrame],
    columns_by_table: dict[str, list[str]],
    code_parser: Callable[[Any], set[str]],
    code_mapper: Callable[[str], str | Iterable[str] | None],
) -> pd.DataFrame:
    records: list[tuple[int, float, str, str]] = []
    for table_name, df in tables.items():
        if df.empty:
            continue
        code_cols = [c for c in columns_by_table.get(table_name, []) if c in df.columns]
        if not code_cols:
            continue
        use_cols = ["participant_id", "days_before_index", *code_cols]
        tmp = df[use_cols].copy().reset_index(drop=True)
        tmp["participant_id"] = pd.to_numeric(tmp["participant_id"], errors="coerce").astype("Int64")
        tmp["days_before_index"] = pd.to_numeric(tmp["days_before_index"], errors="coerce")
        tmp = tmp.dropna(subset=["participant_id", "days_before_index"])
        for row_idx, row in enumerate(tmp.itertuples(index=False, name=None)):
            participant_id = int(row[0])
            days_before_index = float(row[1])
            event_key = f"{table_name}:{row_idx}"
            codes: set[str] = set()
            for raw_code_val in row[2:]:
                codes.update(code_parser(raw_code_val))
            if not codes:
                continue
            groups: set[str] = set()
            for code in codes:
                mapped = code_mapper(code)
                if mapped is None:
                    continue
                if isinstance(mapped, str):
                    mapped_values = [mapped]
                else:
                    mapped_values = list(mapped)
                for group_name in mapped_values:
                    cleaned_group = clean_token(group_name)
                    if cleaned_group:
                        groups.add(cleaned_group)
            for group in groups:
                records.append((participant_id, days_before_index, group, event_key))
    if not records:
        return pd.DataFrame(columns=["participant_id", "days_before_index", "group", "event_key"])
    return pd.DataFrame(records, columns=["participant_id", "days_before_index", "group", "event_key"])


def build_burden_group_episode_events(
    grouped_events: pd.DataFrame,
    burden_module_groups: dict[str, list[str]],
) -> pd.DataFrame:
    """Collapse predeclared ICD groups into burden domains inside the frozen family universe."""
    if grouped_events.empty:
        return pd.DataFrame(columns=["participant_id", "days_before_index", "group", "event_key"])

    grouped_events = grouped_events.copy()
    if "event_key" not in grouped_events.columns:
        grouped_events["event_key"] = grouped_events.index.map(lambda idx: f"derived:{idx}")

    source_to_modules: dict[str, list[str]] = {}
    for module_name, source_groups in burden_module_groups.items():
        for source_group in source_groups:
            cleaned_source = clean_token(source_group)
            if not cleaned_source:
                continue
            source_to_modules.setdefault(cleaned_source, []).append(module_name)

    records: list[tuple[int, float, str, str]] = []
    for row in grouped_events.itertuples(index=False):
        modules = source_to_modules.get(clean_token(row.group), [])
        for module_name in modules:
            records.append((int(row.participant_id), float(row.days_before_index), module_name, str(row.event_key)))

    if not records:
        return pd.DataFrame(columns=["participant_id", "days_before_index", "group", "event_key"])

    burden_events = pd.DataFrame(records, columns=["participant_id", "days_before_index", "group", "event_key"])
    # Collapse only repeated mappings from the same source episode into the same burden domain.
    # Keep distinct same-day encounters by deduplicating on event identity rather than date alone.
    return burden_events.drop_duplicates(subset=["event_key", "group"], ignore_index=True)


def build_raw_code_events(
    tables: dict[str, pd.DataFrame],
    columns_by_table: dict[str, list[str]],
    code_parser: Callable[[Any], set[str]],
) -> pd.DataFrame:
    records: list[tuple[int, float, str, str]] = []
    for table_name, df in tables.items():
        if df.empty:
            continue
        code_cols = [c for c in columns_by_table.get(table_name, []) if c in df.columns]
        if not code_cols:
            continue
        use_cols = ["participant_id", "days_before_index", *code_cols]
        tmp = df[use_cols].copy()
        tmp["participant_id"] = pd.to_numeric(tmp["participant_id"], errors="coerce").astype("Int64")
        tmp["days_before_index"] = pd.to_numeric(tmp["days_before_index"], errors="coerce")
        tmp = tmp.dropna(subset=["participant_id", "days_before_index"])
        for row in tmp.itertuples(index=False, name=None):
            participant_id = int(row[0])
            days_before_index = float(row[1])
            codes: set[str] = set()
            for raw_code_val in row[2:]:
                codes.update(code_parser(raw_code_val))
            for code in codes:
                records.append((participant_id, days_before_index, code, table_name))
    if not records:
        return pd.DataFrame(columns=["participant_id", "days_before_index", "normalized_code", "source_table"])
    out = pd.DataFrame(records, columns=["participant_id", "days_before_index", "normalized_code", "source_table"])
    return out.drop_duplicates(ignore_index=True)


def build_raw_icd_signal_discovery_artifacts(
    participants: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    years: float,
    icd_policy_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tag = year_tag(years)
    participants_base = participants[["participant_id"]].drop_duplicates().copy()
    raw_code_events = build_raw_code_events(
        tables=tables,
        columns_by_table=ICD_SIGNAL_DISCOVERY_COLUMNS_BY_TABLE,
        code_parser=extract_icd_codes,
    )
    total_participants = int(participants_base["participant_id"].nunique())
    group_levels = dict((icd_policy_meta or {}).get("group_levels", {}))
    include_in_default_model = dict((icd_policy_meta or {}).get("include_in_default_model", {}))
    include_in_lr_relevant_baseline = dict((icd_policy_meta or {}).get("include_in_lr_relevant_baseline", {}))
    dosage_manifest_provenance_fields = [
        "pairwise_view",
        "supporting_contrasts",
        "contrast_support_count",
        "dosage_candidate_tier",
    ]

    matrix = participants_base.copy()
    dictionary_columns = [
        "normalized_code",
        "feature_column",
        "source_tables",
        "source_table_count",
        "mapped_group_anchors",
        "mapped_group_anchor_count",
        "mapped_default_anchor_count",
        "mapped_lr_relevant_anchor_count",
    ]
    stage_a_columns = [
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
    group_anchor_columns = [
        "normalized_code",
        "feature_column",
        "group_anchor",
        "group_level",
        "include_in_default_model",
        "include_in_lr_relevant_baseline",
    ]

    if raw_code_events.empty:
        return {
            "raw_code_discovery_matrix": matrix,
            "raw_code_dictionary": pd.DataFrame(columns=dictionary_columns),
            "stage_a_preparation": pd.DataFrame(columns=stage_a_columns),
            "grouped_anchor_comparison": pd.DataFrame(columns=group_anchor_columns),
            "meta": {
                "authoritative_source": "diag_all",
                "source_columns_by_table": ICD_SIGNAL_DISCOVERY_COLUMNS_BY_TABLE,
                "raw_code_event_rows": 0,
                "raw_code_unique_count": 0,
                "raw_code_matrix_feature_columns": [],
                "stage_a_preparation_only": True,
                "grouped_anchor_comparison_rows": 0,
                "dosage_manifest_provenance_fields": dosage_manifest_provenance_fields,
            },
        }

    raw_code_events = raw_code_events.copy()
    raw_code_events["feature_column"] = raw_code_events["normalized_code"].map(lambda code: f"icd_raw_{code}_ever_{tag}")
    code_order = sorted(raw_code_events["normalized_code"].unique().tolist())
    feature_column_order = [f"icd_raw_{code}_ever_{tag}" for code in code_order]

    participant_code = raw_code_events[["participant_id", "feature_column"]].drop_duplicates()
    matrix_wide = (
        participant_code.assign(value=1)
        .pivot(index="participant_id", columns="feature_column", values="value")
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    matrix = participants_base.merge(matrix_wide, on="participant_id", how="left")
    for col in feature_column_order:
        if col not in matrix.columns:
            matrix[col] = 0
        matrix[col] = pd.to_numeric(matrix[col], errors="coerce").fillna(0).astype(int)
    ordered_matrix_cols = ["participant_id", *feature_column_order]
    matrix = matrix[ordered_matrix_cols]

    participant_support = raw_code_events.groupby("normalized_code")["participant_id"].nunique().to_dict()
    event_occurrence = raw_code_events.groupby("normalized_code").size().to_dict()
    source_tables_by_code = (
        raw_code_events.groupby("normalized_code")["source_table"]
        .apply(lambda s: sorted(set(s.astype(str).tolist())))
        .to_dict()
    )
    mapped_groups_by_code = {code: sorted(map_icd_groups(code)) for code in code_order}

    dictionary_records: list[dict[str, Any]] = []
    stage_a_records: list[dict[str, Any]] = []
    group_anchor_records: list[dict[str, Any]] = []

    for code in code_order:
        feature_column = f"icd_raw_{code}_ever_{tag}"
        source_tables = source_tables_by_code.get(code, [])
        mapped_groups = mapped_groups_by_code.get(code, [])
        support_n = int(participant_support.get(code, 0))
        event_n = int(event_occurrence.get(code, 0))
        prevalence = float(support_n / total_participants) if total_participants > 0 else 0.0
        majority_share = float(max(prevalence, 1.0 - prevalence)) if total_participants > 0 else 1.0
        dictionary_records.append(
            {
                "normalized_code": code,
                "feature_column": feature_column,
                "source_tables": "|".join(source_tables),
                "source_table_count": int(len(source_tables)),
                "mapped_group_anchors": "|".join(mapped_groups),
                "mapped_group_anchor_count": int(len(mapped_groups)),
                "mapped_default_anchor_count": int(
                    sum(int(include_in_default_model.get(group, 0)) for group in mapped_groups)
                ),
                "mapped_lr_relevant_anchor_count": int(
                    sum(int(include_in_lr_relevant_baseline.get(group, 0)) for group in mapped_groups)
                ),
            }
        )
        stage_a_records.append(
            {
                "normalized_code": code,
                "feature_column": feature_column,
                "participant_support_n": support_n,
                "event_occurrence_n": event_n,
                "participant_prevalence": prevalence,
                "binary_majority_share": majority_share,
                "nonzero_variance_flag": int(0 < prevalence < 1),
                "source_tables": "|".join(source_tables),
                "source_table_count": int(len(source_tables)),
                "stage_a_preparation_only": 1,
            }
        )
        for group in mapped_groups:
            group_anchor_records.append(
                {
                    "normalized_code": code,
                    "feature_column": feature_column,
                    "group_anchor": group,
                    "group_level": group_levels.get(group),
                    "include_in_default_model": int(include_in_default_model.get(group, 0)),
                    "include_in_lr_relevant_baseline": int(include_in_lr_relevant_baseline.get(group, 0)),
                }
            )

    return {
        "raw_code_discovery_matrix": matrix,
        "raw_code_dictionary": pd.DataFrame(dictionary_records, columns=dictionary_columns),
        "stage_a_preparation": pd.DataFrame(stage_a_records, columns=stage_a_columns),
        "grouped_anchor_comparison": pd.DataFrame(group_anchor_records, columns=group_anchor_columns),
        "meta": {
            "authoritative_source": "diag_all",
            "source_columns_by_table": ICD_SIGNAL_DISCOVERY_COLUMNS_BY_TABLE,
            "raw_code_event_rows": int(raw_code_events.shape[0]),
            "raw_code_unique_count": int(len(code_order)),
            "raw_code_matrix_feature_columns": feature_column_order,
            "stage_a_preparation_only": True,
            "grouped_anchor_comparison_rows": int(len(group_anchor_records)),
            "dosage_manifest_provenance_fields": dosage_manifest_provenance_fields,
        },
    }


def aggregate_group_features(
    participants: pd.DataFrame,
    grouped_events: pd.DataFrame,
    prefix: str,
    groups: list[str],
    years: float,
    threshold_enabled: bool,
    threshold_value: int,
    threshold_overrides: dict[str, int | None] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], list[str], list[str], list[str]]:
    tag = year_tag(years)
    out = participants.copy()
    count_cols: list[str] = []
    recency_cols: list[str] = []
    feature_cols: list[str] = []

    if grouped_events.empty:
        grouped_events = pd.DataFrame(columns=["participant_id", "days_before_index", "group"])
    else:
        grouped_events = grouped_events.copy()
        grouped_events["participant_id"] = pd.to_numeric(grouped_events["participant_id"], errors="coerce").astype("Int64")
        grouped_events["days_before_index"] = pd.to_numeric(grouped_events["days_before_index"], errors="coerce")
        grouped_events = grouped_events.dropna(subset=["participant_id", "days_before_index", "group"])
        grouped_events = grouped_events[grouped_events["group"].isin(set(groups))]

    group_positive = (
        grouped_events.groupby("group")["participant_id"].nunique().to_dict()
        if not grouped_events.empty
        else {}
    )
    resolved_overrides = threshold_overrides or {}
    active_groups: list[str] = []
    dropped_sparse_groups: list[str] = []
    group_thresholds_applied: dict[str, int] = {}

    for group in groups:
        positives = int(group_positive.get(group, 0))
        override_value = resolved_overrides.get(group)
        group_threshold_value = int(override_value) if override_value is not None else int(threshold_value)
        if group_threshold_value < 1:
            group_threshold_value = int(threshold_value)
        group_thresholds_applied[group] = int(group_threshold_value)

        if threshold_enabled and positives < group_threshold_value:
            dropped_sparse_groups.append(group)
            continue

        active_groups.append(group)
        ever_col = f"{prefix}_{group}_ever_{tag}"
        count_col = f"{prefix}_{group}_count_{tag}"
        last_col = f"{prefix}_{group}_days_since_last_{tag}"
        first_col = f"{prefix}_{group}_days_since_first_{tag}"

        if positives > 0:
            stats = (
                grouped_events[grouped_events["group"] == group]
                .groupby("participant_id", as_index=False)["days_before_index"]
                .agg(size="size", min="min", max="max")
                .rename(columns={"size": count_col, "min": last_col, "max": first_col})
            )
            stats[ever_col] = 1.0
            out = out.merge(stats[["participant_id", ever_col, count_col, last_col, first_col]], on="participant_id", how="left")
        else:
            out[ever_col] = 0.0
            out[count_col] = 0.0
            out[last_col] = np.nan
            out[first_col] = np.nan

        if ever_col in out.columns:
            out[ever_col] = pd.to_numeric(out[ever_col], errors="coerce").fillna(0.0)
        if count_col in out.columns:
            out[count_col] = pd.to_numeric(out[count_col], errors="coerce").fillna(0.0)

        count_cols.append(count_col)
        recency_cols.extend([last_col, first_col])
        feature_cols.extend([ever_col, count_col, last_col, first_col])

    meta = {
        "groups_considered": groups,
        "groups_active": active_groups,
        "groups_dropped_sparse": dropped_sparse_groups,
        "group_positive_participants": {k: int(v) for k, v in group_positive.items()},
        "threshold_enabled": bool(threshold_enabled),
        "threshold_value": int(threshold_value),
        "group_thresholds_applied": group_thresholds_applied,
    }
    return out, meta, count_cols, recency_cols, feature_cols


# %% Cell 3: HES temporal/statistical aggregation helpers
def prepare_hes_events(
    df: pd.DataFrame,
    event_date_col: str,
    cohort_index: pd.DataFrame,
    table_name: str,
) -> pd.DataFrame:
    """Normalize event dates and enforce pre-index alignment."""
    if df.empty:
        return pd.DataFrame(columns=["participant_id", "event_date", "sequencing_date", "days_before_index"])

    out = ensure_participant_id(df, table_name)
    out["event_date"] = parse_date_col(out, event_date_col)
    if "sequencing_date" not in out.columns:
        out = out.merge(cohort_index, on="participant_id", how="left")
    else:
        out["sequencing_date"] = pd.to_datetime(out["sequencing_date"], errors="coerce")

    out = out.dropna(subset=["event_date"]).copy()
    out["days_before_index"] = (out["sequencing_date"] - out["event_date"]).dt.total_seconds() / SECONDS_PER_DAY

    # Preserve rows when sequencing_date is missing (C1 review policy),
    # but enforce strict pre-index ordering when sequencing_date exists.
    keep = out["sequencing_date"].isna() | (out["days_before_index"] > 0)
    out = out.loc[keep].copy()
    return out


def filter_window(df: pd.DataFrame, years: float) -> pd.DataFrame:
    if df.empty:
        return df
    max_days = years * DAYS_PER_YEAR
    mask = df["days_before_index"].between(0, max_days, inclusive="both")
    return df.loc[mask].copy()


def aggregate_temporal(df: pd.DataFrame, prefix: str, years: float) -> pd.DataFrame:
    tag = year_tag(years)
    out_cols = {
        "size": f"{prefix}_event_count_{tag}",
        "min": f"{prefix}_days_since_last_event_{tag}",
        "max": f"{prefix}_days_since_first_event_{tag}",
    }
    if df.empty:
        return pd.DataFrame(columns=["participant_id", *out_cols.values()])

    agg = df.groupby("participant_id")["days_before_index"].agg(size="size", min="min", max="max").reset_index()
    agg = agg.rename(columns=out_cols)
    return agg


def aggregate_numeric(
    df: pd.DataFrame,
    value_col: str,
    prefix: str,
    years: float,
) -> pd.DataFrame:
    tag = year_tag(years)
    out_names = {
        "sum": f"{prefix}_{value_col}_sum_{tag}",
        "mean": f"{prefix}_{value_col}_mean_{tag}",
        "max": f"{prefix}_{value_col}_max_{tag}",
    }
    if df.empty or value_col not in df.columns:
        return pd.DataFrame(columns=["participant_id", *out_names.values()])

    tmp = df[["participant_id", value_col]].copy()
    tmp[value_col] = pd.to_numeric(tmp[value_col], errors="coerce")
    tmp = tmp.dropna(subset=[value_col])
    if tmp.empty:
        return pd.DataFrame(columns=["participant_id", *out_names.values()])

    agg = tmp.groupby("participant_id")[value_col].agg(sum="sum", mean="mean", max="max").reset_index()
    agg = agg.rename(columns=out_names)
    return agg


def aggregate_boolean_count(
    df: pd.DataFrame,
    bool_series: pd.Series,
    feature_name: str,
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["participant_id", feature_name])
    tmp = pd.DataFrame({"participant_id": df["participant_id"], "__flag__": bool_series.astype(int)})
    return tmp.groupby("participant_id", as_index=False)["__flag__"].sum().rename(columns={"__flag__": feature_name})


def aggregate_code_event_count(
    tables: dict[str, pd.DataFrame],
    columns_by_table: dict[str, list[str]],
    code_parser: Callable[[Any], set[str]],
    feature_name: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for table_name, df in tables.items():
        if df.empty:
            continue
        code_cols = [c for c in columns_by_table.get(table_name, []) if c in df.columns]
        if not code_cols:
            continue
        tmp = df[["participant_id", *code_cols]].copy()
        tmp["participant_id"] = pd.to_numeric(tmp["participant_id"], errors="coerce").astype("Int64")
        tmp = tmp.dropna(subset=["participant_id"])
        if tmp.empty:
            continue
        has_code_event = pd.Series(False, index=tmp.index)
        for col in code_cols:
            has_code_event = has_code_event | tmp[col].map(lambda value: len(code_parser(value)) > 0)
        coded = tmp.loc[has_code_event, ["participant_id"]].copy()
        if not coded.empty:
            frames.append(coded)
    if not frames:
        return pd.DataFrame(columns=["participant_id", feature_name])
    stacked = pd.concat(frames, ignore_index=True)
    return stacked.groupby("participant_id", as_index=False).size().rename(columns={"size": feature_name})


def aggregate_mode_feature(df: pd.DataFrame, col: str, feature_name: str) -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return pd.DataFrame(columns=["participant_id", feature_name])
    tmp = df[["participant_id", col]].copy()
    tmp[col] = tmp[col].map(clean_token)
    tmp = tmp[tmp[col] != ""]
    if tmp.empty:
        return pd.DataFrame(columns=["participant_id", feature_name])
    mode_df = tmp.groupby("participant_id")[col].apply(mode_nonempty).reset_index(name=feature_name)
    return mode_df


def stack_column(tables: dict[str, pd.DataFrame], col: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, df in tables.items():
        if df.empty or col not in df.columns:
            continue
        part = df[["participant_id", col]].copy()
        part = part.rename(columns={col: "value"})
        part["value"] = part["value"].map(clean_token)
        part = part[part["value"] != ""]
        if not part.empty:
            frames.append(part)
    if not frames:
        return pd.DataFrame(columns=["participant_id", "value"])
    return pd.concat(frames, ignore_index=True)


def add_feature_block(base: pd.DataFrame, block: pd.DataFrame, key: str = "participant_id") -> pd.DataFrame:
    if block.empty:
        return base
    return base.merge(block, on=key, how="left")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value


# %% Cell 4: Raw feature-store builder
def build_feature_store(
    cohort: pd.DataFrame,
    apc: pd.DataFrame,
    op: pd.DataFrame,
    ae: pd.DataFrame,
    core_window_years: float,
    recent_window_years: float,
    include_optional_icd_groups: bool,
    include_optional_opcs_groups: bool,
    diagnosis_occurrence_threshold_enabled: bool,
    diagnosis_occurrence_threshold: int,
    procedure_occurrence_threshold_enabled: bool,
    procedure_occurrence_threshold: int,
    icd_core_groups: list[str] | None = None,
    icd_optional_groups: list[str] | None = None,
    icd_min_positive_overrides: dict[str, int | None] | None = None,
    icd_policy_meta: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    cohort = ensure_participant_id(cohort, "cohort")
    if "sequencing_date" not in cohort.columns:
        raise KeyError("cohort missing required column: sequencing_date")
    if "tier12_positive" not in cohort.columns and "scn5a_plp_flag" in cohort.columns:
        cohort["tier12_positive"] = (
            pd.to_numeric(cohort["scn5a_plp_flag"], errors="coerce").fillna(0).astype(int)
        )

    cohort["sequencing_date"] = pd.to_datetime(cohort["sequencing_date"], errors="coerce")
    cohort["sequencing_date_missing"] = cohort["sequencing_date"].isna().astype(int)
    if "sequencing_date_policy" not in cohort.columns:
        cohort["sequencing_date_policy"] = "preserve_missing_for_now_filter_downstream"
    cohort["sequencing_index_available"] = (1 - cohort["sequencing_date_missing"]).astype(int)

    cohort_index = cohort[["participant_id", "sequencing_date"]].drop_duplicates("participant_id")
    base = cohort[["participant_id"]].drop_duplicates().copy()

    apc_norm = prepare_hes_events(apc, "admidate", cohort_index, "hes_apc")
    op_norm = prepare_hes_events(op, "apptdate", cohort_index, "hes_op")
    ae_norm = prepare_hes_events(ae, "arrivaldate", cohort_index, "hes_ae")

    apc_w_core = filter_window(apc_norm, core_window_years)
    op_w_core = filter_window(op_norm, core_window_years)
    ae_w_core = filter_window(ae_norm, core_window_years)
    apc_w_recent = filter_window(apc_norm, recent_window_years)
    op_w_recent = filter_window(op_norm, recent_window_years)
    ae_w_recent = filter_window(ae_norm, recent_window_years)

    feature_cols: list[str] = []
    count_cols: list[str] = []
    duration_cols: list[str] = []
    ratio_cols: list[str] = []
    recency_cols: list[str] = []
    categorical_cols: list[str] = []

    for prefix, core_df, recent_df in (
        ("apc", apc_w_core, apc_w_recent),
        ("op", op_w_core, op_w_recent),
        ("ae", ae_w_core, ae_w_recent),
    ):
        agg_core = aggregate_temporal(core_df, prefix, core_window_years)
        agg_recent = aggregate_temporal(recent_df, prefix, recent_window_years)
        base = add_feature_block(base, agg_core)
        base = add_feature_block(base, agg_recent)
        core_tag = year_tag(core_window_years)
        recent_tag = year_tag(recent_window_years)
        count_cols.extend([f"{prefix}_event_count_{core_tag}", f"{prefix}_event_count_{recent_tag}"])
        recency_cols.extend(
            [
                f"{prefix}_days_since_last_event_{core_tag}",
                f"{prefix}_days_since_first_event_{core_tag}",
                f"{prefix}_days_since_last_event_{recent_tag}",
                f"{prefix}_days_since_first_event_{recent_tag}",
            ]
        )
        feature_cols.extend(count_cols[-2:] + recency_cols[-4:])

    core_tag = year_tag(core_window_years)
    recent_tag = year_tag(recent_window_years)

    # Duration/intensity blocks
    for prefix, core_df, recent_df, col_name in (
        ("apc", apc_w_core, apc_w_recent, "epidur"),
        ("ae", ae_w_core, ae_w_recent, "concldur"),
    ):
        block_core = aggregate_numeric(core_df, col_name, prefix, core_window_years)
        block_recent = aggregate_numeric(recent_df, col_name, prefix, recent_window_years)
        base = add_feature_block(base, block_core)
        base = add_feature_block(base, block_recent)
        for metric in ("sum", "mean", "max"):
            duration_cols.append(f"{prefix}_{col_name}_{metric}_{core_tag}")
            duration_cols.append(f"{prefix}_{col_name}_{metric}_{recent_tag}")
            feature_cols.append(f"{prefix}_{col_name}_{metric}_{core_tag}")
            feature_cols.append(f"{prefix}_{col_name}_{metric}_{recent_tag}")

    # Grouped ICD features (core + optional sensitivity blocks), with editable policy support.
    resolved_icd_core_groups = icd_core_groups if icd_core_groups is not None else ICD_CORE_GROUPS
    resolved_icd_optional_groups = icd_optional_groups if icd_optional_groups is not None else ICD_OPTIONAL_GROUPS
    icd_groups = resolved_icd_core_groups + (resolved_icd_optional_groups if include_optional_icd_groups else [])
    icd_events = build_group_episode_events(
        tables={"apc": apc_w_core, "op": op_w_core, "ae": ae_w_core},
        columns_by_table=ICD_GROUP_COLUMNS_BY_TABLE,
        code_parser=extract_icd_codes,
        code_mapper=map_icd_groups,
    )
    base, icd_meta, icd_count_cols, icd_recency_cols, icd_feature_cols = aggregate_group_features(
        participants=base,
        grouped_events=icd_events,
        prefix="icd_grp",
        groups=icd_groups,
        years=core_window_years,
        threshold_enabled=diagnosis_occurrence_threshold_enabled,
        threshold_value=diagnosis_occurrence_threshold,
        threshold_overrides=icd_min_positive_overrides,
    )
    count_cols.extend(icd_count_cols)
    recency_cols.extend(icd_recency_cols)
    feature_cols.extend(icd_feature_cols)

    icd_burden_events = build_burden_group_episode_events(
        grouped_events=icd_events,
        burden_module_groups=ICD_BURDEN_MODULE_GROUPS,
    )
    base, icd_burden_meta, icd_burden_count_cols, icd_burden_recency_cols, icd_burden_feature_cols = (
        aggregate_group_features(
            participants=base,
            grouped_events=icd_burden_events,
            prefix="icd_burden",
            groups=list(ICD_BURDEN_MODULE_GROUPS.keys()),
            years=core_window_years,
            threshold_enabled=False,
            threshold_value=1,
        )
    )
    count_cols.extend(icd_burden_count_cols)
    recency_cols.extend(icd_burden_recency_cols)
    feature_cols.extend(icd_burden_feature_cols)

    icd_code_event_count_col = f"icd_code_event_count_{core_tag}"
    icd_code_event_count = aggregate_code_event_count(
        tables={"apc": apc_w_core, "op": op_w_core, "ae": ae_w_core},
        columns_by_table=ICD_GROUP_COLUMNS_BY_TABLE,
        code_parser=extract_icd_codes,
        feature_name=icd_code_event_count_col,
    )
    base = add_feature_block(base, icd_code_event_count)
    if icd_code_event_count_col not in base.columns:
        base[icd_code_event_count_col] = 0.0
    base[icd_code_event_count_col] = pd.to_numeric(base[icd_code_event_count_col], errors="coerce").fillna(0.0)
    count_cols.append(icd_code_event_count_col)
    feature_cols.append(icd_code_event_count_col)

    # Grouped OPCS features (core + optional sensitivity blocks).
    opcs_groups = OPCS_CORE_GROUPS + (OPCS_OPTIONAL_GROUPS if include_optional_opcs_groups else [])
    opcs_events = build_group_episode_events(
        tables={"apc": apc_w_core, "op": op_w_core},
        columns_by_table=OPCS_GROUP_COLUMNS_BY_TABLE,
        code_parser=extract_opcs_codes,
        code_mapper=map_opcs_group,
    )
    base, opcs_meta, opcs_count_cols, opcs_recency_cols, opcs_feature_cols = aggregate_group_features(
        participants=base,
        grouped_events=opcs_events,
        prefix="opcs_grp",
        groups=opcs_groups,
        years=core_window_years,
        threshold_enabled=procedure_occurrence_threshold_enabled,
        threshold_value=procedure_occurrence_threshold,
    )
    count_cols.extend(opcs_count_cols)
    recency_cols.extend(opcs_recency_cols)
    feature_cols.extend(opcs_feature_cols)

    signal_discovery_artifacts = build_raw_icd_signal_discovery_artifacts(
        participants=base,
        tables={"apc": apc_w_core, "op": op_w_core, "ae": ae_w_core},
        years=core_window_years,
        icd_policy_meta=icd_policy_meta,
    )

    # Fill count columns with 0 where missing (pre-mask for missing index policy).
    for col in count_cols:
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0).astype(float)

    # Combined event-level table for global temporal features.
    event_parts = [apc_norm[["participant_id", "event_date", "days_before_index"]],
                   op_norm[["participant_id", "event_date", "days_before_index"]],
                   ae_norm[["participant_id", "event_date", "days_before_index"]]]
    all_events = pd.concat(event_parts, ignore_index=True) if event_parts else pd.DataFrame()
    all_events = all_events.dropna(subset=["days_before_index"]) if not all_events.empty else all_events
    all_events = all_events[all_events["days_before_index"] >= 0] if not all_events.empty else all_events

    if all_events.empty:
        global_temporal = pd.DataFrame(
            columns=[
                "participant_id",
                "has_any_event_preindex",
                "days_since_last_event_preindex",
                "days_since_first_event_preindex",
                "observation_years_preindex",
            ]
        )
    else:
        global_temporal = all_events.groupby("participant_id")["days_before_index"].agg(min="min", max="max").reset_index()
        global_temporal = global_temporal.rename(
            columns={
                "min": "days_since_last_event_preindex",
                "max": "days_since_first_event_preindex",
            }
        )
        global_temporal["has_any_event_preindex"] = 1
        global_temporal["observation_years_preindex"] = (
            global_temporal["days_since_first_event_preindex"] / DAYS_PER_YEAR
        )
    base = add_feature_block(base, global_temporal)
    feature_cols.extend(
        [
            "has_any_event_preindex",
            "days_since_last_event_preindex",
            "days_since_first_event_preindex",
            "observation_years_preindex",
        ]
    )

    # Total utilization counts and rates.
    apc_core_col = f"apc_event_count_{core_tag}"
    op_core_col = f"op_event_count_{core_tag}"
    ae_core_col = f"ae_event_count_{core_tag}"
    apc_recent_col = f"apc_event_count_{recent_tag}"
    op_recent_col = f"op_event_count_{recent_tag}"
    ae_recent_col = f"ae_event_count_{recent_tag}"

    for required_col in [apc_core_col, op_core_col, ae_core_col, apc_recent_col, op_recent_col, ae_recent_col]:
        if required_col not in base.columns:
            base[required_col] = 0.0

    base[f"total_event_count_{core_tag}"] = base[apc_core_col] + base[op_core_col] + base[ae_core_col]
    base[f"total_event_count_{recent_tag}"] = base[apc_recent_col] + base[op_recent_col] + base[ae_recent_col]
    base[f"total_event_count_prior_{recent_tag}_to_{core_tag}"] = (
        base[f"total_event_count_{core_tag}"] - base[f"total_event_count_{recent_tag}"]
    ).clip(lower=0)
    base[f"recent_to_prior_event_ratio_{recent_tag}_vs_{core_tag}"] = (
        base[f"total_event_count_{recent_tag}"] / (base[f"total_event_count_prior_{recent_tag}_to_{core_tag}"] + 1.0)
    )

    for setting, col in (("apc", apc_core_col), ("op", op_core_col), ("ae", ae_core_col)):
        ratio_col = f"{setting}_share_{core_tag}"
        base[ratio_col] = np.where(
            base[f"total_event_count_{core_tag}"] > 0,
            base[col] / base[f"total_event_count_{core_tag}"],
            0.0,
        )
        ratio_cols.append(ratio_col)
        feature_cols.append(ratio_col)

    base["exposure_years_core"] = np.where(
        base["observation_years_preindex"].notna(),
        np.minimum(base["observation_years_preindex"], core_window_years),
        np.nan,
    )
    short_history_col = f"short_history_indicator_{core_tag}"
    base[short_history_col] = np.where(
        base["exposure_years_core"].notna(),
        (base["exposure_years_core"] < 2.0).astype(float),
        np.nan,
    )
    base[f"total_event_rate_per_year_{core_tag}"] = np.where(
        base["exposure_years_core"] > 0,
        base[f"total_event_count_{core_tag}"] / base["exposure_years_core"],
        np.nan,
    )
    for setting, col in (("apc", apc_core_col), ("op", op_core_col), ("ae", ae_core_col)):
        rate_col = f"{setting}_event_rate_per_year_{core_tag}"
        base[rate_col] = np.where(base["exposure_years_core"] > 0, base[col] / base["exposure_years_core"], np.nan)
        feature_cols.append(rate_col)

    grouped_density_cols: list[str] = []
    burden_density_cols: list[str] = []
    for col in [*icd_count_cols, *icd_burden_count_cols, *opcs_count_cols]:
        if col not in base.columns:
            continue
        if f"_count_{core_tag}" not in col:
            continue
        rate_col = col.replace(f"_count_{core_tag}", f"_rate_per_year_{core_tag}")
        base[rate_col] = np.where(base["exposure_years_core"] > 0, base[col] / base["exposure_years_core"], np.nan)
        grouped_density_cols.append(rate_col)
        if col in set(icd_burden_count_cols):
            burden_density_cols.append(rate_col)
        feature_cols.append(rate_col)

    feature_cols.extend(
        [
            f"total_event_count_{core_tag}",
            f"total_event_count_{recent_tag}",
            f"total_event_count_prior_{recent_tag}_to_{core_tag}",
            f"recent_to_prior_event_ratio_{recent_tag}_vs_{core_tag}",
            "exposure_years_core",
            short_history_col,
            f"total_event_rate_per_year_{core_tag}",
        ]
    )
    count_cols.extend(
        [
            f"total_event_count_{core_tag}",
            f"total_event_count_{recent_tag}",
            f"total_event_count_prior_{recent_tag}_to_{core_tag}",
        ]
    )
    ratio_cols.append(f"recent_to_prior_event_ratio_{recent_tag}_vs_{core_tag}")

    observability_covariate_cols = [
        col
        for col in [
            "exposure_years_core",
            f"total_event_count_{core_tag}",
            icd_code_event_count_col,
            short_history_col,
        ]
        if col in base.columns
    ]

    # APC care-pathway signals.
    if not apc_w_core.empty and "admimeth" in apc_w_core.columns:
        admimeth = apc_w_core["admimeth"].astype(str).str.strip()
        emg = admimeth.str.startswith("2", na=False)
        elec = admimeth.str.startswith("1", na=False)
        emg_count = aggregate_boolean_count(apc_w_core, emg, f"apc_emergency_count_{core_tag}")
        elec_count = aggregate_boolean_count(apc_w_core, elec, f"apc_elective_count_{core_tag}")
        base = add_feature_block(base, emg_count)
        base = add_feature_block(base, elec_count)
        for col in [f"apc_emergency_count_{core_tag}", f"apc_elective_count_{core_tag}"]:
            if col not in base.columns:
                base[col] = 0.0
            base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0.0)
            count_cols.append(col)
            feature_cols.append(col)
        base[f"apc_emergency_ratio_{core_tag}"] = np.where(
            base[apc_core_col] > 0,
            base[f"apc_emergency_count_{core_tag}"] / base[apc_core_col],
            0.0,
        )
        ratio_cols.append(f"apc_emergency_ratio_{core_tag}")
        feature_cols.append(f"apc_emergency_ratio_{core_tag}")

    # OP pathway signals.
    if not op_w_core.empty and "firstatt" in op_w_core.columns:
        firstatt = op_w_core["firstatt"].astype(str).str.strip()
        is_first = firstatt.str.startswith("1", na=False)
        first_count = aggregate_boolean_count(op_w_core, is_first, f"op_first_attendance_count_{core_tag}")
        base = add_feature_block(base, first_count)
        if f"op_first_attendance_count_{core_tag}" not in base.columns:
            base[f"op_first_attendance_count_{core_tag}"] = 0.0
        base[f"op_first_attendance_count_{core_tag}"] = pd.to_numeric(
            base[f"op_first_attendance_count_{core_tag}"], errors="coerce"
        ).fillna(0.0)
        base[f"op_first_attendance_ratio_{core_tag}"] = np.where(
            base[op_core_col] > 0,
            base[f"op_first_attendance_count_{core_tag}"] / base[op_core_col],
            0.0,
        )
        count_cols.append(f"op_first_attendance_count_{core_tag}")
        ratio_cols.append(f"op_first_attendance_ratio_{core_tag}")
        feature_cols.extend([f"op_first_attendance_count_{core_tag}", f"op_first_attendance_ratio_{core_tag}"])

    # AE pathway signals.
    if not ae_w_core.empty and "aeattend_exc_planned" in ae_w_core.columns:
        raw = ae_w_core["aeattend_exc_planned"].astype(str).str.strip().str.upper()
        is_unplanned = raw.isin({"1", "Y", "YES", "TRUE", "T", "UNPLANNED"})
        unplanned_count = aggregate_boolean_count(ae_w_core, is_unplanned, f"ae_unplanned_count_{core_tag}")
        base = add_feature_block(base, unplanned_count)
        if f"ae_unplanned_count_{core_tag}" not in base.columns:
            base[f"ae_unplanned_count_{core_tag}"] = 0.0
        base[f"ae_unplanned_count_{core_tag}"] = pd.to_numeric(
            base[f"ae_unplanned_count_{core_tag}"], errors="coerce"
        ).fillna(0.0)
        base[f"ae_unplanned_ratio_{core_tag}"] = np.where(
            base[ae_core_col] > 0,
            base[f"ae_unplanned_count_{core_tag}"] / base[ae_core_col],
            0.0,
        )
        count_cols.append(f"ae_unplanned_count_{core_tag}")
        ratio_cols.append(f"ae_unplanned_ratio_{core_tag}")
        feature_cols.extend([f"ae_unplanned_count_{core_tag}", f"ae_unplanned_ratio_{core_tag}"])

    # Demographic/context modes from combined 5y events.
    combined_5y_tables = {"apc": apc_w_core, "op": op_w_core, "ae": ae_w_core}

    for raw_col, feature_name in (
        ("ethnos", f"ethnos_mode_{core_tag}"),
        ("sex", f"sex_mode_{core_tag}"),
    ):
        stacked = stack_column(combined_5y_tables, raw_col)
        if not stacked.empty:
            mode_df = stacked.groupby("participant_id", as_index=False)["value"].apply(lambda s: mode_nonempty(s, "Unknown"))
            mode_df = mode_df.rename(columns={"value": feature_name})
            base = add_feature_block(base, mode_df)
            categorical_cols.append(feature_name)
            feature_cols.append(feature_name)

    # IMD as both numeric median and categorical mode.
    stacked_imd = stack_column(combined_5y_tables, "imd04")
    if not stacked_imd.empty:
        imd_numeric = stacked_imd.copy()
        imd_numeric["imd_num"] = pd.to_numeric(imd_numeric["value"], errors="coerce")
        imd_med = imd_numeric.groupby("participant_id", as_index=False)["imd_num"].median().rename(
            columns={"imd_num": f"imd04_median_{core_tag}"}
        )
        base = add_feature_block(base, imd_med)
        feature_cols.append(f"imd04_median_{core_tag}")

        imd_mode = stacked_imd.groupby("participant_id", as_index=False)["value"].apply(lambda s: mode_nonempty(s, "Unknown"))
        imd_mode = imd_mode.rename(columns={"value": f"imd04_mode_{core_tag}"})
        base = add_feature_block(base, imd_mode)
        categorical_cols.append(f"imd04_mode_{core_tag}")
        feature_cols.append(f"imd04_mode_{core_tag}")

    # Distinct provider/specialty activity.
    stacked_provider = stack_column(combined_5y_tables, "procode")
    if not stacked_provider.empty:
        prov = (
            stacked_provider.groupby("participant_id", as_index=False)["value"]
            .nunique()
            .rename(columns={"value": f"unique_provider_count_{core_tag}"})
        )
        base = add_feature_block(base, prov)
        count_cols.append(f"unique_provider_count_{core_tag}")
        feature_cols.append(f"unique_provider_count_{core_tag}")

    spec_parts: list[pd.DataFrame] = []
    for table_df in (apc_w_core, op_w_core):
        for col in ("mainspef", "tretspef"):
            if col in table_df.columns:
                tmp = table_df[["participant_id", col]].rename(columns={col: "value"})
                tmp["value"] = tmp["value"].map(clean_token)
                tmp = tmp[tmp["value"] != ""]
                if not tmp.empty:
                    spec_parts.append(tmp)
    if spec_parts:
        stacked_spec = pd.concat(spec_parts, ignore_index=True)
        spec = (
            stacked_spec.groupby("participant_id", as_index=False)["value"]
            .nunique()
            .rename(columns={"value": f"unique_specialty_count_{core_tag}"})
        )
        base = add_feature_block(base, spec)
        count_cols.append(f"unique_specialty_count_{core_tag}")
        feature_cols.append(f"unique_specialty_count_{core_tag}")

    # Merge selected cohort context columns into raw store.
    context_cols = [
        "participant_id",
        "sequencing_date",
        "sequencing_date_missing",
        "sequencing_date_policy",
        "sequencing_index_available",
        "promoter_carrier",
        "promoter_zygosity",
        "promoter_dosage",
        "promoter_zygosity_inferred",
        "has_rs41310239",
        "label_primary",
        "label_detail",
        "label",
        "target_name",
        "has_scn5a_any",
        "scn5a_plp_flag",
        "tier12_positive",
        "scn5a_tier3_flag",
        "scn5a_tier3_only_flag",
        "is_proband_scn5a",
        "n_scn5a_variants_total",
        "n_scn5a_tier1_2",
        "n_scn5a_tier3",
        "mixed_tier_flag",
        "best_scn5a_tier_num",
        "scn5a_best_tier",
        "scn5a_consequence_types",
        "scn5a_has_consequence",
        "any_het_scn5a",
        "any_hom_or_biallelic_scn5a",
        "any_AD_compatible",
        "any_AR_compatible",
        "any_de_novo_like",
        "monogenic_scn5a",
        "monogenic_high",
        "modifier_only",
        "scn5a_negative",
        "burden_class",
        "architecture_label",
        "promoter_only",
        "no_scn5a_signal",
        "has_scn5a_vcf",
        "scn5a_evidence_source",
        "scn5a_conflict",
        "tiering_label_primary",
        "tiering_label_detail",
    ]
    context_cols_present = [c for c in context_cols if c in cohort.columns]
    raw_store = base.merge(
        cohort[context_cols_present].drop_duplicates("participant_id"),
        on="participant_id",
        how="left",
    )

    # Index-dependent features: set to NaN when sequencing date is missing.
    index_dependent_cols = sorted(set(feature_cols + recency_cols + ratio_cols + duration_cols + count_cols))
    missing_index_mask = raw_store["sequencing_date_missing"] == 1
    for col in index_dependent_cols:
        if col in raw_store.columns:
            raw_store.loc[missing_index_mask, col] = np.nan

    diagnostics = {
        "cohort_rows": int(cohort.shape[0]),
        "cohort_unique_participants": int(cohort["participant_id"].nunique()),
        "cohort_missing_sequencing_date_rows": int(cohort["sequencing_date_missing"].sum()),
        "hes_apc_rows_norm": int(apc_norm.shape[0]),
        "hes_op_rows_norm": int(op_norm.shape[0]),
        "hes_ae_rows_norm": int(ae_norm.shape[0]),
        "hes_apc_rows_core_window": int(apc_w_core.shape[0]),
        "hes_op_rows_core_window": int(op_w_core.shape[0]),
        "hes_ae_rows_core_window": int(ae_w_core.shape[0]),
        "icd_grouped_episode_rows_core_window": int(icd_events.shape[0]),
        "opcs_grouped_episode_rows_core_window": int(opcs_events.shape[0]),
        "raw_icd_signal_discovery_event_rows_core_window": int(signal_discovery_artifacts["meta"]["raw_code_event_rows"]),
        "raw_icd_signal_discovery_unique_code_count": int(signal_discovery_artifacts["meta"]["raw_code_unique_count"]),
        "icd_groups_active_count": int(len(icd_meta["groups_active"])),
        "opcs_groups_active_count": int(len(opcs_meta["groups_active"])),
        "raw_feature_rows": int(raw_store.shape[0]),
        "raw_feature_cols": int(raw_store.shape[1]),
        "engineered_feature_count": len(set(feature_cols)),
    }

    feature_meta = {
        "feature_cols": sorted(set(feature_cols)),
        "count_cols": sorted(set([c for c in count_cols if c in raw_store.columns])),
        "duration_cols": sorted(set([c for c in duration_cols if c in raw_store.columns])),
        "ratio_cols": sorted(set([c for c in ratio_cols if c in raw_store.columns])),
        "recency_cols": sorted(set([c for c in recency_cols if c in raw_store.columns])),
        "density_cols": sorted(set([c for c in grouped_density_cols if c in raw_store.columns])),
        "icd_group_feature_cols": sorted(set([c for c in icd_feature_cols if c in raw_store.columns])),
        "burden_feature_cols": sorted(
            set(
                [
                    *[c for c in icd_burden_feature_cols if c in raw_store.columns],
                    *[c for c in burden_density_cols if c in raw_store.columns],
                ]
            )
        ),
        "opcs_group_feature_cols": sorted(set([c for c in opcs_feature_cols if c in raw_store.columns])),
        "categorical_context_cols": sorted(set([c for c in categorical_cols if c in raw_store.columns])),
        "observability_covariate_cols": observability_covariate_cols,
        "index_dependent_cols": [c for c in index_dependent_cols if c in raw_store.columns],
        "grouping_meta": {
            "icd": {
                **icd_meta,
                "core_groups_configured": resolved_icd_core_groups,
                "optional_groups_configured": resolved_icd_optional_groups,
                "burden_modules_configured": ICD_BURDEN_MODULE_GROUPS,
                "burden_meta": icd_burden_meta,
                "policy_meta": icd_policy_meta or {},
            },
            "opcs": opcs_meta,
        },
    }

    return raw_store, {"diagnostics": diagnostics, "feature_meta": feature_meta, "signal_discovery_meta": signal_discovery_artifacts["meta"]}, signal_discovery_artifacts


# %% Cell 5: Governed preprocessing-spec builder
def summarize_preprocessing_spec(preprocessing_spec: dict[str, Any]) -> dict[str, Any]:
    class_assignments = preprocessing_spec.get("feature_class_assignments", {})
    return {
        "predictor_count": int(len(preprocessing_spec.get("predictor_columns", []))),
        "predictor_columns": preprocessing_spec.get("predictor_columns", []),
        "target_columns": preprocessing_spec.get("target_columns", []),
        "default_target_column": None,
        "target_selection_policy": "explicit_target_selection_required_in_train_stage",
        "target_source_columns_from_policy": preprocessing_spec.get("target_source_columns_from_policy", []),
        "numeric_predictor_columns": preprocessing_spec.get("numeric_predictor_columns", []),
        "categorical_predictor_columns": preprocessing_spec.get("categorical_predictor_columns", []),
        "feature_class_assignments": class_assignments,
        "feature_class_counts": {k: int(len(v)) for k, v in class_assignments.items()},
        "clinically_central_columns": preprocessing_spec.get("clinically_central_columns", []),
        "log_eligible_columns": preprocessing_spec.get("log_eligible_columns", []),
        "winsor_eligible_columns": preprocessing_spec.get("winsor_eligible_columns", []),
        "scaling_eligible_columns": preprocessing_spec.get("scaling_eligible_columns", []),
        "missingness_policy": preprocessing_spec.get("missingness_policy", {}),
        "categorical_policy": preprocessing_spec.get("categorical_policy", {}),
        "recency_policy": preprocessing_spec.get("recency_policy", {}),
        "log_transform_policy": preprocessing_spec.get("log_transform_policy", {}),
        "winsor_policy": preprocessing_spec.get("winsor_policy", {}),
        "scaling_policy": preprocessing_spec.get("scaling_policy", {}),
        "evaluation_defaults": preprocessing_spec.get("evaluation_defaults", {}),
        "model_defaults": preprocessing_spec.get("model_defaults", {}),
        "default_recency_sentinel_days": preprocessing_spec.get("default_recency_sentinel_days"),
        "default_excluded_secondary_genetics": preprocessing_spec.get("default_excluded_secondary_genetics", []),
        "default_excluded_legacy_vcf_fields": preprocessing_spec.get("default_excluded_legacy_vcf_fields", []),
        "include_legacy_vcf_fields": preprocessing_spec.get("include_legacy_vcf_fields"),
        "include_sequencing_missing_flag": preprocessing_spec.get("include_sequencing_missing_flag"),
        "preprocessing_policy_id": preprocessing_spec.get("policy_id"),
        "preprocessing_policy_version": preprocessing_spec.get("policy_version"),
        "preprocessing_policy_path": preprocessing_spec.get("policy_path"),
    }


# %% Cell 6: CLI argument parsing
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage 5B participant-level HES feature matrices")
    parser.add_argument("--cohort", required=True, help="Path to cohort_basic_with_haplotype CSV")
    parser.add_argument("--hes-apc", required=True, help="Path to hes_apc_censored CSV")
    parser.add_argument("--hes-op", required=True, help="Path to hes_op_censored CSV")
    parser.add_argument("--hes-ae", required=True, help="Path to hes_ae_censored CSV")
    parser.add_argument("--out-dir", required=False, default=".", help="Output directory")
    parser.add_argument("--core-window-years", type=float, default=5.0, help="Core lookback window in years")
    parser.add_argument("--recent-window-years", type=float, default=1.0, help="Recent lookback window in years")
    parser.add_argument(
        "--winsor-upper-q",
        type=float,
        default=0.995,
        help="Deprecated build-time argument retained for compatibility; winsor fitting now happens in train_models.",
    )
    parser.add_argument(
        "--include-legacy-vcf-fields",
        action="store_true",
        help="Include legacy VCF-derived fields in predictor candidates (default: excluded)",
    )
    parser.add_argument(
        "--include-sequencing-missing-flag",
        action="store_true",
        help="Include sequencing_date_missing in model matrix (default: excluded while C1 remains under review)",
    )
    parser.add_argument(
        "--include-optional-icd-groups",
        action="store_true",
        help="Include optional ICD grouped feature modules (default: core groups only)",
    )
    parser.add_argument(
        "--include-optional-opcs-groups",
        action="store_true",
        help="Include optional OPCS grouped feature modules in feature generation (default: core groups only)",
    )
    parser.add_argument(
        "--include-opcs-in-model-matrix",
        action="store_true",
        help="Deprecated build-time argument retained for compatibility; model-family pruning now happens in train_models.",
    )
    parser.add_argument(
        "--include-missingness-indicators",
        action="store_true",
        help="Deprecated build-time argument retained for compatibility; missingness indicators are now training-fitted.",
    )
    parser.add_argument(
        "--icd-group-policy-csv",
        default=str(DEFAULT_ICD_POLICY_CSV),
        help="CSV policy file defining ICD group levels (core/optional) and baseline relevance flags",
    )
    parser.add_argument(
        "--recency-policy-csv",
        default=str(DEFAULT_RECENCY_POLICY_CSV),
        help="CSV policy file defining ICD grouped recency feature inclusion/exclusion",
    )
    parser.add_argument(
        "--recency-policy-id",
        default="minimal",
        help="Recency policy id from recency policy CSV (default: minimal)",
    )
    parser.add_argument(
        "--target-policy-csv",
        default=str(DEFAULT_TARGET_POLICY_CSV),
        help="CSV policy file defining target-profile source columns used downstream by train_models",
    )
    parser.add_argument(
        "--diagnosis-occurrence-threshold-enabled",
        action="store_true",
        help="Enable participant-prevalence filtering for ICD grouped features",
    )
    parser.add_argument(
        "--diagnosis-occurrence-threshold",
        type=int,
        default=10,
        help="Minimum positive participants required to keep an ICD grouped feature (when enabled)",
    )
    parser.add_argument(
        "--procedure-occurrence-threshold-enabled",
        action="store_true",
        help="Enable participant-prevalence filtering for OPCS grouped features",
    )
    parser.add_argument(
        "--procedure-occurrence-threshold",
        type=int,
        default=10,
        help="Minimum positive participants required to keep an OPCS grouped feature (when enabled)",
    )
    parser.add_argument(
        "--recency-sentinel-days",
        type=float,
        default=None,
        help="Optional default recency sentinel value recorded in the preprocessing spec; default is core_window_days + 1",
    )
    parser.add_argument(
        "--preprocessing-policy-json",
        default=str(DEFAULT_PREPROCESSING_POLICY_JSON),
        help="Version-controlled preprocessing policy JSON consumed by build_features and train_models",
    )
    parser.add_argument("--stamp", required=False, help="Optional date stamp override (YYYY-MM-DD)")
    return parser.parse_args()


# %% Cell 7: Main execution and artifact writing
def main() -> None:
    args = parse_args()
    stamp = args.stamp if args.stamp else date.today().isoformat()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cohort = load_csv(Path(args.cohort), "cohort")
    apc = load_csv(Path(args.hes_apc), "hes_apc")
    op = load_csv(Path(args.hes_op), "hes_op")
    ae = load_csv(Path(args.hes_ae), "hes_ae")
    icd_policy_path = Path(args.icd_group_policy_csv)
    target_policy_path = Path(args.target_policy_csv)
    recency_policy_path = Path(args.recency_policy_csv)
    preprocessing_policy_path = Path(args.preprocessing_policy_json)
    icd_core_groups, icd_optional_groups, icd_policy_meta = load_icd_group_policy(icd_policy_path)
    icd_min_positive_overrides = (
        dict(icd_policy_meta.get("min_positive_n_override", {}))
        if isinstance(icd_policy_meta, dict)
        else {}
    )
    recency_sentinel_days = (
        float(args.recency_sentinel_days)
        if args.recency_sentinel_days is not None
        else float(args.core_window_years * DAYS_PER_YEAR + 1.0)
    )

    raw_store, build_meta, signal_discovery_artifacts = build_feature_store(
        cohort=cohort,
        apc=apc,
        op=op,
        ae=ae,
        core_window_years=args.core_window_years,
        recent_window_years=args.recent_window_years,
        include_optional_icd_groups=args.include_optional_icd_groups,
        include_optional_opcs_groups=args.include_optional_opcs_groups,
        diagnosis_occurrence_threshold_enabled=args.diagnosis_occurrence_threshold_enabled,
        diagnosis_occurrence_threshold=args.diagnosis_occurrence_threshold,
        procedure_occurrence_threshold_enabled=args.procedure_occurrence_threshold_enabled,
        procedure_occurrence_threshold=args.procedure_occurrence_threshold,
        icd_core_groups=icd_core_groups,
        icd_optional_groups=icd_optional_groups,
        icd_min_positive_overrides=icd_min_positive_overrides,
        icd_policy_meta=icd_policy_meta,
    )

    preprocessing_policy = load_preprocessing_policy(preprocessing_policy_path)
    preprocessing_spec = build_governed_preprocessing_spec(
        raw_store=raw_store,
        feature_meta=build_meta["feature_meta"],
        core_window_years=args.core_window_years,
        include_legacy_vcf_fields=args.include_legacy_vcf_fields,
        include_sequencing_missing_flag=args.include_sequencing_missing_flag,
        target_policy_csv=target_policy_path,
        preprocessing_policy=preprocessing_policy,
        recency_sentinel_days=recency_sentinel_days,
    )
    prep_meta = summarize_preprocessing_spec(preprocessing_spec)

    raw_path = out_dir / f"features_matrix_raw_{stamp}.csv"
    preprocessing_spec_path = out_dir / f"feature_preprocessing_spec_{stamp}.json"
    raw_icd_matrix_path = out_dir / f"icd_raw_discovery_matrix_{stamp}.csv"
    raw_icd_dictionary_path = out_dir / f"icd_raw_code_dictionary_{stamp}.csv"
    stage_a_prep_path = out_dir / f"icd_raw_stage_a_preparation_{stamp}.csv"
    grouped_anchor_path = out_dir / f"icd_group_anchor_comparison_{stamp}.csv"
    metadata_path = out_dir / f"features_matrix_metadata_{stamp}.json"

    raw_store.to_csv(raw_path, index=False)
    signal_discovery_artifacts["raw_code_discovery_matrix"].to_csv(raw_icd_matrix_path, index=False)
    signal_discovery_artifacts["raw_code_dictionary"].to_csv(raw_icd_dictionary_path, index=False)
    signal_discovery_artifacts["stage_a_preparation"].to_csv(stage_a_prep_path, index=False)
    signal_discovery_artifacts["grouped_anchor_comparison"].to_csv(grouped_anchor_path, index=False)
    with preprocessing_spec_path.open("w", encoding="utf-8") as f:
        json.dump(to_jsonable(preprocessing_spec), f, indent=2, sort_keys=True)

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "cohort": str(Path(args.cohort).resolve()),
            "hes_apc": str(Path(args.hes_apc).resolve()),
            "hes_op": str(Path(args.hes_op).resolve()),
            "hes_ae": str(Path(args.hes_ae).resolve()),
        },
        "config": {
            "core_window_years": args.core_window_years,
            "recent_window_years": args.recent_window_years,
            "winsor_upper_q": args.winsor_upper_q,
            "include_legacy_vcf_fields": args.include_legacy_vcf_fields,
            "include_sequencing_missing_flag": args.include_sequencing_missing_flag,
            "include_opcs_in_model_matrix": args.include_opcs_in_model_matrix,
            "include_missingness_indicators": args.include_missingness_indicators,
            "include_optional_icd_groups": args.include_optional_icd_groups,
            "include_optional_opcs_groups": args.include_optional_opcs_groups,
            "diagnosis_occurrence_threshold_enabled": args.diagnosis_occurrence_threshold_enabled,
            "diagnosis_occurrence_threshold": args.diagnosis_occurrence_threshold,
            "procedure_occurrence_threshold_enabled": args.procedure_occurrence_threshold_enabled,
            "procedure_occurrence_threshold": args.procedure_occurrence_threshold,
            "icd_group_policy_csv": str(icd_policy_path.resolve()),
            "recency_policy_csv": str(recency_policy_path.resolve()) if recency_policy_path.exists() else str(recency_policy_path),
            "recency_policy_id": args.recency_policy_id,
            "target_policy_csv": str(target_policy_path.resolve()) if target_policy_path.exists() else str(target_policy_path),
            "preprocessing_policy_json": str(preprocessing_policy_path.resolve()) if preprocessing_policy_path.exists() else str(preprocessing_policy_path),
            "recency_sentinel_days": recency_sentinel_days,
            "sequencing_date_policy": "preserve_missing_for_now_filter_downstream",
            "build_stage_preprocessing_contract": "raw_governed_features_plus_spec_only",
        },
        "diagnostics": build_meta["diagnostics"],
        "feature_meta": build_meta["feature_meta"],
        "signal_discovery_meta": build_meta["signal_discovery_meta"],
        "preprocessing_meta": prep_meta,
        "outputs": {
            "features_matrix_raw": str(raw_path.resolve()),
            "feature_preprocessing_spec": str(preprocessing_spec_path.resolve()),
            "icd_raw_discovery_matrix": str(raw_icd_matrix_path.resolve()),
            "icd_raw_code_dictionary": str(raw_icd_dictionary_path.resolve()),
            "icd_raw_stage_a_preparation": str(stage_a_prep_path.resolve()),
            "icd_group_anchor_comparison": str(grouped_anchor_path.resolve()),
        },
        "deprecation_notes": {
            "vcf_augmentation_active_use": False,
            "legacy_fields_retained_for_backcompat": ["has_scn5a_vcf", "scn5a_evidence_source"],
            "full_cohort_model_preprocessing_removed": True,
            "build_time_linear_tree_matrices_removed": True,
        },
    }

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(to_jsonable(metadata), f, indent=2, sort_keys=True)

    print(f"Wrote raw feature store: {raw_path}")
    print(f"Wrote preprocessing spec: {preprocessing_spec_path}")
    print(f"Wrote raw ICD discovery matrix: {raw_icd_matrix_path}")
    print(f"Wrote raw ICD code dictionary: {raw_icd_dictionary_path}")
    print(f"Wrote raw ICD Stage A preparation table: {stage_a_prep_path}")
    print(f"Wrote grouped-anchor comparison table: {grouped_anchor_path}")
    print(f"Wrote metadata: {metadata_path}")
    print(f"Rows: {raw_store.shape[0]}, Raw cols: {raw_store.shape[1]}")
    print(f"Governed predictors: {len(preprocessing_spec.get('predictor_columns', []))}")


if __name__ == "__main__":
    main()
