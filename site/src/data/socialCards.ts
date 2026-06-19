export interface SocialCard {
  slug: string;
  path: string;
  eyebrow: string;
  title: string;
  description: string;
  imageAlt: string;
}

export const socialCards = [
  {
    slug: 'home',
    path: '/',
    eyebrow: 'Professional portfolio',
    title: 'Jubileejoy "JJ" Zirebwa',
    description: 'First Class Biomedical Science graduate across genomics, health data science, healthcare innovation and evidence-led strategy.',
    imageAlt: 'Social preview card for Jubileejoy Zirebwa professional portfolio.'
  },
  {
    slug: 'about',
    path: '/about/',
    eyebrow: 'Profile',
    title: 'About Jubileejoy Zirebwa',
    description: 'Biomedical Science graduate profile across genomics, applied health data work, healthcare innovation and evidence.',
    imageAlt: 'Social preview card for the About page.'
  },
  {
    slug: 'academic',
    path: '/academic/',
    eyebrow: 'Academic profile',
    title: 'Academic profile',
    description: 'First Class Biomedical Science record, selected marks and protected transcript access.',
    imageAlt: 'Social preview card for the academic profile.'
  },
  {
    slug: 'case-studies',
    path: '/case-studies/',
    eyebrow: 'Experience',
    title: 'Parent case studies',
    description: 'Experience-level pages across final-year project, health innovation placement and biomedical research internship.',
    imageAlt: 'Social preview card for parent experience case studies.'
  },
  {
    slug: 'health-innovation-east',
    path: '/case-studies/health-innovation-east/',
    eyebrow: 'Commercial placement',
    title: 'Health Innovation East',
    description: 'One-year NHS-facing commercial health innovation placement across evidence, market intelligence and adoption logic.',
    imageAlt: 'Social preview card for the Health Innovation East case study.'
  },
  {
    slug: 'ai-medtech-toolkit',
    path: '/case-studies/ai-medtech-toolkit/',
    eyebrow: 'AI/MedTech governance',
    title: 'AI Toolkit',
    description: 'Practical internal guidance-support material for AI/MedTech evidence, governance and implementation questions.',
    imageAlt: 'Social preview card for the AI Toolkit case study.'
  },
  {
    slug: 'market-intelligence',
    path: '/case-studies/market-intelligence/',
    eyebrow: 'Market and competitors',
    title: 'Market intelligence',
    description: 'Reusable market and competitor analysis shaped around evidence quality, pathway fit and maturity signals.',
    imageAlt: 'Social preview card for the Market Intelligence case study.'
  },
  {
    slug: 'final-year-project',
    path: '/case-studies/final-year-project/',
    eyebrow: 'Academic research',
    title: 'Final-year project',
    description: '83/100 dissertation component, secure genomics-linked hospital trajectory analysis and technical pipeline.',
    imageAlt: 'Social preview card for the final-year project case study.'
  },
  {
    slug: 'consoneai-dioscor',
    path: '/case-studies/consoneai-dioscor/',
    eyebrow: 'Research internship',
    title: 'ConsoneAI / DioScor',
    description: 'High-level toxicology data mapping and structured data-preparation work in a proprietary platform context.',
    imageAlt: 'Social preview card for the ConsoneAI and DioScor case study.'
  },
  {
    slug: 'projects',
    path: '/projects/',
    eyebrow: 'Projects',
    title: 'Projects',
    description: 'Contained deliverables and methods linked to parent experiences.',
    imageAlt: 'Social preview card for project deliverables and methods.'
  },
  {
    slug: 'skills',
    path: '/skills/',
    eyebrow: 'Skills',
    title: 'Skills',
    description: 'Health innovation strategy, evidence synthesis, AI governance, data analysis and clear professional writing.',
    imageAlt: 'Social preview card for skills and working strengths.'
  },
  {
    slug: 'now',
    path: '/now/',
    eyebrow: 'Current direction',
    title: 'Now',
    description: 'Current focus areas, active questions and the direction Jubileejoy Zirebwa is sharpening next.',
    imageAlt: 'Social preview card for the Now page.'
  },
  {
    slug: 'cv',
    path: '/cv/',
    eyebrow: 'CV',
    title: 'General portfolio CV',
    description: 'General CV for Biomedical Science, genomics-linked health data work and healthcare innovation roles.',
    imageAlt: 'Social preview card for the CV page.'
  },
  {
    slug: 'documents',
    path: '/documents/',
    eyebrow: 'Documents',
    title: 'Documents',
    description: 'Selected public and protected portfolio documents, including CV, transcript and dissertation overview.',
    imageAlt: 'Social preview card for selected documents.'
  },
  {
    slug: 'contact',
    path: '/contact/',
    eyebrow: 'Contact',
    title: 'Contact',
    description: 'Role scope, location and professional contact details for Jubileejoy Zirebwa.',
    imageAlt: 'Social preview card for contact and role scope.'
  }
] satisfies SocialCard[];

const normalizePath = (path: string) => {
  if (path === '') return '/';
  return path.endsWith('/') ? path : `${path}/`;
};

export const getSocialCardByPath = (path: string) =>
  socialCards.find((card) => card.path === normalizePath(path)) ?? socialCards[0];
