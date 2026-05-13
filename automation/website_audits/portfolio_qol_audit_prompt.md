# Portfolio QoL Audit Prompt

Use this as the recurring Codex automation task prompt.

```text
Run the portfolio website QoL audit for the current repository.

Goal:
- Identify practical improvements across UX, design, components, phrasing, site structure, accessibility, SEO, metadata, performance, maintainability, and portfolio-adjacent feature ideas.
- Include external research where available.
- Do not treat generic publication-safety review as the main objective. Only flag genuinely risky disclosures or restricted details when they appear.

Required setup:
1. Run `automation/website_audits/scripts/init_run_dir.sh`.
2. Use the current date's run directory at `private/regular_audits/runs/YYYY-MM-DD/`.
3. Update these files for today's run:
   - `RUN_SUMMARY.md`
   - `QOL_RESEARCH.md`
   - `CODE_SITE_AUDIT.md`
   - `PROPOSALS.md`
   - `sources.md`
4. Update `private/regular_audits/AUDIT_INDEX.md`.

Primary website sources to inspect:
- `site/package.json`
- `site/astro.config.mjs`
- `site/src/layouts/BaseLayout.astro`
- `site/src/components/**/*.astro`
- `site/src/pages/**/*.astro`
- `site/src/styles/global.css`
- `site/tests/**/*.ts`
- `README.md`
- `PORTFOLIO_INDEX.md`

Audit behaviour:
- Review the Astro site as the primary surface.
- Use the root Markdown portfolio files as secondary context only.
- If the repo already supports checks, run safe non-destructive ones when useful:
  - `cd site && npm run check`
  - `cd site && npm run build`
  - `cd site && npm run test:ui`
- If a command fails or is too expensive for this run, say so explicitly in the audit output.

External research requirement:
- Use web research when available.
- Diversify sources across real technical discussion spaces and primary docs where helpful.
- Prefer practical sources over generic SEO filler.
- Aim for at least four distinct source domains when available.
- Good source families include Reddit, Hacker News, GitHub Discussions/issues, official docs, practitioner blogs, framework/library discussions, accessibility resources, and design references that lead to implementable ideas.
- Every research-backed proposal must include at least one citation URL.
- If external research is unavailable, state that clearly and fall back to local-only audit.

Research targets:
- Portfolio UX improvements
- Project and case-study structure
- Typography and visual hierarchy
- Navigation and information scent
- Blog or writing section structure
- Search, tags, filters, reading time, status badges, maturity labels
- Timeline or changelog/project-log ideas
- "Now" page and lightweight personal knowledge-base ideas
- AI-assisted features that do not feel gimmicky
- Accessibility, Core Web Vitals, SEO, rich metadata, theme handling, trust signals, proof-of-work presentation
- Better presentation patterns for academic, research, policy, data-science, health-innovation, and governance-heavy work

Output requirements:
- `QOL_RESEARCH.md`
  - Research findings
  - Practical takeaways
  - Why each idea fits this site
- `CODE_SITE_AUDIT.md`
  - Code, layout, accessibility, SEO, metadata, performance, maintainability, and QA findings
  - Note whether checks were run and the result
- `PROPOSALS.md`
  - Maintain a `## QoL proposals` section for this run
  - For each proposal include:
    - Proposal ID
    - Title
    - Area
    - Why it matters
    - Implementation sketch
    - Evidence and citations
    - Suggested priority (`now`, `soon`, `later`)
    - Suggested implementation stance (`direct-implement` or `discuss-first`)
- `sources.md`
  - Maintain a `## QoL sources` section with URLs and one-line relevance notes
- `RUN_SUMMARY.md`
  - Maintain a `## QoL audit` section with:
    - run status
    - checks run
    - number of proposals
    - highest-priority items
    - any blockers
- `AUDIT_INDEX.md`
  - Add or refresh today's entry with links or paths to the run files and a brief status line

Proposal ID format:
- `QOL-YYYYMMDD-short-slug`
- Use a short kebab-case slug based on the proposal title.
- Reuse the same ID when a same-day rerun keeps the same proposal materially intact.

Final quality bar:
- Be specific, not vague.
- Prefer implementable proposals over broad taste commentary.
- Cite sources honestly.
- Keep recommendations grounded in this repo's actual structure.
```
