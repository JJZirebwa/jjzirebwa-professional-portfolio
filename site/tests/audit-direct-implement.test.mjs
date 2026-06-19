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

test('refreshed portfolio routes render the graduate, FYP and document surfaces', async (t) => {
  execFileSync('npm', ['run', 'build'], {
    cwd: siteRoot,
    stdio: 'pipe'
  });

  await t.test('home page leads with the balanced Biomedical Science graduate positioning', () => {
    const html = readBuiltPage('');

    assert.match(html, /First Class Biomedical Science graduate/);
    assert.match(html, /Biomedical science, genomics and health data/);
    assert.match(html, /href="\/case-studies\/final-year-project\/"/);
    assert.match(html, /href="\/academic\/"/);
    assert.match(html, /href="\/documents\/"/);
    assert.match(html, /Genomics and health data science/);
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

    assert.match(html, /83\/100/);
    assert.match(html, /logistic regression/i);
    assert.match(html, /random forest/i);
    assert.match(html, /shallow neural network/i);
    assert.match(html, /observability controls/i);
    assert.match(html, /Fairness, subgroup and governance considerations/i);
    assert.match(html, /Jubileejoy_Zirebwa_Dissertation_Overview\.pdf/);
    assert.match(html, /academic\/final-year-project\/pipeline/);
    assert.match(html, /feature-domain-summary\.png/);
    assert.match(html, /sanitised reconstruction/i);
    assert.doesNotMatch(html, /2208155|SID|\/Users\/|\/home\/|raw patient|account name/i);
  });

  await t.test('academic, CV and documents routes expose the right protected-document model', () => {
    const academicHtml = readBuiltPage('academic');
    const cvHtml = readBuiltPage('cv');
    const documentsHtml = readBuiltPage('documents');

    assert.match(academicHtml, /First Class Honours awarded on 10 June 2026/);
    assert.match(academicHtml, /Undergraduate Project/);
    assert.match(academicHtml, /82, A, 30 credits/);
    assert.match(academicHtml, /Jubileejoy_Zirebwa_Transcript_password_protected\.pdf/);
    assert.match(academicHtml, /password protected/i);

    assert.match(cvHtml, /General portfolio CV/);
    assert.match(cvHtml, /Jubileejoy_Zirebwa_CV\.pdf/);
    assert.match(cvHtml, /not tailored to one application/i);
    assert.doesNotMatch(cvHtml, /First-class trajectory|on track|expected first class/i);

    assert.match(documentsHtml, /Document library/);
    assert.match(documentsHtml, /Privacy status/);
    assert.match(documentsHtml, /Password-protected transcript/);
    assert.match(documentsHtml, /Jubileejoy_Zirebwa_Dissertation_Overview\.pdf/);
    assert.match(documentsHtml, /Jubileejoy_Zirebwa_CV\.pdf/);
    assert.doesNotMatch(documentsHtml, /password[^<]{0,60}=/i);
  });

  await t.test('supporting pages keep the graduate/data profile aligned', () => {
    const aboutHtml = readBuiltPage('about');
    const caseStudiesHtml = readBuiltPage('case-studies');
    const contactHtml = readBuiltPage('contact');
    const skillsHtml = readBuiltPage('skills');

    assert.match(aboutHtml, /First Class Honours/);
    assert.match(aboutHtml, /genomics-linked health data research/);
    assert.match(caseStudiesHtml, /biomedical data research, healthcare innovation, AI\/MedTech governance and market analysis/i);
    assert.match(contactHtml, /biomedical science, genomics-linked health data work/i);
    assert.match(skillsHtml, /Biomedical data analysis/);

    for (const pageHtml of [aboutHtml, caseStudiesHtml, contactHtml, skillsHtml]) {
      assert.doesNotMatch(pageHtml, /expected first class|on track|First-class trajectory/i);
    }
  });

  await t.test('route-specific social images are generated as static PNG files', () => {
    for (const imagePath of [
      'og/home.png',
      'og/academic.png',
      'og/cv.png',
      'og/documents.png',
      'og/final-year-project.png'
    ]) {
      const imageStats = statSync(path.join(distRoot, imagePath));
      assert.ok(imageStats.size > 1000, `${imagePath} should be a non-empty generated PNG`);
    }
  });
});
