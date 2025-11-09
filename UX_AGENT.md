# UX Agent Instructions

## Mission
Create lightweight UX prototypes (HTML/CSS/JS or image mockups) that showcase proposed interactions for Skymarshal/Litemarshal and related Bluesky tooling. Favor fast iteration over polish; every deliverable should load directly inside a browser without external build steps.

## Output Location & Hosting
- All prototypes must live in `~/UX_TEST` (`/home/coolhand/UX_TEST`).
- Each concept gets its own subfolder: `~/UX_TEST/<concept_slug>/index.html` (include assets in the same folder).
- Prototypes are served at `https://dr.eamer.dev/ux/<concept_slug>/`, so keep slugs URL-safe.
- Static assets (images, fonts, JS) must use relative paths so they render correctly via the `/ux/` prefix.
- Provide a short `README.md` inside every concept folder describing purpose, login assumptions, and key interactions.

## Recommended Workflow
1. Sketch low-fidelity ideas first (wireframes or screenshots). Save as `draft.png` inside the concept folder.
2. Build interactive HTML/CSS mockups once direction is clear. Prefer vanilla JS + Tailwind CDN or simple CSS to avoid bundlers.
3. Keep bundle size <2 MB so the page loads quickly over the proxy.
4. Use placeholder data; never embed real credentials or personal content.
5. When iterating, version folders with suffixes (`cleanup-v2`, `analytics-lite-v1`) so reviewers can compare.

## Hand-off Checklist
- `index.html` loads without build tooling (`python3 -m http.server` sanity check is fine).
- Relative links stay under `/ux/<concept_slug>/`.
- Include `notes.md` (or update `README.md`) with:
  - Problem statement & goals
  - Interaction summary + navigation map
  - Open questions / next steps
- Optional: add GIF screencast (`demo.gif`) under 5 MB.

## Communication
- Announce new prototypes in project updates or PR descriptions with the live URL and key screenshots.
- When a prototype graduates into production work, move its assets into the target project repo and leave a pointer in `~/UX_TEST/<concept_slug>/README.md`.

