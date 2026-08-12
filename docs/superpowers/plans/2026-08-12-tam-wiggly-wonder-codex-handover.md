# Tam / Wiggly Wonder Codex Handover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify one self-contained zip that Tam can hand to a fresh Codex session together with only the exact paths to her website and personal repositories.

**Architecture:** Build an ignored delivery tree with a portable core of generic skills and a quarantined library of sanitised JJ/ORION source patterns. A manifest-driven bootstrap prompt makes Tam's Codex audit her two repositories, local renders and live deployment before it adapts or installs anything. Standard-library validation, checksum verification and a cold-start simulation prove that the archive is complete, portable and independent of this conversation.

**Tech Stack:** Markdown, JSON-compatible YAML, CSV, Python 3 standard library, POSIX shell utilities, `zip`, Codex `SKILL.md` conventions, primary-source web research.

## Global Constraints

- The approved design is `docs/superpowers/specs/2026-08-12-tam-wiggly-wonder-codex-handover-design.md`.
- Create delivery artefacts only under `private/handover/tam-wiggly-wonder/`; this ignored directory must not be force-added to Git.
- Treat `/Users/jjzirebwa/Documents/my_type_outs/GitHub/ORION` and globally installed skills as read-only evidence.
- Do not alter JJ's portfolio site, ORION or global skill installation.
- Preserve all unrelated modified files in the working tree.
- Do not include Being and Being Well, private writing samples, private audit output, secrets, tokens, credentials or absolute local paths in the archive.
- Do not redistribute third-party content unless its licence permits it; use concise concept extraction plus official links otherwise.
- Superpowers is the required process layer and ECC is the required domain/execution layer when matching triggers apply in Tam's future sessions.
- Tam's Codex, not this implementation, decides which supplied patterns are installed, adapted, merged, deferred or rejected after repository inspection.
- Consequential actions in Tam's session require Tam's approval: global instruction writes, external installation, accounts, analytics/tracking, recurring automation activation, deployment, outreach and privacy-sensitive decisions.
- Generated source-pattern files must say `DO NOT INSTALL AS-IS` near the top.
- Every installable skill directory contains one valid `SKILL.md`; supporting detail belongs in `references/` and every relative reference must resolve.
- The final archive must require only the zip, the website-repository path and the personal-repository path.
- Because `private/` is intentionally ignored, task checkpoints are recorded in `verification/PACK_VALIDATION.md`; only this implementation-plan document is committed.

## File and responsibility map

```text
private/handover/tam-wiggly-wonder/
├── tam-wiggly-wonder-codex-handover/
│   ├── START_HERE.md                         # Human/agent archive entry point
│   ├── TAM_CODEX_HANDOVER_PROMPT.md          # Full cold-start execution prompt
│   ├── handover-manifest.yaml                # JSON-compatible YAML inventory and policy
│   ├── LICENSES_AND_PROVENANCE.md             # Derivation and redistribution boundaries
│   ├── SHA256SUMS                             # Generated last; excludes itself
│   ├── portable-core/
│   │   ├── cross-repo-venture-reconciler/
│   │   ├── commercial-website-audit-assessor/
│   │   ├── live-local-site-quality-sweep/
│   │   ├── form-and-conversion-integrity/
│   │   ├── public-claim-boundary/
│   │   ├── final-publication-validator/
│   │   ├── venture-opportunity-radar/
│   │   ├── commercial-copy-humaniser/
│   │   ├── personal-voice-curator/
│   │   └── repo-owned-automation-designer/
│   ├── source-patterns-do-not-install-as-is/
│   │   ├── INDEX.md
│   │   ├── jj-writing-style-concepts.md
│   │   ├── human-writing-and-anti-slop.md
│   │   ├── audit-assessment-state-model.md
│   │   ├── opportunity-and-growth-scan.md
│   │   ├── orion-claim-and-export-controls.md
│   │   ├── target-preparation-action-boundaries.md
│   │   ├── portfolio-orion-bridge-pattern.md
│   │   ├── portfolio-audit-system-pattern.md
│   │   ├── nexus-weekly-monthly-synthesis-pattern.md
│   │   └── speech-mascot-motion-media-pattern.md
│   ├── automation-blueprints/
│   │   ├── RUN_PROTOCOL.md
│   │   ├── AUTOMATION_ACTIVATION_CHECKLIST.md
│   │   ├── site-form-integrity/PROMPT.md
│   │   ├── cross-repo-reconciliation/PROMPT.md
│   │   ├── venture-opportunity-radar/PROMPT.md
│   │   └── periodic-synthesis/PROMPT.md
│   ├── research/
│   │   ├── wiggly-wonder-live-observations.md
│   │   ├── website-launch-and-operations-checklist.md
│   │   ├── integration-candidate-register.md
│   │   └── sources.md
│   ├── templates/
│   │   ├── cross-repo-contract.md
│   │   ├── existing-audit-proposal-ledger.csv
│   │   ├── route-inventory.csv
│   │   ├── skill-migration-decision-log.csv
│   │   ├── integration-candidate-register.csv
│   │   ├── automation-run-index.csv
│   │   └── voice-sample-register.csv
│   └── verification/
│       ├── validate_pack.py                   # Standard-library structural/leak validator
│       ├── expected-inventory.txt
│       ├── cold-start-smoke-test.md
│       └── PACK_VALIDATION.md
├── TAM_CODEX_HANDOVER_PROMPT.md               # Convenience copy beside archive
└── tam-wiggly-wonder-codex-handover.zip        # Final delivery archive
```

