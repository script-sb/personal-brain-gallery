from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Iterable

from .douyin import (
    cookie_config_status,
    expand_shortlink,
    inspect_douyin_url,
    load_aweme_detail,
)
from .video import (
    build_video_note,
    build_project_report,
    download_video,
    extract_audio,
    extract_contact_sheet,
    fetch_metadata,
    probe_media,
    render_project_report_markdown,
    safe_filename,
    stable_video_id,
    tool_available,
    transcribe_audio,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "registry" / "projects.json"
DB_PATH = ROOT / "data" / "brain.sqlite"
THIRD_PARTY = ROOT / "third_party"
WORKSPACE_ROOT = ROOT / "workspace"
VIDEO_WORKSPACE = WORKSPACE_ROOT / "videos"
PRIVATE_CONFIG_ROOT = ROOT / "data" / "private"
DOUYIN_COOKIE_PATH = PRIVATE_CONFIG_ROOT / "douyin_cookie.txt"
DEVTOOLS_MCP_BIN = THIRD_PARTY / "chrome-devtools-mcp" / "build" / "src" / "bin" / "chrome-devtools-mcp.js"
AGENTMEMORY_CLI = THIRD_PARTY / "agentmemory" / "dist" / "cli.mjs"
CLAUDE_CONTEXT_MCP_BIN = THIRD_PARTY / "claude-context" / "packages" / "mcp" / "dist" / "index.js"
MIRAGE_TS_ROOT = THIRD_PARTY / "mirage" / "typescript"


FUND_PROFILES = {
    "conservative": {
        "stock": 35,
        "bond": 60,
        "cash": 5,
        "note": "偏稳健，适合波动承受能力较低或目标期限较短的投资者。",
    },
    "balanced": {
        "stock": 60,
        "bond": 35,
        "cash": 5,
        "note": "股债平衡，适合中长期目标和中等波动承受能力。",
    },
    "growth": {
        "stock": 80,
        "bond": 15,
        "cash": 5,
        "note": "偏成长，适合长期目标且能承受较大回撤的投资者。",
    },
}

FUND_SLEEVES = {
    "us_total_market": "美国全市场或 S&P 500 指数基金",
    "international": "国际股票指数基金",
    "bond": "综合债券或短中期国债指数基金",
    "cash": "货币基金、短债或现金储备",
}


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    repo: str
    collection: str
    status: str
    capability: str
    role: str
    priority: str
    integration: str
    risk: str
    local_path: str
    notes: str

    @property
    def clone_url(self) -> str:
        if self.repo.startswith("https://github.com/"):
            return f"{self.repo}.git"
        return self.repo


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_projects() -> list[Project]:
    with REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return [Project(**item) for item in raw["projects"]]


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                tags TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                goal TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                plan TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS video_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source_url TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                duration_seconds REAL,
                note_json TEXT NOT NULL,
                artifact_dir TEXT NOT NULL
            )
            """
        )


def print_table(rows: Iterable[Iterable[str]], headers: list[str]) -> None:
    rows = [list(row) for row in rows]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))
    fmt = "  ".join("{:<" + str(width) + "}" for width in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * width for width in widths]))
    for row in rows:
        print(fmt.format(*row))


def cmd_status(_: argparse.Namespace) -> int:
    projects = load_projects()
    init_db()
    counts: dict[str, int] = {}
    for project in projects:
        counts[project.status] = counts.get(project.status, 0) + 1
    print("Local Brain: ready")
    print(f"Workspace: {ROOT}")
    print(f"Registry: {len(projects)} projects")
    print(f"Database: {DB_PATH}")
    print(f"Statuses: {', '.join(f'{key}={value}' for key, value in sorted(counts.items()))}")
    return 0


def cmd_registry_list(args: argparse.Namespace) -> int:
    projects = load_projects()
    if args.status:
        projects = [project for project in projects if project.status == args.status]
    if args.collection:
        projects = [project for project in projects if project.collection == args.collection]
    print_table(
        (
            [
                project.id,
                project.name,
                project.status,
                project.priority,
                project.capability,
                project.repo,
            ]
            for project in projects
        ),
        ["id", "name", "status", "priority", "capability", "repo"],
    )
    return 0


def cmd_registry_matrix(_: argparse.Namespace) -> int:
    projects = load_projects()
    print_table(
        (
            [
                project.name,
                project.collection,
                project.status,
                project.priority,
                project.integration,
                project.risk,
            ]
            for project in projects
        ),
        ["name", "collection", "status", "priority", "integration", "risk"],
    )
    return 0


def cmd_memory_add(args: argparse.Namespace) -> int:
    init_db()
    tags = ",".join(tag.strip() for tag in args.tags.split(",") if tag.strip())
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT INTO memories (created_at, tags, content) VALUES (?, ?, ?)",
            (utc_now(), tags, args.content),
        )
    print("Memory written.")
    return 0


def cmd_memory_list(_: argparse.Namespace) -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT id, created_at, tags, content FROM memories ORDER BY id DESC LIMIT 50"
        ).fetchall()
    print_table(([str(row[0]), row[1], row[2], row[3]] for row in rows), ["id", "created_at", "tags", "content"])
    return 0


def cmd_memory_search(args: argparse.Namespace) -> int:
    init_db()
    needle = f"%{args.query}%"
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            """
            SELECT id, created_at, tags, content
            FROM memories
            WHERE content LIKE ? OR tags LIKE ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (needle, needle),
        ).fetchall()
    print_table(([str(row[0]), row[1], row[2], row[3]] for row in rows), ["id", "created_at", "tags", "content"])
    return 0


