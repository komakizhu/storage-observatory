---
name: codex-storage-cleanup-compat
description: "中文：旧目录兼容入口，将 Codex 存储检查与清理任务转交给独立维护的 Codex 存储清理 Skill；本目录不再包含扫描、报告、执行或备份实现。 English: Compatibility entry for the retired nested Codex cleanup package; route all work to the independently maintained Codex Storage Cleanup Skill."
---

# Codex 存储清理旧路径兼容入口

此目录只保留历史路径兼容，不再包含扫描器、报告生成器、清理执行器或备份工具。唯一规则和实际入口在独立仓库 [Codex 存储清理](https://github.com/komakizhu/codex-storage-cleanup) 中。

收到 Codex 存储检查、清理建议、清理操作、备份、恢复或每日检查请求时，使用已安装的 `$codex-storage-cleanup` Skill。扫描范围、候选证据、建议表、操作授权、T1 规则和每日北京时间 09:00 自动化都以该 Skill 及其 SOP 为准。

如果独立 Skill 尚未安装，说明需要先安装 `komakizhu/codex-storage-cleanup`，然后停止本任务；不要回退到已退役的本目录脚本或旧 T7_1T 流程。
