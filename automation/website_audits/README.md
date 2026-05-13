# Website Audit Automations

This folder defines the regular Codex maintenance audits for the portfolio site.

## Automations

- `portfolio_qol_audit_prompt.md`: website QoL, design, code quality, accessibility, SEO, performance, feature, and research-backed improvement audit.
- `portfolio_orion_audit_prompt.md`: ORION-to-website content and framing audit.
- `orion_allowlist.txt`: the ORION scope and exclusions for the content audit.
- `scripts/init_run_dir.sh`: creates the dated audit run folder and the required output files.

## Output Location

All generated audit output lives under:

`private/regular_audits/`

That directory is already ignored by git in this repository, so normal commits and pushes will not include audit runs unless you force-add ignored files.

## Local Config

The ORION audit reads the local path from:

`private/regular_audits/config/orion_repo_path.txt`

That file is intentionally ignored by git. It keeps machine-specific paths out of the committed workflow.

## Manual Use

To run the QoL audit manually in a Codex thread:

`Run the portfolio QoL audit defined in automation/website_audits/portfolio_qol_audit_prompt.md as a force run. Do not skip because of unchanged sources.`

To run the ORION content audit manually in a Codex thread:

`Run the ORION-to-website content audit defined in automation/website_audits/portfolio_orion_audit_prompt.md as a force run. Do not skip because of unchanged sources.`

To implement accepted proposals later:

`Open the latest private/regular_audits/.../PROPOSALS.md and implement proposal IDs <ID1>, <ID2>. Only apply items marked direct-implement.`

## Proposal IDs

Proposal IDs use this format:

- `QOL-YYYYMMDD-short-slug`
- `ORION-YYYYMMDD-short-slug`

The slug is a short kebab-case summary of the proposal title. This is more stable than simple numbering when the same day is rerun.

## Git Safety

- `private/`, `_private/`, and `review/` are already ignored in `.gitignore`.
- Netlify only publishes `site/dist`, so audit output under `private/regular_audits/` is outside the deploy surface.
- Normal `git add .` and `git commit` flows will continue to skip the audits because they are ignored.
- The only common way to publish them accidentally is to force-add ignored files with `git add -f`.
