from pathlib import Path
import sys
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from chat_report import option_totals, render_chat_report


class ChatReportTests(TestCase):
    def test_alternative_plan_includes_keepers_without_expanding_deletion(self):
        def build(path, size, state, priority):
            return dict(path=path, size_bytes=size, active=state, review_priority=priority,
                        source_entries=['src/main.rs'], rebuild_basis='verified', trash_paths=[])
        old = build('/old', 10_000_000_000, False, 'delete-old-build')
        latest = build('/latest', 20_000_000_000, None, 'old-artifact')
        busy = build('/busy', 5_000_000_000, True, 'old-artifact')
        parent = dict(path='/workspace', size_bytes=100_000_000_000, tier='protected')
        items = [old, latest, busy, parent, dict(old)]
        totals = option_totals(items)
        self.assertEqual(totals['keep_latest_bytes'], 10_000_000_000)
        self.assertEqual(totals['all_build_bytes'], 35_000_000_000)
        self.assertEqual(totals['all_build_usage_unknown_bytes'], 20_000_000_000)
        self.assertEqual(totals['all_build_in_use_bytes'], 5_000_000_000)
        self.assertEqual(latest['trash_paths'], [])
        self.assertIn('估计可清 30.00 GB', render_chat_report({'items': items}))

    def test_user_outputs_are_not_disposable_cache(self):
        items = [dict(path='/images', artifact_type='生成图片与用户输出', size_bytes=100),
                 dict(path='/sessions', artifact_type='当前/普通会话', size_bytes=200),
                 dict(path='/cache', tier='regenerable', size_bytes=10)]
        totals = option_totals(items)
        self.assertEqual(totals['secondary_cache_bytes'], 10)
        self.assertEqual(totals['session_bytes'], 200)
        self.assertEqual(totals['image_output_bytes'], 100)
        self.assertEqual(totals['all_build_bytes'], 0)
