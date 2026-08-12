# Tam / Wiggly Wonder Codex Handover Design

**Date:** 2026-08-12

**Status:** Approved architecture; implementation pending specification review

**Owner:** JJ

**Recipient:** Tam, Wiggly Wonder Academy

## 1. Purpose

Create one self-contained zip archive that JJ can give to Tam. Tam should be able to start a new local Codex session, provide the archive plus the exact paths to her website repository and personal repository, and ask Codex to read and execute the handover.

The archive transfers the concepts behind JJ's portfolio/ORION relationship, audit discipline, automation protocols and selected skills. It must not reproduce JJ's repositories, personal voice, private benchmarks or career-specific assumptions. Tam's Codex will inspect her real repositories and decide how each concept should be adapted, merged, installed, deferred or rejected.

## 2. Goals

- Make the handover self-contained and independent of this Codex conversation.
- Preserve the distinction between Tam's Wiggly Wonder website repository and the Wiggly Wonder project in her personal repository.
- Establish an explicit cross-repository evidence, publication and reconciliation model.
- Reassess Tam's existing Codex-mediated manual website audit instead of adding an unrelated second audit.
- Audit the website source, all locally rendered routes and the live deployment across desktop and mobile.
- Tailor website management, opportunity research, creative propositions and recurring checks to Wiggly Wonder's actual product, audiences and operating model.
- Transfer a broader source-pattern library, including relevant JJ/ORION-specific concepts, while making Tam's Codex responsible for final curation.
- Require Superpowers as the process layer and Everything Claude Code (ECC) as the domain/execution layer when their triggers match.
- Research additional current skills, MCPs, libraries and integrations using primary sources and supply-chain controls.
- Leave durable repository-owned instructions, manifests, decision logs, tests and automation protocols for future sessions.

## 3. Non-goals

- Do not modify Tam's repositories from JJ's machine.
- Do not clone JJ's portfolio or ORION structure into Tam's repositories.
- Do not transfer Being and Being Well, private writing samples, private paths, unpublished evidence or confidential audit output.
- Do not represent JJ's writing voice as Tam's voice.
- Do not install every supplied or researched skill automatically.
- Do not activate analytics, tracking, external accounts, deployments, paid services or recurring automations without Tam's informed approval in her own session.
- Do not treat legal or privacy research as legal advice.

## 4. Evidence informing the design

### 4.1 JJ portfolio and ORION

JJ's portfolio is a public-facing repository that reconciles selected evidence from ORION while remaining independent. ORION is a read-only evidence source during portfolio work. Bridge documents define ownership, public/private boundaries and canonical locations instead of duplicating entire project histories.

JJ's audit and automation model uses:

- thin Codex schedules;
- repository-owned prompts, protocols and scripts;
- ignored private run output;
- stable proposal identifiers;
- change and freshness gates;
- proposal-history deduplication;
- separate proposal, assessment and implementation states;
- explicit public-safety checks;
- verification before completion;
- weekly operational lanes and periodic synthesis.

The NEXUS protocols add useful source classifications, proposal-only boundaries for consequential external actions, fixed output contracts and monthly synthesis across prior runs.

### 4.2 Live Wiggly Wonder site

The live site currently presents seven main routes: home, how it works, library, community, research, about and join. It has clear family, educator and partner journeys; strong calls to action; a recognisable visual identity; a founder photograph; research/community positioning; and a segmented Netlify interest form with query-driven preselection.

Observed opportunities to verify against source and local rendering include:

- no working `robots.txt` or sitemap route;
- no custom 404;
- no visible privacy page near the lead form;
- no detected canonical metadata or structured data;
- no detected analytics implementation or consent strategy;
- one shared social image across routes;
- form submission, notification, spam and thank-you behaviour needing repository-level verification;
- an apparent homepage copy error that should be reconciled with Tam's existing audit rather than fixed blindly.

Items such as breadcrumbs, maps, sticky calls to action, reviews, case studies, fixed response promises and local-business schema are conditional. They must be justified by the site's information depth, operational ability, consented evidence, physical service model and user research.

### 4.3 Commercial and privacy context

