from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def stable_video_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def safe_filename(text: str, fallback: str = "video") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-._")
    return cleaned[:80] or fallback


def run_json(command: list[str], timeout: int = 60) -> dict[str, Any]:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(message or f"Command failed: {' '.join(command)}")
    return json.loads(result.stdout)


def run_text(command: list[str], timeout: int = 120) -> str:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(message or f"Command failed: {' '.join(command)}")
    return result.stdout.strip()


def fetch_metadata(url: str, downloader: str = "yt-dlp") -> dict[str, Any]:
    return run_json([downloader, "--dump-json", "--no-warnings", url], timeout=90)


def download_video(url: str, artifact_dir: Path, downloader: str = "yt-dlp") -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    before = set(artifact_dir.glob("source.*"))
    output_template = str(artifact_dir / "source.%(ext)s")
    result = subprocess.run(
        [downloader, "-f", "bv*+ba/b", "-o", output_template, url],
        text=True,
        capture_output=True,
        check=False,
        timeout=300,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(message or "Video download failed.")
    after = set(artifact_dir.glob("source.*"))
    created = sorted(after - before, key=lambda item: item.stat().st_mtime, reverse=True)
    if created:
        return created[0]
    existing = sorted(after, key=lambda item: item.stat().st_mtime, reverse=True)
    if existing:
        return existing[0]
    raise RuntimeError("Video download completed but no source file was found.")


def probe_media(path: Path) -> dict[str, Any]:
    if not tool_available("ffprobe"):
        return {"status": "skipped", "reason": "ffprobe not installed"}
    return run_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_name,codec_type,width,height,duration,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        timeout=30,
    )


def extract_audio(video_path: Path, artifact_dir: Path) -> Path | None:
    if not tool_available("ffmpeg"):
        return None
    audio_path = artifact_dir / "audio.m4a"
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path), "-vn", "-c:a", "aac", str(audio_path)],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        return None
    return audio_path if audio_path.exists() else None


def extract_contact_sheet(video_path: Path, artifact_dir: Path, every_seconds: int = 10) -> Path | None:
    if not tool_available("ffmpeg"):
        return None
    image_path = artifact_dir / "contact_sheet.jpg"
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{every_seconds},scale=320:-1,tile=5x5",
            str(image_path),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        return None
    return image_path if image_path.exists() else None


def transcribe_audio(audio_path: Path, artifact_dir: Path, command_template: str | None = None) -> dict[str, str]:
    if command_template:
        command = [part.format(audio=str(audio_path), output_dir=str(artifact_dir)) for part in command_template.split()]
        try:
            text = run_text(command, timeout=600)
        except Exception as exc:
            return {"status": "failed", "reason": str(exc), "text": ""}
        transcript_path = artifact_dir / "transcript.txt"
        transcript_path.write_text(text + "\n", encoding="utf-8")
        return {"status": "ok", "source": "custom-command", "text": text, "path": str(transcript_path)}
    if tool_available("whisper"):
        model = os.environ.get("LOCAL_BRAIN_WHISPER_MODEL", "base")
        language = os.environ.get("LOCAL_BRAIN_WHISPER_LANGUAGE", "zh")
        result = subprocess.run(
            [
                "whisper",
                str(audio_path),
                "--model",
                model,
                *([] if not language else ["--language", language]),
                "--fp16",
                "False",
                "--output_format",
                "txt",
                "--output_dir",
                str(artifact_dir),
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=900,
        )
        transcript_path = artifact_dir / f"{audio_path.stem}.txt"
        if result.returncode == 0 and transcript_path.exists():
            text = transcript_path.read_text(encoding="utf-8", errors="ignore").strip()
            return {"status": "ok", "source": "whisper-cli", "text": text, "path": str(transcript_path)}
        return {"status": "failed", "reason": (result.stderr or result.stdout).strip(), "text": ""}
    return {"status": "skipped", "reason": "no transcription command configured and whisper CLI not installed", "text": ""}


def metadata_text(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return value if isinstance(value, str) else ""


def extract_key_points(description: str) -> list[str]:
    points: list[str] = []
    for line in description.splitlines():
        cleaned = line.strip()
        match = re.match(r"^\s*(?:[-*]|\d+[.、])\s*(.+)$", cleaned)
        if match:
            points.append(match.group(1).strip())
    if points:
        return points[:12]
    sentences = re.split(r"[。！？\n]+", description)
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) >= 12][:8]


