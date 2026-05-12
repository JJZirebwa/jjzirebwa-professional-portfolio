# Deploying the Astro site on Netlify

This folder contains the Netlify-facing Astro site layer. The Markdown portfolio remains the source/archive in the repository root.

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

1. Commit the reviewed repository to GitHub only after the public-safety review is complete.
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

## References

- Astro Netlify deployment guide: <https://docs.astro.build/en/guides/deploy/netlify/>
- Netlify monorepo build settings: <https://docs.netlify.com/build/configure-builds/monorepos/>
