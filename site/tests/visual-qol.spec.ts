import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const pages = [
  { path: '/', name: 'home' },
  { path: '/about/', name: 'about' },
  { path: '/academic/', name: 'academic' },
  { path: '/cv/', name: 'cv' },
  { path: '/documents/', name: 'documents' },
  { path: '/now/', name: 'now' },
  { path: '/projects/', name: 'projects' },
  { path: '/projects/clinical-informatics/', name: 'clinical-informatics' },
  { path: '/case-studies/health-innovation-east/', name: 'health-innovation-east' },
  { path: '/case-studies/ai-medtech-toolkit/', name: 'ai-medtech-toolkit' },
  { path: '/case-studies/market-intelligence/', name: 'market-intelligence' },
  { path: '/case-studies/final-year-project/', name: 'final-year-project' },
  { path: '/case-studies/consoneai-dioscor/', name: 'consoneai-dioscor' },
  { path: '/contact/', name: 'contact' },
  { path: '/skills/', name: 'skills' },
  { path: '/404.html', name: 'not-found' }
];

for (const pageInfo of pages) {
  test(`${pageInfo.name} has no obvious layout or accessibility regressions`, async ({ page }, testInfo) => {
    await page.goto(pageInfo.path);
    await page.waitForLoadState('networkidle');

    const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(horizontalOverflow).toBe(false);

    const overlappingElements = await page.evaluate(() => {
      const candidates = Array.from(document.querySelectorAll('a, button, h1, h2, h3, p, li, .card, .contact-panel'));
      const visible = candidates
        .map((element) => {
          const rects = Array.from(element.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0);
          return { element, rects };
        })
        .filter(({ rects }) => rects.length > 0);

      const overlaps: string[] = [];
      for (let index = 0; index < visible.length; index += 1) {
        for (let next = index + 1; next < visible.length; next += 1) {
          const first = visible[index];
          const second = visible[next];
          if (first.element.contains(second.element) || second.element.contains(first.element)) continue;

          const intersects = first.rects.some((a) => second.rects.some((b) =>
            a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
          ));
          if (!intersects) continue;

          const describe = (element: Element) => {
            const label = (element.getAttribute('aria-label') ?? element.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 60);
            const href = element instanceof HTMLAnchorElement ? ` ${element.getAttribute('href') ?? ''}` : '';
            return `${element.tagName}${href}${label ? ` “${label}”` : ''}`;
          };
          overlaps.push(`${describe(first.element)} overlaps ${describe(second.element)}`);
        }
      }
      return overlaps.slice(0, 5);
    });
    expect(overlappingElements).toEqual([]);

    const accessibility = await new AxeBuilder({ page }).analyze();
    if (accessibility.violations.length > 0) {
      await testInfo.attach(`${pageInfo.name}-${testInfo.project.name}-axe-violations.json`, {
        body: Buffer.from(JSON.stringify(accessibility.violations, null, 2)),
        contentType: 'application/json'
      });
    }
    expect(accessibility.violations).toEqual([]);

    if (testInfo.project.name.includes('mobile') && ['cv', 'documents'].includes(pageInfo.name)) {
      const previews = page.locator('.document-preview');
      await expect(previews).toHaveCount(pageInfo.name === 'documents' ? 2 : 1);
      for (let index = 0; index < await previews.count(); index += 1) {
        await expect(previews.nth(index)).toBeHidden();
      }
    }

    await testInfo.attach(`${pageInfo.name}-${testInfo.project.name}.png`, {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png'
    });
  });
}

test('adaptive navigation exposes secondary routes on desktop and through More on mobile', async ({ page }, testInfo) => {
  await page.goto('/');

  const secondaryNavigation = page.locator('.secondary-nav');
  const moreNavigation = page.locator('.more-nav');

  if (testInfo.project.name.includes('mobile')) {
    await expect(secondaryNavigation).toBeHidden();
    await expect(moreNavigation).toBeVisible();
    await moreNavigation.locator('summary').click();
    await expect(moreNavigation).toHaveAttribute('open', '');

    for (const label of ['About', 'Academic', 'Skills', 'Documents', 'Current work']) {
      await expect(moreNavigation.getByRole('link', { name: label, exact: true })).toBeVisible();
    }

    await page.keyboard.press('Escape');
    await expect(moreNavigation).not.toHaveAttribute('open', '');
    await expect(moreNavigation.locator('summary')).toBeFocused();
  } else {
    await expect(secondaryNavigation).toBeVisible();
    await expect(moreNavigation).toBeHidden();

    for (const label of ['About', 'Academic', 'Skills', 'Documents', 'Current work']) {
      await expect(secondaryNavigation.getByRole('link', { name: label, exact: true })).toBeVisible();
    }
  }
});

test('selected context cards are full-area keyboard-accessible links', async ({ page }) => {
  const destinations = [
    '/case-studies/health-innovation-east/',
    '/academic/',
    '/case-studies/final-year-project/'
  ];

  for (const destination of destinations) {
    await page.goto('/');

    const card = page.locator(`[data-context-card][href="${destination}"]`);
    await expect(card).toHaveCount(1);
    await expect(card).toBeVisible();
    await expect(card).toHaveCSS('display', 'block');

    const fillsExistingCard = await card.evaluate((link) => {
      const figure = link.querySelector('figure');
      if (!figure) return false;

      const linkBounds = link.getBoundingClientRect();
      const figureBounds = figure.getBoundingClientRect();
      const tolerance = 0.5;

      return (
        Math.abs(linkBounds.left - figureBounds.left) <= tolerance &&
        Math.abs(linkBounds.top - figureBounds.top) <= tolerance &&
        Math.abs(linkBounds.width - figureBounds.width) <= tolerance &&
        Math.abs(linkBounds.height - figureBounds.height) <= tolerance
      );
    });
    expect(fillsExistingCard).toBe(true);

    await card.focus();
    await expect(card).toBeFocused();
    await Promise.all([
      page.waitForURL(`**${destination}`),
      page.keyboard.press('Enter')
    ]);
  }
});