The ten core skills are small routing/workflow units. Each owns one decision surface and refers to a narrowly scoped schema in its `references/` directory where needed. Source patterns are explanatory migration evidence, not active skills. Automation blueprints are repository-owned prompt candidates, not active Codex schedules.

---

### Task 1: Create the archive contract and validator

**Files:**

- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/verification/validate_pack.py`
- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/verification/expected-inventory.txt`
- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/START_HERE.md`
- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/handover-manifest.yaml`
- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/LICENSES_AND_PROVENANCE.md`
- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/verification/PACK_VALIDATION.md`

**Interfaces:**

- Consumes: the approved design and the exact file map above.
- Produces: `validate_pack.py ROOT [--allow-incomplete] -> exit 0|1`; a JSON-compatible YAML manifest with `pack`, `requirements`, `policies`, `entrypoints`, `artefacts` and `research_sources` keys; an inventory consumed by the validator and Task 9.

- [ ] **Step 1: Write the validator before the pack exists**

Implement these exact functions using only the Python 3 standard library:

```python
def load_manifest(root: Path) -> dict[str, object]: ...
def load_expected_inventory(root: Path) -> list[str]: ...
def parse_skill_frontmatter(path: Path) -> dict[str, str]: ...
def check_inventory(root: Path, expected: list[str], allow_incomplete: bool) -> list[str]: ...
def check_manifest(root: Path, manifest: dict[str, object]) -> list[str]: ...
def check_skills(root: Path) -> list[str]: ...
def check_relative_markdown_links(root: Path) -> list[str]: ...
def check_forbidden_content(root: Path) -> list[str]: ...
def check_source_pattern_labels(root: Path) -> list[str]: ...
def main(argv: list[str]) -> int: ...
```

`check_forbidden_content` must reject `/Users/`, `jjzirebwa`, `Being and Being Well` outside the explicit exclusion sentence in `jj-writing-style-concepts.md`, common secret assignments, and any file larger than 1 MiB. `check_skills` must require kebab-case skill directories, YAML frontmatter containing only `name` and `description`, a matching `name`, and a description that states when to use the skill. The command prints `PASS: pack validation` on success and one `ERROR: <message>` line per failure.

- [ ] **Step 2: Run the validator to prove the scaffold is absent**

Run:

```bash
python3 private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/verification/validate_pack.py private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover
```

Expected: non-zero exit with missing manifest/inventory errors.

- [ ] **Step 3: Create the root contract files**

`START_HERE.md` must contain these operational sections:

```markdown
# Wiggly Wonder Codex handover
## The one instruction Tam gives Codex
## What this archive is
## Safe opening procedure
## Required inputs
## Trust and approval boundaries
## Continue with the embedded prompt
```

The one instruction must be exactly:

```text
Read this Wiggly Wonder Codex handover zip and execute it. My website repository is <exact path> and my personal repository is <exact path>.
```

The manifest must be valid JSON as well as YAML 1.2 and use this exact top-level shape:

