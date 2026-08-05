import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pagesRoot = path.resolve(__dirname, '../src/pages');
const readPage = (name) => readFileSync(path.join(pagesRoot, name), 'utf8');

test('laboratory practice is discoverable without overstating degree experience', () => {
  const home = readPage('index.astro');
  const academic = readPage('academic.astro');
  const skills = readPage('skills.astro');

  assert.match(home, /href="\/academic\/#laboratory-practice"/);
  assert.match(home, /Laboratory practice/);

  assert.match(academic, /id="laboratory-practice"/);
  assert.match(academic, /supervised and assessed degree practicals/i);
  assert.match(academic, /aseptic technique/i);
  assert.match(academic, /PCR/);
  assert.match(academic, /ELISA/);
  assert.match(academic, /H&amp;E|H&E/);
  assert.match(academic, /simulation|simulated/i);

  assert.match(skills, /Laboratory and diagnostic practice/);
  assert.match(skills, /micropipettes/i);
  assert.match(skills, /thermocycler/i);
  assert.match(skills, /plate reader/i);
  assert.match(skills, /light microscopes/i);

  for (const page of [home, academic, skills]) {
    assert.doesNotMatch(page, /independent (?:laboratory|lab) (?:employment|practice)/i);
    assert.doesNotMatch(page, /independent (?:maintenance|calibration|troubleshooting)/i);
    assert.doesNotMatch(page, /advanced analyser operation/i);
  }
});
