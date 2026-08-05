import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(__dirname, '..');
const readSiteFile = (relativePath) => readFileSync(path.join(siteRoot, relativePath), 'utf8');

const pageFiles = (directory) => readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
  const entryPath = path.join(directory, entry.name);
  return entry.isDirectory() ? pageFiles(entryPath) : entry.name.endsWith('.astro') ? [entryPath] : [];
});

test('the More menu has an opaque defined surface', () => {
  const css = readSiteFile('src/styles/global.css');
  const menuRules = css.match(/\.more-nav nav\s*\{([\s\S]*?)\n\}/)?.[1] ?? '';

  assert.match(menuRules, /background:\s*var\(--surface\);/);
  assert.doesNotMatch(menuRules, /--paper/);
});

test('final-year project figures use Astro image metadata while retaining their descriptions', () => {
  const page = readSiteFile('src/pages/case-studies/final-year-project.astro');

  assert.match(page, /import\s*\{\s*Image\s*\}\s*from\s*['"]astro:assets['"];/);
  assert.match(page, /import analyticalDesign from ['"]\.\.\/\.\.\/assets\/images\/fyp\/analytical-design\.png['"];/);
  assert.match(page, /<Image\s+src=\{figure\.src\}\s+alt=\{figure\.alt\}\s+widths=\{\[480,\s*760,\s*1120\]\}\s+sizes=/);
  assert.doesNotMatch(page, /<img\s+src=\{figure\.src\}/);

  for (const text of [
    'Analytical design diagram for the final-year project.',
    'Analysis design: cohort, hospital-event features, model comparison and interpretation boundary.',
    'Random forest feature stability chart across repeated splits.',
    'Feature-stability review helped test whether signal was stable enough to discuss.'
  ]) {
    assert.match(page, new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('portfolio links that open a new tab include a screen-reader cue', () => {
  const pagesRoot = path.join(siteRoot, 'src/pages');

  const violations = [];
  for (const pagePath of pageFiles(pagesRoot)) {
    const page = readFileSync(pagePath, 'utf8');
    for (const match of page.matchAll(/<a\b[^>]*>[\s\S]*?<\/a>/g)) {
      if (!/target=["']_blank["']/.test(match[0])) continue;
      if (!match[0].includes('<NewTabCue')) violations.push(path.relative(siteRoot, pagePath));
    }
  }

  assert.deepEqual(violations, []);
});