```json
{
  "format_version": 1,
  "pack": {
    "pack_id": "tam-wiggly-wonder-codex-handover",
    "recipient": "Tam / Wiggly Wonder Academy",
    "entrypoint": "START_HERE.md",
    "bootstrap_prompt": "TAM_CODEX_HANDOVER_PROMPT.md"
  },
  "requirements": {
    "inputs": ["website_repository_path", "personal_repository_path"],
    "capability_families": ["superpowers", "ecc"]
  },
  "policies": {
    "inspect_before_install": true,
    "source_patterns_installable": false,
    "external_actions_require_approval": true
  },
  "entrypoints": [],
  "artefacts": [],
  "research_sources": []
}
```

Populate `entrypoints`, `artefacts` and `research_sources` with real pack-relative records. Classify all ten core skill directories as `portable_core` and every source pattern as `adaptation_source_do_not_install`.

`LICENSES_AND_PROVENANCE.md` must separate: JJ-authored derived material; public factual observations; third-party names and links; excluded private material; and a rule that no third-party skill text is redistributed without licence permission.

- [ ] **Step 4: Populate the complete expected inventory**

Write one sorted relative path per line for every file in the file map, excluding `SHA256SUMS`, the outer prompt copy and the zip. The validator treats missing paths as warnings only under `--allow-incomplete` and errors otherwise.

- [ ] **Step 5: Validate the contract in incomplete mode**

Run:

```bash
python3 private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/verification/validate_pack.py private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover --allow-incomplete
```

Expected: `PASS: pack validation` plus clearly labelled missing-inventory warnings; no manifest, frontmatter, path-leak or provenance errors.

- [ ] **Step 6: Record the Task 1 checkpoint**

Append the date, command, exit code and observed warning count under `## Task checkpoints` in `verification/PACK_VALIDATION.md`. Do not stage ignored delivery files.

---

### Task 2: Build cross-repository, website and form audit skills

**Files:**

- Create: `portable-core/cross-repo-venture-reconciler/SKILL.md`
- Create: `portable-core/cross-repo-venture-reconciler/references/bridge-contract.md`
- Create: `portable-core/commercial-website-audit-assessor/SKILL.md`
- Create: `portable-core/commercial-website-audit-assessor/references/proposal-schema.md`
- Create: `portable-core/live-local-site-quality-sweep/SKILL.md`
- Create: `portable-core/live-local-site-quality-sweep/references/route-matrix.md`
- Create: `portable-core/form-and-conversion-integrity/SKILL.md`
- Create: `portable-core/form-and-conversion-integrity/references/form-contract.md`

**Interfaces:**

- Consumes: two repository roots, applicable `AGENTS.md` files, live URL, local render command, prior audit records and route/form inventories.
- Produces: `cross-repo-contract.md`, `existing-audit-proposal-ledger.csv`, `route-inventory.csv`, an evidence-backed form contract and a site audit whose proposals use the state model defined below.

- [ ] **Step 1: Create the cross-repository reconciliation skill**

Its description must trigger when a public website and a private/personal venture repository must be compared. The workflow must enforce:

```text
discover instructions -> locate canonical evidence -> classify public/private/unknown
-> propose ownership contract -> detect drift -> record provenance
-> request approval before cross-repo writes
```

The bridge schema must define: subject, canonical repository/path, public projection path, allowed flow, prohibited flow, freshness class, last verified date, conflict rule and owner. Repository silence is `unknown`, never proof that a fact is absent.

- [ ] **Step 2: Create the audit-assessment skill**

Use these independent fields in the proposal schema:

```text
proposal_id
proposal_stance: direct | discuss | monitor
historical_state: new | repeated | evolved | superseded
assessment_decision: implement | discuss | defer | superseded | already_satisfied | drop
implementation_state: not_started | in_progress | verified | failed | blocked
```

The skill must ingest Tam's existing audit before generating recommendations, deduplicate by meaning rather than wording, and require evidence, value, dependencies, risk and rationale for every decision.

- [ ] **Step 3: Create the live/local/source site sweep skill**

The route matrix reference must require route, audience, source file, status, desktop render, mobile render, title, description, canonical, social image, primary CTA, internal links, accessibility status, performance note and discrepancy fields. The skill must compare source, local and live surfaces and must not infer live behaviour from source alone.

It must cover all items in design Phase 3, including apex/`www` consistency, robots, sitemap, 404, form path, analytics/consent, structured data, generic-LLM visual patterns and conditional checklist items.

- [ ] **Step 4: Create the form and conversion integrity skill**

The form contract must define:

