# Portfolio ORION Content Audit Prompt

Use this as the recurring Codex automation task prompt.

```text
Run the ORION-to-website content and framing audit for the current repository.

Goal:
- Compare the website against selected ORION source material.
- Find stronger wording, missing details, sharper framing, better role alignment, and content or structure ideas that would materially improve the site.
- Flag genuinely risky disclosures such as restricted cohort counts, export-sensitive details, or oversharing from ORION when present.
- Do not let general "public-facing caution" dominate the audit.

Required setup:
1. Run `automation/website_audits/scripts/init_run_dir.sh`.
2. Read `private/regular_audits/config/orion_repo_path.txt`.
3. If the ORION path file is missing or invalid, record that in today's run and stop after writing a blocked summary.
4. Read `automation/website_audits/orion_allowlist.txt` and stay within that scope.
5. Use the current date's run directory at `private/regular_audits/runs/YYYY-MM-DD/`.

Skip gate:
- Find the most recent previous `ORION_CONTENT_AUDIT.md` from an earlier run date.
- If there is no earlier run, continue.
- If there is an earlier run, compare its modification time against:
  - `site/src/pages/**/*.astro`
  - `site/src/layouts/**/*.astro`
  - `site/src/components/**/*.astro`
  - `README.md`
  - `PORTFOLIO_INDEX.md`
  - the allowed ORION roots from `orion_allowlist.txt`
- If nothing relevant is newer than the previous ORION audit, do not perform a full audit.
- Instead:
  - update `RUN_SUMMARY.md`
  - update `ORION_CONTENT_AUDIT.md`
  - update `AUDIT_INDEX.md`
  - state clearly that the scheduled content audit was skipped because no relevant source changes were detected since the previous ORION audit
  - leave `PROPOSALS.md` unchanged unless you need to add a skip note

Primary comparison order:
1. Website Astro pages under `site/src/pages/**/*.astro`
2. Website layout/components when they affect framing
3. Root portfolio Markdown files as secondary website context
4. ORION files within the allowed roots

Audit targets:
- Stronger wording in ORION that is missing from the website
- Awkward, weak, repetitive, vague, or under-confident website phrasing
- Missing or underused details from careers, FYP, Allomics, and modules
- Sharper framing for recruiters, analysts, health-innovation roles, health strategy teams, AI governance roles, research/data science roles, and adjacent opportunities
- Terminology consistency across pages
- Better pairings between content improvements and site/feature opportunities

Output requirements:
- `ORION_CONTENT_AUDIT.md`
  - Summary of the website-vs-ORION gap
  - Notable wording weaknesses on the website
  - Underused ORION source areas
  - Any real disclosure risks that should be fixed
- `PROPOSALS.md`
  - Maintain a `## ORION proposals` section for this run
  - For each proposal include:
    - Proposal ID
    - Current website file/page
    - Current wording or section summary
    - Exact proposed replacement wording
    - Why the change improves the site
    - ORION source file(s) used
    - Privacy/publication risk rating (`low`, `medium`, `high`)
    - Suggested implementation stance (`direct-implement`, `discuss-first`, or `keep-private`)
- `sources.md`
  - Maintain a `## ORION sources` section with repo-relative ORION file paths and one-line relevance notes
- `RUN_SUMMARY.md`
  - Maintain a `## ORION audit` section with:
    - run status
    - whether the skip gate fired
    - number of proposals
    - highest-priority wording/framing issues
    - any real disclosure-risk findings
- `AUDIT_INDEX.md`
  - Add or refresh today's entry with ORION audit status and paths

Proposal ID format:
- `ORION-YYYYMMDD-short-slug`
- Use a short kebab-case slug based on the proposal title.
- Reuse the same ID when a same-day rerun keeps the same proposal materially intact.

Final quality bar:
- Be exact with replacement wording.
- Prefer sharper positioning over defensive hedging when the evidence supports it.
- Stay inside the allowed ORION scope.
- Flag truly risky details, but do not turn the whole audit into a generic safety pass.
```