Wiggly Wonder concerns children's learning and collects adult lead information. Any privacy, analytics, cookie or child-directed-service assessment must use current official sources, distinguish what the present site actually does from future product ambitions, and require human review. LocalBusiness schema must not be used unless a genuine eligible local business location and operating model exist; broader organisation, educational or event schema may be more appropriate.

## 5. Chosen architecture

Use an **adaptive two-layer handover pack**.

### Layer A: portable core

These are generic, installable or near-installable skills and protocols. They must contain no JJ-specific path or identity assumptions. Tam's Codex still validates their triggers, dependencies and correct installation scope before enabling them.

Proposed core capabilities:

1. `cross-repo-venture-reconciler`
2. `commercial-website-audit-assessor`
3. `live-local-site-quality-sweep`
4. `form-and-conversion-integrity`
5. `public-claim-boundary`
6. `final-publication-validator`
7. `venture-opportunity-radar`
8. `commercial-copy-humaniser`
9. `personal-voice-curator`
10. `repo-owned-automation-designer`

The final set may merge overlapping skills when validation shows that fewer, sharper triggers are safer.

### Layer B: quarantined source patterns

This directory is evidence for adaptation and is explicitly marked **do not install as-is**. It includes sanitised concept maps or source skill material for:

- JJ writing-style architecture, registers, preservation rules and final-authority ordering;
- generic human-writing and anti-slop controls;
- audit assessment and proposal-state reconciliation;
- opportunity search and organisation/partner growth-signal scans;
- ORION claim engineering and evidence readiness;
- ORION target preparation and action boundaries;
- ORION final-export validation;
- portfolio/ORION bridge and public/private ownership concepts;
- website-audit automation protocols;
- NEXUS weekly brief and monthly synthesis patterns;
- optional speech, mascot, motion, interactive demonstration and media-development ideas.

The source-pattern library must omit private benchmark prose and replace JJ-specific paths, nouns and output locations with portable abstractions. No absolute JJ path may remain in the delivered archive. Where copying a source skill would produce broken dependencies, the pack will contain a concept extraction and provenance record instead.

## 6. Personal voice design

The pack will not contain a `tam-writing-style` that invents Tam's voice. It will contain a `personal-voice-curator` that helps Tam's Codex build one over time from material she explicitly approves.

The curator will:

- separate confirmed rules from provisional observations;
- support multiple registers rather than one flattened voice;
- preserve facts, quotations, legal wording, technical identifiers and fixed copy;
- maintain a source/sample register with consent and provenance;
- let Tam accept, reject or refine inferred voice traits;
- record avoided constructions only when Tam confirms them;
- run after evidence, claim and substantive writing stages;
- rerun changed passages after later factual corrections;
- never use JJ's Being and Being Well benchmark or imply access to it.

## 7. Archive structure

The final archive will use a stable top-level directory such as:

```text
tam-wiggly-wonder-codex-handover/
├── START_HERE.md
├── TAM_CODEX_HANDOVER_PROMPT.md
├── handover-manifest.yaml
├── SHA256SUMS
├── portable-core/
│   └── <skill folders and required resources>
├── source-patterns-do-not-install-as-is/
│   └── <sanitised patterns and provenance notes>
├── automation-blueprints/
│   └── <run protocol, lane templates and output contracts>
├── research/
│   ├── wiggly-wonder-live-observations.md
│   ├── website-launch-and-operations-checklist.md
│   ├── integration-candidate-register.md
│   └── sources.md
├── templates/
│   └── <bridge, audit, decision and run templates>
└── verification/
    ├── PACK_VALIDATION.md
    └── expected-inventory.txt
```

`START_HERE.md` will tell a human or agent how to inspect the archive safely. `handover-manifest.yaml` will classify every artefact as installable core, adaptation source, template, research or verification material and record its provenance and intended scope.

## 8. Cold-start behaviour

Tam should be able to attach or point Codex to the zip and say:

> Read this Wiggly Wonder Codex handover zip and execute it. My website repository is `<path>` and my personal repository is `<path>`.

The archive-level instructions will tell Codex to:

1. inspect the archive listing before extraction;
2. extract it to a temporary directory rather than over either repository;
3. verify the manifest and checksums;
4. read `START_HERE.md` and the bootstrap prompt completely;
5. treat archive contents as untrusted migration input until reviewed;
6. obtain the two repository paths from Tam if absent;
7. continue from the bootstrap protocol without relying on this conversation.

