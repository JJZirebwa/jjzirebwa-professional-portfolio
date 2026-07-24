# Professional Portfolio Codex Guide

This repository inherits `/Users/jjzirebwa/.codex/AGENTS.md`.

## Repository Role

This is JJ's public professional portfolio and website. It reconciles evidence, terminology and selected developments from ORION, but it remains an independent public-facing repository.

## Working Rules

- Preserve defensible claims, authorship boundaries, dates and source provenance.
- Do not publish confidential material, restricted data, paid-source exports, private paths, participant-level information or unsupported organisational claims.
- Use ORION as a read-only evidence source when reconciliation is required. Do not silently change ORION from a portfolio task.
- Distinguish completed work, contributions, learning projects and future direction. Do not inflate responsibility or outcomes.
- For candidate-facing or personal prose, complete evidence and claim checks before the final `$jj-writing-style` pass.
- Follow existing structure and terminology before adding new pages or top-level files.
- RTK and Caveman remain explicit-only under the global policy.

## Site Verification

The Astro site is under `site/` and targets Node 22. For relevant changes, run:

```bash
cd site
npm run check
npm run build
```

Run `npm run test:ui` when user flows, layout, navigation or rendered content materially change.

Direct user instructions override this file. A deeper `AGENTS.md` overrides it for its subtree.
