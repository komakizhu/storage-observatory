from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import os
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import scan_codex as scan


class CleanupPolicyTests(TestCase):
    def test_documents_chatgpt_is_discovered(self):
        with TemporaryDirectory() as temp:
            home = Path(temp)
            target = home / 'Documents' / 'ChatGPT'
            target.mkdir(parents=True)
            self.assertIn(target, [p for p, _, _ in scan.root_candidates(home)])

    def test_old_dependencies_retained_and_builds_require_retention_evidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('node_modules', '.pnpm-store', '.venv', 'target', 'build'):
                path = root / name
                path.mkdir()
                old = time.time() - 86400 * 30
                os.utime(path, (old, old))
            user = {'user': 'test', 'home': temp, 'platform': 'macOS', 'issues': []}
            items = []
            with mock.patch.object(scan, 'safe_size', return_value=(1_000_000, None)):
                scan.add_project_artifacts(user=user, root=root, workspace_roots=[root], items=items)
            by_name = {item['name']: item for item in items}
            for name in ('node_modules', '.pnpm-store', '.venv'):
                self.assertEqual(by_name[name]['tier'], 'protected')
            for name in ('target', 'build'):
                self.assertEqual(by_name[name]['tier'], 'manual')
                self.assertTrue(by_name[name]['retained_path'])
            self.assertTrue(all(not item['trash_paths'] for item in items))

    def test_plugin_download_cache_is_not_actionable(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / '.codex'
            (root / 'plugins' / 'cache').mkdir(parents=True)
            user = {'user': 'test', 'home': temp, 'platform': 'macOS', 'issues': [], 'codex_roots': []}
            items = []
            with mock.patch.object(scan, 'safe_size', return_value=(1_000_000, None)), mock.patch.object(scan, 'open_handle_status', return_value=(False, 'idle')):
                scan.scan_root(user, root, 'Codex', 'codex', items)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['tier'], 'protected')
            self.assertEqual(items[0]['trash_paths'], [])

    def test_cargo_registry_cache_is_retained(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root / 'cargo-home' / 'registry' / 'index' / 'index.crates.io' / '.cache'
            cache.mkdir(parents=True)
            user = {'user': 'test', 'home': temp, 'platform': 'macOS', 'issues': []}
            items = []
            with mock.patch.object(scan, 'safe_size', return_value=(43_000_000, None)):
                scan.add_project_artifacts(user=user, root=root, workspace_roots=[root], items=items)
            cargo = next(item for item in items if item['path'] == str(cache))
            self.assertEqual(cargo['artifact_type'], 'Cargo 下载缓存')
            self.assertEqual(cargo['tier'], 'protected')
            self.assertEqual(cargo['trash_paths'], [])

    def test_unverified_artifacts_do_not_inflate_candidate_total(self):
        with TemporaryDirectory() as temp:
            home = Path(temp)
            (home / 'Documents' / 'ChatGPT' / 'Project' / 'target').mkdir(parents=True)
            old = time.time() - 86400 * 30
            os.utime(home / 'Documents' / 'ChatGPT' / 'Project' / 'target', (old, old))
            users = [{'user': 'test', 'home': temp, 'readable': True, 'codex_roots': [], 'issues': []}]
            with mock.patch.object(scan, 'user_homes', return_value=users), mock.patch.object(scan, 'active_process_snapshot', return_value=(False, [])), mock.patch.object(scan, 'safe_size', return_value=(1_000_000, None)):
                data = scan.build_data()
            self.assertEqual(data['summary']['candidate_bytes'], 0)
            self.assertEqual(data['users'][0]['candidate_bytes'], 0)
            self.assertEqual(data['summary']['manual_bytes'], 1_000_000)
            self.assertTrue(data['ledger_meta']['recommendation_review_pending'])


if __name__ == '__main__':
    import unittest
    unittest.main()
