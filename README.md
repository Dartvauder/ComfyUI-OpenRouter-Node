# OpenRouter Image Generator

A ComfyUI custom node for generating images via the OpenRouter API. Supports multiple AI image generation models with advanced features like batch generation, seed control, aspect ratio presets, and proxy support.

## Features

- **Multiple Models**: FLUX 2 Max, RiverFlow V2 Pro, Seedream 4.5
- **Aspect Ratio Presets**: 1:1, 16:9, 9:16, 4:3, 3:4, 21:9, or custom dimensions
- **Batch Generation**: Generate up to 8 images in a single run
- **Seed Control**: Reproducible results with fixed seed, or random with `-1`
- **Safety Checker Toggle**: Enable or disable content filtering
- **Proxy Support**: Optional proxy URL for restricted regions
- **Rate Limit Handling**: Automatic exponential backoff on 429 responses
- **Partial Success**: Returns successfully generated images even if some fail
- **Metadata Output**: JSON metadata with model, seed, timing, and prompt info
- **Environment Variable Fallback**: API key can be set via `OPENROUTER_API_KEY` env var
- **Connection Pooling**: Reusable HTTP sessions for better performance
- **Comprehensive Error Handling**: Timeout, connection, HTTP, and API error recovery

## Installation

1. Clone or copy this repository into your ComfyUI `custom_nodes` directory:

```
ComfyUI/custom_nodes/openrouter_node_api/
```

2. Ensure the required Python packages are installed:

```bash
pip install requests pillow numpy torch
```

3. Restart ComfyUI.

## Usage

The node appears in the **OpenRouter** category as **OpenRouter Image Generator**.

### Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | STRING | `""` | Text prompt for image generation (multiline) |
| `negative_prompt` | STRING | `""` | Negative prompt to exclude unwanted elements |
| `model` | DROPDOWN | `FLUX 2 Max` | AI model to use |
| `aspect_ratio` | DROPDOWN | `1:1 (1024x1024)` | Preset resolution or Custom for manual input |
| `width` | INT | `1024` | Image width (256-2048, step 64). Overridden by preset |
| `height` | INT | `1024` | Image height (256-2048, step 64). Overridden by preset |
| `api_key` | STRING | `""` | OpenRouter API key |
| `quality` | DROPDOWN | `high` | Generation quality: `standard` or `high` |
| `seed` | INT | `-1` | Random seed (`-1` = random, any positive = fixed) |
| `num_images` | INT | `1` | Number of images to generate (1-8) |
| `retries` | INT | `3` | Retry attempts on failure (1-10) |
| `safety_checker` | BOOLEAN | `True` | Enable content safety filtering |
| `proxy_url` | STRING | `""` | Optional proxy URL (http/https) |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `images` | IMAGE | Generated image(s) as a batch tensor |
| `metadata` | STRING | JSON with generation details (model, seed, timing, errors) |

## Models

| Display Name | Model ID | Description |
|--------------|----------|-------------|
| FLUX 2 Max | `black-forest-labs/flux.2-max` | High-quality image generation by Black Forest Labs |
| RiverFlow V2 Pro | `sourceful/riverflow-v2-pro` | Professional image generation by Sourceful |
| Seedream 4.5 | `bytedance-seedance/seedream-4.5` | Advanced image generation by ByteDance |

## Aspect Ratio Presets

| Preset | Resolution |
|--------|------------|
| 1:1 | 1024x1024 |
| 16:9 | 1344x768 |
| 9:16 | 768x1344 |
| 4:3 | 1152x896 |
| 3:4 | 896x1152 |
| 21:9 | 1536x640 |
| Custom | Manual width/height input |

## API Key

Provide your OpenRouter API key in the node's `api_key` field, or set it as an environment variable:

```bash
export OPENROUTER_API_KEY="your-key-here"
```

Get your API key at [openrouter.ai](https://openrouter.ai/).

## Metadata Output Example

```json
{
  "images_generated": 2,
  "images_failed": 0,
  "metadata": [
    {
      "model": "black-forest-labs/flux.2-max",
      "seed": 1234567890,
      "width": 1024,
      "height": 1024,
      "quality": "high",
      "generation_time_sec": 12.34,
      "timestamp": "2026-04-25T10:30:00",
      "prompt": "A beautiful sunset over mountains"
    }
  ],
  "errors": []
}
```

## Error Handling

- **401/403**: Authentication failure — stops immediately, no retries
- **429**: Rate limited — waits for `Retry-After` header or exponential backoff
- **Timeout**: 120s per request, retries with exponential backoff (2s → 4s → 8s, max 30s)
- **Partial success**: If some images fail but others succeed, successful images are returned with error details in metadata

## License

MIT

---

## Usage

1. Open ComfyUI
2. Right click → search:

   ```
   OpenRouter FLUX PRO
   ```
3. Insert node into workflow
4. Enter:

   * API Key
   * Prompt
   * Negative Prompt (optional)
   * Width / Height
5. Connect to:

   * Preview Image
   * Save Image

---

## API Key

You need an OpenRouter API key from:
[https://openrouter.ai/](https://openrouter.ai/)

Insert it directly into the node input.

---

## Notes

* This node uses OpenRouter cloud inference (no local model required)
* Image quality and speed depend on OpenRouter backend load
* FLUX model output may vary per request (non-deterministic)
