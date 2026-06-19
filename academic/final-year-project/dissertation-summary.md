# Dissertation summary

## Background

Brugada syndrome is a rare inherited arrhythmia syndrome. It is not safely understood from routine hospital coding alone because diagnosis and risk interpretation depend on specialist ECG findings, symptoms, family history and genetic evidence. This made it a useful context for testing how far routine health-data trajectories can support exploratory research without being treated as a diagnostic substitute.

## Aim

My dissertation investigated whether pre-sequencing ICD-10 encoded hospital trajectories could support retrospective, governance-bound stratification inside an SCN5A-related Brugada-suspect research context.

## Data context

The work used linked hospital-trajectory information inside a secure, genomics-linked research environment. Cohort counts, tables, raw extracts, model outputs or disclosure-sensitive results have been withheld.

## Methods

The project involved:

- cohort construction and temporal censoring around a sequencing index point
- feature engineering from hospital episode sources (EHR)
- grouped phenotype and utilisation-style feature design
- model comparison across interpretable baseline approaches
- leakage control and split-first preprocessing discipline
- documentation of target definitions, exclusions, limitations and governance boundaries

## Results

 Hospital-coded trajectories were useful for constructing research features and asking structured questions, but the evidence did not support clinical classification or practical diagnostic use. The careful methodological choice allowed this negative result to inform exact identification of the cause of failure to classify. This allowed baseline tests of future-methods that addressed these problems and showed promise for further work.

## Discussion

The project shows how rare-disease evidence work can be technically interesting while still requiring restraint. Routine data can help frame research questions and reveal possible pathway signals, but it cannot replace clinician-adjudicated phenotype data, ECG evidence, family-history interpretation or external validation.

## Limitations

- small and imbalanced rare-disease context
- routine hospital codes are incomplete and source-dependent
- no external validation
- no causal proof from promoter-target modelling

## Relevance

This project is relevant to health innovation, evidence judgement and biomedical data because it shows how I handle complex evidence under constraints by defining the question, tracing decisions, explaining limitations and resisting unsupported claims.