```text
form identifier, target audience, fields, required flags, validation, honeypot/spam controls,
query prefill, submission destination, success state, failure state, notification owner,
retention/deletion rule, privacy notice, analytics events, last test, and unresolved risk
```

The skill must test the rendered form without submitting real personal data unless Tam authorises a controlled test. It must distinguish markup detection, successful delivery and notification receipt as separate states.

- [ ] **Step 5: Validate the four skills**

Run `quick_validate.py` separately on every directory:

```bash
python3 /Users/jjzirebwa/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-directory>
```

Then run the pack validator with `--allow-incomplete`. Expected: each skill reports valid; no unresolved relative link or forbidden-content error.

- [ ] **Step 6: Record the Task 2 checkpoint**

Record the four validation results and pack-validator exit code in `verification/PACK_VALIDATION.md`.

---

### Task 3: Build claim, publication, copy and personal-voice skills

**Files:**

- Create: `portable-core/public-claim-boundary/SKILL.md`
- Create: `portable-core/public-claim-boundary/references/claim-ledger.md`
- Create: `portable-core/final-publication-validator/SKILL.md`
- Create: `portable-core/final-publication-validator/references/release-gate.md`
- Create: `portable-core/commercial-copy-humaniser/SKILL.md`
- Create: `portable-core/commercial-copy-humaniser/references/audit-checklist.md`
- Create: `portable-core/personal-voice-curator/SKILL.md`
- Create: `portable-core/personal-voice-curator/references/voice-profile-schema.md`

**Interfaces:**

- Consumes: approved venture evidence, page purpose, audience, fixed strings, legal copy and Tam-approved writing samples.
- Produces: claim ledger, release gate, human-copy audit, provisional/confirmed voice profile and voice-sample register.

- [ ] **Step 1: Create the public-claim boundary skill**

Use these claim categories:

```text
DIRECT_EVIDENCE
ADJACENT_EVIDENCE
REASONABLE_INFERENCE
FUTURE_DIRECTION
REQUIRES_CONSENT
DO_NOT_PUBLISH
```

Track evidence readiness separately as `verified_now`, `verification_required`, `fallback_required`, `removed`. The skill must preserve confident commercial writing while preventing unsupported outcomes, inflated partnerships, invented testimonials, unverified research claims and leakage from the personal repository.

- [ ] **Step 2: Create the final-publication validator**

The release gate must cover route identity, names, contact details, links, claim-ledger consistency, privacy/consent dependencies, metadata, accessibility, form state, build/test result, local/live discrepancy, asset licence and deployment approval. The skill validates prose after the voice pass without restyling it; any later prose correction reruns only the changed passage through the personal voice skill.

- [ ] **Step 3: Create the commercial-copy humaniser**

Its audit checklist must detect generic admiration, abstract noun piles, visible research scaffolding, false urgency, unearned superlatives, repetitive three-part lists, identical sentence rhythm, generic EdTech claims, adult copy addressed ambiguously to children, and fake social proof. It must preserve facts, necessary SEO terms, safety wording and Tam's confirmed register.

- [ ] **Step 4: Create the personal-voice curator**

The profile schema must contain:

```yaml
profile_version: 1
owner: Tam
approved_samples: []
registers: {}
confirmed_traits: []
provisional_traits: []
rejected_traits: []
fixed_language: []
preservation_rules: []
review_history: []
```

The skill must start from no inferred voice, analyse only samples Tam approves, distinguish confirmed from provisional traits, support multiple registers, invite correction and never contain or reconstruct JJ's benchmark. It runs last after evidence, substantive drafting and humanisation.

- [ ] **Step 5: Validate and scan the four skills**

Run `quick_validate.py` on all four directories, then:

```bash
rg -n -i 'jjzirebwa|/Users/|being and being well|career(s)? orion' private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/portable-core
```

Expected: no matches. Run the pack validator in incomplete mode and expect exit 0.

- [ ] **Step 6: Record the Task 3 checkpoint**

Record skill validation, leak-scan result and pack-validator result in `verification/PACK_VALIDATION.md`.

---

### Task 4: Build opportunity and repository-owned automation skills

**Files:**

- Create: `portable-core/venture-opportunity-radar/SKILL.md`
- Create: `portable-core/venture-opportunity-radar/references/opportunity-register.md`
- Create: `portable-core/repo-owned-automation-designer/SKILL.md`
- Create: `portable-core/repo-owned-automation-designer/references/run-protocol.md`