def cmd_memory_export_json(args: argparse.Namespace) -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT id, created_at, tags, content FROM memories ORDER BY id ASC"
        ).fetchall()
    payload = {
        "exported_at": utc_now(),
        "source": str(DB_PATH),
        "memories": [
            {
                "id": row[0],
                "created_at": row[1],
                "tags": row[2],
                "content": row[3],
            }
            for row in rows
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        print(f"Exported {len(rows)} memories to {output_path}")
    else:
        print(text)
    return 0


def cmd_memory_import_json(args: argparse.Namespace) -> int:
    init_db()
    input_path = Path(args.input).expanduser().resolve()
    with input_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    memories = payload.get("memories", payload if isinstance(payload, list) else [])
    if not isinstance(memories, list):
        print("Import file must contain a memories array or be an array.", file=sys.stderr)
        return 2
    imported = 0
    with sqlite3.connect(DB_PATH) as db:
        if args.replace:
            db.execute("DELETE FROM memories")
        for item in memories:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            tags = str(item.get("tags", ""))
            created_at = str(item.get("created_at", utc_now()))
            db.execute(
                "INSERT INTO memories (created_at, tags, content) VALUES (?, ?, ?)",
                (created_at, tags, content),
            )
            imported += 1
    mode = "replaced and imported" if args.replace else "imported"
    print(f"{mode.capitalize()} {imported} memories from {input_path}")
    return 0


def cmd_memory_adapter_status(_: argparse.Namespace) -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        count = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    local_ready = AGENTMEMORY_CLI.exists()
    configured = os.environ.get("AGENTMEMORY_CMD")
    print("Memory facade: ready")
    print(f"Default store: sqlite ({DB_PATH})")
    print(f"SQLite memories: {count}")
    print(f"Agentmemory build: {'present' if local_ready else 'missing'}")
    print(f"Configured adapter command: {configured or '(not set)'}")
    if local_ready:
        print(f"Suggested server command: {configured or f'node {AGENTMEMORY_CLI}'}")
        print(f"Suggested MCP command: {configured or f'node {AGENTMEMORY_CLI} mcp'}")
        print("Adapter policy: opt-in; SQLite remains the source of truth until promoted.")
    return 0


def cmd_memory_adapter_command(args: argparse.Namespace) -> int:
    configured = os.environ.get("AGENTMEMORY_CMD")
    if configured:
        base = configured
    elif AGENTMEMORY_CLI.exists():
        base = f"node {AGENTMEMORY_CLI}"
    else:
        print("Agentmemory is not built yet.", file=sys.stderr)
        return 2
    if args.mode == "mcp":
        print(f"{base} mcp")
    elif args.mode == "status":
        print(f"{base} status")
    else:
        print(base)
    return 0


def cmd_task_plan(args: argparse.Namespace) -> int:
    init_db()
    risk = "confirm-required" if args.risky else "read-only"
    plan = (
        "1. Retrieve relevant memory and registry context.\n"
        "2. Draft a plan before action.\n"
        "3. Request confirmation before writes, commands, browser actions, or desktop actions.\n"
        "4. Execute through a registered tool wrapper.\n"
        "5. Record outcome and memory updates."
    )
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute(
            "INSERT INTO runs (created_at, status, goal, risk_level, plan) VALUES (?, ?, ?, ?, ?)",
            (utc_now(), "planned", args.goal, risk, plan),
        )
    print(f"Run planned: {cursor.lastrowid}")
    print(plan)
    return 0


def cmd_runs_list(args: argparse.Namespace) -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            """
            SELECT id, created_at, status, risk_level, goal
            FROM runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
    print_table(
        ([str(row[0]), row[1], row[2], row[3], row[4]] for row in rows),
        ["id", "created_at", "status", "risk", "goal"],
    )
    return 0


def cmd_runs_show(args: argparse.Namespace) -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT id, created_at, status, goal, risk_level, plan FROM runs WHERE id = ?",
            (args.run_id,),
        ).fetchone()
    if row is None:
        print(f"Run not found: {args.run_id}", file=sys.stderr)
        return 2
    print(f"Run: {row[0]}")
    print(f"Created: {row[1]}")
    print(f"Status: {row[2]}")
    print(f"Risk: {row[4]}")
    print(f"Goal: {row[3]}")
    print("")
    print("Plan:")
    print(row[5])
    summary = safe_workspace_path(f"runs/{args.run_id}/summary.md")
    payload = safe_workspace_path(f"runs/{args.run_id}/run.json")
    print("")
    print("Artifacts:")
    print(f"- summary: {summary if summary.exists() else '(missing)'}")
    print(f"- payload: {payload if payload.exists() else '(missing)'}")
    return 0


def cmd_runs_artifact(args: argparse.Namespace) -> int:
    artifact = safe_workspace_path(f"runs/{args.run_id}/{args.name}")
    if not artifact.exists() or not artifact.is_file():
        print(f"Run artifact not found: {artifact}", file=sys.stderr)
        return 2
    print(artifact.read_text(encoding="utf-8", errors="ignore"))
    return 0


def create_run(goal: str, risk_level: str, plan: str, status: str = "planned") -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute(
            "INSERT INTO runs (created_at, status, goal, risk_level, plan) VALUES (?, ?, ?, ?, ?)",
            (utc_now(), status, goal, risk_level, plan),
        )
        return int(cursor.lastrowid)


def fetch_recent_memories(limit: int = 5) -> list[dict[str, str]]:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT id, created_at, tags, content FROM memories ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": str(row[0]),
            "created_at": row[1],
            "tags": row[2],
            "content": row[3],
        }
        for row in rows
    ]


def fetch_relevant_memories(query: str, limit: int = 5) -> list[dict[str, str]]:
    init_db()
    needle = f"%{query}%"
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            """
            SELECT id, created_at, tags, content
            FROM memories
            WHERE content LIKE ? OR tags LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (needle, needle, limit),
        ).fetchall()
    if rows:
        return [
            {
                "id": str(row[0]),
                "created_at": row[1],
                "tags": row[2],
                "content": row[3],
            }
            for row in rows
        ]
    return fetch_recent_memories(limit=limit)


def collect_context_matches(query: str, path: Path, limit: int = 8) -> list[dict[str, str]]:
    if not path.exists():
        return []
    matches: list[dict[str, str]] = []
    needle = query.lower()
    for file_path in iter_text_files(path):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if needle in line.lower():
                matches.append(
                    {
                        "file": str(file_path.relative_to(path)),
                        "line": str(line_no),
                        "match": line.strip()[:180],
                    }
                )
                if len(matches) >= limit:
                    return matches
    return matches


def infer_capabilities(goal: str) -> list[dict[str, str]]:
    text = goal.lower()
    candidates = [
        ("memory", "长期记忆", "检索或沉淀偏好、项目事实和失败经验。", ["记忆", "remember", "memory", "偏好", "经验"]),
        ("context", "上下文搜索", "搜索本地文件、代码和文档片段。", ["代码", "文件", "上下文", "context", "search", "文档"]),
        ("github", "GitHub 研究", "查看项目注册表、镜像状态和开源项目风险。", ["github", "repo", "仓库", "开源", "项目"]),
        ("devtools", "浏览器调试", "在确认后分析页面、控制台和网络请求。", ["浏览器", "网页", "console", "devtools", "页面"]),
        ("workspace", "本地工作区", "读取或生成 workspace 下的可追踪工作产物。", ["整理", "workspace", "文档", "页面", "报告"]),
        ("video", "视频读取", "解析视频链接、生成结构化视频笔记并沉淀到本地库。", ["视频", "抖音", "b站", "youtube", "字幕", "转录"]),
        ("funds", "指数基金教育", "提供教育性配置模板、评分和再平衡提示。", ["基金", "投资", "指数", "rebalance", "fund"]),
    ]
    selected = [
        {"id": cap_id, "name": name, "reason": reason}
        for cap_id, name, reason, keywords in candidates
        if any(keyword in text for keyword in keywords)
    ]
    if selected:
        return selected[:4]
    return [
        {"id": "memory", "name": "长期记忆", "reason": "先检查是否有相关偏好或历史经验。"},
        {"id": "context", "name": "上下文搜索", "reason": "再搜索本地上下文补齐事实。"},
        {"id": "workspace", "name": "本地工作区", "reason": "必要时生成可追踪的工作产物。"},
    ]


def infer_risk(goal: str) -> tuple[str, list[str]]:
    risky_keywords = [
        "写",
        "修改",
        "删除",
        "执行",
        "运行",
        "发送",
        "邮件",
        "浏览器",
        "桌面",
        "安装",
        "commit",
        "push",
        "deploy",
    ]
    hits = [keyword for keyword in risky_keywords if keyword.lower() in goal.lower()]
    if hits:
        return "confirm-required", [
            "涉及写入、命令、外部工具或账号动作时必须先确认。",
            f"触发风险词：{', '.join(hits[:6])}",
        ]
    return "read-only", ["当前可先进行只读理解、检索和规划。"]


def build_jarvis_plan(goal: str, context_path: Path, memory_limit: int = 4, context_limit: int = 5) -> dict[str, object]:
    goal = goal.strip()
    if not goal:
        raise ValueError("Goal is required.")
    risk_level, confirmation = infer_risk(goal)
    memories = fetch_relevant_memories(goal, limit=memory_limit)
    context_matches = collect_context_matches(goal, context_path, limit=context_limit)
    capabilities = infer_capabilities(goal)
    plan = [
        "确认任务目标、期望输出和不可触碰边界。",
        "检索相关长期记忆和本地上下文，优先使用已有事实。",
        "选择必要能力模块，并把高风险动作拆成确认点。",
        "先给出可验证的小步计划，再等待用户授权执行。",
        "完成后记录结果摘要和可复用经验。"
    ]
    memory_candidate = f"用户正在推进 Jarvis 化个人副脑任务：{goal[:120]}"
    return {
        "created_at": utc_now(),
        "goal": goal,
        "understanding": f"我会把这个请求当作个人副脑任务处理：先理解目标，再检索背景，最后给出安全的下一步。",
        "risk_level": risk_level,
        "confirmation_required": risk_level == "confirm-required",
        "confirmation_notes": confirmation,
        "capabilities": capabilities,
        "memories": memories,
        "context_matches": context_matches,
        "plan": plan,
        "next_step": "请确认是否进入执行阶段；未确认前不会写文件、运行外部命令、控制浏览器或访问邮箱。",
        "memory_candidate": memory_candidate,
    }


def cmd_jarvis_plan(args: argparse.Namespace) -> int:
    context_path = Path(args.context_path).expanduser().resolve()
    payload = build_jarvis_plan(
        args.goal,
        context_path,
        memory_limit=args.memory_limit,
        context_limit=args.context_limit,
    )
    if args.record:
        plan_text = "\n".join(f"{index}. {step}" for index, step in enumerate(payload["plan"], start=1))
        run_id = create_run(str(payload["goal"]), str(payload["risk_level"]), plan_text, status="planned")
        payload["run_id"] = run_id
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("Jarvis plan generated.")
    print(f"Goal: {payload['goal']}")
    print(f"Risk: {payload['risk_level']}")
    print("")
    print("Understanding:")
    print(payload["understanding"])
    print("")
    print("Plan:")
    for index, step in enumerate(payload["plan"], start=1):
        print(f"{index}. {step}")
    print("")
    print("Needs confirmation:")
    for note in payload["confirmation_notes"]:
        print(f"- {note}")
    print("")
    print(f"Next: {payload['next_step']}")
    return 0


def dashboard_snapshot() -> dict[str, object]:
    projects = load_projects()
    init_db()
    counts: dict[str, int] = {}
    for project in projects:
        counts[project.status] = counts.get(project.status, 0) + 1
    with sqlite3.connect(DB_PATH) as db:
        memory_count = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        video_count = db.execute("SELECT COUNT(*) FROM video_notes").fetchone()[0]
        run_rows = db.execute(
            "SELECT id, created_at, status, risk_level, goal FROM runs ORDER BY id DESC LIMIT 5"
        ).fetchall()
        memory_rows = db.execute(
            "SELECT id, created_at, tags, content FROM memories ORDER BY id DESC LIMIT 5"
        ).fetchall()
        run_count = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    modules = [
        {"id": "memory", "name": "长期记忆", "status": "已启用", "summary": f"SQLite 记忆源可用，当前 {memory_count} 条记忆。"},
        {"id": "context", "name": "上下文搜索", "status": "已启用", "summary": "本地文本搜索可用，claude-context 处于适配器验证阶段。"},
        {"id": "devtools", "name": "浏览器调试", "status": "需确认", "summary": "Chrome DevTools MCP 已构建，浏览器会话访问需要用户确认。"},
        {"id": "workspace", "name": "本地工作区", "status": "已启用", "summary": "本地工作区门面可用，仅处理本机 workspace 文件。"},
        {"id": "video", "name": "视频读取", "status": "已启用", "summary": f"视频链接解析和结构化笔记可用，当前 {video_count} 条视频笔记。"},
        {"id": "funds", "name": "指数基金教育", "status": "已启用", "summary": "可生成教育性风险画像、配置模板、评分和再平衡提示。"},
        {"id": "email", "name": "邮箱 MCP", "status": "暂停", "summary": "Gmail/163 授权测试已尝试，因 IMAP 网络延迟暂停读取能力。"},
    ]
    recent = [f"运行 #{row[0]} [{row[2]}] {row[4]}" for row in run_rows]
    recent.extend(f"记忆 #{row[0]} [{row[2]}] {row[3][:80]}" for row in memory_rows)
    return {
        "generated_at": utc_now(),
        "mode": "local-snapshot",
        "summary": {
            "registry_projects": len(projects),
            "integrate": counts.get("integrate", 0),
            "mirror": counts.get("mirror", 0),
            "watch": counts.get("watch", 0),
            "runs": run_count,
            "memories": memory_count,
            "video_notes": video_count,
        },
        "modules": modules,
        "recent": recent[:6],
    }


def cmd_jarvis_snapshot(args: argparse.Namespace) -> int:
    payload = dashboard_snapshot()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = WORKSPACE_ROOT / "brain-dashboard-data.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")
    print(f"Jarvis dashboard snapshot written: {output_path}")
    return 0


class JarvisRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, directory: str | None = None, **kwargs: object) -> None:
        super().__init__(*args, directory=directory or str(WORKSPACE_ROOT), **kwargs)

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self._send_json(dashboard_snapshot())
            return
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/plan":
            self._send_json({"error": "not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            goal = str(payload.get("goal", "")).strip()
            response = build_jarvis_plan(goal, ROOT, memory_limit=4, context_limit=5)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json(response)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"[jarvis] {format % args}\n")


def cmd_jarvis_serve(args: argparse.Namespace) -> int:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    address = (args.host, args.port)
    server = ThreadingHTTPServer(address, lambda *handler_args, **handler_kwargs: JarvisRequestHandler(*handler_args, directory=str(WORKSPACE_ROOT), **handler_kwargs))
    print(f"Jarvis console serving at http://{args.host}:{args.port}/personal-brain-hud.html")
    print("API: GET /api/status, POST /api/plan")
    print("Policy: read-only status and planning only; no tool execution.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nJarvis console stopped.")
    finally:
        server.server_close()
    return 0


def write_memory(content: str, tags: str) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT INTO memories (created_at, tags, content) VALUES (?, ?, ?)",
            (utc_now(), tags, content),
        )


def store_video_note(note: dict[str, object]) -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute(
            """
            INSERT INTO video_notes (
                created_at, source_url, title, author, duration_seconds, note_json, artifact_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now(),
                str(note.get("source_url", "")),
                str(note.get("title", "")),
                str(note.get("author", "")),
                note.get("duration_seconds"),
                json.dumps(note, ensure_ascii=False, indent=2),
                str(note.get("artifact_dir", "")),
            ),
        )
        return int(cursor.lastrowid)


def load_metadata_arg(args: argparse.Namespace) -> dict[str, object] | None:
    if not args.metadata_json:
        return None
    metadata_path = Path(args.metadata_json).expanduser().resolve()
    with metadata_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("--metadata-json must point to a JSON object")
    return payload


def cmd_video_analyze(args: argparse.Namespace) -> int:
    url = args.url.strip()
    if not url:
        print("Video URL is required.", file=sys.stderr)
        return 2
    errors: list[str] = []
    metadata: dict[str, object]
    try:
        loaded_metadata = load_metadata_arg(args)
        metadata = loaded_metadata if loaded_metadata is not None else fetch_metadata(url, downloader=args.downloader)
    except Exception as exc:
        print(f"Video metadata extraction failed: {exc}", file=sys.stderr)
        return 2

    video_id = str(metadata.get("id") or stable_video_id(url))
    title = str(metadata.get("title") or metadata.get("fulltitle") or video_id)
    artifact_dir = (VIDEO_WORKSPACE / f"{safe_filename(video_id)}-{safe_filename(title)}").resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = artifact_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    video_path: Path | None = None
    media_probe: dict[str, object] = {}
    transcript = {"status": "skipped", "reason": "download disabled or unavailable", "text": ""}
    contact_sheet: Path | None = None

    if not args.no_download:
        if not tool_available(args.downloader):
            errors.append(f"{args.downloader} is not installed")
        else:
            try:
                video_path = download_video(url, artifact_dir, downloader=args.downloader)
            except Exception as exc:
                errors.append(f"download failed: {exc}")
    if video_path:
        try:
            media_probe = probe_media(video_path)
        except Exception as exc:
            errors.append(f"ffprobe failed: {exc}")
        if not args.no_frames:
            try:
                contact_sheet = extract_contact_sheet(video_path, artifact_dir, every_seconds=args.frame_interval)
                if contact_sheet is None:
                    errors.append("contact sheet skipped: ffmpeg unavailable or frame extraction failed")
            except Exception as exc:
                errors.append(f"frame extraction failed: {exc}")
        if not args.no_transcript:
            audio_path = extract_audio(video_path, artifact_dir)
            if audio_path is None:
                transcript = {"status": "skipped", "reason": "audio extraction failed or ffmpeg not installed", "text": ""}
            else:
                transcript = transcribe_audio(audio_path, artifact_dir, command_template=args.transcribe_command)

    note = build_video_note(
        url,
        metadata,
        artifact_dir=artifact_dir,
        media_probe=media_probe,
        transcript=transcript,
        contact_sheet=contact_sheet,
        errors=errors,
    )
    note_path = artifact_dir / "video_note.json"
    note_path.write_text(json.dumps(note, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    row_id: int | None = None
    if not args.no_store:
        row_id = store_video_note(note)
    if args.memory:
        write_memory(
            f"视频笔记：{note['title']}。摘要：{note['summary']}。来源：{note['source_url']}",
            "video,note",
        )

    if args.json:
        payload = {"stored_id": row_id, "note_path": str(note_path), "note": note}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Video analysis completed.")
    print(f"Title: {note['title']}")
    print(f"Author: {note['author'] or '(unknown)'}")
    print(f"Duration: {note['duration_string'] or note['duration_seconds'] or '(unknown)'}")
    print(f"Stored id: {row_id if row_id is not None else '(not stored)'}")
    print(f"Note: {note_path}")
    if contact_sheet:
        print(f"Contact sheet: {contact_sheet}")
    if transcript.get("status") != "ok":
        print(f"Transcript: {transcript.get('status')} - {transcript.get('reason', '')}")
    if errors:
        print("Warnings:")
        for error in errors:
            print(f"- {error}")
    return 0


def cmd_video_list(args: argparse.Namespace) -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            """
            SELECT id, created_at, title, author, duration_seconds, source_url
            FROM video_notes
            ORDER BY id DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
    print_table(
        (
            [
                str(row[0]),
                row[1],
                row[2],
                row[3],
                "" if row[4] is None else str(round(float(row[4]))),
                row[5],
            ]
            for row in rows
        ),
        ["id", "created_at", "title", "author", "seconds", "url"],
    )
    return 0


def cmd_video_show(args: argparse.Namespace) -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT note_json FROM video_notes WHERE id = ?",
            (args.video_note_id,),
        ).fetchone()
    if row is None:
        print(f"Video note not found: {args.video_note_id}", file=sys.stderr)
        return 2
    if args.json:
        print(row[0])
        return 0
    note = json.loads(row[0])
    print(f"Video note: {args.video_note_id}")
    print(f"Title: {note.get('title')}")
    print(f"Author: {note.get('author') or '(unknown)'}")
    print(f"URL: {note.get('source_url')}")
    print("")
    print("Summary:")
    print(note.get("summary") or "(empty)")
    print("")
    points = note.get("key_points") or []
    if points:
        print("Key points:")
        for point in points:
            print(f"- {point}")
    return 0


