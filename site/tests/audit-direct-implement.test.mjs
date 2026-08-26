import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, statSync } from 'node:fs';
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

test('current-work and discovery pages keep evidence ahead of portfolio administration', () => {
  const nowSource = readFileSync(path.join(siteRoot, 'src/pages/now.astro'), 'utf8');
  const contactSource = readFileSync(path.join(siteRoot, 'src/pages/contact.astro'), 'utf8');
  const caseStudiesSource = readFileSync(path.join(siteRoot, 'src/pages/case-studies/index.astro'), 'utf8');
  const projectsSource = readFileSync(path.join(siteRoot, 'src/pages/projects.astro'), 'utf8');
  const socialCardsSource = readFileSync(path.join(siteRoot, 'src/data/socialCards.ts'), 'utf8');

  assert.match(nowSource, /title="Current work"/);
  assert.match(nowSource, /<h1>Current work<\/h1>/);
  assert.match(nowSource, /Clinical Informatics/);
  for (const removedTerm of [
    'focusAreas',
    'sharpeningQuestions',
    'directionTags',
    'Present tense',
    'public route',
    'public evidence',
    'for readers',
    'tracking development',
    'Analyst roles',
    'Market intelligence'
  ]) {
    assert.doesNotMatch(nowSource, new RegExp(removedTerm, 'i'));
  }

  assert.match(contactSource, /open to conversations/i);
  assert.doesNotMatch(contactSource, /open to early-career Analyst and Market Intelligence roles/i);
  assert.doesNotMatch(caseStudiesSource, /Parent lane|Contained work|parent experience/i);
  assert.doesNotMatch(projectsSource, /Contained lane|parent experience/i);
  assert.doesNotMatch(socialCardsSource, /Parent case studies|Contained deliverables|parent experience|active questions|role scope/i);
  const homeSource = readFileSync(path.join(siteRoot, 'src/pages/index.astro'), 'utf8');
  assert.match(homeSource, /title="Current work"/);
  assert.doesNotMatch(homeSource, /what I am sharpening|Profile direction|Parent case studies|Role interests/i);
  assert.doesNotMatch(readFileSync(path.join(siteRoot, 'src/content.config.ts'), 'utf8'), /now-updates/);
});

