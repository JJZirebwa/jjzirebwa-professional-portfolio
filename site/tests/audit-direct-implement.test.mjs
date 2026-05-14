import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(__dirname, '..');
const distRoot = path.join(siteRoot, 'dist');

const readBuiltPage = (relativePath) => {
  const filePath = relativePath.endsWith('.html')
    ? path.join(distRoot, relativePath)
    : path.join(distRoot, relativePath, 'index.html');

  return readFileSync(filePath, 'utf8');
};

test('audit direct-implement routes render the expected upgraded content and structure', async (t) => {
  execFileSync('npm', ['run', 'build'], {
    cwd: siteRoot,
    stdio: 'pipe'
  });

  await t.test('home page uses the stronger role-alignment copy and Astro asset output', () => {
    const html = readBuiltPage('');

    assert.match(
      html,
      /I work at the point where biomedical evidence has to become a real healthcare decision: testing product claims against evidence quality, pathway fit, governance constraints, stakeholder priorities and what still needs to be proved\./
    );
    assert.match(html, /My strongest public evidence comes from a full-year Health Innovation East placement/);
    assert.match(html, /src="\/_astro\//);
    assert.doesNotMatch(html, /src="\/images\/jubileejoy-zirebwa-headshot\.jpg"/);
  });

  await t.test('case-study pages include breadcrumbs, summary facts, and ORION copy updates', () => {
    const hieHtml = readBuiltPage('case-studies/health-innovation-east');
    const marketHtml = readBuiltPage('case-studies/market-intelligence');
    const fypHtml = readBuiltPage('case-studies/final-year-project');

    assert.match(hieHtml, /<nav class="breadcrumbs" aria-label="Breadcrumbs">/);
    assert.match(hieHtml, /Role<\/dt>/);
    assert.match(hieHtml, /Outputs<\/dt>/);
    assert.match(hieHtml, /My role combined independently owned deliverables with co-authored advisory work\./);
    assert.match(hieHtml, /"@type":"BreadcrumbList"/);

    assert.match(
      marketHtml,
      /I turned noisy market data into reusable decision support: structured company lists, competitor matrices, funding and maturity signals, evidence comparisons, and pathway-fit questions that colleagues could use quickly\./
    );
    assert.match(
      fypHtml,
      /The main contribution is not a deployable classifier\. It is a biologically and numerically honest account of what hospital trajectories can and cannot reveal in a rare-disease, weak-signal setting\./
    );
  });

  await t.test('about and 404 pages expose the new recovery and academic trajectory signals', () => {
    const aboutHtml = readBuiltPage('about');
    const notFoundHtml = readBuiltPage('404.html');

    assert.match(
      aboutHtml,
      /Interim transcript currently supports a First-class trajectory, with final classification still subject to official confirmation\./
    );
    assert.match(notFoundHtml, /Best places to start/);
    assert.match(notFoundHtml, /Health Innovation East/);
    assert.match(notFoundHtml, /About my profile/);
  });
});
