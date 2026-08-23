from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch
import json
import sys


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import server  # noqa: E402


class ServerAllowlistTests(TestCase):
    def test_browser_opens_only_after_report_returns_200(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response

        with patch.object(server, "urlopen", return_value=response) as request:
            with patch.object(server.webbrowser, "open") as open_browser:
                server.open_browser_when_ready("http://127.0.0.1:43210/")

        request.assert_called_once_with("http://127.0.0.1:43210/", timeout=0.5)
        open_browser.assert_called_once_with("http://127.0.0.1:43210/")

    def test_only_current_verified_non_symlink_cache_is_delete_allowed(self):
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            work = workspace / "work"
            outputs = workspace / "outputs"
            work.mkdir()
            outputs.mkdir()
            valid = workspace / "valid-cache"
            valid.mkdir()
            stale = workspace / "stale-cache"
            link = workspace / "linked-cache"
            try:
                link.symlink_to(valid, target_is_directory=True)
            except (OSError, NotImplementedError):
                link = None
            green = [
                {"verified": True, "trash_paths": [str(valid)]},
                {"verified": False, "trash_paths": [str(stale)]},
            ]
            if link is not None:
                green.append({"verified": True, "trash_paths": [str(link)]})
            (work / "storage-analysis-live.json").write_text(
                json.dumps({"green": green, "yellow": [], "red": [], "top5": []}),
                encoding="utf-8",
            )
            (outputs / "storage-observatory-report.html").write_text(
                "<html></html>", encoding="utf-8"
            )

            server.load_report(workspace)

            self.assertIn(str(valid), server.RM_ALLOW)
            self.assertNotIn(str(stale), server.RM_ALLOW)
            if link is not None:
                self.assertNotIn(str(link), server.RM_ALLOW)


if __name__ == "__main__":
    import unittest

    unittest.main()
