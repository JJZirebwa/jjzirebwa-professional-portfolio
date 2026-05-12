# Site polish report

## Live site source

The Netlify site is driven by the Astro project in `site/`.

- `netlify.toml` sets `base = "site"`, `command = "npm run build"` and `publish = "dist"`.
- Live page copy is in `site/src/pages/`.
- Shared layout, navigation, metadata and footer copy are in `site/src/layouts/BaseLayout.astro`.
- Shared case-study structure is in `site/src/components/CaseStudyPage.astro`.
- Styling is in `site/src/styles/global.css`.
- The `website/` Markdown folder is not imported by Astro.

## Visual and QoL changes

- Added the headshot to the homepage hero beside the opening positioning copy.
- Added a restrained homepage context strip for Health Innovation East, ARU and Genomics England.
- Added Health Innovation East logo placement on the HIE case study as placement context.
- Added Genomics England logo placement on the final-year project case study as research context.
- Added ARU logo placement on the academic profile section.
- Added SVG line icons across starting-point cards, case-study cards, project cards and skill cards.
- Added/kept active navigation states, skip-to-content, Open Graph/Twitter metadata, favicon and custom 404 page.
- Added Google Analytics 4 support using the supplied measurement ID. The tag is not visible in the site UI, and `PUBLIC_GA_MEASUREMENT_ID` can still override the baked-in ID later if needed.

## Public assets added

Assets were copied from the ignored local buffer into clean public filenames:

- `site/public/images/jubileejoy-zirebwa-headshot.jpg`
- `site/public/images/logo-health-innovation-east.webp`
- `site/public/images/logo-aru.png`
- `site/public/images/logo-genomics-england.png`

The originals remain in an ignored local buffer. The logos are presented as context markers rather than endorsement badges.

## Copy and safety notes

- Preserved the latest user-edited wording and phrasing where possible.
- Made one small grammar correction on the homepage introduction.
- Kept Health Innovation East, final-year project and ConsoneAI/DioScor boundaries intact.
- Did not add raw documents, PDFs, dissertation extracts, figures, HIE files, CB Insights exports, ConsoneAI/DioScor materials, private ORION content or restricted data.
- The supplied GA4 measurement ID is baked into the analytics component because browser analytics IDs are public once the site is built. No Google account credentials or private analytics access details were added.

## Verification

- `npm run build` passed from `site/`.
- `astro check` reported 0 errors, 0 warnings and 0 hints across 18 Astro files.
- Astro built 12 pages, including the custom 404 page.
- Internal root-relative links in generated HTML resolve.
- Generated output contains no private/review/PDF/ORION links and no removed scaffold phrases.
- The current build includes the Google Analytics tag with the supplied GA4 measurement ID.
- A previous test build with `PUBLIC_GA_MEASUREMENT_ID=G-TEST12345` confirmed the environment-variable override path; the sample value is not present in the current build output.

## Remaining manual checks

- Review the homepage image crop and logo strip in a browser at desktop and mobile widths.
- Confirm that public use of the HIE, ARU and Genomics England logos is acceptable.
- Confirm the direct email, phone and LinkedIn details on the contact page should remain public.
- Confirm the Health Innovation East and final-year project logo placements read as context rather than endorsement.
- Verify page views in the Google Analytics Realtime report after the next deploy.
- Review whether a privacy/cookie notice or consent handling is needed before using Google Analytics on the production site.

## Independent review

A read-only reviewer agent reviewed the visual/QoL pass after implementation. Per instruction, the review findings below were logged as mitigation proposals only and were not applied in this pass.

- High: the homepage logo strip could read like a sponsor or endorsement strip because the marks appear prominently before the main proof points. Mitigation proposal: remove logos from the homepage, or demote them to smaller context-only placements with adjacent wording such as "context only, no endorsement".
- High: the homepage and skills page remain fairly text-heavy, with repeated evidence/governance/judgement phrasing. Mitigation proposal: cut the homepage by roughly one third, compress the "How the work connects" area, and turn the skills page into a tighter proof matrix.
- Medium-high: the "Future biological evidence methods" project may still sound speculative because of phrases such as "provenance-aware biological priors" and "missing-variable discovery". Mitigation proposal: relabel it as future exploration or rewrite it in plainer language tied directly to the dissertation.
- Medium-high: named third-party/product references remain uneven across pages. Mitigation proposal: anonymise names unless there is explicit public permission, or place boundary language next to named references rather than relying on separate notes.
- Medium: the headshot is strong, but the homepage first screen may feel busy because the portrait, evidence map and logo strip appear close together. Mitigation proposal: keep the portrait, collapse the evidence map further on small screens, and hide the homepage logo strip on mobile.
- Medium: several lines could still be tightened for trust and flow, including selected wording in the About, Projects, AI Toolkit and Health Innovation East pages. Mitigation proposal: run a short final copy pass focused only on grammar, concrete outcomes and reducing abstract phrasing.
- Low: accessibility is acceptable but can be polished. Mitigation proposal: remove low-value `aria-label` attributes from plain `div` elements and add intrinsic image dimensions to logo images to reduce layout shift risk.