**Interfaces:**

- Consumes: current venture priorities, repository change state, past proposals, official sources, available capacity and existing automations.
- Produces: scored but prose-justified opportunity proposals, rejection history, thin schedule definitions, repository-owned prompts and fixed run-output contracts.

- [ ] **Step 1: Create the venture opportunity radar**

The opportunity register must include stable ID, lane, observed need, evidence, audience, expected value, effort, dependency, route to action, freshness, duplication result, decision and next review. Search lanes must include pilots, schools/nurseries, family/community programmes, research/knowledge exchange, grants/accelerators, content, partnerships and creative product demonstrations.

The skill must generate a small number of tailored proposals, such as a mascot demonstration only when current product state and audience need support it. It must reject generic weekly novelty and keep an explicit rejected/monitor register.

- [ ] **Step 2: Create the automation designer**

Its run protocol reference must define:

```text
lane_id, purpose, sources, freshness gate, change gate, allowed reads, prohibited actions,
proposal_id format, dedupe sources, output directory, fixed output headings,
failure behaviour, escalation rule, activation approval and last protocol version
```

The skill must keep scheduler prompts thin, put logic in repository-owned versioned files, keep private run output ignored, and treat deployment, outreach, tracking and account changes as proposal-only.

- [ ] **Step 3: Validate both skills**

Run `quick_validate.py`, pack validation in incomplete mode and the absolute-path leak scan. Expected: all pass and no matches.

- [ ] **Step 4: Record the Task 4 checkpoint**

Record both skill validation results and the pack-validator result in `verification/PACK_VALIDATION.md`.

---

### Task 5: Create the quarantined source-pattern library

**Files:**

- Create every file under `source-patterns-do-not-install-as-is/` from the file map.

**Interfaces:**

- Consumes: read-only JJ global skills, portfolio audit protocols and ORION skills/bridges.
- Produces: sanitised concept documents with `Source concepts`, `Why it may help Tam`, `What must not migrate`, `Adaptation questions`, `Candidate outputs` and `Provenance` sections.

- [ ] **Step 1: Create the source-pattern index**

Place this warning immediately under the title:

```markdown
> **DO NOT INSTALL AS-IS.** These are migration references. Tam's Codex must inspect her repositories, dependencies, triggers and existing skills, then record an install/adapt/merge/defer/reject decision.
```

The index must list all ten patterns and explain that concepts are transferable while identity, paths, output nouns and assumptions are not.

- [ ] **Step 2: Extract the writing and assessment patterns**

`jj-writing-style-concepts.md` must explain final-authority ordering, register selection, fact/fixed-string preservation, read-aloud checks and confirmed-versus-provisional voice rules. It may mention the excluded benchmark only in this exact sentence:

```text
JJ's private benchmark titled “Being and Being Well” is intentionally excluded and must not be requested, reconstructed or inferred.
```

`human-writing-and-anti-slop.md` must separate generic anti-slop concepts from JJ-specific preferences. `audit-assessment-state-model.md` must preserve independent proposal, history, assessment and implementation states.

- [ ] **Step 3: Extract opportunity, claim and target patterns**

Describe search lanes, hard rejection gates, route value, growth signals, evidence classifications, claim readiness, final export gates, stable target identities, preparation-before-action and default-unsent boundaries. Replace career-application nouns with venture-neutral examples and state that Tam's Codex chooses Wiggly Wonder-specific categories.

- [ ] **Step 4: Extract bridge and automation patterns**

Describe public/private ownership, read-only evidence sources, export allowlists, ignored outputs, thin schedules, stable proposal IDs, fixed run contracts, weekly briefs and periodic synthesis. Do not include JJ's actual private paths, target names or unpublished run content.

- [ ] **Step 5: Extract optional creative-media patterns**

Cover speech/voiceover disclosure, accessible audio alternatives, mascot animation, Motion/Rive/Remotion candidates, interaction budgets, reduced motion, asset rights and the rule that a creative demonstration needs a product/audience hypothesis rather than novelty alone.

- [ ] **Step 6: Validate quarantine and leakage**

Run:

```bash
rg -L 'DO NOT INSTALL AS-IS' private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/source-patterns-do-not-install-as-is/*.md
rg -n '/Users/|jjzirebwa|projects/careers_orion|projects/nexus_orion' private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/source-patterns-do-not-install-as-is
```

