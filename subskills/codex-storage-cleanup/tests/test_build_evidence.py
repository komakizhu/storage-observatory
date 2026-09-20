import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_evidence import decide_builds, inspect_artifact
from scan_codex import discover_nested_dirs


class BuildDecisionTests(TestCase):
    def fixture(self, home, name, timestamp, complete=True, custom=False):
        home = home.resolve()
        repo = home / name
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', 'https://example.test/project.git'], check=True)
        subprocess.run(['git', '-C', str(repo), 'symbolic-ref', 'HEAD', 'refs/heads/' + name], check=True)
        (repo / '.gitignore').write_text('target*/\n')
        (repo / 'Cargo.toml').write_text('[package]\nname="example"\nversion="1.0.0"\nedition="2021"\n')
        (repo / 'src').mkdir()
        (repo / 'src/main.rs').write_text('fn main() {}')
        target = repo / ('target-custom' if custom else 'target')
        (target / 'debug/.fingerprint').mkdir(parents=True)
        (target / '.rustc_info.json').write_text('{}')
        if complete:
            output = target / 'debug/libexample.rlib'
            output.write_bytes(b'compiled')
            os.utime(output, (timestamp, timestamp))
        return {'path': str(target), 'home': str(home), 'review_priority': 'old-artifact', 'tier': 'manual', 'trash_paths': []}

    def test_keep_one_latest_across_branches_delete_older_and_incomplete(self):
        with TemporaryDirectory() as temp:
            home = Path(temp)
            old = self.fixture(home, 'oldbranch', 1000)
            latest = self.fixture(home, 'newbranch', 2000)
            failed = self.fixture(home, 'failedbranch', 3000, complete=False)
            items = decide_builds([old, latest, failed], lambda _: (False, 'idle'))
            self.assertEqual(latest['retention'], 'latest')
            self.assertEqual(sum(i['tier'] == 'regenerable' for i in items), 2)
            self.assertEqual(old['retained_path'], latest['path'])
            self.assertEqual(failed['trash_paths'], [failed['path']])
            self.assertIn('Cargo.toml', old['rebuild_command'])

    def test_missing_source_and_tracked_content_cannot_be_deleted(self):
        with TemporaryDirectory() as temp:
            home = Path(temp)
            item = self.fixture(home, 'missing', 1000)
            (home / 'missing/src/main.rs').unlink()
            with self.assertRaisesRegex(ValueError, '源码入口缺失'):
                inspect_artifact(item['path'])

    def test_untracked_user_document_inside_output_is_protected(self):
        with TemporaryDirectory() as temp:
            home = Path(temp)
            item = self.fixture(home, 'mixed', 1000)
            (Path(item['path']) / 'debug/notes.md').write_text('user notes')
            with self.assertRaisesRegex(ValueError, '混有无法识别'):
                inspect_artifact(item['path'])
            item = self.fixture(home, 'tracked', 1000)
            subprocess.run(['git', '-C', str(home / 'tracked'), 'add', '-f', 'target/debug/libexample.rlib'], check=True)
            with self.assertRaisesRegex(ValueError, 'Git 跟踪'):
                inspect_artifact(item['path'])

    def test_active_and_unknown_activity_preserved(self):
        for state in (True, None):
            with TemporaryDirectory() as temp:
                home = Path(temp)
                old = self.fixture(home, 'old', 1000)
                latest = self.fixture(home, 'latest', 2000)
                decide_builds([old, latest], lambda _: (state, 'busy/unknown'))
                self.assertEqual(old['tier'], 'protected')
                self.assertEqual(old['trash_paths'], [])

    def test_unique_build_retained(self):
        with TemporaryDirectory() as temp:
            item = self.fixture(Path(temp), 'only', 1000)
            decide_builds([item], lambda _: (False, 'idle'))
            self.assertEqual(item['retained_path'], item['path'])
            self.assertEqual(item['tier'], 'protected')

    def test_binary_without_executable_bit_and_unignored_custom_target(self):
        with TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            item = self.fixture(home, 'custom', 1000, custom=True)
            target = Path(item['path'])
            (home / 'custom/.gitignore').write_text('')
            (target / 'CACHEDIR.TAG').write_text('Signature: 8a477f597d28d172789f06886806bc55')
            (target / 'debug/libexample.rlib').unlink()
            binary = target / 'debug/example'
            binary.write_bytes(b'\xcf\xfa\xed\xfe' + b'0' * 20)
            binary.chmod(0o600)
            evidence = inspect_artifact(target)
            self.assertIn(str(binary), evidence['completed_outputs'])

    def test_bundled_model_requires_identical_local_original(self):
        with TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            item = self.fixture(home, 'model', 1000)
            repo = home / 'model'
            (repo / 'tauri.conf.json').write_text('{"bundle":{"resources":{"resources/models/**/*":"models"}}}')
            (repo / 'resources/models').mkdir(parents=True)
            original = repo / 'resources/models/model.bin'
            original.write_bytes(b'model weights')
            bundled = Path(item['path']) / 'debug/models'
            bundled.mkdir()
            (bundled / 'model.bin').write_bytes(b'model weights')
            self.assertTrue(inspect_artifact(item['path'])['source_entries'])
            original.unlink()
            with self.assertRaisesRegex(ValueError, '混有无法识别'):
                inspect_artifact(item['path'])

    def test_custom_target_discovered_as_whole_directory(self):
        with TemporaryDirectory() as temp:
            item = self.fixture(Path(temp), 'custom', 1000, custom=True)
            (Path(item['path']) / 'debug/build').mkdir()
            self.assertEqual(discover_nested_dirs(Path(temp).resolve()), [Path(item['path'])])
            self.assertTrue(inspect_artifact(item['path'])['source_entries'])

    def test_different_project_and_user_do_not_share_keeper(self):
        with TemporaryDirectory() as temp:
            home = Path(temp)
            a = self.fixture(home, 'a', 1000)
            b = self.fixture(home, 'b', 2000)
            b['home'] = str(home / 'another-user')
            decide_builds([a, b], lambda _: (False, 'idle'))
            self.assertTrue(all(i['tier'] == 'protected' for i in (a, b)))

    def test_parent_mtime_does_not_override_completed_output_time(self):
        with TemporaryDirectory() as temp:
            home = Path(temp)
            a = self.fixture(home, 'a', 1000)
            b = self.fixture(home, 'b', 2000)
            os.utime(a['path'], (9000, 9000))
            decide_builds([a, b], lambda _: (False, 'idle'))
            self.assertEqual(a['retained_path'], b['path'])

    def test_server_refuses_newer_build_or_missing_keeper(self):
        import serve_codex_report as server
        with TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            old = self.fixture(home, 'old', 1000)
            latest = self.fixture(home, 'latest', 2000)
            decide_builds([old, latest], lambda _: (False, 'idle'))
            with patch.object(server, 'DATA', {'items': [old, latest]}), patch.object(server, 'USER_HOMES', {str(home)}), patch.object(server, 'open_handle_status', return_value=(False, 'idle')):
                server.revalidate_build(old['path'])
                output = Path(old['path']) / 'debug/libexample.rlib'
                os.utime(output, (3000, 3000))
                with self.assertRaisesRegex(ValueError, '更新的构建'):
                    server.revalidate_build(old['path'])
                (Path(latest['path']) / 'debug/libexample.rlib').unlink()
                with self.assertRaisesRegex(ValueError, '缺少已完成'):
                    server.revalidate_build(old['path'])

    def test_vite_output_from_same_project_keeps_latest(self):
        with TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            items = []
            for name, timestamp in [('old', 1000), ('new', 2000)]:
                self.fixture(home, name, timestamp)
                repo = home / name
                (repo / '.gitignore').write_text('dist/\ntarget/\n')
                (repo / 'package.json').write_text('{"scripts":{"build":"vite build"},"devDependencies":{"vite":"1"}}')
                (repo / 'src/main.ts').write_text('console.log(1)')
                (repo / 'dist/assets').mkdir(parents=True)
                (repo / 'dist/index.html').write_text('<html></html>')
                output = repo / 'dist/assets/main.js'
                output.write_text('console.log(1)')
                os.utime(output, (timestamp, timestamp))
                items.append({'path': str(repo / 'dist'), 'home': str(home), 'review_priority': 'old-artifact', 'tier': 'manual', 'trash_paths': []})
            decide_builds(items, lambda _: (False, 'idle'))
            self.assertEqual(items[0]['tier'], 'regenerable')
            self.assertEqual(items[0]['retained_path'], items[1]['path'])
