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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_RUN_ROOT = Path(
    "data/example_run"
)


# %% ---------------------------------------------------------------------------
# STEP 0 helpers: argument parsing and run resolution
# -----------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate EDA plots for feature-engineering outputs")
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT), help="Path containing testing_<n> folders")
    parser.add_argument("--run-dir", default=None, help="Specific testing_<n> folder (default: latest)")
    parser.add_argument("--stamp", default=None, help="Optional date stamp override (YYYY-MM-DD)")
    parser.add_argument("--top-n", type=int, default=20, help="Top-N features for summary bar charts")
    parser.add_argument(
        "--investigation-id",
        default=None,
        help="Optional investigation id used to namespace EDA output folder",
    )

    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print(f"[STEP 0] Ignoring unrecognized args: {unknown}")
    args.investigation_id = (args.investigation_id or "").strip() or None
    return args


def print_step(step_title: str) -> None:
    bar = "=" * 88
    print(f"\n{bar}\n{step_title}\n{bar}")


def slug_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    return cleaned.strip("_") or "unset"


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
        raise FileNotFoundError(f"No metadata files found in {run_dir}")

    match = re.search(r"(\d{4}-\d{2}-\d{2})", meta_paths[0].name)
    if not match:
        raise RuntimeError(f"Could not infer stamp from {meta_paths[0].name}")
    return match.group(1)


# %% ---------------------------------------------------------------------------
# STEP 1 helpers: load run artifacts
# -----------------------------------------------------------------------------
def load_metadata_and_raw(run_dir: Path, stamp: str) -> tuple[dict[str, Any], pd.DataFrame]:
    meta_path = run_dir / f"features_matrix_metadata_{stamp}.json"
    raw_path = run_dir / f"features_matrix_raw_{stamp}.csv"

    if not meta_path.exists() or not raw_path.exists():
        raise FileNotFoundError(
            "Missing required artifacts for EDA: "
            f"metadata={meta_path.exists()} raw_matrix={raw_path.exists()}"
        )

    metadata = json.loads(meta_path.read_text())
    raw = pd.read_csv(raw_path)
    return metadata, raw


# %% ---------------------------------------------------------------------------
# STEP 2 helpers: summary table construction
# -----------------------------------------------------------------------------
def build_missingness_table(raw: pd.DataFrame) -> pd.DataFrame:
    missingness = pd.DataFrame(
        {
            "column": raw.columns,
            "missing_pct": raw.isna().mean().values * 100.0,
        }
    ).sort_values("missing_pct", ascending=False)
    return missingness


