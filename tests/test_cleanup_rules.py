from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import os
import sys


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cleanup_rules  # noqa: E402
import run_snapshot  # noqa: E402


class CleanupRuleTests(TestCase):
    def test_existing_measured_cache_becomes_verified_candidate(self):
        with TemporaryDirectory() as temp:
            cache = Path(temp) / "cache"
            cache.mkdir()
            (cache / "payload.bin").write_bytes(b"x" * 1_200_000)
            rule = cleanup_rules._rule(
                "测试缓存", [str(cache)], "可以重新生成的测试数据。"
            )

            item, issues = cleanup_rules._scan_rule(rule)

            self.assertEqual(issues, [])
            self.assertIsNotNone(item)
            self.assertTrue(item["verified"])
            self.assertEqual(item["trash_paths"], [os.path.abspath(cache)])
            self.assertGreaterEqual(item["size_bytes"], 1_000_000)

    def test_symbolic_link_never_enters_actionable_candidate(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "target"
            target.mkdir()
            (target / "payload.bin").write_bytes(b"x" * 1_200_000)
            link = Path(temp) / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable on this platform")

            item, issues = cleanup_rules._scan_rule(
                cleanup_rules._rule("链接缓存", [str(link)], "测试")
            )

            self.assertIsNone(item)
            self.assertTrue(issues)
            self.assertIn("符号链接", issues[0]["reason"])

    def test_cleanup_sections_are_rebuilt_from_current_inputs(self):
        current = {
            "system": {"disk_free": "4.0 GB"},
            "groups": {"home": [], "app_support": [], "containers": [], "applications": []},
            "denied": [],
            "warnings": [],
        }
        fresh = {
            "green": [{"name": "当前缓存", "size_bytes": 2_000_000}],
            "issues": [],
        }

        sections = run_snapshot.rebuild_cleanup_sections(current, fresh)

        self.assertEqual([item["name"] for item in sections["green"]], ["当前缓存"])
        self.assertEqual(sections["yellow"], [])
        self.assertEqual(sections["red"], [])

    @mock.patch("run_snapshot.platform.system", return_value="Darwin")
    def test_macos_permission_message_is_explicit(self, _platform):
        status = run_snapshot.permission_status(
            {"denied": ["~/Library/Mail"], "warnings": []},
            {"issues": []},
        )

        self.assertTrue(status["needs_attention"])
        self.assertEqual(status["platform"], "macOS")
        joined = " ".join(status["steps"])
        self.assertIn("完全磁盘访问权限", joined)
        self.assertIn("Codex", joined)
        self.assertIn("不会扩大网页删除白名单", status["note"])

    @mock.patch("run_snapshot.platform.system", return_value="Windows")
    def test_windows_program_folder_is_open_only_uninstall_candidate(self, _platform):
        with TemporaryDirectory() as temp:
            app = Path(temp) / "Example App"
            app.mkdir()
            current = {
                "groups": {
                    "program_files": [{
                        "name": "Example App",
                        "path": str(app),
                        "size_kb": 700_000,
                    }]
                }
            }

            candidates = run_snapshot.derive_red_candidates(current)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["app_paths"], [str(app)])
            self.assertTrue(candidates[0]["verified"])


if __name__ == "__main__":
    import unittest

    unittest.main()
