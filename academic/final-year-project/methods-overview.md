# Methods overview

## Public-facing summary

This project used a secure, retrospective research design to study whether hospital trajectories could contribute to Brugada-suspect stratification.

## Approach

| Method area | Public-safe description |
|---|---|
| Study design | Retrospective machine-learning analysis in a secure research environment. |
| Cohort construction | Governance-controlled Brugada-suspect research cohort with temporal indexing. |
| Data source type | Pre-sequencing hospital episode trajectories, treated as partial and noisy clinical-history evidence. |
| Feature engineering | Grouped ICD/OPCS and utilisation-style features with policy-driven inclusion controls. |
| Modelling | Comparison of baseline model families, including interpretable and non-linear approaches. |
| Evaluation | Repeated evaluation with attention to imbalance, instability and calibration limits. |
| Governance | Claim boundaries, decision logs, leakage controls and public non-disclosure of sensitive outputs. |

## What I deliberately avoided

- treating hospital codes as direct Brugada diagnosis
- presenting model outputs as clinical decision support
- implying validated clinical utility
- turning exploratory promoter biology into causal proof

## What this shows

The methods work shows the discipline I tried to bring to the project by identifying what the available data can and cannot answer, building a proportionate workflow and reporting limitations as part of the result.
