import os
import json
import time
import base64
import logging
import requests
import torch
import numpy as np
from PIL import Image
from io import BytesIO
from datetime import datetime

logger = logging.getLogger(__name__)

MODELS = {
    "FLUX 2 Max": "black-forest-labs/flux.2-max",
    "RiverFlow V2 Pro": "sourceful/riverflow-v2-pro",
    "Seedream 4.5": "bytedance-seedance/seedream-4.5",
}

ASPECT_RATIOS = {
    "1:1 (1024x1024)": (1024, 1024),
    "16:9 (1344x768)": (1344, 768),
    "9:16 (768x1344)": (768, 1344),
    "4:3 (1152x896)": (1152, 896),
    "3:4 (896x1152)": (896, 1152),
    "21:9 (1536x640)": (1536, 640),
    "Custom": (0, 0),
}

_session = None

def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=0,
        )
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session


class OpenRouterImageGenerator:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "model": (list(MODELS.keys()), {"default": "FLUX 2 Max"}),
                "aspect_ratio": (list(ASPECT_RATIOS.keys()), {"default": "1:1 (1024x1024)"}),
                "width": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64}),
                "height": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
                "quality": (["standard", "high"], {"default": "high"}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 0xFFFFFFFFFFFFFFFF}),
                "num_images": ("INT", {"default": 1, "min": 1, "max": 8}),
                "retries": ("INT", {"default": 3, "min": 1, "max": 10}),
                "safety_checker": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "proxy_url": ("STRING", {"default": "", "multiline": False}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "metadata")
    FUNCTION = "generate"
    CATEGORY = "OpenRouter"
    OUTPUT_NODE = True

    def generate(
        self,
        prompt,
        negative_prompt,
        model,
        aspect_ratio,
        width,
        height,
        api_key,
        quality,
        seed,
        num_images,
        retries,
        safety_checker,
        proxy_url="",
    ):
        start_time = time.time()

        api_key = api_key.strip() or os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("API key is required. Provide it in the node or set OPENROUTER_API_KEY environment variable.")

        if aspect_ratio in ASPECT_RATIOS:
            ar_w, ar_h = ASPECT_RATIOS[aspect_ratio]
            if ar_w > 0 and ar_h > 0:
                width = ar_w
                height = ar_h

        if seed == -1:
            seed = int(torch.randint(0, 0xFFFFFFFFFFFFFFFF, (1,)).item())

        model_id = MODELS[model]
        logger.info(f"[OpenRouter] model={model_id} size={width}x{height} seed={seed} count={num_images}")

        full_prompt = prompt.strip()
        if negative_prompt.strip():
            full_prompt += f"\n\nNegative prompt: {negative_prompt.strip()}"

        session = get_session()
        if proxy_url and proxy_url.strip():
            session.proxies = {
                "http": proxy_url.strip(),
                "https": proxy_url.strip(),
            }

        all_images = []
        all_metadata = []
        errors = []

        for img_idx in range(num_images):
            current_seed = seed + img_idx
            last_error = None

            for attempt in range(retries):
                try:
                    payload = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": full_prompt}],
                        "modalities": ["image"],
                        "width": width,
                        "height": height,
                        "quality": quality,
                        "seed": current_seed,
                    }

                    if not safety_checker:
                        payload["safety"] = False

                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/comfyui",
                        "X-Title": "ComfyUI OpenRouter Node",
                    }

                    response = session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=120,
                    )

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 2 ** (attempt + 1)))
                        logger.warning(f"[OpenRouter] Rate limited, waiting {retry_after}s (attempt {attempt + 1}/{retries})")
                        time.sleep(retry_after)
                        continue

                    response.raise_for_status()

                    data = response.json()

                    if "error" in data:
                        err_msg = data["error"].get("message", str(data["error"]))
                        raise RuntimeError(f"API error: {err_msg}")

                    choices = data.get("choices", [])
                    if not choices:
                        raise RuntimeError(f"No choices in response: {data}")

                    message = choices[0].get("message", {})
                    images = message.get("images", [])

                    if not images:
                        raise RuntimeError(f"No images in response: {data}")

                    img_data = images[0]
                    img = self._decode_image(img_data, session)

                    img_np = np.array(img).astype(np.float32) / 255.0
                    img_tensor = torch.from_numpy(img_np)[None,]
                    all_images.append(img_tensor)

                    gen_time = time.time() - start_time
                    meta = {
                        "model": model_id,
                        "seed": current_seed,
                        "width": width,
                        "height": height,
                        "quality": quality,
                        "generation_time_sec": round(gen_time, 2),
                        "timestamp": datetime.now().isoformat(),
                        "prompt": prompt.strip(),
                    }
                    all_metadata.append(meta)

                    logger.info(f"[OpenRouter] Image {img_idx + 1}/{num_images} generated (seed={current_seed}, {gen_time:.1f}s)")
                    break

                except requests.exceptions.Timeout:
                    last_error = "Request timed out"
                    logger.warning(f"[OpenRouter] Timeout (attempt {attempt + 1}/{retries})")
                except requests.exceptions.ConnectionError as e:
                    last_error = f"Connection error: {e}"
                    logger.warning(f"[OpenRouter] Connection error (attempt {attempt + 1}/{retries})")
                except requests.exceptions.HTTPError as e:
                    last_error = f"HTTP error: {e}"
                    logger.error(f"[OpenRouter] {last_error}")
                    if response.status_code in (401, 403):
                        raise ValueError(f"Authentication failed: {e}")
                except RuntimeError:
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"[OpenRouter] Error: {last_error} (attempt {attempt + 1}/{retries})")

                if attempt < retries - 1:
                    delay = min(2 ** attempt * 2, 30)
                    logger.info(f"[OpenRouter] Retrying in {delay}s...")
                    time.sleep(delay)

            if last_error and len(all_images) <= img_idx:
                errors.append(f"Image {img_idx + 1} failed: {last_error}")
                logger.error(f"[OpenRouter] {errors[-1]}")

        if not all_images:
            raise RuntimeError(f"All attempts failed. Last error: {errors[-1] if errors else 'unknown'}")

        combined = torch.cat(all_images, dim=0)

        result_meta = {
            "images_generated": len(all_images),
            "images_failed": len(errors),
            "metadata": all_metadata,
            "errors": errors,
        }

        total_time = time.time() - start_time
        logger.info(f"[OpenRouter] Complete: {len(all_images)} images in {total_time:.1f}s")

        return (combined, json.dumps(result_meta, indent=2))

    def _decode_image(self, img_data, session):
        if "image_base64" in img_data:
            return Image.open(BytesIO(base64.b64decode(img_data["image_base64"]))).convert("RGB")

        if "url" in img_data:
            resp = session.get(img_data["url"], timeout=60)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGB")

        if "image_url" in img_data:
            url = img_data["image_url"]
            if isinstance(url, dict):
                url = url.get("url", "")
            if not url:
                raise RuntimeError(f"Empty URL in image_url: {img_data}")
            if url.startswith("data:image"):
                b64 = url.split(",", 1)[1]
                return Image.open(BytesIO(base64.b64decode(b64))).convert("RGB")
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGB")

        raise RuntimeError(f"Unknown image format: {list(img_data.keys())}")


NODE_CLASS_MAPPINGS = {
    "OpenRouterImageGenerator": OpenRouterImageGenerator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OpenRouterImageGenerator": "OpenRouter Image Generator",
}