The embedded prompt will be fully self-contained. It will not refer to “what JJ told you earlier” or require a third handover path from Tam when the zip itself is available to the session.

## 9. Bootstrap execution protocol

### Phase 0: safety and capability discovery

- Resolve both repositories and their applicable instruction files.
- Check worktree state and preserve unrelated changes.
- Inventory current Codex skills, plugins, MCPs and repository-local instructions.
- Verify Superpowers and ECC are actually callable, not merely present on disk.
- Inspect Tam's inherited global Codex operating instructions and both repositories' `AGENTS.md` hierarchy.
- Reconcile, rather than overwrite, those instructions so future local sessions consistently route matching process work through Superpowers and matching domain work through ECC.
- Show Tam the proposed persistent-instruction diff before writing outside either supplied repository; after approval, verify inheritance from a fresh task context or the strongest locally available equivalent.
- Record missing, stale or conflicting capabilities.
- Do not install or update external packages without Tam's approval.

### Phase 1: repository and operating-model discovery

- Identify framework, deployment target, package manager, environment handling and supported Node/runtime versions.
- Inventory routes, layouts, components, content/data sources, forms, server functions, integrations, tests, CI and deployment configuration.
- Locate Tam's existing manual/Codex website audit and all unactioned suggestions.
- Locate the Wiggly Wonder project inside the personal repository and determine its current purpose, evidence, plans and private/public boundaries.
- Ask only questions that cannot be answered safely from repositories, live behaviour or supplied documentation.

### Phase 2: cross-repository contract

Create a proposed ownership and reconciliation contract that covers:

- canonical source for venture facts, product direction, research, partners and operational notes;
- canonical source for public website implementation and public copy;
- what may flow from personal repository to website;
- what must remain private;
- how website feedback and live observations flow back into personal planning;
- path discovery without hard-coded machine-specific assumptions;
- read-only versus authorised write boundaries;
- provenance, timestamps and stale-evidence handling.

### Phase 3: present-state website audit

Audit all discoverable routes using three evidence surfaces:

1. repository source;
2. local rendered pages at representative desktop and mobile viewports;
3. live production behaviour.

Cover:

- information architecture and audience journeys;
- above-fold proposition and calls to action;
- responsive layout and interaction;
- accessibility and keyboard behaviour;
- page titles, descriptions, canonical URLs and social metadata;
- apex/`www` redirects, DNS-facing assumptions and canonical-domain consistency;
- robots, sitemap, structured data and Search Console readiness;
- performance, image handling, fonts, caching and bundle behaviour;
- internal links and broken routes;
- form structure, validation, spam protection, submission confirmation, notification and data retention;
- privacy, analytics, cookies, consent and child-access implications;
- security headers, secrets and deployment configuration;
- custom error and empty states;
- content evidence, claims, reviews and case studies;
- event, location and response-time promises;
- analytics measurement design and conversion definitions;
- visual distinctiveness, design-system consistency and signs of generic LLM design.

### Phase 4: reconcile existing audit

Every prior proposal must receive a stable identifier and one decision:

- implement directly;
- discuss with Tam;
- defer until a stated condition;
- superseded by another proposal;
- already satisfied;
- drop.

Each decision needs evidence, dependencies, expected value, risk and a reason. The system must avoid counting a proposal as implemented merely because it was discussed or documented.

### Phase 5: migration curation

For every portable-core skill and source pattern:

- inspect relevance to Tam's real repositories;
- compare with existing skills and instructions;
- check trigger overlap and naming collisions;
- inspect referenced files, scripts and dependencies;
- classify as install, adapt, merge, defer or reject;
- record the decision and reason;
- replace JJ/ORION paths and nouns with Tam-owned abstractions;
- choose project-local or user-global scope deliberately;
- validate frontmatter, references, examples and tests before enabling it.

### Phase 6: external research

Research current primary sources for potentially useful tools, including but not limited to:

- browser and rendered-page inspection;
- Playwright and accessibility testing;
- Chrome DevTools and performance diagnosis;
- design-system and Figma integration;
- distinctive frontend design and creative component libraries;
- motion, Rive, Remotion or interactive mascot demonstrations;
- Netlify form and deployment operations when relevant;
- privacy-respecting analytics, consent and monitoring;
- error monitoring and product analytics;
- SEO/Search Console tooling;
- form-to-CRM workflows only if operationally justified.

