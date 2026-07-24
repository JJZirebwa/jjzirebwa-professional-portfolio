#!/usr/bin/env node

import { existsSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const minimumMinor = 12;

export const isSupportedNodeVersion = (version) => {
  const match = /^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)/.exec(version);
  if (!match?.groups) {
    return false;
  }

  const major = Number.parseInt(match.groups.major, 10);
  const minor = Number.parseInt(match.groups.minor, 10);

  return major === 22 && minor >= minimumMinor;
};

export const findDuplicateDependencyDirectories = (nodeModulesPath) => {
  if (!existsSync(nodeModulesPath)) {
    return [];
  }

  const duplicates = [];
  const pending = [nodeModulesPath];

  while (pending.length > 0) {
    const current = pending.pop();
    if (!current) continue;

    for (const entry of readdirSync(current, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;

      const entryPath = path.join(current, entry.name);
      if (entry.name.endsWith(' 2')) {
        duplicates.push(entryPath);
        if (duplicates.length >= 10) return duplicates;
      }
      pending.push(entryPath);
    }
  }

  return duplicates;
};

const run = () => {
  const currentVersion = process.versions.node;
  if (!isSupportedNodeVersion(currentVersion)) {
    console.error(
      [
        `Unsupported Node version ${currentVersion}.`,
        'This portfolio requires Node 22.12.0 or newer within the Node 22 release line.',
        'From the repository root, run `nvm use` and then repeat the npm command.'
      ].join('\n')
    );
    process.exitCode = 1;
    return;
  }

  const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const nodeModulesPath = path.join(siteRoot, 'node_modules');

  if (!existsSync(path.join(nodeModulesPath, 'astro'))) {
    console.error('Site dependencies are missing. From the repository root, run `npm run setup`.');
    process.exitCode = 1;
    return;
  }

  const duplicateDirectories = findDuplicateDependencyDirectories(nodeModulesPath);
  if (duplicateDirectories.length > 0) {
    const relativeDuplicates = duplicateDirectories.map((directory) => path.relative(siteRoot, directory));
    console.error(
      [
        'The site dependency tree contains duplicated package directories and cannot be trusted.',
        ...relativeDuplicates.map((directory) => `- ${directory}`),
        'From the repository root, run `npm run setup` to restore the locked dependency tree before starting Astro.'
      ].join('\n')
    );
    process.exitCode = 1;
  }
};

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  run();
}
