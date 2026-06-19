# Final-year project

## Summary

I completed a full-year Biomedical Science dissertation using secure, genomics-linked hospital trajectory analysis in a Brugada-suspect context. This project is presented here as research-only academic work, not as a clinical tool.

The dissertation write-up component was awarded **83/100**. The final award transcript records the wider Undergraduate Project module as **82, A, 30 credits**.

## Working title

Retrospective machine-learning stratification of a Brugada-suspect cohort using ICD-10 encoded hospital trajectories.

## Research problem

Brugada syndrome is a rare inherited arrhythmia syndrome where clinical interpretation depends on ECG pattern, symptoms, family history and genetic context. Routine hospital-coded data is incomplete and cannot replace clinical diagnosis. This project asked whether pre-sequencing hospital trajectories could support careful retrospective stratification inside a Brugada-suspect cohort without overstating clinical utility.

## Methods at high level

- I worked within an approved secure research environment.
- I used temporally censored hospital episode data before the sequencing index date.
- I engineered grouped ICD/OPCS and utilisation-style features.
- I used observability controls to avoid treating unequal record history as invisible noise.
- I compared baseline model families, including logistic regression, random forest and a shallow neural network.
- I maintained governance boundaries around target definitions, leakage control, reproducibility and limitations.
- I treated subgroup/fairness and service-impact questions as reporting and governance considerations, not as clinical deployment claims.

## Repository handling

This repository includes the project overview, selected document assets, selected exported figures and a technical pipeline representation. It does not include private research-environment paths, access material, participant-level data, restricted source exports or raw patient-level files.

## Artefacts

- Website page: `/case-studies/final-year-project/`
- Pipeline: [pipeline/README.md](pipeline/README.md)
- Dissertation overview PDF: `site/public/documents/Jubileejoy_Zirebwa_Dissertation_Overview.pdf`

## Skills demonstrated

- secure health-data research discipline
- rare-disease evidence judgement
- feature-engineering and model-evaluation literacy
- reproducibility and decision-trace documentation
- claim-boundary discipline in biomedical AI/data contexts
- scientific writing under constraints