test('refreshed portfolio routes render the graduate, FYP and document surfaces', async (t) => {
  execFileSync('npm', ['run', 'build'], {
    cwd: siteRoot,
    stdio: 'pipe'
  });

  await t.test('home page leads with the balanced Biomedical Science graduate positioning', () => {
    const html = readBuiltPage('');

    assert.match(html, /First Class Biomedical Science graduate/);
    assert.match(html, /Biomedical science \| Genomics \| Health Data/);
    assert.match(html, /href="\/case-studies\/final-year-project\/"/);
    assert.match(html, /href="\/academic\/"/);
    assert.match(html, /href="\/documents\/"/);
    assert.match(html, /Genomics and health data science/);
    const selectedContextLinks = [...html.matchAll(/<a\b(?=[^>]*\bdata-context-card\b)[^>]*\bhref="([^"]+)"[^>]*>/g)]
      .map((match) => match[1]);
    assert.deepEqual(selectedContextLinks, [
      '/case-studies/health-innovation-east/',
      '/academic/',
      '/case-studies/final-year-project/'
    ]);
    assert.doesNotMatch(html, /data-editorial-variant="evidence-journey"/);
    assert.doesNotMatch(html, /Evidence to decision/);
    assert.doesNotMatch(html, /Working lens/);
    assert.doesNotMatch(html, /healthcare strategy specialist/i);
    assert.match(html, /<meta property="og:image" content="https:\/\/jubileejoyzirebwa\.com\/og\/home\.png">/);
    assert.match(html, /"@type":"WebSite"/);
    assert.doesNotMatch(html, /"@type":"ProfilePage"/);
  });

  await t.test('final-year project route exposes source-backed evidence without sensitive identifiers', () => {
    const html = readBuiltPage('case-studies/final-year-project');

    assert.match(html, /83%/);
    assert.match(html, /logistic regression/i);
    assert.match(html, /random forest/i);
    assert.match(html, /shallow neural[- ]network/i);
    assert.match(html, /observability controls/i);
    assert.match(html, /subgroup\/fairness review/i);
    assert.match(html, /Jubileejoy_Zirebwa_Dissertation_Overview\.pdf/);
    assert.match(html, /academic\/final-year-project\/pipeline/);
    assert.match(html, /\/_astro\/feature-domain-summary\.[^" ]+\.webp/);
    assert.match(html, /srcset="[^"]*feature-domain-summary[^"]*480w[^"]*760w[^"]*1120w/);
    assert.match(html, /Applied health data science workflow/i);
    assert.doesNotMatch(html, /2208155|\bSID\b|\/Users\/|\/home\/|raw patient|account name/i);
  });

  await t.test('academic, CV and documents routes expose the right protected-document model', () => {
    const academicHtml = readBuiltPage('academic');
    const cvHtml = readBuiltPage('cv');
    const documentsHtml = readBuiltPage('documents');

    assert.match(academicHtml, /First Class Honours/);
    assert.match(academicHtml, /Awarded 10 June 2026/);
    assert.match(academicHtml, /Undergraduate Project/);
    assert.match(academicHtml, /82, A/);
    assert.match(academicHtml, /30-credit final-year project module/);
    assert.match(academicHtml, /Jubileejoy_Zirebwa_Transcript_password_protected\.pdf/);
    assert.match(academicHtml, /password[- ]protected/i);

    assert.match(cvHtml, /General portfolio CV/);
    assert.match(cvHtml, /Jubileejoy_Zirebwa_CV\.pdf/);
    assert.match(cvHtml, /not tailored to one application/i);
    assert.match(cvHtml, /3 pages/);
    assert.match(cvHtml, /122 KB/);
    assert.match(cvHtml, /<dt>Updated<\/dt>/);
    assert.match(cvHtml, /<dd>26 August 2026<\/dd>/);
    assert.doesNotMatch(cvHtml, /First-class trajectory|on track|expected first class/i);

    assert.match(documentsHtml, /Selected documents and resources/);
    assert.match(documentsHtml, /Password protected/);
    assert.match(documentsHtml, /Jubileejoy_Zirebwa_Dissertation_Overview\.pdf/);
    assert.match(documentsHtml, /Jubileejoy_Zirebwa_CV\.pdf/);
    assert.match(documentsHtml, /12 pages/);
    assert.match(documentsHtml, /395 KB/);
    assert.match(documentsHtml, /34 KB/);
    assert.doesNotMatch(documentsHtml, /password[^<]{0,60}=/i);
  });

  await t.test('supporting pages keep the graduate/data profile aligned', () => {
    const aboutHtml = readBuiltPage('about');
    const caseStudiesHtml = readBuiltPage('case-studies');
    const contactHtml = readBuiltPage('contact');
    const skillsHtml = readBuiltPage('skills');
    const projectsHtml = readBuiltPage('projects');
    const nowHtml = readBuiltPage('now');

    assert.match(aboutHtml, /First Class Honours/);
    assert.match(aboutHtml, /award confirmed on 10 June 2026/);
    assert.match(aboutHtml, /"dateModified":"2026-07-24"/);
    assert.match(aboutHtml, /Page updated <time datetime="2026-07-24">24 July 2026<\/time>/);
    assert.doesNotMatch(aboutHtml, /award confirmed[^<]*July 2026/i);
    assert.match(aboutHtml, /genomics-linked health data research/);
    assert.match(caseStudiesHtml, /final-year project, Health Innovation East placement and ConsoneAI\/DioScor internship/i);
    assert.match(caseStudiesHtml, /Broader experience/i);
    assert.doesNotMatch(caseStudiesHtml, /Parent lane|Contained work|parent experience/i);
    assert.match(contactHtml, /open to conversations/i);
    assert.match(contactHtml, /biomedical evidence, genomics-linked data/i);
    assert.doesNotMatch(contactHtml, /governance roles/i);
    assert.match(contactHtml, /Page updated <time datetime="2026-08-05">5 August 2026<\/time>/);
    assert.match(skillsHtml, /Clinical informatics and operational data/);
    assert.match(skillsHtml, /Biomedical data analysis/);
    const supportingWorkLinks = [...skillsHtml.matchAll(
      /<a class="skill-proof-link" href="([^"]+)">([^<]+)<\/a>/g
    )].map((match) => ({ href: match[1], label: match[2].trim() }));
    assert.deepEqual(supportingWorkLinks, [
      { href: '/academic/#laboratory-practice', label: 'View laboratory practice' },
      { href: '/projects/clinical-informatics/', label: 'View Clinical Informatics project' },
      { href: '/case-studies/final-year-project/', label: 'Read final-year project' },
      { href: '/case-studies/health-innovation-east/', label: 'View Health Innovation East case study' },
      { href: '/case-studies/final-year-project/', label: 'Review research evidence' },
      { href: '/case-studies/ai-medtech-toolkit/', label: 'View AI/MedTech Toolkit' },
      { href: '/case-studies/market-intelligence/', label: 'View market intelligence case study' },
      { href: '/documents/', label: 'View selected documents' }
    ]);
    assert.match(projectsHtml, /Clinical informatics trial operations/);
    assert.match(projectsHtml, /href="\/projects\/clinical-informatics\/"/);
    assert.match(projectsHtml, /Focused project work/);
    assert.doesNotMatch(projectsHtml, /Contained lane|parent experience/i);
    assert.match(nowHtml, /Current work/);
    assert.match(nowHtml, /Clinical Informatics/);
    assert.doesNotMatch(nowHtml, /Recent updates|Present tense|Analyst roles|Market intelligence/i);
    assert.match(nowHtml, /"dateModified":"2026-08-05"/);

    for (const pageHtml of [aboutHtml, caseStudiesHtml, contactHtml, skillsHtml]) {
      assert.doesNotMatch(pageHtml, /expected first class|on track|First-class trajectory/i);
    }
  });

  await t.test('Clinical Informatics has a project route with public evidence links', () => {
    const html = readBuiltPage('projects/clinical-informatics');

    assert.match(html, /Clinical informatics trial-operations demonstration/);
    assert.match(html, /Eight linked trial-operations tables/);
    assert.match(html, /https:\/\/github\.com\/JJZirebwa\/clinical-informatics/);
    assert.match(html, /https:\/\/clinical-informatics\.streamlit\.app/);
    assert.match(html, /"dateModified":"2026-08-05"/);
    assert.match(html, /\/og\/clinical-informatics\.png/);
    assert.doesNotMatch(html, /\/Users\/|private\/regular_audits|task queue|implementation note/i);
  });

  await t.test('adaptive navigation preserves primary and secondary discovery routes', () => {
    const html = readBuiltPage('');

    const primaryNavigation = html.match(/<nav class="site-nav primary-nav"[^>]*>([\s\S]*?)<\/nav>/)?.[1] ?? '';
    const secondaryNavigation = html.match(/<nav class="secondary-nav"[^>]*>([\s\S]*?)<\/nav>/)?.[1] ?? '';
    const moreNavigation = html.match(/<details class="more-nav">([\s\S]*?)<\/details>/)?.[1] ?? '';

    for (const label of ['Home', 'Experience', 'Projects', 'CV', 'Contact']) {
      assert.match(primaryNavigation, new RegExp(`>\\s*${label}\\s*<`));
    }
    for (const label of ['About', 'Academic', 'Skills', 'Documents', 'Current work']) {
      assert.match(secondaryNavigation, new RegExp(`>\\s*${label}\\s*<`));
      assert.match(moreNavigation, new RegExp(`>\\s*${label}\\s*<`));
    }
    assert.match(moreNavigation, /<summary>More<\/summary>/);
  });

  await t.test('page update dates remain separate from document file dates', () => {
    const cvHtml = readBuiltPage('cv');
    const documentsHtml = readBuiltPage('documents');
    const sitemap = readFileSync(path.join(distRoot, 'sitemap-0.xml'), 'utf8');

    assert.doesNotMatch(cvHtml, /"dateModified"/);
    assert.doesNotMatch(documentsHtml, /"dateModified"/);
    assert.match(cvHtml, /<dt>Updated<\/dt>\s*<dd>26 August 2026<\/dd>/);
    assert.match(documentsHtml, /<dt>Updated<\/dt>\s*<dd>19 June 2026<\/dd>/);
    assert.match(sitemap, /<loc>https:\/\/jubileejoyzirebwa\.com\/now\/<\/loc><lastmod>2026-08-05T00:00:00\.000Z<\/lastmod>/);
    assert.match(sitemap, /<loc>https:\/\/jubileejoyzirebwa\.com\/projects\/clinical-informatics\/<\/loc><lastmod>2026-08-05T00:00:00\.000Z<\/lastmod>/);
  });

  await t.test('route-specific social images are generated as static PNG files', () => {
    for (const imagePath of [
      'og/home.png',
      'og/academic.png',
      'og/cv.png',
      'og/documents.png',
      'og/final-year-project.png',
      'og/clinical-informatics.png'
    ]) {
      const imageStats = statSync(path.join(distRoot, imagePath));
      assert.ok(imageStats.size > 1000, `${imagePath} should be a non-empty generated PNG`);
    }
  });

  await t.test('repository-root npm commands delegate to the Astro site', () => {
    const rootPackagePath = path.resolve(siteRoot, '..', 'package.json');
    const rootPackage = JSON.parse(readFileSync(rootPackagePath, 'utf8'));
    const sitePackage = JSON.parse(readFileSync(path.join(siteRoot, 'package.json'), 'utf8'));

    assert.equal(rootPackage.engines.node, '>=22.12.0 <23');
    assert.equal(rootPackage.scripts.dev, 'npm --prefix site run dev');
    assert.equal(rootPackage.scripts.check, 'npm --prefix site run check');
    assert.equal(rootPackage.scripts.build, 'npm --prefix site run build');
    assert.equal(rootPackage.scripts['test:ui'], 'npm --prefix site run test:ui');
    assert.equal(sitePackage.scripts.predev, 'node scripts/require-node-22.mjs');
    assert.equal(sitePackage.scripts.precheck, 'node scripts/require-node-22.mjs');
    assert.equal(sitePackage.scripts.prebuild, 'node scripts/require-node-22.mjs');
    assert.equal(sitePackage.scripts['pretest:ui'], 'node scripts/require-node-22.mjs');
  });

  await t.test('site commands reject unsupported Node versions before Astro starts', async () => {
    const { findDuplicateDependencyDirectories, isSupportedNodeVersion } = await import('../scripts/require-node-22.mjs');

    assert.equal(isSupportedNodeVersion('22.12.0'), true);
    assert.equal(isSupportedNodeVersion('22.23.0'), true);
    assert.equal(isSupportedNodeVersion('22.11.0'), false);
    assert.equal(isSupportedNodeVersion('23.0.0'), false);
    assert.equal(isSupportedNodeVersion('26.0.0'), false);
    assert.deepEqual(findDuplicateDependencyDirectories(path.join(siteRoot, 'node_modules')), []);
  });
});
