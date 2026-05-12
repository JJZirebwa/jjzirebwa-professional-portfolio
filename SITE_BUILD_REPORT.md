# Site build report

## What was created

An Astro static site layer was added under `site/` as the polished Netlify-facing front door for the portfolio.

Created:

- `site/package.json`
- `site/package-lock.json`
- `site/astro.config.mjs`
- `site/src/layouts/BaseLayout.astro`
- `site/src/components/SectionHeader.astro`
- `site/src/components/LinkCard.astro`
- `site/src/components/CaseStudyPage.astro`
- `site/src/styles/global.css`
- `site/src/pages/index.astro`
- `site/src/pages/about.astro`
- `site/src/pages/case-studies/index.astro`
- `site/src/pages/case-studies/health-innovation-east.astro`
- `site/src/pages/case-studies/ai-medtech-toolkit.astro`
- `site/src/pages/case-studies/market-intelligence.astro`
- `site/src/pages/case-studies/final-year-project.astro`
- `site/src/pages/case-studies/consoneai-dioscor.astro`
- `site/src/pages/projects.astro`
- `site/src/pages/skills.astro`
- `site/src/pages/contact.astro`
- `site/DEPLOYMENT.md`
- `netlify.toml`

Updated:

- `.gitignore` now excludes `site/node_modules/`, `site/dist/` and `site/.astro/`.

## Site structure

The site is organised as a concise public front door:

- Home page: positioning, best starting points, portfolio themes, selected case studies and confidentiality note.
- About: academic and professional profile.
- Case studies: curated public-safe case-study set.
- Projects: grouped project themes and bounded exploratory methods.
- Skills: evidence-backed skill map.
- Contact: application-safe contact direction and professional scope.

## Claims reused

The site reuses already-public claims from the Markdown portfolio:

- Final-year Biomedical Science student at Anglia Ruskin University.
- One-year Health Innovation East commercial placement.
- Authored practical internal AI/MedTech guidance-support material.
- Market intelligence and competitor-analysis work using CB Insights and secondary research.
- Governance-bound final-year project using secure, genomics-linked hospital trajectory analysis in a Brugada-suspect context.
- Short ConsoneAI/DioScor research internship involving high-level toxicology data mapping and structured data preparation.
- Skills across evidence synthesis, commercial health innovation, AI/MedTech governance, data handling and scientific/commercial writing.

## Intentionally excluded

The site does not include:

- raw datasets
- dissertation extracts or PDFs
- restricted dissertation figures, model tables, counts or participant-level details
- internal Health Innovation East documents
- CB Insights exports, screenshots or paid-source reports
- ConsoneAI/DioScor NDA material, proprietary schemas or platform screenshots
- private ORION references
- review files or `_private/` material
- fake metrics, invented endorsements or unsupported outcome claims

## Build and test status

Completed local verification:

- `npm install` completed and generated `site/package-lock.json`.
- `npm run build` completed successfully.
- `astro check` reported 0 errors, 0 warnings and 0 hints.
- Astro generated 11 static pages in `site/dist/`.
- A local internal-link check confirmed that all root-relative links in the generated HTML resolve.
- A search for generated links to `review/`, `_private/`, `private/`, ORION, build reports, publication-safety files, assets or PDFs returned no matches.
- `npm audit --omit=dev` found 0 runtime dependency vulnerabilities.
- Local preview served successfully at `http://127.0.0.1:4321/`; the home page and final-year project page returned HTTP 200.

Full npm audit still reports moderate advisories in the `@astrojs/check` development-tool chain through `yaml-language-server`. I did not run `npm audit fix --force` because npm indicates that would force a breaking checker change. The deployed static site does not run this development dependency.

Preview locally with:

```bash
cd site
npm run preview
```

## Remaining manual checks

- Read every generated page in browser preview before publication.
- Confirm all case-study boundaries remain accurate and do not imply organisational endorsement.
- Confirm the contact page wording is acceptable without publishing a personal email address.
- Decide whether to add a reviewed LinkedIn or email link later.
- Confirm that no ignored private folders are reachable in any deployed output.
- Review mobile layout in Netlify deploy preview before making the site public.

## Netlify deployment instructions

Recommended Netlify settings:

| Setting | Value |
|---|---|
| Base directory | `site` |
| Build command | `npm run build` |
| Publish directory | `dist` |

Because Netlify's monorepo documentation describes the publish directory as relative to the base directory, `dist` is the expected publish value when the base directory is `site`. If the Netlify UI asks for a repository-root-relative path, use `site/dist`.

The root `netlify.toml` already sets:

```toml
[build]
  base = "site"
  command = "npm run build"
  publish = "dist"

[build.environment]
  NODE_VERSION = "22.12.0"
```

Do not deploy until the manual public-safety review is complete.

References:

- Astro Netlify deployment guide: <https://docs.astro.build/en/guides/deploy/netlify/>
- Netlify monorepo build settings: <https://docs.netlify.com/build/configure-builds/monorepos/>
