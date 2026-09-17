---
name: codex-storage-cleanup
description: "Cross-platform, multi-user inspection and cleanup of Codex-generated storage on macOS and Windows, including archived or closed sessions, caches, logs, temporary files, and old regenerable artifacts inside Codex worktrees or Codex-created Documents workspaces. Use when auditing or cleaning Codex disk usage; preserve workspace roots and source projects, produce an evidence-backed candidate list first, prefer Trash or Recycle Bin, and require explicit authorization before moving or deleting anything."
---

# Codex Storage Cleanup

Use this skill to audit and clean Codex-generated storage for every readable local user on macOS or Windows. Read [the full SOP](references/codex-storage-cleanup-sop.md) before inspecting or proposing a concrete operation, and read the sections relevant to the current platform and candidate type. Preserve each workspace and worktree root; this skill handles old artifacts inside them, not removal of the workspace itself. This child skill is maintained inside the main `storage-observatory` skill tree and shares its visual/reporting rules.

## Scope

- Cover all readable, non-system local user profiles rather than assuming the current user or mac2. Record the platform, user, home directory, Codex roots, ownership, permissions, and inaccessible profiles.
- Inspect Codex roots plus only those Documents or application-data directories with evidence that Codex created or manages them. Never treat an entire Documents, Downloads, user home, C:\Users, or disk as a Codex cleanup target.
- Include archived or demonstrably closed sessions, Codex caches, logs, temporary files, and old complete regenerable artifacts inside confirmed Codex worktrees or Codex-created Documents workspaces. Keep workspace/worktree roots, source, Git metadata, and user outputs protected.
- Use provenance, ownership, active-process/open-handle checks, Git status, configuration/metadata, and content inspection. Age, size, or a name such as cache, build, or dist is not enough.

## Authorization and safety

- Separate discovery, candidate reporting, authorization, action, and verification. Inspection, backup, and planning remain read-only.
- Require authorization that covers the affected user/platform, exact artifact paths or an identified candidate group, and whether to use Trash/Recycle Bin or permanent deletion. Do not expand a confirmed group to adjacent paths or to its parent workspace.
- Prefer reversible moves to macOS Trash or Windows Recycle Bin for sessions and artifacts. Permit permanent deletion only for explicitly authorized, verified, regenerable caches or complete build directories. Never delete a workspace or worktree root as part of this skill.
- For another user, inspect only what the OS permits; do not use elevation or permissions changes merely to bypass uncertainty. Report inaccessible profiles and stop on protected or ambiguous data.
- Treat workspace/worktree roots, active sessions, running tasks, open files, uncommitted or unknown project data, source code, user documents, settings, credentials, databases, lock files, and system snapshots as protected.
- Never empty Trash/Recycle Bin, delete APFS/Time Machine/Windows recovery data, or use broad recursive deletion against unresolved paths.

## Required workflow

1. Discover users and platform-specific Codex roots, resolve absolute paths, and reject symlinks, aliases, junctions, and reparse points for destructive actions.
2. Build a candidate ledger with user/platform, exact path, Codex provenance, type, size, time, active/open state, Git state, risk, recovery path, and proposed action.
3. Classify each item as protected, regenerable, high-risk user data, or unknown/system. Confirm the parent workspace/worktree provenance, but propose only precise child artifacts; never propose deleting the workspace/worktree root.
4. Back up and content-verify archived/closed sessions before deletion. Do not infer that sessions are deletable from age alone.
5. Present the complete candidate list and wait for scoped authorization before any move or deletion. Execute only exact, revalidated paths using the platform’s reversible disposal mechanism where possible.
6. Verify the result per user and category, confirm that unapproved data and source state are unchanged, calculate actual space change, and report skipped or inaccessible items.

## Candidate-specific rules

- For archives, compare file count, total bytes, and content checksums; exclude filesystem metadata sidecars from real-chat counts and explain them.
- For caches, logs, and temporary files, confirm Codex ownership, non-critical content, no active use, and regeneration before proposing permanent deletion.
- For artifacts inside Documents workspaces, require strong Codex provenance for both the parent and child path, no active use, and path-level confirmation. Preserve source, user documents, and the workspace root; do not require a clean Git tree to delete a separately verified generated artifact, but never delete mixed or ambiguous content.
- For worktrees and build artifacts, group by user/project/configuration/architecture/platform and remove complete confirmed artifact directories only; do not delete the worktree root or hand-delete internal object or incremental files.

## Report presentation

Reuse the main skill’s existing visualization system instead of inventing a second visual language. Before generating an HTML/dashboard report, read the [主 skill「存储观察站」](../../SKILL.md), especially its data-口径、可视化交付契约、当前色系与语义、懒加载 and local-service rules. Keep its Lieflat Charts Wire black/gray base, plum-green/orange change semantics, 2×2 chart arrangement, F11/F2/G10 visual vocabulary, and per-category neutral cleanup bars. Add cleanup-specific dimensions—user, platform, artifact type, risk, provenance, recoverability, and exact path—without changing the parent palette or chart grammar.

Keep the candidate ledger readable with progressive disclosure: show items of 100 MB or more individually, collect smaller items under “其他”, and reveal the next level at 10 MB or more when that group is opened. Continue dividing the remaining group by ten (1 MB, 100 KB, 10 KB, and so on) until the concrete items are visible. If the 100 MB rule would leave fewer than five individual items while the category has more than five items, show the five largest items individually and collect only the sixth and later items under “其他”. If a category has five or fewer items in total, show all of them without an “其他” group. The group summary must show its total size and item count; expanding a group must never widen the cleanup scope.

## Completion report

Report all inspected users and platforms, discovered roots, candidate counts and sizes by category, exact artifact paths/actions for anything moved or deleted, backup and checksum results, actual space released, inaccessible/skipped items and reasons, and explicit confirmation that workspace/worktree roots, active sessions, unapproved user data, source/Git state, credentials, settings, Trash/Recycle Bin contents, and system recovery data were preserved.

## Report runner

For a visual audit, run the bundled read-only scanner and child report builder:

```sh
CHILD_SKILL_ROOT=/path/to/storage-observatory/subskills/codex-storage-cleanup
python3 "$CHILD_SKILL_ROOT/scripts/scan_codex.py" --workspace <scratch-workspace>
python3 "$CHILD_SKILL_ROOT/scripts/serve_codex_report.py" --workspace <scratch-workspace>
```

The scanner writes `work/storage-analysis-live.json` and the builder writes `outputs/codex-storage-cleanup-report.html`. The child report imports the main `存储观察站` CSS/visual tokens at build time, but its page content is Codex-only: users and roots, archived sessions, Codex application diagnostics/cache, old workspace/worktree artifacts, exact-path evidence, protected context, and authorization state. The child server uses a fresh local token and an allowlist derived from the ledger, supports only exact `open` and reversible `trash` actions, and never acts during scanning or report generation.
