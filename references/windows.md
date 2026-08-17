# Windows 数据布局与分级参考

Windows 的扫描结果进入与其他平台相同的快照 JSON 和 HTML 报告。这里只记录平台特有的目录含义，不改变报告的数据结构或图表。

- `%USERPROFILE%`：当前用户文件、Downloads 和用户级开发目录。
- `%LOCALAPPDATA%`：浏览器缓存、应用缓存、临时文件和本地应用数据。
- `%APPDATA%`：漫游配置和应用数据，通常需要人工判断。
- `C:\Program Files`、`C:\Program Files (x86)`：应用本体，不作为普通缓存自动删除。
- `C:\$Recycle.Bin`：回收站，只展示为人工处理项。
- `WinSxS`、`pagefile.sys`、`hiberfil.sys` 等系统项目不提供手工删除按钮，应通过 Windows 设置、磁盘清理或系统命令处理。

Windows 可以有多个盘符。报告会列出所有可见盘符，但自动清理候选默认限制在当前用户目录内，并通过 Shell 回收站接口执行可逆操作。
