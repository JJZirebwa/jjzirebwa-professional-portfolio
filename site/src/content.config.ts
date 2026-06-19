import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const editorialVariants = [
  'current-vector',
  'adoption-pathway',
  'market-landscape',
  'governance-lifecycle',
  'genomics-ml-pipeline',
  'toxicity-workflow',
  'weak-signal-methods'
] as const;

const iconNames = ['strategy', 'governance', 'market', 'data', 'research', 'evidence', 'academic', 'contact', 'writing'] as const;

const caseStudies = defineCollection({
  loader: glob({
    base: './src/content/case-studies',
    pattern: '**/*.json'
  }),
  schema: z.object({
    order: z.number().int().nonnegative(),
    slug: z.string(),
    icon: z.enum(iconNames),
    eyebrow: z.string(),
    title: z.string(),
    pageTitle: z.string().optional(),
    kicker: z.string(),
    summary: z.string(),
    cardText: z.string(),
    cardMeta: z.array(z.string()),
    homeFeatureOrder: z.number().int().positive().optional(),
    routeContext: z.object({
      order: z.number().int().positive(),
      title: z.string(),
      description: z.string(),
      meta: z.array(z.string())
    }).optional(),
    facts: z.array(z.object({
      label: z.string(),
      value: z.string()
    })),
    skills: z.array(z.string()),
    boundary: z.string().optional(),
    visualVariant: z.enum(editorialVariants).optional(),
    contextLogoKey: z.enum(['health-innovation-east', 'aru', 'genomics-england']).optional(),
    contextLogoAlt: z.string().optional(),
    contextLogoLabel: z.string().optional(),
    contextLogoNote: z.string().optional(),
    related: z.array(z.object({
      href: z.string(),
      label: z.string()
    })),
    sections: z.array(z.object({
      heading: z.string(),
      body: z.string().optional(),
      items: z.array(z.string()).optional()
    }))
  })
});

const projectContexts = defineCollection({
  loader: glob({
    base: './src/content/project-contexts',
    pattern: '**/*.json'
  }),
  schema: z.object({
    order: z.number().int().nonnegative(),
    kind: z.enum(['card', 'exploratory-strand']),
    icon: z.enum(iconNames).optional(),
    eyebrow: z.string(),
    title: z.string(),
    href: z.string().optional(),
    text: z.string().optional(),
    cardMeta: z.array(z.string()),
    lead: z.string().optional(),
    boundary: z.string().optional(),
    items: z.array(z.string()).optional(),
    visualVariant: z.enum(editorialVariants).optional()
  })
});

const nowUpdates = defineCollection({
  loader: glob({
    base: './src/content/now-updates',
    pattern: '**/*.json'
  }),
  schema: z.object({
    date: z.coerce.date(),
    title: z.string(),
    summary: z.string(),
    href: z.string().optional(),
    category: z.string()
  })
});

export const collections = {
  'case-studies': caseStudies,
  'project-contexts': projectContexts,
  'now-updates': nowUpdates
};
