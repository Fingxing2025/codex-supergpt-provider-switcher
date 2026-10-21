---
name: "supergpt-imagegen"
description: "Generate images with SuperGPT in either desktop SuperGPT mode, including independent API mode without Work browser. Use for requests to draw, create pictures, or generate images with the active SuperGPT provider."
---

# SuperGPT Image Generation

Use this skill when the user wants a new image while either SuperGPT mode is active. It calls SuperGPT's `/v1/images/generations` endpoint with the provider's own key. No Work browser, `node_repl`, or ChatGPT login token is needed for this request. The script checks the active provider before sending.

Run the bundled helper with a concrete prompt:

```bash
"${CODEX_HOME:-$HOME/.codex}/skills/supergpt-imagegen/scripts/generate.sh" \
  --prompt "<image prompt>" \
  --out "<output path>"
```

Use a unique absolute output path under the task's `outputs/imagegen/` directory. The helper defaults to `gpt-image-2.5-sunburst`, `1024x1024`, maximum (`max`) quality, and PNG output. It reads the active provider's key or the local `supergpt-api-key` file without exposing it in process arguments. `--prompt-file` accepts a UTF-8 prompt file. `--dry-run` reports non-secret settings without contacting SuperGPT; `--config` can inspect either mode's template.

Sunburst is the quality-first default; the upstream image prompting guide recommends it for demanding quality requirements. The SuperGPT model plaza also lists `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-2.5-flare`. The provider's support for `max` quality has not been confirmed by a live request; report unsupported-parameter errors without silently downgrading. When the user explicitly chooses an older model, the helper defaults that model to `high` instead of unsupported `max`. Actual access depends on the user's key group. Do not automatically try alternative models after a failure. Successful image generation may be billed by SuperGPT; timeouts do not prove no image was generated. Report errors without claiming success, and check before repeating a possibly billed request.

After success, use the returned absolute `image_path` to inspect the local image with `view_image` and display it using `![description](/absolute/path.png)`. A saved helper response is not proof of success until an image path is returned. This helper supports new image generation; it does not currently implement editing an attached image.

Use the built-in `$imagegen` skill when the user explicitly wants the official Codex image generation route. Do not claim that the built-in route uses SuperGPT.

Reference: [SuperGPT model plaza](https://console.supergpt.dev/model-plaza).

Model choice reference: https://developers.openai.com/api/docs/guides/image-prompting
