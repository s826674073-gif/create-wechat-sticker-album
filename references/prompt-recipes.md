# Prompt Recipes

Use the approved character anchor as a local reference image in every generation after Phase 1. Keep the character lock verbatim across the complete album and change only the requested emotion, action, and necessary props.

## Key-color rule

- Default to a perfectly flat `#00ff00` background.
- Use `#ff00ff` when the character or required props contain green.
- Do not use the chosen key color anywhere in the subject.
- Require no floor plane, cast shadow, contact shadow, gradient, texture, reflection, scenery, or lighting variation on transparent-asset sources.

## Character anchor and cover source

```text
Use case: stylized-concept
Asset type: WeChat static sticker character anchor and future album cover
Primary request: Create one clear, front-facing half-body or full-body view of the described original character.
Subject: <character description>
Style/medium: <approved style>
Composition/framing: One centered character, recognizable silhouette, generous but not excessive edge padding, no crop.
Color palette: <locked palette>
Scene/backdrop: Perfectly flat solid <key color> chroma-key background.
Constraints: Preserve the exact face, proportions, clothing, colors, line weight, and rendering rules in <character lock>. No pose sheet and no multiple views.
Avoid: text, letters, numbers, speech bubbles, logos, signatures, watermark, white outline, decoration, floor, shadow, reflection, gradient, scenery.
```

## Main expression

```text
Use case: stylized-concept
Asset type: One static WeChat sticker source image
Primary request: Show the approved character expressing <meaning> through <visual action>.
Input images: Image 1 is the identity and style anchor; preserve it exactly.
Subject: The same character only, with a strongly readable facial expression, pose, silhouette, and only necessary props.
Composition/framing: Centered square composition, full action visible, no clipped ears/hands/feet/props, compact readable silhouette.
Scene/backdrop: Perfectly flat solid <key color> chroma-key background.
Constraints: Keep <character lock> unchanged. Make this pose clearly different from every other numbered item. Communicate without written language.
Avoid: text of any kind, letters, numbers, punctuation, speech bubbles, logos, signature, watermark, white outline, scenery, floor, cast shadow, reflection, gradient, extra characters unless approved.
```

## Chat icon source

```text
Use case: stylized-concept
Asset type: 50×50 WeChat chat icon source
Primary request: Create one front-facing head portrait of the approved character.
Input images: Image 1 is the identity and style anchor; preserve it exactly.
Composition/framing: Centered symmetrical head, highly recognizable at tiny size, simple silhouette, comfortable padding.
Scene/backdrop: Perfectly flat solid <key color> chroma-key background.
Constraints: Keep the face, colors, line weight, and rendering identical to the anchor.
Avoid: body pose, props, decoration, text, letters, numbers, logo, signature, watermark, white outline, shadow, reflection, gradient.
```

## Detail banner

```text
Use case: illustration-story
Asset type: 750×400 WeChat album detail banner
Primary request: Create a lively, story-like wide scene related to <album theme> featuring the approved character.
Input images: Image 1 is the identity and style anchor; preserve it exactly.
Composition/framing: Wide 15:8 layout; keep faces, limbs, and important props inside the central 80% crop-safe region; no stretched anatomy.
Scene/backdrop: Opaque bright colored setting with clear contrast from a white interface; never white or transparent.
Constraints: Preserve <character lock>. Make the scene rich but readable and directly related to the album.
Avoid: all text, letters, numbers, signage, captions, speech bubbles, logo, signature, watermark, white background, transparent background.
```

## Iteration rule

Inspect each result before continuing. If it fails, make one targeted correction while repeating all identity and no-text invariants. Save only approved sources into the `raw/` contract used by the packager.
