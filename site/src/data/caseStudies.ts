export interface CaseStudyFact {
  label: string;
  value: string;
}

export interface CaseStudyCardMetadata {
  slug: string;
  href: string;
  icon: string;
  eyebrow: string;
  title: string;
  summary: string;
  text: string;
  cardMeta: string[];
  facts: CaseStudyFact[];
}

const caseStudies: CaseStudyCardMetadata[] = [
  {
    slug: 'health-innovation-east',
    href: '/case-studies/health-innovation-east/',
    icon: 'strategy',
    eyebrow: 'Commercial placement',
    title: 'Health Innovation East',
    summary: 'A one-year commercial placement working across NHS-facing innovation, evidence synthesis, market intelligence, competitor analysis, pathway fit and adoption logic.',
    text: 'One-year NHS-facing commercial health innovation placement across evidence, market intelligence, pathway fit and adoption reasoning.',
    cardMeta: ['One-year placement', 'Owned deliverables', 'NHS-facing innovation'],
    facts: [
      {
        label: 'Role',
        value: 'Commercial health innovation placement work across triage, market intelligence, adoption logic and toolkit authoring.'
      },
      {
        label: 'Timeframe',
        value: '2024-2025'
      },
      {
        label: 'Context',
        value: 'Health Innovation East placement in an NHS-facing innovation environment.'
      },
      {
        label: 'Work mode',
        value: 'Independently owned deliverables plus co-authored advisory support.'
      },
      {
        label: 'Outputs',
        value: 'Evidence briefs, competitor packs, market scans, QOF-alignment material and an internal AI Toolkit.'
      },
      {
        label: 'Why it matters',
        value: 'Shows I can turn product, pathway and evidence questions into decision-ready analysis.'
      }
    ]
  },
  {
    slug: 'ai-medtech-toolkit',
    href: '/case-studies/ai-medtech-toolkit/',
    icon: 'governance',
    eyebrow: 'AI/MedTech governance',
    title: 'AI Toolkit',
    summary: 'A practical internal toolkit I authored to turn AI/MedTech regulation, evidence, data governance and implementation considerations into usable advisory guidance.',
    text: 'Practical internal guidance-support material for advisory work, not formal regulatory or clinical-safety advice.',
    cardMeta: ['Authored toolkit', 'Governance guidance', 'Internal advisory'],
    facts: [
      {
        label: 'Role',
        value: 'Author of an internal AI/MedTech toolkit for innovation advisory work.'
      },
      {
        label: 'Timeframe',
        value: 'Placement period, 2024-2025'
      },
      {
        label: 'Context',
        value: 'Health Innovation East internal governance and advisory support.'
      },
      {
        label: 'Work mode',
        value: 'Independently authored guidance-support material.'
      },
      {
        label: 'Outputs',
        value: 'Topic summaries, checklists and practical governance framing for advisory conversations.'
      },
      {
        label: 'Why it matters',
        value: 'Shows I can translate dense governance requirements into usable decision support.'
      }
    ]
  },
  {
    slug: 'market-intelligence',
    href: '/case-studies/market-intelligence/',
    icon: 'market',
    eyebrow: 'Market and competitors',
    title: 'Market intelligence',
    summary: 'Market-intelligence and competitor-analysis work across health technologies, including company search, horizon scanning, evidence comparison and adoption-readiness framing.',
    text: 'Market-analysis, competitor-landscape and horizon-scanning work shaped around evidence quality, pathway fit and commercial maturity.',
    cardMeta: ['Reusable decision support', 'Competitor matrices', 'CB Insights buildout'],
    facts: [
      {
        label: 'Role',
        value: 'Market-intelligence and competitor-analysis support for live innovation questions.'
      },
      {
        label: 'Timeframe',
        value: 'Placement period, 2024-2025'
      },
      {
        label: 'Context',
        value: 'Health Innovation East commercial innovation and market analysis work.'
      },
      {
        label: 'Work mode',
        value: 'Independently authored analyses and reusable research buildout.'
      },
      {
        label: 'Outputs',
        value: 'Structured company lists, competitor matrices, horizon scans and sector snapshots.'
      },
      {
        label: 'Why it matters',
        value: 'Shows I can turn noisy market evidence into reusable commercial judgement.'
      }
    ]
  },
  {
    slug: 'final-year-project',
    href: '/case-studies/final-year-project/',
    icon: 'data',
    eyebrow: 'Academic research',
    title: 'Final-year project',
    summary: 'A Biomedical Science dissertation using secure, genomics-linked hospital trajectory analysis in a Brugada-suspect research context.',
    text: 'Secure genomics-linked hospital trajectory analysis with explicit governance, reproducibility and limitations boundaries.',
    cardMeta: ['Secure research context', 'Leakage-controlled', 'Limitations-led'],
    facts: [
      {
        label: 'Role',
        value: 'Biomedical Science dissertation using secure, genomics-linked hospital trajectory analysis.'
      },
      {
        label: 'Timeframe',
        value: 'Final-year dissertation, 2025-2026'
      },
      {
        label: 'Context',
        value: 'Secure, genomics-linked research environment with disclosure and governance constraints.'
      },
      {
        label: 'Work mode',
        value: 'Independently designed and executed within approved research boundaries.'
      },
      {
        label: 'Outputs',
        value: 'Governance-aware methodology, feature reasoning, model comparisons and a limitations-led dissertation account.'
      },
      {
        label: 'Why it matters',
        value: 'Shows research discipline under weak-signal, disclosure-bound conditions.'
      }
    ]
  },
  {
    slug: 'consoneai-dioscor',
    href: '/case-studies/consoneai-dioscor/',
    icon: 'research',
    eyebrow: 'Research internship',
    title: 'ConsoneAI / DioScor',
    summary: 'A short research internship involving toxicology data mapping and structured data preparation in a dose-toxicity platform context.',
    text: 'High-level toxicology data mapping and structured data-preparation work in a dose-toxicity platform context.',
    cardMeta: ['Six-week internship', 'Data mapping', 'Proprietary context'],
    facts: [
      {
        label: 'Role',
        value: 'Research intern supporting toxicology data mapping and structured data preparation.'
      },
      {
        label: 'Timeframe',
        value: 'Six-week internship'
      },
      {
        label: 'Context',
        value: 'Dose-toxicity platform work kept high level because of proprietary boundaries.'
      },
      {
        label: 'Work mode',
        value: 'Support-based research and data-preparation work.'
      },
      {
        label: 'Outputs',
        value: 'Mapping notes, structured non-public data outputs and a poster presentation.'
      },
      {
        label: 'Why it matters',
        value: 'Shows early data discipline in messy biological evidence contexts.'
      }
    ]
  }
];

export { caseStudies };

export const getCaseStudy = (slug: string) => {
  const caseStudy = caseStudies.find((item) => item.slug === slug);

  if (!caseStudy) {
    throw new Error(`Unknown case study slug: ${slug}`);
  }

  return caseStudy;
};