PROJECT_HINTS = {
    "ppt-master": {
        "name": "PPT Master",
        "category": "AI PPT / presentation workflow",
        "repo": "https://github.com/hugohe3/ppt-master",
        "value": "生成原生可编辑 PPTX，适合把文档、网页、论文或报告转成可继续修改的演示稿。",
        "watchouts": "依赖强模型和较清晰的素材；不是一键许愿池，仍需要确认大纲、风格和成品修订。",
    },
    "codex-ppt": {
        "name": "Codex PPT Skill",
        "category": "image-based PPT skill",
        "repo": "https://github.com/ningzimu/codex-ppt-skill",
        "value": "用阶段化流程生成强视觉统一的图片式 PPT，并可沉淀个人风格库。",
        "watchouts": "整页图片式产物不适合直接编辑单个文字或图表，中文小字需要重点校验。",
    },
    "gpt-image": {
        "name": "GPT Image workflow",
        "category": "visual generation",
        "repo": "",
        "value": "为封面、概念图、页面背景和强视觉页面提供高质量素材。",
        "watchouts": "图片里的文字、图表和细节要人工复核，避免把整页可编辑内容栅格化。",
    },
    "codex": {
        "name": "Codex",
        "category": "agent runtime",
        "repo": "https://developers.openai.com/codex/",
        "value": "把资料读取、脚本执行、文件生成和多轮修订串成可执行工作流。",
        "watchouts": "需要明确权限边界和验收标准，避免只生成漂亮但不可维护的产物。",
    },
}


def normalize_text(*parts: str) -> str:
    return "\n".join(part for part in parts if part).lower()


def infer_project_tools(note: dict[str, Any]) -> list[dict[str, str]]:
    text = normalize_text(
        str(note.get("title") or ""),
        str(note.get("summary") or ""),
        "\n".join(str(point) for point in note.get("key_points") or []),
        str((note.get("transcript") or {}).get("text") or ""),
    )
    tools: list[dict[str, str]] = []
    for keyword, payload in PROJECT_HINTS.items():
        if keyword in text:
            tools.append({"keyword": keyword, **payload})
    return tools


def infer_content_type(note: dict[str, Any]) -> str:
    text = normalize_text(str(note.get("title") or ""), str(note.get("summary") or ""))
    if "/note/" in str(note.get("webpage_url") or "") or "图文" in text:
        return "图文笔记"
    if "ppt" in text or "slide" in text or "presentation" in text:
        return "PPT 工作流展示"
    if "github" in text or "开源" in text:
        return "开源项目介绍"
    return "视频/图文内容"


def build_project_report(note: dict[str, Any], target: str = "local-brain") -> dict[str, Any]:
    title = str(note.get("title") or "Untitled")
    summary = str(note.get("summary") or "").strip()
    key_points = [str(point) for point in note.get("key_points") or []]
    tools = infer_project_tools(note)
    content_type = infer_content_type(note)
    source_confidence = note.get("confidence") if isinstance(note.get("confidence"), dict) else {}
    transcript_confidence = str(source_confidence.get("transcript") or "missing")
    visual_confidence = str(source_confidence.get("visual") or "missing")

    opportunities = [
        "把链接解析、元数据、字幕、画面帧和外部项目检索合并成一个标准入口。",
        "输出不止摘要，还要给出可执行的项目价值、风险、安装/接入路径和落地建议。",
        "把高频格式沉淀成可复用模板，降低每次看视频后的人工整理成本。",
    ]
    if tools:
        opportunities.insert(0, f"识别到 {len(tools)} 个工具/项目线索，可进入 GitHub 或官方文档研究。")

    risks = [
        "短视频平台可能拦截命令行抓取，必须允许元数据、人工摘录或浏览器截图作为备用输入。",
        "没有字幕或图文原图时，视觉判断只能作为低置信度推断。",
        "涉及开源项目时，需要用官方仓库 README 或文档复核，不应只依据视频标题做结论。",
    ]
    if transcript_confidence == "missing":
        risks.insert(0, "当前没有可用转录文本，内容理解主要依赖标题、描述和人工补充。")
    if visual_confidence in {"missing", "low"}:
        risks.insert(0, "当前没有可靠视觉 OCR/画面理解，图文页细节需要后续补图或浏览器读取。")

    workflow = [
        "解析链接：展开短链，识别平台、内容类型、作者、标题和真实页面。",
        "采集素材：优先下载视频/图文；失败时保存元数据、人工摘录、截图或浏览器结果。",
        "提取信息：生成字幕、关键帧、描述要点和可疑项目名。",
        "项目研究：对识别出的 GitHub/工具名查官方仓库、README、安装方式和限制。",
        "落地映射：把视频方法映射到当前副脑、网站或具体项目的改造项。",
        "沉淀记忆：保存结构化报告、来源、置信度和下一步动作。",
    ]

    action_items = [
        {
            "priority": "P0",
            "item": "为每条链接生成结构化报告",
            "detail": "固定输出摘要、工具线索、风险、落地建议、置信度和来源路径。",
        },
        {
            "priority": "P1",
            "item": "增加 GitHub/官方文档复核",
            "detail": "对标题里出现的项目名自动生成待检索清单，优先使用官方仓库。",
        },
        {
            "priority": "P1",
            "item": "补浏览器/截图备用通道",
            "detail": "当 yt-dlp 或 curl 被 WAF 拦截时，允许导入截图或浏览器提取结果。",
        },
        {
            "priority": "P2",
            "item": "接入视觉 OCR",
            "detail": "对图文笔记、PPT 展示和代码截图提取页面文字，提升图文内容解析质量。",
        },
    ]

    return {
        "schema": "local-brain.video-project-report.v1",
        "source": {
            "title": title,
            "author": note.get("author") or "",
            "source_url": note.get("source_url") or "",
            "webpage_url": note.get("webpage_url") or "",
            "content_type": content_type,
        },
        "target": target,
        "summary": summary or "当前缺少足够正文，需补充字幕、截图或人工摘录后再做深度分析。",
        "key_points": key_points,
        "detected_tools": tools,
        "opportunities": opportunities,
        "risks": risks,
        "recommended_workflow": workflow,
        "action_items": action_items,
        "confidence": {
            "metadata": str(source_confidence.get("metadata") or "unknown"),
            "transcript": transcript_confidence,
            "visual": visual_confidence,
            "project_inference": "medium" if tools else "low",
        },
    }


