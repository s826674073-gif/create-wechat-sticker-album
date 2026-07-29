---
name: create-wechat-sticker-album
description: "Plan, generate, validate, and package upload-ready static WeChat sticker albums from a theme, character brief, reference image, or item-by-item content. Use when Codex is asked to create a 微信表情包、微信表情专辑、静态表情套图, or a WeChat sticker asset package containing 8–24 expressions plus a cover, chat icon, banner, copy suggestions, preview, and QA report."
---

# Create a WeChat Static Sticker Album

Create a coherent, upload-ready static PNG album. Keep generation creative, but make dimensions, transparency, file size, naming, and packaging deterministic.

## Enforce the boundaries

- Support static PNG albums only. Do not create GIFs or 120×120 legacy thumbnails.
- Require an explicit count from 8 through 24. If the user omits it, ask for the count before planning. If it is outside the range, ask them to revise it; never choose or randomize a count.
- Keep every upload image free of text, letters, numbers, logos, signatures, and watermarks. Put meanings and copy only in review documents.
- Do not log in to, upload to, or submit on the WeChat Sticker Open Platform.
- Treat supplied people, characters, brands, and reference artwork as user-authorized. Ask for an original alternative when authorization is unclear.
- Use the built-in image generation tool by default. Do not silently switch to an API/CLI path requiring `OPENAI_API_KEY`.

Read [references/wechat-static-spec.md](references/wechat-static-spec.md) before planning or validating. Read [references/prompt-recipes.md](references/prompt-recipes.md) before generating any album image.

## Resolve the Python runtime

- Resolve one usable absolute Python executable before running either bundled script. In Codex desktop, call `codex_app__load_workspace_dependencies` and use the returned Python executable. If that loader is unavailable on Windows, probe `%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` before searching elsewhere.
- Reject the Windows Microsoft Store alias under `WindowsApps` when it cannot execute. Do not keep retrying the bare `python` command.
- Verify the chosen executable with `-c "import PIL; print(PIL.__version__)"`. Keep that absolute path as `<python-executable>` for all later commands.

## Collect the brief

Obtain these required values:

- album theme;
- character description or one or more authorized reference images;
- exact expression count, 8–24.

Accept either a theme-only brief that needs a full expression plan or an itemized list of meanings/actions. Also accept optional style, palette, audience, mood, and output-directory preferences. If an itemized list is shorter than the requested count, propose additions in the plan. If it is longer, ask which items to remove before generation.

Inspect every local reference image with `view_image` before using it. Label each image's role as character reference, style reference, or supporting reference; never treat a reference as an edit target unless the user asks.

## Phase 1: plan and obtain approval

1. Create a balanced list of everyday chat meanings. Make every pose, facial expression, prop, and silhouette clearly distinguishable while preserving one character and one art direction.
2. Lock the character and style in a concise invariant block: body proportions, face, colors, clothing, line work, rendering, and forbidden drift.
3. Create `album-plan.json` with this shape:

```json
{
  "album_name": "专辑名称",
  "count": 8,
  "theme": "专辑主题",
  "character_lock": "不可漂移的角色与画风规范",
  "copy": {
    "title": "标题建议",
    "introduction": "简介建议",
    "copyright": "版权信息或待填写提示"
  },
  "items": [
    {"id": "01", "meaning": "开心", "visual": "具体且无文字的动作画面"}
  ]
}
```

4. Generate exactly one front-facing half-body or full-body character anchor on a removable chroma-key background. Make it representative, uncluttered, text-free, and suitable to become the cover.
5. Remove the chroma key with the installed imagegen helper, save the transparent anchor locally, and display it with the numbered expression plan.
6. Ask the user to approve or revise both the plan and anchor. Stop before generating expressions, icon, or banner. Treat any revision as a return to this phase.

## Phase 2: generate after explicit approval

1. Freeze the approved plan and anchor. Use the saved anchor path as a reference in every later generation call.
2. Generate each expression in a separate built-in image generation call. Repeat the character lock and the item's unique action; prohibit all text and background detail.
3. Generate one dedicated front-facing head icon from the anchor reference.
4. Use the approved anchor as the cover source.
5. Generate one dedicated wide 15:8 banner from the anchor reference. Use an opaque, bright, non-white setting related to the album and stage all important content inside the central safe area.
6. For transparent assets, generate on a perfectly flat key color, then resolve `$CODEX_HOME` (fallback `~/.codex`) and run:

```text
<python-executable> <codex-home>/skills/.system/imagegen/scripts/remove_chroma_key.py --input <key-source> --out <transparent-png> --auto-key border --soft-matte --transparent-threshold 12 --opaque-threshold 220 --despill
```

   Use green by default and magenta when the character contains green. Validate alpha and edge spill. Ask before any true-transparency CLI fallback.
7. Arrange preprocessed sources exactly as follows:

```text
raw/
├─ expressions/01.png ... NN.png
├─ cover.png
├─ icon.png
└─ banner.png
```

8. Save the approved JSON plan outside the intended output directory. Choose a new versioned output directory; never overwrite an earlier album.
9. Run the bundled packager:

```text
<python-executable> <skill-dir>/scripts/package_album.py --raw-dir <raw> --plan <album-plan.json> --out-dir <new-album-dir>
```

10. Require exit code 0 and `automated_status: passed` in `review/qa-report.json`. Inspect `review/contact-sheet.png` at high detail for character drift, unwanted text, edge halos/jaggies, excessive blank space, clipped anatomy, repeated poses, banner story, and safe cropping. Regenerate only failing assets and package into a new versioned directory.
11. Deliver the upload folder, review folder, ZIP path, final prompt set, generation mode, automated warnings, and manual visual-QA result.

## Preserve the output contract

Produce this structure:

```text
<album-name>/
├─ upload/
│  ├─ expressions/01.png ... NN.png
│  ├─ cover.png
│  ├─ icon.png
│  └─ banner.png
├─ review/
│  ├─ album-plan.md
│  ├─ album-plan.json
│  ├─ album-copy.md
│  ├─ item-manifest.csv
│  ├─ contact-sheet.png
│  └─ qa-report.json
└─ <album-name>-package.zip
```

Treat the ZIP as a convenience archive, not as a platform bulk-import format. Upload the individual files under `upload/`.
