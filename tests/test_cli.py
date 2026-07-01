import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from brain_core import cli


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db_path = cli.DB_PATH
        self._old_workspace_root = cli.WORKSPACE_ROOT
        self._old_video_workspace = cli.VIDEO_WORKSPACE
        cli.DB_PATH = Path(self._tmp.name) / "brain.sqlite"
        cli.WORKSPACE_ROOT = Path(self._tmp.name) / "workspace"
        cli.VIDEO_WORKSPACE = cli.WORKSPACE_ROOT / "videos"

    def tearDown(self) -> None:
        cli.DB_PATH = self._old_db_path
        cli.WORKSPACE_ROOT = self._old_workspace_root
        cli.VIDEO_WORKSPACE = self._old_video_workspace
        self._tmp.cleanup()

    def run_cli(self, *args: str) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(list(args))
        self.assertEqual(code, 0)
        return output.getvalue()

    def test_status(self) -> None:
        output = self.run_cli("status")
        self.assertIn("Local Brain: ready", output)
        self.assertIn("Registry:", output)

    def test_registry_lists_integrations(self) -> None:
        output = self.run_cli("registry", "list", "--status", "integrate")
        self.assertIn("Agentmemory", output)
        self.assertIn("Chrome DevTools MCP", output)

    def test_mirror_plan_is_preview_only(self) -> None:
        output = self.run_cli("github", "mirror-plan", "--status", "integrate")
        self.assertIn("git", output)
        self.assertIn("claude-context", output)

    def test_devtools_status(self) -> None:
        output = self.run_cli("devtools", "status")
        self.assertIn("Chrome DevTools MCP slot: ready", output)
        self.assertIn("Local build:", output)

    def test_memory_adapter_status(self) -> None:
        output = self.run_cli("memory", "adapter-status")
        self.assertIn("Memory facade: ready", output)
        self.assertIn("Default store: sqlite", output)

    def test_memory_export_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "memories.json"
            output = self.run_cli("memory", "export-json", "--output", str(output_path))
            self.assertIn("Exported", output)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIn("memories", payload)

    def test_memory_import_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "memories.json"
            input_path.write_text(
                json.dumps(
                    {
                        "memories": [
                            {
                                "created_at": "2026-05-26T00:00:00+00:00",
                                "tags": "test",
                                "content": "import smoke memory",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output = self.run_cli("memory", "import-json", str(input_path))
            self.assertIn("Imported 1 memories", output)

    def test_devtools_smoke_test(self) -> None:
        output = self.run_cli("devtools", "smoke-test")
        self.assertIn("Chrome DevTools MCP smoke test:", output)
        self.assertTrue("ok" in output or "unavailable" in output)

    def test_context_adapter_status(self) -> None:
        output = self.run_cli("context", "adapter-status")
        self.assertIn("Context facade: ready", output)
        self.assertIn("Default search: local text search", output)

    def test_context_adapter_smoke_test(self) -> None:
        output = self.run_cli("context", "adapter-smoke-test")
        self.assertIn("claude-context MCP smoke test:", output)
        self.assertTrue("ok" in output or "unavailable" in output)

    def test_workspace_status(self) -> None:
        output = self.run_cli("workspace", "status")
        self.assertIn("Workspace facade: ready", output)
        self.assertIn("local-only", output)

    def test_workspace_smoke_test(self) -> None:
        output = self.run_cli("workspace", "smoke-test")
        self.assertIn("Workspace smoke test: ok", output)

    def test_workflow_local_task(self) -> None:
        output = self.run_cli(
            "workflow",
            "local-task",
            "Test workflow local task",
            "--query",
            "Local Brain",
            "--context-limit",
            "2",
        )
        self.assertIn("Workflow run completed:", output)
        self.assertIn("Summary:", output)

    def test_runs_list_and_show(self) -> None:
        self.run_cli("task", "plan", "Test run log")
        output = self.run_cli("runs", "list")
        self.assertIn("Test run log", output)
        shown = self.run_cli("runs", "show", "1")
        self.assertIn("Run: 1", shown)
        self.assertIn("Goal: Test run log", shown)

    def test_funds_profile(self) -> None:
        output = self.run_cli("funds", "profile", "--years", "12", "--risk", "4")
        self.assertIn("Suggested profile: growth", output)
        self.assertIn("stocks", output)

    def test_funds_template(self) -> None:
        output = self.run_cli("funds", "template", "--profile", "balanced")
        self.assertIn("Index fund template: balanced", output)
        self.assertIn("美国全市场", output)

    def test_funds_score(self) -> None:
        output = self.run_cli(
            "funds",
            "score",
            "--expense-ratio",
            "0.03",
            "--tracking-error",
            "0.02",
            "--assets-under-management",
            "10000",
            "--broad",
            "--liquid",
        )
        self.assertIn("Fund score:", output)

    def test_funds_rebalance(self) -> None:
        output = self.run_cli(
            "funds",
            "rebalance",
            "--profile",
            "balanced",
            "--stock",
            "70",
            "--bond",
            "25",
            "--cash",
            "5",
        )
        self.assertIn("Suggested rebalance actions", output)

    def test_jarvis_plan_json_is_read_only(self) -> None:
        self.run_cli("memory", "add", "I prefer confirm-before-risk automation.", "--tags", "preference")
        output = self.run_cli("jarvis", "plan", "帮我规划一个本地副脑任务", "--json")
        payload = json.loads(output)
        self.assertEqual(payload["risk_level"], "read-only")
        self.assertIn("plan", payload)
        self.assertIn("memory_candidate", payload)
        self.assertFalse(payload["confirmation_required"])

    def test_jarvis_snapshot_writes_dashboard_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "dashboard.json"
            output = self.run_cli("jarvis", "snapshot", "--output", str(output_path))
            self.assertIn("Jarvis dashboard snapshot written:", output)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIn("summary", payload)
            self.assertIn("modules", payload)
            self.assertIn("video_notes", payload["summary"])

    def test_douyin_inspect_note_with_aweme_images(self) -> None:
        aweme_path = Path(self._tmp.name) / "aweme.json"
        aweme_path.write_text(
            json.dumps(
                {
                    "aweme_detail": {
                        "aweme_type": 68,
                        "images": [
                            {
                                "uri": "image-one",
                                "width": 1080,
                                "height": 1440,
                                "url_list": [
                                    "https://example.test/image-one.jpeg",
                                    "https://example.test/image-one.jpeg",
                                ],
                            },
                            {
                                "uri": "image-two",
                                "display_image": {
                                    "url_list": ["https://example.test/image-two.webp"]
                                },
                            },
                        ],
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = self.run_cli(
            "douyin",
            "inspect",
            "https://www.douyin.com/note/7654131052999627456",
            "--aweme-json",
            str(aweme_path),
            "--json",
        )
        payload = json.loads(output)
        self.assertEqual(payload["content_type"], "note")
        self.assertEqual(payload["content_id"], "7654131052999627456")
        self.assertEqual(payload["image_count"], 2)
        self.assertEqual(payload["note_images"][0]["urls"], ["https://example.test/image-one.jpeg"])

    def test_douyin_cookie_status(self) -> None:
        output = self.run_cli("douyin", "cookie-status")
        self.assertIn("Douyin cookie status:", output)
        self.assertIn("cookie file:", output)

    def test_video_analyze_from_metadata_json(self) -> None:
        metadata_path = Path(self._tmp.name) / "metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "id": "sample123",
                    "title": "AI 建站流｜电影感网页",
                    "description": "真正有用的是这套流程：\n1. 先定 landing page 的参考结构\n2. 再备好人物、流体、动态视频这些素材\n3. 用 Gemini 把网站骨架先跑出来",
                    "duration": 208,
                    "duration_string": "3:28",
                    "channel": "设计师言炎",
                    "webpage_url": "https://example.test/video/sample123",
                    "like_count": 12467,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = self.run_cli(
            "video",
            "analyze",
            "https://example.test/video/sample123",
            "--metadata-json",
            str(metadata_path),
            "--no-download",
        )
        self.assertIn("Video analysis completed.", output)
        self.assertIn("Stored id: 1", output)
        shown = self.run_cli("video", "show", "1")
        self.assertIn("AI 建站流", shown)
        self.assertIn("先定 landing page", shown)
        listed = self.run_cli("video", "list")
        self.assertIn("sample123", self.run_cli("video", "show", "1", "--json"))
        self.assertIn("设计师言炎", listed)

    def test_video_report_from_note(self) -> None:
        metadata_path = Path(self._tmp.name) / "ppt_metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "id": "pptnote123",
                    "title": "Codex生成PPT效果展示。ppt-master",
                    "description": "展示如何用 Codex 结合 ppt-master 把文档变成可编辑 PPT，并沉淀成 skill 工作流。",
                    "duration": 20,
                    "channel": "AI运粮官",
                    "webpage_url": "https://www.douyin.com/note/7654131052999627456",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.run_cli(
            "video",
            "analyze",
            "https://v.douyin.com/r0yWuUpe8Zo/",
            "--metadata-json",
            str(metadata_path),
            "--no-download",
        )
        report_path = Path(self._tmp.name) / "project_report.md"
        output = self.run_cli("video", "report", "1", "--target", "local-brain", "--output", str(report_path))
        self.assertIn("Video project report written:", output)
        self.assertIn("Detected tools:", output)
        report = report_path.read_text(encoding="utf-8")
        self.assertIn("PPT Master", report)
        self.assertIn("Codex", report)
        self.assertIn("落地动作", report)


if __name__ == "__main__":
    unittest.main()
