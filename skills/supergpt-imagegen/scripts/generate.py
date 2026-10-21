#!/usr/bin/env python3
"""Generate one image with the selected SuperGPT provider; never load ChatGPT tokens."""

import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://api.supergpt.dev/v1/images/generations"
MODELS = ("gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-2.5-sunburst", "gpt-image-2.5-flare")
MAX_BYTES = 64 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_limited(response):
    data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Image response exceeds the 64 MiB limit.")
    return data


def save_image(path, data):
    is_image = data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff") or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    if not is_image:
        raise ValueError("SuperGPT returned no recognizable PNG, JPEG, or WebP image.")
    if path.exists():
        raise ValueError("Output already exists; choose another --out path to preserve it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".supergpt-image-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main():
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    parser = argparse.ArgumentParser(description=__doc__)
    prompts = parser.add_mutually_exclusive_group(required=True)
    prompts.add_argument("--prompt")
    prompts.add_argument("--prompt-file", type=Path)
    parser.add_argument("--out", type=Path, default=Path("outputs/imagegen/supergpt-image.png"))
    parser.add_argument("--model", choices=MODELS, default="gpt-image-2.5-sunburst")
    parser.add_argument("--size", default="1024x1024", choices=("1024x1024",))
    parser.add_argument("--quality", default=None, choices=("low", "medium", "high", "xhigh", "max", "auto"))
    parser.add_argument("--config", type=Path, default=home / "config.toml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.quality is None:
        args.quality = "max" if args.model.startswith("gpt-image-2.5-") else "high"
    if args.quality in ("xhigh", "max") and not args.model.startswith("gpt-image-2.5-"):
        parser.error("xhigh/max quality requires a GPT Image 2.5 model.")
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("The image prompt is empty.")
    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    provider_name = config.get("model_provider", "openai")
    provider = config.get("model_providers", {}).get(provider_name, {})
    if provider_name != "supergpt" or provider.get("base_url", "").rstrip("/") != "https://api.supergpt.dev/v1":
        raise ValueError("Select a SuperGPT mode before using this image helper.")
    payload = {"model": args.model, "prompt": prompt, "n": 1, "size": args.size, "quality": args.quality, "output_format": "png"}
    output = args.out.expanduser().resolve()
    if output.exists() and not args.dry_run:
        raise ValueError("Output already exists; choose another --out path.")
    if args.dry_run:
        print(json.dumps({"endpoint": ENDPOINT, "provider": provider_name, "requires_openai_auth": provider.get("requires_openai_auth", False), "model": args.model, "size": args.size, "quality": args.quality, "output_path": str(output), "prompt_characters": len(prompt), "request_sent": False}, ensure_ascii=False, indent=2))
        return
    key_path = home / "supergpt-api-key"
    key = provider.get("experimental_bearer_token") or (key_path.read_text().strip() if key_path.is_file() else "")
    if not isinstance(key, str) or not key.strip() or "\r" in key or "\n" in key:
        raise ValueError("No valid SuperGPT API key is configured.")
    key = key.strip()
    opener = build_opener(NoRedirect())
    request = Request(ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    try:
        with opener.open(request, timeout=300) as response:
            result = json.loads(read_limited(response))
    except HTTPError as error:
        message = ""
        try:
            body = json.loads(read_limited(error))
            detail = body.get("error", body)
            message = str(detail.get("message", "")) if isinstance(detail, dict) else str(detail)
        except (ValueError, TypeError, AttributeError):
            pass
        message = message.replace(key, "[REDACTED]")[:600]
        raise ValueError(f"SuperGPT image API returned HTTP {error.code}. {message} No automatic retry was sent.") from None
    data = result.get("data") if isinstance(result, dict) else None
    image = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
    if image.get("b64_json"):
        binary = base64.b64decode("".join(image["b64_json"].split()), validate=True)
    elif image.get("url"):
        url = image["url"]
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Image download URL must use HTTPS without embedded credentials.")
        with opener.open(Request(url), timeout=300) as response:
            binary = read_limited(response)
    else:
        raise ValueError("SuperGPT returned neither image data nor an image URL. No retry was sent.")
    save_image(output, binary)
    print(json.dumps({"image_path": str(output), "model": args.model, "provider": "supergpt", "bytes": len(binary)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, URLError, binascii.Error) as error:
        print("SuperGPT image generation failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)
