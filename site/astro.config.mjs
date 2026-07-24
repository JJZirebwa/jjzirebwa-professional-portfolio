import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import pageUpdates from './src/data/page-updates.json' with { type: 'json' };

export default defineConfig({
  site: 'https://jubileejoyzirebwa.com',
  output: 'static',
  prefetch: {
    prefetchAll: false,
    defaultStrategy: 'hover'
  },
  devToolbar: {
    enabled: false
  },
  integrations: [
    sitemap({
      serialize(item) {
        const pathname = new URL(item.url).pathname;
        const lastmod = pageUpdates[pathname];

        return lastmod ? { ...item, lastmod } : item;
      }
    })
  ]
});
