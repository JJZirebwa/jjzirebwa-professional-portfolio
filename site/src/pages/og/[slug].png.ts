import type { APIRoute, GetStaticPaths } from 'astro';
import { Resvg } from '@resvg/resvg-js';
import { socialCards, type SocialCard } from '../../data/socialCards';

interface StaticPath {
  params: { slug: string };
  props: { card: SocialCard };
}

const cardWidth = 1200;
const cardHeight = 630;

const escapeXml = (value: string) =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');

const wrapText = (text: string, maxLineLength: number) => {
  const lines: string[] = [];
  let current = '';

  for (const word of text.split(/\s+/)) {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxLineLength && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }

  if (current) lines.push(current);
  return lines;
};

const textLines = (lines: string[], x: number, y: number, lineHeight: number, fontSize: number, weight = 500) =>
  lines
    .map((line, index) => (
      `<text x="${x}" y="${y + index * lineHeight}" font-family="Inter, Avenir, Helvetica, Arial, sans-serif" font-size="${fontSize}" font-weight="${weight}" fill="#223127">${escapeXml(line)}</text>`
    ))
    .join('');

const renderCardSvg = (card: SocialCard) => {
  const titleLines = wrapText(card.title, 28).slice(0, 2);
  const descriptionLines = wrapText(card.description, 58).slice(0, 3);

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg width="${cardWidth}" height="${cardHeight}" viewBox="0 0 ${cardWidth} ${cardHeight}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${cardWidth}" height="${cardHeight}" fill="#f7f6f1"/>
  <rect x="48" y="48" width="1104" height="534" rx="28" fill="#ffffff"/>
  <rect x="48" y="48" width="1104" height="534" rx="28" fill="none" stroke="#d8d5cb" stroke-width="2"/>
  <path d="M840 48h312v534H840z" fill="#e7efe9"/>
  <path d="M844 582c104-68 146-152 126-252-22-114 26-198 144-252" fill="none" stroke="#9db7a6" stroke-width="24" stroke-linecap="round" opacity="0.75"/>
  <path d="M920 138c68 38 108 86 120 144 12 62-4 124-48 186" fill="none" stroke="#c3a55f" stroke-width="12" stroke-linecap="round" opacity="0.8"/>
  <circle cx="1014" cy="242" r="66" fill="#ffffff" stroke="#9db7a6" stroke-width="10"/>
  <circle cx="1014" cy="242" r="18" fill="#c3a55f"/>
  <text x="96" y="128" font-family="Inter, Avenir, Helvetica, Arial, sans-serif" font-size="30" font-weight="700" letter-spacing="0" fill="#667568">${escapeXml(card.eyebrow.toUpperCase())}</text>
  ${textLines(titleLines, 96, 254, 82, 72, 800)}
  ${textLines(descriptionLines, 96, 410, 44, 34, 500)}
  <text x="96" y="530" font-family="Inter, Avenir, Helvetica, Arial, sans-serif" font-size="28" font-weight="700" fill="#223127">jubileejoyzirebwa.com</text>
</svg>`;
};

export const getStaticPaths: GetStaticPaths = () =>
  socialCards.map((card) => ({
    params: { slug: card.slug },
    props: { card }
  })) satisfies StaticPath[];

export const GET: APIRoute = ({ props }) => {
  const card = props.card as SocialCard;
  const renderer = new Resvg(renderCardSvg(card), {
    fitTo: {
      mode: 'width',
      value: cardWidth
    }
  });

  const png = new Uint8Array(renderer.render().asPng());

  return new Response(png, {
    headers: {
      'Content-Type': 'image/png',
      'Cache-Control': 'public, max-age=31536000, immutable'
    }
  });
};