Expected: the first command returns no files and the second returns no matches. Run pack validation in incomplete mode and expect exit 0.

- [ ] **Step 7: Record the Task 5 checkpoint**

Record quarantine-label coverage, leak scan and validator result.

---

### Task 6: Create automation blueprints and repository templates

**Files:**

- Create all files under `automation-blueprints/` and `templates/` from the file map.

**Interfaces:**

- Consumes: the two automation-related portable skills and proposal state schema.
- Produces: four inactive repository-owned prompt lanes, one shared protocol, one activation checklist and seven fillable but non-placeholder operational templates.

- [ ] **Step 1: Write the shared run protocol**

Require each run to record:

```text
run ID, lane ID, protocol version, started/completed timestamps, repositories read,
source freshness, source changes, checks executed, proposal IDs, duplicates,
failures, approvals required, prohibited actions avoided, and next review
```

Classify statements as verified fact, inference, proposal, unknown or stale. A run with no changes still executes human/audience simulation where the lane requires it.

- [ ] **Step 2: Write the four lane prompts**

Every `PROMPT.md` must be a thin pointer to the shared run protocol plus lane-specific sources, checks, change gate, output headings and proposal prefix:

```text
WW-SITE-####
WW-XREPO-####
WW-OPP-####
WW-SYN-####
```

The synthesis lane reads prior run indexes and does not repeat unchanged proposals. None of the prompts contains a hard-coded schedule or machine path.

- [ ] **Step 3: Write the activation checklist**

Require repository discovery, command verification, output ignore rules, owner, cadence rationale, time zone, duplicate check, privacy review, dry run, Tam approval and post-activation verification before any recurring task is created.

- [ ] **Step 4: Create the Markdown and CSV templates**

Use these exact CSV headers:

```csv
proposal_id,title,source_audit,proposal_stance,historical_state,assessment_decision,implementation_state,evidence,value,dependencies,risk,rationale,last_verified
route,audience,source_file,local_url,live_url,status,desktop_render,mobile_render,title,description,canonical,social_image,primary_cta,internal_links,accessibility,performance,discrepancy,last_checked
skill_name,source_kind,current_equivalent,trigger_overlap,dependency_status,scope,decision,rationale,validation,owner,last_reviewed
candidate,category,observed_need,official_source,licence,data_access,permissions,maintenance,cost,lock_in,overlap,benefit,decision,rationale,last_verified
run_id,lane_id,protocol_version,started_at,completed_at,source_state,change_gate,proposal_ids,failures,approval_required,output_path
sample_id,register,source_path_or_description,owner_approved,allowed_uses,confirmed_traits,provisional_traits,rejected_traits,reviewed_at
```

The cross-repo Markdown contract must contain canonical ownership, allowed flow, prohibited flow, freshness, conflict resolution, write approvals and privacy boundary sections.

- [ ] **Step 5: Validate blueprints and templates**

Check every CSV has one header and no example personal data. Run pack validation in incomplete mode. Expected: exit 0.

- [ ] **Step 6: Record the Task 6 checkpoint**

Record prompt count, CSV header check and validator result.

---

### Task 7: Write the Wiggly Wonder and integration research dossier

**Files:**

- Create all four files under `research/` from the file map.

**Interfaces:**

- Consumes: live observations already gathered, current official documentation and primary repositories.
- Produces: dated observations separated from recommendations, a checklist reconciliation, a candidate register and a directly linked source list.

- [ ] **Step 1: Reverify unstable live facts**

Check the live homepage and all discoverable routes, `robots.txt`, `sitemap.xml`, a nonexistent route, the join form and apex/`www` redirect. Record observation time, surface and uncertainty. Do not submit the form.

- [ ] **Step 2: Write the live-observation dossier**

Separate `Observed strengths`, `Observed gaps to verify in source`, `Conditional ideas`, `Form observations`, `Audience journeys`, `Privacy-sensitive questions` and `Known external recognition`. Cite the ARU and ESBF primary pages for public recognition and label social-network claims by source type.

- [ ] **Step 3: Reconcile the launch checklist**

Classify every item JJ supplied as `observed present`, `missing/high relevance`, `needs source verification`, `conditional`, or `not currently justified`. Explain why an arbitrary count of five FAQs, breadcrumbs, maps, LocalBusiness schema, reviews, a sticky CTA and a response promise should not be installed blindly.

