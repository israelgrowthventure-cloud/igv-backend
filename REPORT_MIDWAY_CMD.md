# Report Midway

## Status
- About source identified in CMS backend.
- Premium About generator implemented for `fr`, `en`, and `he`.
- Startup/bootstrap upsert added so Render deploy rewrites About content automatically.

## Current Routes
- Public CMS equivalent route: `/api/pages/public/about?language=fr`
- Public CMS equivalent route: `/api/pages/public/about?language=en`
- Public CMS equivalent route: `/api/pages/public/about?language=he`

## Technical Notes
- The repository does not contain Mickael Benmoussa's image asset locally.
- The migration preserves the current photo by extracting the existing `<img src>` from the saved About HTML in MongoDB and reinjecting it into the new layout.
- Public CMS routes were adjusted to prefer canonical `content` payloads over legacy `flat_content` when both are present.
- The About migration explicitly removes legacy `flat_content` from About documents during upsert.
- Canonical paths exposed in CMS SEO payload:
  - `fr`: `/about/`
  - `en`: `/en/about/`
  - `he`: `/he/about/`

## Local Verification
- `python -m compileall app/services/about_page_content.py cms_routes.py server.py` : OK
- `pytest tests_api/test_about_page_content.py -q -p no:cacheprovider` : 3 passed
- HTML generation check:
  - `fr`: 1 H1, canonical `/about/`, robots `index,follow`, image preserved
  - `en`: 1 H1, canonical `/en/about/`, robots `index,follow`, image preserved
  - `he`: 1 H1, canonical `/he/about/`, robots `index,follow`, image preserved, `dir="rtl"`

## Pending
- Commit changes
- Push to GitHub / trigger Render deploy
- Verify production API and site URLs post-deploy

## Production Blocker
- Git pushes completed successfully to `origin/main`, including a forced Render trigger commit.
- Public service checked: `https://igv-cms-backend.onrender.com/debug/routers`
- Observed payload still shows `build_timestamp: 2025-12-29T17:20:00Z`, which proves the live Render service has not pulled today's commits.
- Public About endpoints still return the legacy content:
  - `GET /api/pages/public/about?language=fr`
  - `GET /api/pages/public/about?language=en`
  - `GET /api/pages/public/about?language=he`
- Documented admin credentials in the repo now return `401 Unauthorized`, so a direct CMS override through production auth could not be executed from this workspace.