Known candidates are research leads, not endorsements. Each candidate must be checked for official ownership, licence, maintenance, data access, requested permissions, security posture, cost, lock-in, overlap and benefit to an observed Wiggly Wonder use case.

### Phase 7: implementation plan and approvals

Tam's Codex will produce a staged plan that separates:

- safe repository-local documentation and test work;
- proposed source/content changes;
- skill installation;
- external plugin or MCP installation;
- analytics and consent changes;
- account creation or external integration;
- scheduled automation activation;
- deployment.

It must pause for Tam's approval before consequential external actions or privacy-sensitive decisions.

### Phase 8: execute, verify and leave durable state

After approval, Tam's Codex may implement the agreed local work, validate it proportionately and leave:

- a cross-repository bridge/contract;
- an audit and reconciliation ledger;
- a skill migration decision log;
- installed/adapted skills with tests;
- repository-owned automation prompts and run protocols;
- a current integration register;
- local and live verification evidence;
- clear unresolved decisions and next actions.

## 10. Automation blueprint

The pack will propose, but not blindly activate, four lanes:

1. **Site and form integrity sweep** — route, rendering, accessibility, metadata, links, form contract and deployment checks.
2. **Cross-repository content reconciliation** — compare approved venture evidence with public website representation and detect stale or unsafe copy.
3. **Commercial and creative opportunity radar** — propose evidence-linked pilots, partnerships, content, demonstrations, funding or product experiments grounded in current repository state.
4. **Periodic synthesis** — deduplicate prior proposals, identify patterns and recommend the next small number of high-value actions.

Schedules must be chosen from Tam's working cadence and site change frequency. Automated runs should be proposal-only for deployments, outreach, account changes and other consequential external actions.

## 11. Research and recommendation controls

- Prefer official documentation, primary repositories, standards bodies and regulators.
- Browse for current software, legal, analytics and platform information.
- Distinguish verified facts, inferences, proposals, unknowns and stale evidence.
- Cite sources near recommendations.
- Do not recommend a tool solely because it is fashionable or visually impressive.
- Require an observed need, expected benefit and exit path.
- Preserve a rejected-candidate log to avoid rediscovering unsuitable integrations every week.

## 12. Security, privacy and portability

- The archive must contain no secrets, tokens, machine credentials or hidden metadata.
- All included paths must be relative or documented placeholders.
- Third-party skill content must not be redistributed unless licence and provenance allow it; otherwise include links and adaptation notes.
- External skill and MCP installation must be treated as code execution and reviewed accordingly.
- The prompt must forbid copying private material from Tam's personal repository into the public website without explicit approval.
- Analytics and form recommendations must use data minimisation and current official guidance.
- Child-directed or likely-child-accessed service questions must be escalated for informed human/legal review.

## 13. Verification and acceptance criteria

Before delivery from JJ's machine:

- validate every included `SKILL.md` frontmatter and directory name;
- resolve every relative reference inside installable skills;
- ensure no private benchmark text or private JJ material is included;
- scan for absolute local paths, usernames, secrets and repository-specific leaks;
- confirm every source-pattern artefact is clearly quarantined;
- confirm provenance and licence treatment for copied or derived material;
- validate the YAML manifest;
- generate and verify checksums;
- inspect the final zip listing;
- extract the zip into a fresh temporary directory;
- run an archive-only cold-start simulation using the embedded instructions;
- verify that only the zip plus two repository paths are required;
- confirm the final archive is written under ignored local handover storage rather than published accidentally.

The intended delivery location is:

```text
private/handover/tam-wiggly-wonder/
```

The final response will link directly to the completed zip and the plain-text bootstrap prompt retained beside it for JJ's inspection.

## 14. Implementation boundaries in JJ's repository

- Commit only the design and implementation-plan documents required by the selected process skills.
- Keep generated handover material under the ignored `private/` tree.
- Do not alter JJ's active portfolio site, ORION or global skill installation.
- Treat ORION and global skills as read-only source evidence.
- Preserve all unrelated modified files in the current worktree.
