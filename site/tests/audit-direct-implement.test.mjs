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

  await t.test('home page uses the stronger role-alignment copy, CTA journey, and Astro asset output', () => {
    const html = readBuiltPage('');

    assert.match(
      html,
      /messy middle between evidence and adoption/
    );
    assert.match(html, /My strongest evidence comes from a full-year Health Innovation East placement/);
    assert.match(html, /src="\/_astro\//);
    assert.doesNotMatch(html, /src="\/images\/jubileejoy-zirebwa-headshot\.jpg"/);
    assert.match(
      html,
      /<div class="action-row">\s*<a class="button" href="\/case-studies\/health-innovation-east\/">Start with strongest evidence<\/a>\s*<a class="button secondary" href="\/now\/">See what I(?:&#39;|')m focused on now<\/a>\s*<a class="button secondary" href="\/contact\/">Get in touch<\/a>/
    );
    assert.match(html, /Choose a first route through the work/);
    assert.match(html, /Healthcare strategy context/);
    assert.match(html, /AI\/MedTech governance exposure/);
    assert.match(html, /Research and data exposure/);
    assert.match(html, /What I(?:&#39;|')m focused on now/);
    assert.match(html, /data-editorial-variant="evidence-journey"/);
    assert.match(html, /Evidence to decision/);
    assert.doesNotMatch(html, /panel-block/);
  });

  await t.test('case-study pages include breadcrumbs, summary facts, ORION copy updates, and editorial variants', () => {
    const hieHtml = readBuiltPage('case-studies/health-innovation-east');
    const marketHtml = readBuiltPage('case-studies/market-intelligence');
    const fypHtml = readBuiltPage('case-studies/final-year-project');
    const toolkitHtml = readBuiltPage('case-studies/ai-medtech-toolkit');
    const consoneHtml = readBuiltPage('case-studies/consoneai-dioscor');

    assert.match(hieHtml, /<nav class="breadcrumbs" aria-label="Breadcrumbs">/);
    assert.match(hieHtml, /Role<\/dt>/);
    assert.match(hieHtml, /Outputs<\/dt>/);
    assert.match(hieHtml, /My role combined independently owned deliverables with co-authored advisory work\./);
    assert.match(hieHtml, /"@type":"BreadcrumbList"/);
    assert.match(hieHtml, /data-editorial-variant="adoption-pathway"/);
    assert.match(hieHtml, /Adoption pathway/);
    assert.match(hieHtml, /Triage/);

    assert.match(
      marketHtml,
      /I turned noisy market data into reusable decision support: structured company lists, competitor matrices, funding and maturity signals, evidence comparisons, and pathway-fit questions that colleagues could use quickly\./
    );
    assert.match(marketHtml, /data-editorial-variant="market-landscape"/);
    assert.match(marketHtml, /Competitive landscape/);
    assert.match(
      fypHtml,
      /The main contribution is not a deployable classifier\. It is a biologically and numerically honest account of what hospital trajectories can and cannot reveal in a rare-disease, weak-signal setting\./
    );
    assert.match(fypHtml, /data-editorial-variant="genomics-ml-pipeline"/);
    assert.match(fypHtml, /Genomics \+ ML pipeline/);
    assert.match(toolkitHtml, /data-editorial-variant="governance-lifecycle"/);
    assert.match(toolkitHtml, /AI\/MedTech lifecycle/);
    assert.match(consoneHtml, /data-editorial-variant="toxicity-workflow"/);
    assert.match(consoneHtml, /Dose-toxicity mapping/);
    for (const pageHtml of [hieHtml, marketHtml, fypHtml, toolkitHtml, consoneHtml]) {
      assert.doesNotMatch(pageHtml, /panel-block/);
    }
  });

  await t.test('now, about, 404, and projects pages expose the new journey content', () => {
    const nowHtml = readBuiltPage('now');
    const aboutHtml = readBuiltPage('about');
    const notFoundHtml = readBuiltPage('404.html');
    const projectsHtml = readBuiltPage('projects');

    assert.match(nowHtml, /<h1>Now<\/h1>/);
    assert.match(nowHtml, /Last updated/);
    assert.match(nowHtml, /Current focus/);
    assert.match(nowHtml, /Questions I am sharpening/);
    assert.match(nowHtml, /Direction I am moving toward/);
    assert.match(nowHtml, /Recent updates/);
    assert.match(nowHtml, /Portfolio shaped around evidence, direction and contact/);
    assert.match(nowHtml, /Public case studies added for healthcare innovation and research work/);
    assert.match(nowHtml, /Future methods interest clarified from final-year research/);
    assert.doesNotMatch(nowHtml, /backend|pull request|GitHub|build log|development changelog/i);
    assert.match(nowHtml, /Where to go next/);
    assert.match(nowHtml, /data-editorial-variant="current-vector"/);
    assert.match(nowHtml, /Current trajectory/);
    assert.match(
      aboutHtml,
      /Interim transcript currently supports a First-class trajectory, with final classification still subject to official confirmation\./
    );
    assert.match(aboutHtml, /See what I(?:&#39;|')m focused on now/);
    assert.match(notFoundHtml, /Best places to start/);
    assert.match(notFoundHtml, /Health Innovation East/);
    assert.match(notFoundHtml, /About my profile/);
    assert.match(
      projectsHtml,
      /Exploratory methods focused on weak-signal recovery\. This strand grows out of the final-year project(?:&#39;|')s rare-disease limits: biologically informed, provenance-aware methods for hypothesis generation, study-design support and measurement prioritisation when the data is sparse and the next evidence decision matters\./
    );
    assert.match(projectsHtml, /Concept-stage methods thinking, not a validated platform or clinical tool\./);
    assert.equal((projectsHtml.match(/Concept-stage methods thinking, not a validated platform or clinical tool\./g) ?? []).length, 1);
    assert.match(projectsHtml, /data-editorial-variant="weak-signal-methods"/);
    assert.match(projectsHtml, /Weak-signal methods/);
    assert.doesNotMatch(projectsHtml, /panel-block/);
  });
});