- [ ] **Step 4: Build the integration candidate register**

Research and record at minimum:

```text
Superpowers, ECC, Vercel skills ecosystem, Anthropic frontend-design,
UI UX Pro Max, design-systems-to-agent-skills, shadcn MCP,
Chrome DevTools MCP, Playwright MCP, Figma MCP, 21st.dev MCP,
React Bits, Motion, Rive, Remotion, Lighthouse CI, axe-core,
Netlify Forms, Google Analytics 4, Google Search Console,
Google Tag Manager/Consent Mode, PostHog, Sentry, Semrush and Cloudflare
```

For each, record official source, owner, observed Wiggly Wonder need, candidate use, licence/terms status, data/permission concerns, overlap and initial stance. Installed-plugin availability is not evidence that the integration is appropriate.

- [ ] **Step 5: Write the source register**

Use direct links to primary documentation for Next.js metadata/robots/sitemap/not-found, Google Search structured data and sitemaps, ICO Children's Code, Netlify Forms, Google consent/analytics and every researched tool. Record access date `2026-08-12` and distinguish official documentation from organisation-controlled announcements.

- [ ] **Step 6: Check citations and claims**

Run a link extraction pass, confirm no search-results URLs are used, and ensure no legal conclusion is presented as advice. Run pack validation in incomplete mode and expect exit 0.

- [ ] **Step 7: Record the Task 7 checkpoint**

Record live routes checked, source count, candidate count and validator result.

---

### Task 8: Write the self-contained Tam Codex bootstrap prompt

**Files:**

- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/TAM_CODEX_HANDOVER_PROMPT.md`
- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/verification/cold-start-smoke-test.md`
- Create: `private/handover/tam-wiggly-wonder/TAM_CODEX_HANDOVER_PROMPT.md`

**Interfaces:**

- Consumes: the manifest, all portable skills, source-pattern index, automation protocol, research dossier and two repository paths.
- Produces: a phase-gated Tam-owned migration/audit session that can continue without JJ's conversation or filesystem.

- [ ] **Step 1: Write the prompt identity and authority block**

The prompt must tell Codex it is facilitating Tam's own system, not reproducing JJ's. It must define the only required variables:

```text
WWA_WEBSITE_REPO=<exact path supplied by Tam>
WWA_PERSONAL_REPO=<exact path supplied by Tam>
HANDOVER_ROOT=<directory containing this extracted prompt; resolve automatically>
```

If either repository path is missing, ask for it. Resolve `HANDOVER_ROOT` from the prompt/manifest location and never require Tam to supply it separately.

- [ ] **Step 2: Encode Phases 0–8 from the design**

Repeat every phase as imperative instructions with explicit inputs, outputs, approval gates and completion checks. Require applicable skills to be read completely before use. Require current web research for unstable software, legal, analytics and platform facts.

- [ ] **Step 3: Encode persistent Superpowers/ECC enforcement**

Require Codex to verify active availability, inspect inherited/global/project `AGENTS.md` files, propose a non-destructive merged diff, obtain Tam's approval for writes outside the two repositories, and verify from a fresh task context that matching future work routes through Superpowers and ECC. Do not permit replacing Tam's existing operating rules wholesale.

- [ ] **Step 4: Encode repository and website audit outputs**

Require a repository map, cross-repo contract, full route/render matrix, existing-audit reconciliation ledger, website management audit, skill-migration decision log, integration register, automation proposal, approval register and final verification report. Require screenshots or equivalent local visual evidence for every route at desktop and mobile sizes.

- [ ] **Step 5: Encode decision and action boundaries**

Make repository inspection, local testing, rendering, research and proposal creation authorised. Require explicit Tam approval before global writes, third-party installation, external accounts, tracking, deployment, scheduled task activation, form submission with data, outreach or legal/privacy conclusions. Require dirty-worktree preservation and no silent cross-repo writes.

- [ ] **Step 6: Encode migration curation and creative research**

Require install/adapt/merge/defer/reject for every pack artefact. Require trigger-collision, dependency, licence, provenance, security and scope checks. Instruct Codex to search beyond the supplied candidates for advanced human-created frontend and website-operation skills that address observed features, while rejecting generic visual novelty.

- [ ] **Step 7: Encode completion behaviour**

The session must not stop after producing an audit. It should continue through the approved safe local implementation work, verify outcomes and leave persistent repository-owned state. If it reaches an approval boundary, it must present the exact proposed change, evidence, impact and rollback path rather than losing context.

