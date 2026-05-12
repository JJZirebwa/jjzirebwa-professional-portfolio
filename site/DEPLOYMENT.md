# Deploying the Astro site on Netlify

This folder contains the Astro site used for Netlify deployment. The Markdown portfolio remains available in the repository root.

Do not deploy until a final manual safety review has confirmed that the site contains no confidential material, restricted dissertation outputs, raw data, internal documents or private review files.

## Local checks

From the repository root:

```bash
cd site
npm install
npm run build
npm run preview
```

The build output is written to `site/dist/`.

## GitHub and Netlify workflow

1. Commit the reviewed repository to GitHub only after the final manual review is complete.
2. In Netlify, choose **Add new site** and then **Import an existing project**.
3. Select the GitHub repository.
4. Use these build settings:

| Setting | Value |
|---|---|
| Base directory | `site` |
| Build command | `npm run build` |
| Publish directory | `dist` |

Netlify's monorepo documentation states that the publish directory is relative to the base directory. If the Netlify UI shows paths relative to the repository root instead, use `site/dist`.

The root `netlify.toml` uses:

```toml
[build]
  base = "site"
  command = "npm run build"
  publish = "dist"

[build.environment]
  NODE_VERSION = "22.12.0"
```

## Deploy preview checks

Before promoting any deploy:

- Review the home page, all case-study pages, projects, skills, about and contact pages.
- Confirm that no `review/`, `_private/`, `private/`, raw dissertation outputs or internal build notes are reachable.
- Confirm that no PDFs, figures, raw datasets, CB Insights exports, HIE internal documents or ConsoneAI/DioScor proprietary material are linked.
- Check mobile and desktop layouts for readable text, no overlap and clear navigation.
- Confirm that the wording remains first-person, bounded and recruiter-readable.

## Google Analytics

The Astro layout includes a Google Analytics 4 tag. It is not visible on the website. The current GA4 measurement ID is baked into the analytics component, so Netlify does not need a separate environment variable for analytics to work.

To verify analytics after deployment:

1. Deploy the site preview or production build.
2. Open the deployed site in a normal browser window.
3. In Google Analytics, use the Realtime report to confirm that page views are being received. Data can take a short time to appear.

To change the GA4 property later without editing the component, set this Netlify build environment variable:

| Variable | Value |
|---|---|
| `PUBLIC_GA_MEASUREMENT_ID` | New `G-XXXXXXXXXX` measurement ID |

For local override testing, copy `site/.env.example` to `site/.env.local`, replace the placeholder value, and run:

```bash
cd site
npm run build
npm run preview
```

Do not commit `.env.local`. The file is ignored. The GA4 measurement ID is not treated as a secret once the site is built because browser analytics tags expose it in page source and network requests.

Before enabling analytics on the public production site, review whether the site needs a privacy/cookie notice or consent handling. Google Analytics uses cookies for website measurement, so this should be treated as a publication/privacy checklist item rather than a purely technical setting.

## References

- Astro Netlify deployment guide: <https://docs.astro.build/en/guides/deploy/netlify/>
- Netlify monorepo build settings: <https://docs.netlify.com/build/configure-builds/monorepos/>
- Astro environment variables: <https://docs.astro.build/en/guides/environment-variables/>
- Google Analytics website setup: <https://support.google.com/analytics/answer/9304153>
- Google tag setup with `gtag.js`: <https://developers.google.com/tag-platform/gtagjs>
- Google Analytics cookie usage: <https://support.google.com/analytics/answer/11397207>