def build_icd_prevalence_table(raw: pd.DataFrame, icd_cols: list[str]) -> pd.DataFrame:
    if not icd_cols:
        return pd.DataFrame(columns=["column", "positive_pct"])

    rows: list[dict[str, Any]] = []
    for col in icd_cols:
        if col not in raw.columns:
            continue
        s = pd.to_numeric(raw[col], errors="coerce")
        rows.append(
            {
                "column": col,
                "positive_pct": float((s > 0).mean() * 100.0),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["column", "positive_pct"])
    return pd.DataFrame(rows).sort_values("positive_pct", ascending=False)


def build_skew_table(raw: pd.DataFrame) -> pd.DataFrame:
    num_cols = [c for c in raw.columns if pd.api.types.is_numeric_dtype(raw[c])]
    rows: list[dict[str, Any]] = []

    for col in num_cols:
        s = pd.to_numeric(raw[col], errors="coerce").dropna()
        if len(s) < 10:
            continue
        rows.append({"column": col, "abs_skew": float(abs(s.skew()))})

    if not rows:
        return pd.DataFrame(columns=["column", "abs_skew"])
    return pd.DataFrame(rows).sort_values("abs_skew", ascending=False)


# %% ---------------------------------------------------------------------------
# STEP 3 helpers: plotting
# -----------------------------------------------------------------------------
def plot_missingness(missingness: pd.DataFrame, out_path: Path, top_n: int) -> bool:
    top = missingness.head(top_n)
    if top.empty:
        return False

    plt.figure(figsize=(10, 6))
    plt.barh(top["column"][::-1], top["missing_pct"][::-1])
    plt.xlabel("Missing %")
    plt.title(f"Top {top_n} columns by missingness")
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()
    return True


def plot_icd_prevalence(icd_prev: pd.DataFrame, out_path: Path, top_n: int) -> bool:
    top = icd_prev.head(top_n)
    if top.empty:
        return False

    plt.figure(figsize=(12, 7))
    plt.barh(top["column"][::-1], top["positive_pct"][::-1])
    plt.xlabel("Participants with value > 0 (%)")
    plt.title(f"Top {top_n} ICD grouped features by prevalence")
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()
    return True


def plot_numeric_histograms(raw: pd.DataFrame, out_path: Path) -> bool:
    candidates = [
        c
        for c in raw.columns
        if pd.api.types.is_numeric_dtype(raw[c])
        and (
            "_count_" in c
            or "_rate_" in c
            or "_sum_" in c
            or "_mean_" in c
            or "days_since" in c
        )
    ]
    if not candidates:
        return False

    show_cols = candidates[:12]
    ncols = 3
    nrows = int(np.ceil(len(show_cols) / ncols))

    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.5 * nrows))
    axes = np.array(axes).reshape(-1)

    last_i = -1
    for i, col in enumerate(show_cols):
        ax = axes[i]
        s = pd.to_numeric(raw[col], errors="coerce").dropna()
        ax.hist(s, bins=30)
        ax.set_title(col)
        last_i = i

    for j in range(last_i + 1, len(axes)):
        axes[j].axis("off")

    fig.suptitle("Distribution snapshots for key numeric feature families", y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return True


def plot_skew(skew_df: pd.DataFrame, out_path: Path, top_n: int) -> bool:
    top = skew_df.head(top_n)
    if top.empty:
        return False

    plt.figure(figsize=(10, 6))
    plt.barh(top["column"][::-1], top["abs_skew"][::-1])
    plt.xlabel("Absolute skew")
    plt.title(f"Top {top_n} most skewed numeric features")
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()
    return True


# %% ---------------------------------------------------------------------------
# STEP 4 helper: output persistence
# -----------------------------------------------------------------------------
def write_summary_tables(
    out_dir: Path,
    stamp: str,
    missingness: pd.DataFrame,
    icd_prev: pd.DataFrame,
    skew_df: pd.DataFrame,
) -> dict[str, str]:
    outputs = {
        "missingness_table": out_dir / f"eda_missingness_all_{stamp}.csv",
        "icd_prevalence_table": out_dir / f"eda_icd_prevalence_all_{stamp}.csv",
        "skew_table": out_dir / f"eda_numeric_abs_skew_all_{stamp}.csv",
    }

    missingness.to_csv(outputs["missingness_table"], index=False)
    icd_prev.to_csv(outputs["icd_prevalence_table"], index=False)
    skew_df.to_csv(outputs["skew_table"], index=False)

    return {k: str(v) for k, v in outputs.items()}


# %% ---------------------------------------------------------------------------
# Orchestration
# -----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    print_step("STEP 0: Resolve run directory and stamp")
    run_root = Path(args.run_root)
    run_dir = find_run_dir(run_root, args.run_dir)
    stamp = infer_stamp(run_dir, args.stamp)
    print(f"RUN_ROOT: {run_root}")
    print(f"RUN_DIR: {run_dir}")
    print(f"STAMP: {stamp}")
    print(f"INVESTIGATION_ID: {args.investigation_id if args.investigation_id else '<none>'}")

    print_step("STEP 1: Load metadata and raw feature matrix")
    metadata, raw = load_metadata_and_raw(run_dir, stamp)
    icd_cols = metadata.get("feature_meta", {}).get("icd_group_feature_cols", [])
    print(f"RAW_SHAPE: {raw.shape}")
    print(f"ICD_GROUP_FEATURE_COUNT(metadata): {len(icd_cols)}")

    print_step("STEP 2: Build EDA summary tables")
    missingness = build_missingness_table(raw)
    icd_prev = build_icd_prevalence_table(raw, icd_cols)
    skew_df = build_skew_table(raw)
    print(f"MISSINGNESS_ROWS: {len(missingness)}")
    print(f"ICD_PREVALENCE_ROWS: {len(icd_prev)}")
    print(f"SKEW_ROWS: {len(skew_df)}")

    if args.investigation_id:
        out_dir = run_dir / f"eda_plots_{stamp}_{slug_token(args.investigation_id)}"
    else:
        out_dir = run_dir / f"eda_plots_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print_step("STEP 3: Render EDA figures")
    plot_outputs = {
        "missingness_top_features": out_dir / "missingness_top_features.png",
        "icd_group_prevalence": out_dir / "icd_group_prevalence.png",
        "numeric_family_histograms": out_dir / "numeric_family_histograms.png",
        "numeric_abs_skew_top_features": out_dir / "numeric_abs_skew_top_features.png",
    }

    generated = {
        "missingness_top_features": plot_missingness(missingness, plot_outputs["missingness_top_features"], args.top_n),
        "icd_group_prevalence": plot_icd_prevalence(icd_prev, plot_outputs["icd_group_prevalence"], args.top_n),
        "numeric_family_histograms": plot_numeric_histograms(raw, plot_outputs["numeric_family_histograms"]),
        "numeric_abs_skew_top_features": plot_skew(skew_df, plot_outputs["numeric_abs_skew_top_features"], args.top_n),
    }

    print_step("STEP 4: Persist summary tables and manifest")
    table_outputs = write_summary_tables(out_dir, stamp, missingness, icd_prev, skew_df)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "stamp": stamp,
        "investigation_id": args.investigation_id,
        "top_n": int(args.top_n),
        "output_dir": str(out_dir),
        "plots": {
            name: {
                "path": str(path),
                "generated": bool(generated[name]),
            }
            for name, path in plot_outputs.items()
        },
        "tables": table_outputs,
    }
    manifest_path = out_dir / "eda_plot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"Wrote EDA outputs to: {out_dir}")
    print("Plots:")
    for name, path in plot_outputs.items():
        status = "generated" if generated[name] else "skipped"
        print(f"- {name}: {status} ({path})")
    print("Tables:")
    for name, path in table_outputs.items():
        print(f"- {name}: {path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