- [ ] **Step 8: Write and execute the cold-start smoke-test rubric**

The rubric must answer yes/no with cited prompt headings for:

```text
Can the session start with only zip + two repo paths?
Does it inspect both repos before adapting skills?
Does it find and reconcile the existing audit?
Does it inspect source + local desktop/mobile + live pages?
Does it verify persistent Superpowers/ECC routing?
Does it protect dirty worktrees and private material?
Does it gate external, tracking, deployment and privacy-sensitive actions?
Does it assess every supplied skill/pattern rather than blindly install it?
Does it leave durable cross-repo, audit, automation and verification state?
Does it avoid dependence on this conversation or JJ's filesystem?
```

All answers must be `yes` before Task 9.

- [ ] **Step 9: Copy the prompt beside the future zip**

Copy without modification, compare SHA-256 values and record the match in `verification/PACK_VALIDATION.md`.

---

### Task 9: Complete full validation and package the archive

**Files:**

- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/SHA256SUMS`
- Modify: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/verification/PACK_VALIDATION.md`
- Create: `private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover.zip`

**Interfaces:**

- Consumes: the complete delivery tree and expected inventory.
- Produces: a deterministic-content zip, verified extracted copy, final validation record and clickable delivery artefacts.

- [ ] **Step 1: Run full structural validation**

Run without `--allow-incomplete`:

```bash
python3 private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover/verification/validate_pack.py private/handover/tam-wiggly-wonder/tam-wiggly-wonder-codex-handover
```

Expected: `PASS: pack validation` and exit 0.

- [ ] **Step 2: Run independent leak and archive-content scans**

Search all files for absolute paths, usernames, secret patterns, private benchmark text beyond the one permitted exclusion sentence, unresolved relative links and source-pattern files missing the quarantine warning. Expected: no prohibited matches.

- [ ] **Step 3: Generate internal checksums**

From the archive root, hash every regular file except `SHA256SUMS`, sort by relative path and write `SHA256SUMS`. Immediately verify every entry. Record command and exit code.

- [ ] **Step 4: Create the zip**

From `private/handover/tam-wiggly-wonder/`, create `tam-wiggly-wonder-codex-handover.zip` containing exactly one top-level `tam-wiggly-wonder-codex-handover/` directory. Exclude `.DS_Store`, editor files, caches and the outer convenience prompt.

- [ ] **Step 5: Inspect the zip before extraction**

Run `unzip -l`, compare its file list with `expected-inventory.txt` plus `SHA256SUMS`, and confirm there is no path traversal entry, absolute path or extra top-level entry.

- [ ] **Step 6: Perform a clean extraction test**

Create a temporary directory with `mktemp -d`, extract the zip there, rerun `validate_pack.py` against the extracted root and verify `SHA256SUMS`. Do not delete the test directory until results have been recorded; afterwards remove only that exact temporary path.

- [ ] **Step 7: Perform the cold-start simulation**

Read only the extracted `START_HERE.md`, manifest and prompt, then complete the rubric in `cold-start-smoke-test.md` without using conversation memory. If any rubric answer is not `yes`, update the prompt, regenerate checksums/zip and repeat Steps 1–7.

- [ ] **Step 8: Finalise the validation record**

Record:

```text
pack ID and version
archive SHA-256
file count
portable skill count
source-pattern count
primary-source count
structural validator result
skill validator results
leak-scan result
checksum result
clean-extraction result
cold-start rubric result
known limitations
delivery paths
```

- [ ] **Step 9: Confirm repository isolation**

Run `git status --short` and verify no generated handover file is staged or visible because `private/` remains ignored. Confirm the user's unrelated modifications are unchanged.

- [ ] **Step 10: Deliver the archive and inspection prompt**

Return clickable absolute links to the zip, the outer prompt copy, validation report and committed design/plan. State that no Tam repository, external account, automation or deployment was modified.

---

## Self-review checklist

- [ ] Map every design section to at least one task and record no uncovered requirement.
- [ ] Search this plan case-insensitively for unresolved placeholder language and replace it with exact content or acceptance criteria.
- [ ] Verify path, field, proposal-prefix and function names are consistent across tasks.
- [ ] Confirm ignored delivery artefacts are never added to Git.
- [ ] Confirm the final cold-start needs only the archive and two repository paths.
