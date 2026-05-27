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
    description: 'Biomedical science, healthcare strategy and evidence-led innovation.',
    imageAlt: 'Social preview card for Jubileejoy Zirebwa professional portfolio.'
  },
  {
    slug: 'about',
    path: '/about/',
    eyebrow: 'Profile',
    title: 'About Jubileejoy Zirebwa',
    description: 'Biomedical science, health innovation placement work, secure research and early toxicology data experience.',
    imageAlt: 'Social preview card for the About page.'
  },
  {
    slug: 'case-studies',
    path: '/case-studies/',
    eyebrow: 'Selected work',
    title: 'Case studies',
    description: 'Healthcare strategy, AI governance, market analysis and biomedical data case studies.',
    imageAlt: 'Social preview card for selected case studies.'
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
    description: 'Secure genomics-linked hospital trajectory analysis with governance, reproducibility and limitations boundaries.',
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
    eyebrow: 'Project themes',
    title: 'Projects',
    description: 'Connected project routes across healthcare strategy, biomedical data and exploratory evidence-methods thinking.',
    imageAlt: 'Social preview card for project themes.'
  },
  {
    slug: 'skills',
    path: '/skills/',
    eyebrow: 'Skills',
    title: 'Skills',
    description: 'Healthcare strategy, evidence synthesis, AI governance, data analysis and clear professional writing.',
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
