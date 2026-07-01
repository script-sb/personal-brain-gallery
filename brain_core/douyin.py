from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener


DOUYIN_HOST_RE = re.compile(r"(^|\.)((douyin|iesdouyin)\.com)$")
DOUYIN_ID_PATTERNS = [
    ("note", re.compile(r"/(?:note|share/note)/(\d+)")),
    ("gallery", re.compile(r"/gallery/(\d+)")),
    ("video", re.compile(r"/(?:video|share/video)/(\d+)")),
]


def extract_first_url(text: str) -> str:
    match = re.search(r"https?://[^\s，。]+", text)
    return match.group(0).rstrip(".,;:，。；：") if match else text.strip()


def is_douyin_url(url: str) -> bool:
    host = urlparse(url).netloc.lower().split(":")[0]
    return bool(DOUYIN_HOST_RE.search(host))


def detect_content_type(url: str) -> str:
    path = urlparse(url).path
    for kind, pattern in DOUYIN_ID_PATTERNS:
        if pattern.search(path):
            return "note" if kind == "gallery" else kind
    if "v.douyin.com" in urlparse(url).netloc.lower():
        return "shortlink"
    return "unknown"


def parse_content_id(url: str) -> str:
    path = urlparse(url).path
    for _, pattern in DOUYIN_ID_PATTERNS:
        match = pattern.search(path)
        if match:
            return match.group(1)
    return ""


def expand_shortlink(url: str, timeout: int = 12) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            )
        },
    )
    opener = build_opener()
    try:
        with opener.open(request, timeout=timeout) as response:
            return {
                "status": "ok",
                "input_url": url,
                "final_url": response.geturl(),
                "http_status": response.status,
            }
    except HTTPError as exc:
        return {
            "status": "failed",
            "input_url": url,
            "final_url": exc.geturl() or "",
            "http_status": exc.code,
            "reason": str(exc),
        }
    except (TimeoutError, URLError, OSError) as exc:
        return {
            "status": "failed",
            "input_url": url,
            "final_url": "",
            "http_status": None,
            "reason": str(exc),
        }


def cookie_config_status(default_path: Path) -> dict[str, Any]:
    env_value = os.environ.get("LOCAL_BRAIN_DOUYIN_COOKIE", "").strip()
    env_file = os.environ.get("LOCAL_BRAIN_DOUYIN_COOKIE_FILE", "").strip()
    configured_path = Path(env_file).expanduser() if env_file else default_path
    has_cookie = bool(env_value)
    if not has_cookie and configured_path.exists():
        has_cookie = bool(configured_path.read_text(encoding="utf-8", errors="ignore").strip())
    return {
        "configured": has_cookie,
        "env_cookie": bool(env_value),
        "cookie_file": str(configured_path),
        "cookie_file_exists": configured_path.exists(),
        "policy": "Keep cookies in env or a private local file; never commit them.",
    }


def _collect_url_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.startswith("http"):
        return [value]
    if isinstance(value, list):
        urls: list[str] = []
        for item in value:
            urls.extend(_collect_url_list(item))
        return urls
    if isinstance(value, dict):
        urls = []
        for key in ("url_list", "download_url_list", "urls"):
            urls.extend(_collect_url_list(value.get(key)))
        for key in ("url", "uri"):
            urls.extend(_collect_url_list(value.get(key)))
        return urls
    return []


def extract_note_images(aweme_detail: dict[str, Any]) -> list[dict[str, Any]]:
    images = aweme_detail.get("images")
    if not isinstance(images, list):
        return []
    extracted: list[dict[str, Any]] = []
    for index, image in enumerate(images, start=1):
        if not isinstance(image, dict):
            continue
        urls = []
        for key in ("url_list", "download_url_list", "origin_cover", "display_image", "image"):
            urls.extend(_collect_url_list(image.get(key)))
        # Preserve order while removing duplicates.
        deduped = list(dict.fromkeys(urls))
        extracted.append(
            {
                "index": index,
                "uri": image.get("uri") or image.get("image_id") or "",
                "width": image.get("width") or image.get("display_width"),
                "height": image.get("height") or image.get("display_height"),
                "urls": deduped,
            }
        )
    return extracted


def build_fallback_plan(content_type: str, has_cookie: bool) -> list[dict[str, str]]:
    plan = [
        {
            "step": "shortlink-expand",
            "status": "ready",
            "detail": "Expand v.douyin.com to a stable /video/ or /note/ URL.",
        },
        {
            "step": "metadata-first",
            "status": "ready",
            "detail": "Try yt-dlp or known API adapters before heavier browser work.",
        },
        {
            "step": "cookie-api",
            "status": "ready" if has_cookie else "needs-cookie",
            "detail": "Use a private Douyin cookie only when the user has provided one locally.",
        },
        {
            "step": "browser-fallback",
            "status": "manual-ready",
            "detail": "Open the page in a real browser session, let the user pass verification, then capture page text/screenshots.",
        },
        {
            "step": "ocr-images",
            "status": "recommended" if content_type == "note" else "optional",
            "detail": "For note/gallery pages, extract image URLs when available; otherwise OCR browser screenshots.",
        },
    ]
    return plan


def inspect_douyin_url(
    raw_input: str,
    *,
    expanded_url: str = "",
    aweme_detail: dict[str, Any] | None = None,
    cookie_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_url = extract_first_url(raw_input)
    final_url = expanded_url or source_url
    content_type = detect_content_type(final_url)
    content_id = parse_content_id(final_url)
    images = extract_note_images(aweme_detail or {})
    cookie_status = cookie_status or {"configured": False}
    return {
        "schema": "local-brain.douyin-inspection.v1",
        "source_url": source_url,
        "final_url": final_url,
        "is_douyin": is_douyin_url(final_url) or is_douyin_url(source_url),
        "content_type": content_type,
        "content_id": content_id,
        "note_images": images,
        "image_count": len(images),
        "cookie": cookie_status,
        "fallback_plan": build_fallback_plan(content_type, bool(cookie_status.get("configured"))),
        "implementation_notes": [
            "aweme_type=68 is commonly used for Douyin image-note/gallery content.",
            "When aweme_detail.images is available, save image URL candidates and run OCR/vision over downloaded images.",
            "When WAF blocks HTTP access, prefer browser-session capture over brittle challenge bypass code.",
        ],
    }


def load_aweme_detail(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Aweme JSON must be an object.")
    detail = payload.get("aweme_detail", payload)
    if not isinstance(detail, dict):
        raise ValueError("aweme_detail must be an object.")
    return detail
