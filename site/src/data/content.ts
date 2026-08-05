import type { ImageMetadata } from 'astro';
import { getCollection, type CollectionEntry } from 'astro:content';
import logoAru from '../assets/images/logo-aru.png';
import logoGenomicsEngland from '../assets/images/logo-genomics-england.png';
import logoHealthInnovationEast from '../assets/images/logo-health-innovation-east.webp';

export type EditorialPanelVariant =
  | 'current-vector'
  | 'adoption-pathway'
  | 'market-landscape'
  | 'governance-lifecycle'
  | 'genomics-ml-pipeline'
  | 'toxicity-workflow'
  | 'weak-signal-methods';

type CaseStudyEntry = CollectionEntry<'case-studies'>;
type CaseStudyData = CaseStudyEntry['data'];
type ContextLogoKey = NonNullable<CaseStudyData['contextLogoKey']>;

const contextLogoMap: Record<ContextLogoKey, ImageMetadata> = {
  'health-innovation-east': logoHealthInnovationEast,
  aru: logoAru,
  'genomics-england': logoGenomicsEngland
};

export interface CaseStudyContextRoute {
  order: number;
  title: string;
  description: string;
  meta: string[];
}

export interface CaseStudyContent {
  slug: string;
  href: string;
  order: number;
  icon: CaseStudyData['icon'];
  eyebrow: string;
  title: string;
  pageTitle: string;
  kicker: string;
  summary: string;
  cardText: string;
  cardMeta: string[];
  homeFeatureOrder?: number;
  routeContext?: CaseStudyContextRoute;
  facts: CaseStudyData['facts'];
  skills: string[];
  boundary?: string;
  visualVariant?: EditorialPanelVariant;
  contextLogo?: {
    src: ImageMetadata;
    alt: string;
    label: string;
    note?: string;
  };
  related: CaseStudyData['related'];
  sections: CaseStudyData['sections'];
}

export interface ProjectContextCard {
  order: number;
  icon: string;
  eyebrow: string;
  title: string;
  href: string;
  text: string;
  cardMeta: string[];
}

export interface ProjectExploratoryStrand {
  eyebrow: string;
  title: string;
  lead: string;
  boundary: string;
  items: string[];
  visualVariant: EditorialPanelVariant;
}

const byOrder = <T extends { order: number }>(left: T, right: T) => left.order - right.order;

const normalizeCaseStudy = ({ data }: CaseStudyEntry): CaseStudyContent => ({
  slug: data.slug,
  href: `/case-studies/${data.slug}/`,
  order: data.order,
  icon: data.icon,
  eyebrow: data.eyebrow,
  title: data.title,
  pageTitle: data.pageTitle ?? data.title,
  kicker: data.kicker,
  summary: data.summary,
  cardText: data.cardText,
  cardMeta: data.cardMeta,
  homeFeatureOrder: data.homeFeatureOrder,
  routeContext: data.routeContext,
  facts: data.facts,
  skills: data.skills,
  boundary: data.boundary,
  visualVariant: data.visualVariant,
  contextLogo: data.contextLogoKey && data.contextLogoAlt && data.contextLogoLabel
    ? {
        src: contextLogoMap[data.contextLogoKey],
        alt: data.contextLogoAlt,
        label: data.contextLogoLabel,
        note: data.contextLogoNote
      }
    : undefined,
  related: data.related,
  sections: data.sections
});

export const getCaseStudies = async () =>
  (await getCollection('case-studies'))
    .map(normalizeCaseStudy)
    .sort(byOrder);

export const getCaseStudy = async (slug: string) => {
  const caseStudies = await getCaseStudies();
  const caseStudy = caseStudies.find((item) => item.slug === slug);

  if (!caseStudy) {
    throw new Error(`Unknown case study slug: ${slug}`);
  }

  return caseStudy;
};

export const getHomeFeaturedCaseStudies = async () =>
  (await getCaseStudies())
    .filter((item) => item.homeFeatureOrder !== undefined)
    .sort((left, right) => (left.homeFeatureOrder ?? 0) - (right.homeFeatureOrder ?? 0));

export const getHomeContextRoutes = async () =>
  (await getCaseStudies())
    .filter((item) => item.routeContext)
    .sort((left, right) => (left.routeContext?.order ?? 0) - (right.routeContext?.order ?? 0));

export const getProjectContextCards = async (): Promise<ProjectContextCard[]> =>
  (await getCollection('project-contexts'))
    .filter((entry) => entry.data.kind === 'card')
    .map((entry) => ({
      order: entry.data.order,
      icon: entry.data.icon ?? 'evidence',
      eyebrow: entry.data.eyebrow,
      title: entry.data.title,
      href: entry.data.href ?? '/',
      text: entry.data.text ?? '',
      cardMeta: entry.data.cardMeta
    }))
    .sort(byOrder);

export const getProjectExploratoryStrand = async (): Promise<ProjectExploratoryStrand> => {
  const strand = (await getCollection('project-contexts')).find((entry) => entry.data.kind === 'exploratory-strand');

  if (!strand || !strand.data.lead || !strand.data.boundary || !strand.data.items || !strand.data.visualVariant) {
    throw new Error('Missing exploratory strand project context.');
  }

  return {
    eyebrow: strand.data.eyebrow,
    title: strand.data.title,
    lead: strand.data.lead,
    boundary: strand.data.boundary,
    items: strand.data.items,
    visualVariant: strand.data.visualVariant
  };
};
