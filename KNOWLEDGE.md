# DesktopNote — 项目长期记忆

> 供新会话快速恢复上下文，不必重新发现。读到即用；每学到一条就追加。

## 这是什么

Windows 10/11 x64 原生桌面便签。C++20 + Win32 + Direct2D + Windowless RichEdit。发布物只有一个静态 CRT 的 `DesktopNote.exe`（约 700 KiB，< 5 MiB 门槛），无 .NET/WebView2/Qt 依赖。仓库：`D:\GitRepo-My\DesktopNote`（git 分支 `main`）。

## 构建 / 测试 / 运行（确切命令）

```bash
cd /d/GitRepo-My/DesktopNote
cmake --preset msvc-release
cmake --build --preset msvc-release --parallel
ctest --preset msvc-release        # 3 套件：DesktopNoteTests / RichEdit / Window
```

- 工具链：CMake 3.31 + Visual Studio 2022 Community（MSVC 19.44，`C:\Program Files\Microsoft Visual Studio\2022\Community`）。
- 输出：`build/msvc-release/Release/DesktopNote.exe`。
- Release 用 `/LTCG` 全程序优化，改 `desktopnote_core` 里的任何 `.cpp` 都会触发慢速 LTCG 重链（约 15–25s/次）。
- 数据目录 `%APPDATA%\DesktopNote\data.json`；`DESKTOPNOTE_DATA_DIR` 环境变量可覆盖（测试用它做隔离）。

## 架构关键点

- `desktopnote_core`（静态库）：模型/序列化/迁移/存储/Win32 工具 + 新加的 `hotkey.{h,cpp}`。
- `DesktopNote`（可执行）：`Application` 控制器（隐藏 controller 窗口 + 托盘 + 消息循环）、`NoteWindow`、`NoteRenderer`（D2D/DWrite）、`RichEditHost`、`NoteToolbar`、`DesktopEmbedder`（WorkerW 桌面层）。
- 桌面嵌入不是改父窗口：保持顶层 `WS_POPUP`，动态解析 Explorer 图标层/壁纸层，夹在中间；失败安全回退普通模式。
- 单实例：命名互斥量 + `FindWindow` controller class；第二实例给第一实例 PostMessage 显示。

## 本次会话决策

- **全局热键快速捕捉**（新增）：`Ctrl+Alt+N` 新建并聚焦便签、`Ctrl+Alt+H` 显示/隐藏全部。设计文档 `docs/quick-capture-hotkey.md`。
  - 组合键选 `Ctrl+Alt+…`（`Win+N` 被系统占用）；都加 `MOD_NOREPEAT` 防按住重复触发。
  - 新模块放 `desktopnote_core`（不是 app），让 `DesktopNoteTests` 可链接单测，不必拉整个窗口应用。
  - 注册在 controller 窗口上（`Run()` 进消息循环前），`WM_HOTKEY` 的 `wParam` 就是 id；分发到既有的 `CreateNewNote(active_window_)` / `ToggleAllWindows()`。
  - 注销在析构 + `Exit()` 两处，`DestroyWindow` 之前，`UnregisterHotkeys()` 对 `controller_window_` 空安全。

## 踩坑（错误签名 + 修法）

- **`RegisterHotKey(nullptr, …)` 在控制台线程失败**：无消息队列时返回 FALSE。修法：注册前先 `PeekMessageW(&msg, nullptr, 0, 0, PM_NOREMOVE)` 强制建队列，或用真实窗口。单测里正是靠这一行才从 SKIP 变 PASS。
- **托盘菜单 "新建便签 (Ctrl+N)" / "置顶模式 (Ctrl+T)" 是死标签**：仓库无 ACCELERATORS / HACCEL / TranslateAccelerator，纯菜单文字。已知遗留，未修（避免范围膨胀），见 JOURNEY.md。
- **本机 `bash` 里 `python` 是 2.7**（f-string 会 SyntaxError）；用 `python3`（3.13）。
- **`tasklist //FI "IMAGENAME eq …"` 在 git-bash 下偶发匹配不到**；用 `tasklist | grep -i` 更稳。

## 数字基线

- 测试：15 单测（含新增 hotkey contract + lifecycle）+ 2 集成套件，`ctest` 3/3 全绿（约 3.5s）。
- 热键端到端验证：发 `Ctrl+Alt+N` → 便签数 1→2；发 `Ctrl+Alt+H` → 可见便签窗口 2→0→2。

## 下一步（按优先级）

1. 跨便签搜索（当前全仓库无任何搜索）。
2. 纯文本/Markdown 模式 + 粘贴无格式。
3. 导出/导入 Markdown。
4. 热键自定义 UI（当前固定默认值）。
