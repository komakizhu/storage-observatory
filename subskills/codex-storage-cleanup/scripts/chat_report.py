"""Compact in-conversation cleanup comparison, without changing action scope."""
from __future__ import annotations


def option_totals(items):
    # Each artifact is counted once, never count a protected parent container.
    unique = {item['path']: item for item in items}
    builds = [item for item in unique.values() if item.get('source_entries') and item.get('rebuild_basis')]
    old = [item for item in builds if item.get('review_priority') == 'delete-old-build']
    size = lambda rows: sum(int(item.get('size_bytes') or 0) for item in rows)
    return {
        'keep_latest_bytes': size(old),
        'all_build_bytes': size(builds),
        'all_build_in_use_bytes': size([item for item in builds if item.get('active') is True]),
        'all_build_usage_unknown_bytes': size([item for item in builds if item.get('active') is None]),
        'all_build_idle_bytes': size([item for item in builds if item.get('active') is False]),
        'secondary_cache_bytes': size([item for item in unique.values() if item.get('tier') == 'regenerable' and item.get('review_priority') != 'delete-old-build']),
        'session_bytes': size([item for item in unique.values() if item.get('artifact_type') in {'归档/已关闭会话', '当前/普通会话'}]),
        'image_output_bytes': size([item for item in unique.values() if item.get('artifact_type') == '生成图片与用户输出']),
    }


def render_chat_report(payload):
    totals = option_totals(payload.get('items', []))
    gb = lambda number: f'{number / 1_000_000_000:.2f} GB'
    a = totals['keep_latest_bytes']
    b = totals['all_build_bytes'] - totals['all_build_in_use_bytes']
    notes = []
    if totals['all_build_usage_unknown_bytes']:
        notes.append(f"全删估算中 {gb(totals['all_build_usage_unknown_bytes'])} 尚需检查使用状态。")
    if totals['all_build_in_use_bytes']:
        notes.append(f"已排除 {gb(totals['all_build_in_use_bytes'])} 正在使用的构建。")
    return '\n'.join([
        f"扫描时间：{payload.get('generated_at', '未知')}。以下是占用/清理估算，尚未执行。",
        '',
        '| 类别 | 占用或可清理量 | 建议 |',
        '|---|---:|---|',
        f"| 应用缓存、临时文件 | 约 {gb(totals['secondary_cache_bytes'])} | 一般保留；Cargo 等下载缓存也保留 |",
        f'| 旧构建：每项目留最新一份 | 可清约 {gb(a)} | 推荐 |',
        f'| 构建：一份也不留 | 估计可清 {gb(b)}，比上一方案多 {gb(max(b-a, 0))} | 源码和依赖保留，下次需要重新构建 |',
        f"| 会话记录 | 占用 {gb(totals['session_bytes'])} | 用户数据，默认保留 |",
        f"| 生成图片及输出 | 占用 {gb(totals['image_output_bytes'])} | 用户数据，默认保留；临时缓存另核实 |",
        '',
        f'建议先清旧构建、每项目留最新一份，约 {gb(a)}；缓存、会话和图片保留。两个构建方案互斥，不能相加。',
        ''.join(notes) + '移入同盘回收站不等于立即释放空间。',
    ])