def load_video_note(video_note_id: int) -> dict[str, object] | None:
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT note_json FROM video_notes WHERE id = ?",
            (video_note_id,),
        ).fetchone()
    if row is None:
        return None
    payload = json.loads(row[0])
    return payload if isinstance(payload, dict) else None


def cmd_video_report(args: argparse.Namespace) -> int:
    note = load_video_note(args.video_note_id)
    if note is None:
        print(f"Video note not found: {args.video_note_id}", file=sys.stderr)
        return 2
    report = build_project_report(note, target=args.target)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    markdown = render_project_report_markdown(report)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        artifact_dir = str(note.get("artifact_dir") or "").strip()
        base_dir = Path(artifact_dir) if artifact_dir else VIDEO_WORKSPACE / f"note-{args.video_note_id}"
        output_path = base_dir / "project_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Video project report written: {output_path}")
    print(f"Detected tools: {len(report.get('detected_tools') or [])}")
    print(f"Target: {report.get('target')}")
    return 0


def cmd_douyin_cookie_status(args: argparse.Namespace) -> int:
    status = cookie_config_status(DOUYIN_COOKIE_PATH)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    print("Douyin cookie status:")
    print(f"- configured: {status['configured']}")
    print(f"- env cookie: {status['env_cookie']}")
    print(f"- cookie file: {status['cookie_file']}")
    print(f"- cookie file exists: {status['cookie_file_exists']}")
    print(f"- policy: {status['policy']}")
    return 0


