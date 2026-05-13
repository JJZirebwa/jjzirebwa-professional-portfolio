import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://jubileejoyzirebwa.com',
  output: 'static',
  devToolbar: {
    enabled: false
  },
  integrations: [sitemap()]
});
