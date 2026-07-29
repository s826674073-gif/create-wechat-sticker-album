# WeChat Static Album Specification

Use this file as the fixed acceptance baseline transcribed from the four screenshots supplied when the skill was created. If the live platform shows different requirements, stop and ask the user whether to update the skill before generating or repackaging assets.

## Album-wide rules

- Use one type for the whole album; this skill supports static PNG only.
- Require any integer count from 8 through 24.
- Keep the character identity, line work, coloring, and rendering style unified.
- Give every expression a substantially different emotion, action, silhouette, or prop.
- Avoid excessive blank space and keep the subject legible at chat size.
- Do not put text, logos, signatures, or watermarks in any generated upload image.

## Upload files

| Asset | Count | Format | Exact size | Maximum bytes | Transparency |
|---|---:|---|---:|---:|---|
| Main expression | 8–24 | PNG | 240×240 | 500 KiB | Required by this skill |
| Album cover | 1 | PNG | 240×240 | 500 KiB | Required |
| Chat icon | 1 | PNG | 50×50 | 100 KiB | Required |
| Detail banner | 1 | PNG | 750×400 | 500 KiB | Forbidden |

Use binary KiB limits in validation: 500 × 1024 bytes and 100 × 1024 bytes.

## Main expressions

- Fit the subject comfortably inside the square without stretching.
- Preserve a clean transparent exterior and transparent corners.
- Keep the action readable at 240×240.
- Do not create near-duplicate poses merely by changing a small facial detail.

## Cover

- Use the approved character anchor as the source.
- Show the most recognizable front-facing half-body or full-body pose; do not use only a head.
- Use a transparent background.
- Avoid white outlines, jagged edges, text, and decorative clutter.
- Keep the composition concise and avoid excessive blank space.

## Chat icon

- Use a dedicated, recognizable front-facing head image based on the approved anchor.
- Keep the composition extremely simple at 50×50.
- Use a transparent background.
- Avoid white outlines, jagged edges, text, and decorative elements.

## Detail banner

- Use an opaque, bright, non-white background with strong separation from WeChat's light interface.
- Keep the content related to the album, visually rich, and story-like.
- Avoid all text.
- Preserve proportions; crop or pad without stretching or squashing subjects.
- Keep important faces, limbs, and props inside the central crop-safe area.

## Automated versus manual checks

Automate count, format, pixel size, byte size, alpha presence, transparent corners, subject occupancy, near-duplicate hashes, banner opacity, and near-white banner borders.

Manually inspect identity/style consistency, accidental text, watermarking, edge halos and jaggies, anatomy, meaningful pose differences, visual storytelling, and whether center cropping removed important content.