def render_project_report_markdown(report: dict[str, Any]) -> str:
    source = report["source"]
    lines = [
        f"# {source['title']}",
        "",
        "## 来源",
        "",
        f"- 作者：{source.get('author') or '(unknown)'}",
        f"- 类型：{source.get('content_type') or '视频/图文内容'}",
        f"- 链接：{source.get('source_url') or source.get('webpage_url')}",
        "",
        "## 摘要",
        "",
        str(report.get("summary") or ""),
        "",
    ]
    key_points = report.get("key_points") or []
    if key_points:
        lines.extend(["## 关键点", ""])
        lines.extend(f"- {point}" for point in key_points)
        lines.append("")
    tools = report.get("detected_tools") or []
    lines.extend(["## 识别到的工具/项目", ""])
    if tools:
        for tool in tools:
            repo = f"（{tool['repo']}）" if tool.get("repo") else ""
            lines.append(f"- {tool['name']}：{tool['value']} {repo}".rstrip())
            lines.append(f"  风险：{tool['watchouts']}")
    else:
        lines.append("- 暂未识别到明确项目名；需要补充字幕、截图或人工摘录。")
    lines.append("")
    for section, key in [
        ("## 可借鉴点", "opportunities"),
        ("## 风险/限制", "risks"),
        ("## 推荐处理流程", "recommended_workflow"),
    ]:
        lines.extend([section, ""])
        lines.extend(f"- {item}" for item in report.get(key) or [])
        lines.append("")
    lines.extend(["## 落地动作", ""])
    for item in report.get("action_items") or []:
        lines.append(f"- [{item['priority']}] {item['item']}：{item['detail']}")
    lines.extend(["", "## 置信度", ""])
    confidence = report.get("confidence") or {}
    lines.extend(f"- {key}：{value}" for key, value in confidence.items())
    return "\n".join(lines).rstrip() + "\n"


def build_video_note(
    url: str,
    metadata: dict[str, Any],
    artifact_dir: Path | None = None,
    media_probe: dict[str, Any] | None = None,
    transcript: dict[str, str] | None = None,
    contact_sheet: Path | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    description = metadata_text(metadata, "description")
    title = metadata_text(metadata, "title") or metadata_text(metadata, "fulltitle") or "Untitled video"
    author = metadata_text(metadata, "uploader") or metadata_text(metadata, "channel") or metadata_text(metadata, "artist")
    transcript = transcript or {"status": "skipped", "text": ""}
    transcript_text = transcript.get("text", "").strip()
    source_fields = ["metadata"]
    if transcript_text:
        source_fields.append("transcript")
    if contact_sheet:
        source_fields.append("visual_contact_sheet")
    summary_source = transcript_text or description
    summary = re.sub(r"\s+", " ", summary_source).strip()[:500]
    return {
        "schema": "local-brain.video-note.v1",
        "video_id": str(metadata.get("id") or stable_video_id(url)),
        "source_url": url,
        "webpage_url": metadata.get("webpage_url") or url,
        "title": title,
        "author": author,
        "duration_seconds": metadata.get("duration"),
        "duration_string": metadata.get("duration_string"),
        "upload_date": metadata.get("upload_date"),
        "stats": {
            "view_count": metadata.get("view_count"),
            "like_count": metadata.get("like_count"),
            "comment_count": metadata.get("comment_count"),
            "repost_count": metadata.get("repost_count"),
            "save_count": metadata.get("save_count"),
        },
        "summary": summary,
        "key_points": extract_key_points(description or transcript_text),
        "transcript": transcript,
        "visual_notes": {
            "status": "contact_sheet_created" if contact_sheet else "skipped",
            "contact_sheet": str(contact_sheet) if contact_sheet else "",
            "note": "OCR and frame-level vision are not enabled in this local MVP.",
        },
        "media_probe": media_probe or {},
        "artifact_dir": str(artifact_dir) if artifact_dir else "",
        "sources_used": source_fields,
        "confidence": {
            "metadata": "high" if metadata else "low",
            "transcript": "high" if transcript_text else "missing",
            "visual": "low" if contact_sheet else "missing",
            "inference": "low",
        },
        "errors": errors or [],
    }
