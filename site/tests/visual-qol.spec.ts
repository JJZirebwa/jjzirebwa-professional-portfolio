import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const pages = [
  { path: '/', name: 'home' },
  { path: '/contact/', name: 'contact' },
  { path: '/skills/', name: 'skills' }
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
          const rect = element.getBoundingClientRect();
          return { element, rect };
        })
        .filter(({ rect }) => rect.width > 0 && rect.height > 0);

      const overlaps: string[] = [];
      for (let index = 0; index < visible.length; index += 1) {
        for (let next = index + 1; next < visible.length; next += 1) {
          const a = visible[index].rect;
          const b = visible[next].rect;
          const intersects = a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
          if (!intersects) continue;

          const aContainsB = a.left <= b.left && a.right >= b.right && a.top <= b.top && a.bottom >= b.bottom;
          const bContainsA = b.left <= a.left && b.right >= a.right && b.top <= a.top && b.bottom >= a.bottom;
          if (!aContainsB && !bContainsA) {
            overlaps.push(`${visible[index].element.tagName} overlaps ${visible[next].element.tagName}`);
          }
        }
      }
      return overlaps.slice(0, 5);
    });
    expect(overlappingElements).toEqual([]);

    const accessibility = await new AxeBuilder({ page })
      .disableRules(['color-contrast'])
      .analyze();
    expect(accessibility.violations).toEqual([]);

    await testInfo.attach(`${pageInfo.name}-${testInfo.project.name}.png`, {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png'
    });
  });
}
