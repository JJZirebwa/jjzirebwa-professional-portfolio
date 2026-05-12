# Dose-Toxicity Data Workflow

## Public-Facing Summary

This page describes a public-safe, high-level workflow for dose-toxicity data handling during the ConsoneAI/DioScor internship.

## Workflow

| Stage | Description |
|---|---|
| Source identification | Identify relevant toxicology and chemical data sources for extraction or comparison. |
| Data extraction | Pull relevant fields such as compound identifiers, organism, route, dose unit, test type and effect category where available. |
| Cleaning | Standardise missing values, split combined categories and remove unusable records where appropriate. |
| Mapping | Align source fields to high-level information needs without exposing proprietary schema. |
| Organisation | Produce structured Excel/CSV outputs for review and downstream use. |
| Communication | Summarise findings, gaps and workflow choices for research collaborators. |

## Limitations

- External source data can be inconsistent, incomplete and terminology-heavy.
- Public pages cannot include proprietary platform mappings, schemas or architecture.
- Raw extracted datasets are excluded from this repository.
- The internship work supported research/data preparation; it did not validate a drug-discovery model.

## Skills Demonstrated

- data cleaning and structuring
- toxicity-domain vocabulary
- source-to-need mapping
- workflow documentation
- communication of data limitations