def cmd_douyin_inspect(args: argparse.Namespace) -> int:
    expanded = ""
    if args.expand:
        expansion = expand_shortlink(args.url, timeout=args.timeout)
        expanded = str(expansion.get("final_url") or "")
    aweme_detail = load_aweme_detail(Path(args.aweme_json).expanduser().resolve()) if args.aweme_json else None
    payload = inspect_douyin_url(
        args.url,
        expanded_url=expanded,
        aweme_detail=aweme_detail,
        cookie_status=cookie_config_status(DOUYIN_COOKIE_PATH),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("Douyin inspection:")
    print(f"- source: {payload['source_url']}")
    print(f"- final: {payload['final_url']}")
    print(f"- type: {payload['content_type']}")
    print(f"- id: {payload['content_id'] or '(unknown)'}")
    print(f"- images: {payload['image_count']}")
    print(f"- cookie configured: {payload['cookie']['configured']}")
    print("")
    print("Fallback plan:")
    for item in payload["fallback_plan"]:
        print(f"- [{item['status']}] {item['step']}: {item['detail']}")
    if payload["note_images"]:
        print("")
        print("Image URL candidates:")
        for image in payload["note_images"]:
            first_url = image["urls"][0] if image["urls"] else "(no url)"
            print(f"- #{image['index']} {image['width'] or '?'}x{image['height'] or '?'} {first_url}")
    return 0


def cmd_workflow_local_task(args: argparse.Namespace) -> int:
    goal = args.goal.strip()
    if not goal:
        print("Goal is required.", file=sys.stderr)
        return 2
    risk = "confirm-required" if args.risky else "read-only"
    context_path = Path(args.context_path).expanduser().resolve()
    memories = fetch_recent_memories(limit=args.memory_limit)
    context_matches = collect_context_matches(args.query or goal, context_path, limit=args.context_limit)
    plan = (
        "1. Review recent memories.\n"
        "2. Search local context for relevant facts.\n"
        "3. Create a workspace artifact with findings and next actions.\n"
        "4. Keep risky tool execution behind explicit confirmation.\n"
        "5. Record workflow summary back into memory."
    )
    run_id = create_run(goal, risk, plan, status="completed")
    run_dir = safe_workspace_path(f"runs/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "summary.md"
    payload_path = run_dir / "run.json"

    memory_lines = (
        "\n".join(f"- #{item['id']} [{item['tags']}] {item['content']}" for item in memories)
        if memories
        else "- No memories found."
    )
    context_lines = (
        "\n".join(
            f"- `{item['file']}:{item['line']}` {item['match']}"
            for item in context_matches
        )
        if context_matches
        else "- No context matches found."
    )
    tool_lines = [
        f"- DevTools: `python3 -m brain_core devtools command --browser-url http://127.0.0.1:9222`",
        f"- Context adapter: `python3 -m brain_core context adapter-command`",
        f"- Workspace: `python3 -m brain_core workspace list --path /runs/{run_id}`",
    ]
    summary = f"""# Local Brain Workflow Run {run_id}

## Goal

{goal}

## Risk Level

{risk}

## Plan

{plan}

## Recent Memories

{memory_lines}

## Context Matches

{context_lines}

## Generated Tool Commands

{chr(10).join(tool_lines)}

## Result

Created a local-only workflow artifact. No browser, shell, desktop, or remote connector action was executed.
"""
    summary_path.write_text(summary, encoding="utf-8")
    payload = {
        "run_id": run_id,
        "created_at": utc_now(),
        "goal": goal,
        "risk_level": risk,
        "context_path": str(context_path),
        "memories": memories,
        "context_matches": context_matches,
        "summary_path": str(summary_path),
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_memory(
        f"Workflow run {run_id} completed for goal: {goal}. Artifact: workspace/runs/{run_id}/summary.md",
        "workflow,run-log",
    )
    print(f"Workflow run completed: {run_id}")
    print(f"Summary: {summary_path}")
    print(f"Payload: {payload_path}")
    return 0


def cmd_workflow_show(args: argparse.Namespace) -> int:
    summary_path = safe_workspace_path(f"runs/{args.run_id}/summary.md")
    if not summary_path.exists():
        print(f"Workflow summary not found: {summary_path}", file=sys.stderr)
        return 2
    print(summary_path.read_text(encoding="utf-8"))
    return 0


def iter_text_files(path: Path) -> Iterable[Path]:
    ignored = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
    for item in path.rglob("*"):
        if any(part in ignored for part in item.parts):
            continue
        if item.is_file() and item.stat().st_size <= 1_000_000:
            yield item


def cmd_context_search(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        print(f"Path does not exist: {root}", file=sys.stderr)
        return 2
    matches: list[list[str]] = []
    query = args.query.lower()
    for file_path in iter_text_files(root):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if query in line.lower():
                matches.append([str(file_path.relative_to(root)), str(line_no), line.strip()[:160]])
                if len(matches) >= args.limit:
                    print_table(matches, ["file", "line", "match"])
                    return 0
    print_table(matches, ["file", "line", "match"])
    return 0


def cmd_context_adapter_status(_: argparse.Namespace) -> int:
    local_ready = CLAUDE_CONTEXT_MCP_BIN.exists()
    configured = os.environ.get("CLAUDE_CONTEXT_MCP_CMD")
    print("Context facade: ready")
    print("Default search: local text search")
    print(f"claude-context MCP build: {'present' if local_ready else 'missing'}")
    print(f"Configured adapter command: {configured or '(not set)'}")
    if local_ready:
        print(f"Suggested MCP command: {configured or f'node {CLAUDE_CONTEXT_MCP_BIN}'}")
        print("Adapter policy: opt-in; requires embedding provider and Milvus before indexing.")
    return 0


def cmd_context_adapter_command(args: argparse.Namespace) -> int:
    configured = os.environ.get("CLAUDE_CONTEXT_MCP_CMD")
    if configured:
        base = configured
    elif CLAUDE_CONTEXT_MCP_BIN.exists():
        base = f"node {CLAUDE_CONTEXT_MCP_BIN}"
    else:
        print("claude-context MCP is not built yet.", file=sys.stderr)
        return 2
    env = []
    if args.provider:
        env.append(f"EMBEDDING_PROVIDER={args.provider}")
    if args.model:
        env.append(f"EMBEDDING_MODEL={args.model}")
    if args.milvus_address:
        env.append(f"MILVUS_ADDRESS={args.milvus_address}")
    print(" ".join([*env, base]))
    return 0


def cmd_context_adapter_smoke_test(_: argparse.Namespace) -> int:
    if not CLAUDE_CONTEXT_MCP_BIN.exists():
        print("claude-context MCP smoke test: unavailable")
        print("Reason: local claude-context MCP build missing.")
        print("Fallback: local text search remains available.")
        return 0
    result = subprocess.run(
        ["node", str(CLAUDE_CONTEXT_MCP_BIN), "--help"],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        print("claude-context MCP smoke test failed.", file=sys.stderr)
        if output:
            print(output.strip(), file=sys.stderr)
        return result.returncode or 1
    if "Context MCP Server" not in output:
        print("claude-context MCP help output did not include expected title.", file=sys.stderr)
        return 1
    print("claude-context MCP smoke test: ok")
    print(f"Binary: {CLAUDE_CONTEXT_MCP_BIN}")
    print("Expected title found: Context MCP Server")
    return 0


def mirror_path(project: Project) -> Path:
    return ROOT / project.local_path


def cmd_github_mirror_plan(args: argparse.Namespace) -> int:
    projects = load_projects()
    if args.status:
        projects = [project for project in projects if project.status == args.status]
    rows = []
    for project in projects:
        target = mirror_path(project)
        action = "pull" if target.exists() else "clone"
        command = (
            f"git -C {target} pull --ff-only"
            if action == "pull"
            else f"git clone {project.clone_url} {target}"
        )
        rows.append([project.name, project.status, action, command])
    print_table(rows, ["name", "status", "action", "command"])
    return 0


def cmd_github_mirror_execute(args: argparse.Namespace) -> int:
    if not args.yes:
        print("Refusing to run network/git commands without --yes.")
        return 2
    projects = load_projects()
    projects = [project for project in projects if project.status == args.status]
    THIRD_PARTY.mkdir(parents=True, exist_ok=True)
    for project in projects:
        target = mirror_path(project)
        if target.exists():
            command = ["git", "-C", str(target), "pull", "--ff-only"]
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            command = ["git", "clone", project.clone_url, str(target)]
        print("Running:", " ".join(command))
        subprocess.run(command, check=True)
    return 0


def cmd_github_audit(_: argparse.Namespace) -> int:
    rows = []
    for project in load_projects():
        target = mirror_path(project)
        state = "present" if target.exists() else "missing"
        commit = "-"
        if target.exists() and (target / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(target), "rev-parse", "--short", "HEAD"],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                commit = result.stdout.strip()
        rows.append([project.name, project.status, state, commit, str(target)])
    print_table(rows, ["name", "status", "mirror", "commit", "path"])
    return 0


def cmd_devtools_status(_: argparse.Namespace) -> int:
    configured = os.environ.get("CHROME_DEVTOOLS_MCP_CMD")
    local_ready = DEVTOOLS_MCP_BIN.exists()
    local_command = f"node {DEVTOOLS_MCP_BIN}" if local_ready else ""
    print("Chrome DevTools MCP slot: ready")
    print(f"Configured command: {configured or '(not set)'}")
    print(f"Local build: {'present' if local_ready else 'missing'}")
    if local_ready:
        print(f"Suggested command: {configured or local_command}")
        print("Recommended flags: --no-usage-statistics --redact-network-headers --slim")
    else:
        print("Build Chrome DevTools MCP before enabling this tool.")
    return 0


def cmd_devtools_command(args: argparse.Namespace) -> int:
    configured = os.environ.get("CHROME_DEVTOOLS_MCP_CMD")
    if configured:
        base = configured
    elif DEVTOOLS_MCP_BIN.exists():
        base = f"node {DEVTOOLS_MCP_BIN}"
    else:
        print("Chrome DevTools MCP is not built yet.", file=sys.stderr)
        return 2
    flags = ["--no-usage-statistics", "--redact-network-headers"]
    if args.slim:
        flags.append("--slim")
    if args.browser_url:
        flags.append(f"--browserUrl {args.browser_url}")
    if args.headless:
        flags.append("--headless")
    print(" ".join([base, *flags]))
    return 0


def cmd_devtools_smoke_test(_: argparse.Namespace) -> int:
    if not DEVTOOLS_MCP_BIN.exists():
        print("Chrome DevTools MCP smoke test: unavailable")
        print("Reason: local Chrome DevTools MCP build missing.")
        print("Fallback: configure CHROME_DEVTOOLS_MCP_CMD or mirror/build third_party/chrome-devtools-mcp.")
        return 0
    result = subprocess.run(
        ["node", str(DEVTOOLS_MCP_BIN), "--help"],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        print("Chrome DevTools MCP smoke test failed.", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return result.returncode or 1
    output = result.stdout + result.stderr
    if "--browserUrl" not in output:
        print("Chrome DevTools MCP help output did not include expected options.", file=sys.stderr)
        return 1
    print("Chrome DevTools MCP smoke test: ok")
    print(f"Binary: {DEVTOOLS_MCP_BIN}")
    print("Expected option found: --browserUrl")
    return 0


def safe_workspace_path(path_text: str) -> Path:
    relative = Path(path_text.lstrip("/"))
    target = (WORKSPACE_ROOT / relative).resolve()
    root = WORKSPACE_ROOT.resolve()
    if target != root and root not in target.parents:
        raise ValueError("workspace path escapes local workspace root")
    return target


def cmd_workspace_status(_: argparse.Namespace) -> int:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    mirage_ready = MIRAGE_TS_ROOT.exists()
    package_ready = (MIRAGE_TS_ROOT / "package.json").exists()
    print("Workspace facade: ready")
    print(f"Local workspace root: {WORKSPACE_ROOT}")
    print(f"Mirage mirror: {'present' if mirage_ready else 'missing'}")
    print(f"Mirage TypeScript package: {'present' if package_ready else 'missing'}")
    print("Mode: local-only RAM/Disk prototype; no remote connectors enabled.")
    return 0


def cmd_workspace_write(args: argparse.Namespace) -> int:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        target = safe_workspace_path(args.path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(args.content + ("\n" if args.newline else ""), encoding="utf-8")
    print(f"Wrote {target}")
    return 0


def cmd_workspace_read(args: argparse.Namespace) -> int:
    try:
        target = safe_workspace_path(args.path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not target.exists() or not target.is_file():
        print(f"Workspace file not found: {target}", file=sys.stderr)
        return 2
    print(target.read_text(encoding="utf-8", errors="ignore"))
    return 0


def cmd_workspace_list(args: argparse.Namespace) -> int:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        target = safe_workspace_path(args.path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not target.exists():
        print(f"Workspace path not found: {target}", file=sys.stderr)
        return 2
    rows = []
    for item in sorted(target.iterdir() if target.is_dir() else [target]):
        kind = "dir" if item.is_dir() else "file"
        size = "-" if item.is_dir() else str(item.stat().st_size)
        rows.append([kind, size, str(item.relative_to(WORKSPACE_ROOT))])
    print_table(rows, ["type", "size", "path"])
    return 0


def cmd_workspace_command(args: argparse.Namespace) -> int:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    if args.runtime == "facade":
        print(f"python3 -m brain_core workspace list --path {args.path}")
    else:
        print("Mirage SDK command generation is not enabled until dependencies are installed and audited.")
        print("Policy: local-only first; no Gmail, Slack, S3, GitHub, or credentialed connectors.")
    return 0


def cmd_workspace_smoke_test(_: argparse.Namespace) -> int:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    sample = safe_workspace_path("smoke/hello.txt")
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_text("local workspace smoke ok\n", encoding="utf-8")
    content = sample.read_text(encoding="utf-8").strip()
    if content != "local workspace smoke ok":
        print("Workspace smoke test failed.", file=sys.stderr)
        return 1
    print("Workspace smoke test: ok")
    print(f"Sample file: {sample}")
    print("Mode: local-only facade")
    return 0


def validate_percent(value: float, name: str) -> float:
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return value


def cmd_funds_profile(args: argparse.Namespace) -> int:
    years = args.years
    risk = args.risk
    if args.profile:
        profile = args.profile
    elif years < 3 or risk <= 2:
        profile = "conservative"
    elif years >= 10 and risk >= 4:
        profile = "growth"
    else:
        profile = "balanced"
    allocation = FUND_PROFILES[profile]
    print(f"Suggested profile: {profile}")
    print(f"Time horizon: {years} years")
    print(f"Risk tolerance: {risk}/5")
    print("")
    print_table(
        [
            ["stocks", f"{allocation['stock']}%"],
            ["bonds", f"{allocation['bond']}%"],
            ["cash", f"{allocation['cash']}%"],
        ],
        ["asset", "target"],
    )
    print("")
    print(allocation["note"])
    print("This is educational guidance, not personalized financial advice.")
    return 0


def cmd_funds_template(args: argparse.Namespace) -> int:
    allocation = FUND_PROFILES[args.profile]
    stock = allocation["stock"]
    international = round(stock * args.international_stock / 100)
    us_stock = stock - international
    rows = [
        [FUND_SLEEVES["us_total_market"], f"{us_stock}%"],
        [FUND_SLEEVES["international"], f"{international}%"],
        [FUND_SLEEVES["bond"], f"{allocation['bond']}%"],
        [FUND_SLEEVES["cash"], f"{allocation['cash']}%"],
    ]
    print(f"Index fund template: {args.profile}")
    print_table(rows, ["sleeve", "target"])
    print("")
    print("Fund selection rules:")
    print("- Prefer broad, low-cost, liquid index funds or ETFs.")
    print("- Compare expense ratio, tracking error, index methodology, tax efficiency, and brokerage fees.")
    print("- Avoid narrow thematic funds as core holdings unless intentionally sized as satellites.")
    print("- Rebalance on a schedule or when an asset class drifts materially from target.")
    return 0


def cmd_funds_score(args: argparse.Namespace) -> int:
    try:
        expense = validate_percent(args.expense_ratio, "expense_ratio")
        tracking = validate_percent(args.tracking_error, "tracking_error")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    score = 100
    score -= min(35, expense * 250)
    score -= min(25, tracking * 100)
    if args.assets_under_management < 100:
        score -= 15
    elif args.assets_under_management < 1000:
        score -= 5
    if not args.broad:
        score -= 20
    if not args.liquid:
        score -= 10
    score = max(0, round(score))
    print(f"Fund score: {score}/100")
    print("")
    print("Interpretation:")
    if score >= 80:
        print("Strong candidate for further due diligence.")
    elif score >= 60:
        print("Usable candidate, but compare alternatives carefully.")
    else:
        print("Weak candidate for a core index allocation.")
    print("")
    print("Inputs:")
    print_table(
        [
            ["expense_ratio", f"{expense}%"],
            ["tracking_error", f"{tracking}%"],
            ["AUM", f"{args.assets_under_management}M"],
            ["broad_index", str(args.broad)],
            ["liquid", str(args.liquid)],
        ],
        ["factor", "value"],
    )
    return 0


def cmd_funds_rebalance(args: argparse.Namespace) -> int:
    targets = FUND_PROFILES[args.profile]
    current_stock = validate_percent(args.stock, "stock")
    current_bond = validate_percent(args.bond, "bond")
    current_cash = validate_percent(args.cash, "cash")
    total = current_stock + current_bond + current_cash
    if abs(total - 100) > 0.5:
        print(f"Current allocation must sum to about 100; got {total}.", file=sys.stderr)
        return 2
    rows = []
    actions = []
    for key, current in [("stock", current_stock), ("bond", current_bond), ("cash", current_cash)]:
        target = targets[key]
        drift = round(current - target, 2)
        rows.append([key, f"{current}%", f"{target}%", f"{drift:+}%"])
        if abs(drift) >= args.threshold:
            direction = "reduce" if drift > 0 else "add"
            actions.append(f"{direction} {key} by about {abs(drift):.1f}%")
    print(f"Rebalance profile: {args.profile}")
    print_table(rows, ["asset", "current", "target", "drift"])
    print("")
    if actions:
        print("Suggested rebalance actions:")
        for action in actions:
            print(f"- {action}")
    else:
        print("No rebalance needed under the selected drift threshold.")
    print("Consider taxes, transaction costs, and account type before trading.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brain")
    sub = parser.add_subparsers(required=True)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)

    registry = sub.add_parser("registry")
    registry_sub = registry.add_subparsers(required=True)
    registry_list = registry_sub.add_parser("list")
    registry_list.add_argument("--status", choices=["watch", "mirror", "integrate"])
    registry_list.add_argument("--collection")
    registry_list.set_defaults(func=cmd_registry_list)
    registry_matrix = registry_sub.add_parser("matrix")
    registry_matrix.set_defaults(func=cmd_registry_matrix)

    douyin = sub.add_parser("douyin")
    douyin_sub = douyin.add_subparsers(required=True)
    douyin_inspect = douyin_sub.add_parser("inspect")
    douyin_inspect.add_argument("url")
    douyin_inspect.add_argument("--expand", action="store_true", help="Follow redirects to resolve short links.")
    douyin_inspect.add_argument("--timeout", type=int, default=12)
    douyin_inspect.add_argument("--aweme-json", help="Optional aweme_detail JSON for note image extraction.")
    douyin_inspect.add_argument("--json", action="store_true")
    douyin_inspect.set_defaults(func=cmd_douyin_inspect)
    douyin_cookie = douyin_sub.add_parser("cookie-status")
    douyin_cookie.add_argument("--json", action="store_true")
    douyin_cookie.set_defaults(func=cmd_douyin_cookie_status)

    memory = sub.add_parser("memory")
    memory_sub = memory.add_subparsers(required=True)
    memory_add = memory_sub.add_parser("add")
    memory_add.add_argument("content")
    memory_add.add_argument("--tags", default="")
    memory_add.set_defaults(func=cmd_memory_add)
    memory_list = memory_sub.add_parser("list")
    memory_list.set_defaults(func=cmd_memory_list)
    memory_search = memory_sub.add_parser("search")
    memory_search.add_argument("query")
    memory_search.set_defaults(func=cmd_memory_search)
    memory_export = memory_sub.add_parser("export-json")
    memory_export.add_argument("--output")
    memory_export.set_defaults(func=cmd_memory_export_json)
    memory_import = memory_sub.add_parser("import-json")
    memory_import.add_argument("input")
    memory_import.add_argument("--replace", action="store_true")
    memory_import.set_defaults(func=cmd_memory_import_json)
    memory_adapter_status = memory_sub.add_parser("adapter-status")
    memory_adapter_status.set_defaults(func=cmd_memory_adapter_status)
    memory_adapter_command = memory_sub.add_parser("adapter-command")
    memory_adapter_command.add_argument("--mode", choices=["server", "mcp", "status"], default="server")
    memory_adapter_command.set_defaults(func=cmd_memory_adapter_command)

    video = sub.add_parser("video")
    video_sub = video.add_subparsers(required=True)
    video_analyze = video_sub.add_parser("analyze")
    video_analyze.add_argument("url")
    video_analyze.add_argument("--metadata-json", help="Use an existing yt-dlp JSON object instead of fetching metadata.")
    video_analyze.add_argument("--downloader", default="yt-dlp")
    video_analyze.add_argument("--no-download", action="store_true")
    video_analyze.add_argument("--no-frames", action="store_true")
    video_analyze.add_argument("--no-transcript", action="store_true")
    video_analyze.add_argument("--frame-interval", type=int, default=10)
    video_analyze.add_argument(
        "--transcribe-command",
        help="Optional command template. Use {audio} and {output_dir}; stdout becomes transcript text.",
    )
    video_analyze.add_argument("--no-store", action="store_true")
    video_analyze.add_argument("--memory", action="store_true", help="Also write a compact video summary into memories.")
    video_analyze.add_argument("--json", action="store_true")
    video_analyze.set_defaults(func=cmd_video_analyze)
    video_list = video_sub.add_parser("list")
    video_list.add_argument("--limit", type=int, default=20)
    video_list.set_defaults(func=cmd_video_list)
    video_show = video_sub.add_parser("show")
    video_show.add_argument("video_note_id", type=int)
    video_show.add_argument("--json", action="store_true")
    video_show.set_defaults(func=cmd_video_show)
    video_report = video_sub.add_parser("report")
    video_report.add_argument("video_note_id", type=int)
    video_report.add_argument("--target", default="local-brain", help="Target project or workflow for landing suggestions.")
    video_report.add_argument("--output", help="Write markdown report to this path. Defaults to the video's artifact directory.")
    video_report.add_argument("--json", action="store_true")
    video_report.set_defaults(func=cmd_video_report)

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(required=True)
    task_plan = task_sub.add_parser("plan")
    task_plan.add_argument("goal")
    task_plan.add_argument("--risky", action="store_true")
    task_plan.set_defaults(func=cmd_task_plan)

    runs = sub.add_parser("runs")
    runs_sub = runs.add_subparsers(required=True)
    runs_list = runs_sub.add_parser("list")
    runs_list.add_argument("--limit", type=int, default=20)
    runs_list.set_defaults(func=cmd_runs_list)
    runs_show = runs_sub.add_parser("show")
    runs_show.add_argument("run_id", type=int)
    runs_show.set_defaults(func=cmd_runs_show)
    runs_artifact = runs_sub.add_parser("artifact")
    runs_artifact.add_argument("run_id", type=int)
    runs_artifact.add_argument("--name", default="summary.md")
    runs_artifact.set_defaults(func=cmd_runs_artifact)

    context = sub.add_parser("context")
    context_sub = context.add_subparsers(required=True)
    context_search = context_sub.add_parser("search")
    context_search.add_argument("query")
    context_search.add_argument("--path", default=str(ROOT))
    context_search.add_argument("--limit", type=int, default=20)
    context_search.set_defaults(func=cmd_context_search)
    context_adapter_status = context_sub.add_parser("adapter-status")
    context_adapter_status.set_defaults(func=cmd_context_adapter_status)
    context_adapter_command = context_sub.add_parser("adapter-command")
    context_adapter_command.add_argument("--provider")
    context_adapter_command.add_argument("--model")
    context_adapter_command.add_argument("--milvus-address")
    context_adapter_command.set_defaults(func=cmd_context_adapter_command)
    context_adapter_smoke = context_sub.add_parser("adapter-smoke-test")
    context_adapter_smoke.set_defaults(func=cmd_context_adapter_smoke_test)

    github = sub.add_parser("github")
    github_sub = github.add_subparsers(required=True)
    mirror_plan = github_sub.add_parser("mirror-plan")
    mirror_plan.add_argument("--status", choices=["watch", "mirror", "integrate"])
    mirror_plan.set_defaults(func=cmd_github_mirror_plan)
    mirror_execute = github_sub.add_parser("mirror-execute")
    mirror_execute.add_argument("--status", choices=["mirror", "integrate"], default="integrate")
    mirror_execute.add_argument("--yes", action="store_true")
    mirror_execute.set_defaults(func=cmd_github_mirror_execute)
    audit = github_sub.add_parser("audit")
    audit.set_defaults(func=cmd_github_audit)

    devtools = sub.add_parser("devtools")
    devtools_sub = devtools.add_subparsers(required=True)
    devtools_status = devtools_sub.add_parser("status")
    devtools_status.set_defaults(func=cmd_devtools_status)
    devtools_command = devtools_sub.add_parser("command")
    devtools_command.add_argument("--browser-url")
    devtools_command.add_argument("--headless", action="store_true")
    devtools_command.add_argument("--slim", action="store_true", default=True)
    devtools_command.set_defaults(func=cmd_devtools_command)
    devtools_smoke = devtools_sub.add_parser("smoke-test")
    devtools_smoke.set_defaults(func=cmd_devtools_smoke_test)

    workspace = sub.add_parser("workspace")
    workspace_sub = workspace.add_subparsers(required=True)
    workspace_status = workspace_sub.add_parser("status")
    workspace_status.set_defaults(func=cmd_workspace_status)
    workspace_write = workspace_sub.add_parser("write")
    workspace_write.add_argument("path")
    workspace_write.add_argument("content")
    workspace_write.add_argument("--no-newline", dest="newline", action="store_false")
    workspace_write.set_defaults(func=cmd_workspace_write)
    workspace_read = workspace_sub.add_parser("read")
    workspace_read.add_argument("path")
    workspace_read.set_defaults(func=cmd_workspace_read)
    workspace_list = workspace_sub.add_parser("list")
    workspace_list.add_argument("--path", default="/")
    workspace_list.set_defaults(func=cmd_workspace_list)
    workspace_command = workspace_sub.add_parser("command")
    workspace_command.add_argument("--runtime", choices=["facade", "mirage"], default="facade")
    workspace_command.add_argument("--path", default="/")
    workspace_command.set_defaults(func=cmd_workspace_command)
    workspace_smoke = workspace_sub.add_parser("smoke-test")
    workspace_smoke.set_defaults(func=cmd_workspace_smoke_test)

    funds = sub.add_parser("funds")
    funds_sub = funds.add_subparsers(required=True)
    funds_profile = funds_sub.add_parser("profile")
    funds_profile.add_argument("--years", type=float, required=True)
    funds_profile.add_argument("--risk", type=int, choices=[1, 2, 3, 4, 5], required=True)
    funds_profile.add_argument("--profile", choices=["conservative", "balanced", "growth"])
    funds_profile.set_defaults(func=cmd_funds_profile)
    funds_template = funds_sub.add_parser("template")
    funds_template.add_argument("--profile", choices=["conservative", "balanced", "growth"], default="balanced")
    funds_template.add_argument("--international-stock", type=float, default=30)
    funds_template.set_defaults(func=cmd_funds_template)
    funds_score = funds_sub.add_parser("score")
    funds_score.add_argument("--expense-ratio", type=float, required=True)
    funds_score.add_argument("--tracking-error", type=float, default=0.05)
    funds_score.add_argument("--assets-under-management", type=float, default=1000, help="AUM in millions")
    funds_score.add_argument("--broad", action="store_true")
    funds_score.add_argument("--liquid", action="store_true")
    funds_score.set_defaults(func=cmd_funds_score)
    funds_rebalance = funds_sub.add_parser("rebalance")
    funds_rebalance.add_argument("--profile", choices=["conservative", "balanced", "growth"], default="balanced")
    funds_rebalance.add_argument("--stock", type=float, required=True)
    funds_rebalance.add_argument("--bond", type=float, required=True)
    funds_rebalance.add_argument("--cash", type=float, required=True)
    funds_rebalance.add_argument("--threshold", type=float, default=5)
    funds_rebalance.set_defaults(func=cmd_funds_rebalance)

    jarvis = sub.add_parser("jarvis")
    jarvis_sub = jarvis.add_subparsers(required=True)
    jarvis_plan = jarvis_sub.add_parser("plan")
    jarvis_plan.add_argument("goal")
    jarvis_plan.add_argument("--context-path", default=str(ROOT))
    jarvis_plan.add_argument("--context-limit", type=int, default=5)
    jarvis_plan.add_argument("--memory-limit", type=int, default=4)
    jarvis_plan.add_argument("--record", action="store_true")
    jarvis_plan.add_argument("--json", action="store_true")
    jarvis_plan.set_defaults(func=cmd_jarvis_plan)
    jarvis_snapshot = jarvis_sub.add_parser("snapshot")
    jarvis_snapshot.add_argument("--output")
    jarvis_snapshot.set_defaults(func=cmd_jarvis_snapshot)
    jarvis_serve = jarvis_sub.add_parser("serve")
    jarvis_serve.add_argument("--host", default="127.0.0.1")
    jarvis_serve.add_argument("--port", type=int, default=8765)
    jarvis_serve.set_defaults(func=cmd_jarvis_serve)

    workflow = sub.add_parser("workflow")
    workflow_sub = workflow.add_subparsers(required=True)
    workflow_local = workflow_sub.add_parser("local-task")
    workflow_local.add_argument("goal")
    workflow_local.add_argument("--query")
    workflow_local.add_argument("--context-path", default=str(ROOT))
    workflow_local.add_argument("--context-limit", type=int, default=8)
    workflow_local.add_argument("--memory-limit", type=int, default=5)
    workflow_local.add_argument("--risky", action="store_true")
    workflow_local.set_defaults(func=cmd_workflow_local_task)
    workflow_show = workflow_sub.add_parser("show")
    workflow_show.add_argument("run_id", type=int)
    workflow_show.set_defaults(func=cmd_workflow_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
