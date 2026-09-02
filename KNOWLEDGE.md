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

---

## 第二次会话（2026-09-01）——光标漂移修复 + 100 增强点子脑暴

### 本次决策
- **修复光标/插入符闪烁位置漂移（贴边时最明显）**：根因是 `RichEditHost` 的坐标系错配——`bounds_`（RichEdit 客户区）在 `NoteWindow::UpdateEditorBounds` 里被存成**设备像素**，但 D2D 渲染目标、插入符、背景都在 **DIP**。任何窗口 DPI != 96 时，控制件把「像素值」当 DIP 布局文字，比例就偏差（120 DPI 时文字 1.25× 过大），于是插入符相对文字漂移。修法：`bounds_` 全链路改成 DIP（`UpdateEditorBounds` 用 `pixel_to_dip` 把客户区像素转 DIP、padding 用 `padding_dip`），`Draw()` 直接以 DIP 的 `bounds_` 作 `TxDrawD2D` 的 `prcView`，插入符同 DIP 空间绘制；`TxGetExtent` 的 HIMETRIC 基改正的 96（而非窗口 DPI）。
- **新增 B/I/U 快捷键**（Ctrl+B / Ctrl+I / Ctrl+U）：`RichEditHost::ApplyBold/Italic/Underline` + `ToggleCharacterFormat(mask, effect)`（读 EM_GETCHARFORMAT 再翻转，真 toggle），`note_window` WM_KEYDOWN 拦截。属于增强点 #17。
- **新增 中英文混合字数统计**：`RichEditHost::CharacterCount()/WordCount()`（CJK 每个字形算 1 词 + 拉丁按空白分词）。属于增强点 #5（计数逻辑部分先落地，页脚 UI 待视觉确认）。
- **新文档**：`docs/enhancements-100-ideas.md` —— 100 条 P0/P1/P2 增强点（用 web-design taste 词汇转译到原生 Win32/Direct2D 便签），含 P0 cull 清单。

### 新学习（Msftedit / D2D 宿主）
- **Windowless RichEdit (ITextHost2) 的客户区、`prcView`、插入符坐标必须统一为 DIP**（因为 D2D 渲染目标/背景/插入符都在 DIP）。把客户区存成像素是漂移类 bug 的温床。
- **`TxGetExtent` 的 HIMETRIC 换算基是 96**（DIP 就 96/inch），不是窗口 DPI。
- **用工具 patch 含 `\\r`/`\\n` 的单字符宽字符字面量会把转义变成真实 CR**（JSON 解码）→ 多字符字面量编译错。用 Python 脚本重写更稳。
- **回归测试法**：在**非 96 DPI** 渲染目标（如 120 DPI）画文字，断言「非透明像素不逃出 DIP 换算后的像素框」。92 基线是 96 DPI 单向，抓不到 DPI 错配。

### 测试基线（当前）
- `ctest` 3/3 全绿（~2.7s）；RichEdit 套件新增：CaretDIP 一致性、B/I/U 翻转、CJK 字数。

### 下一步（P0 增强点，多数需产品/视觉确认）
1. 记事本总览/检索面板（#53，补足当前无总览的缺口）。
2. 贴边折叠 tab 显示首行「peek」标签（#40）。
3. 贴边 tab 不遮挡任务栏（#49，工作区感知）。
4. 快速捕捉不抢占焦点 / 完全钳制到屏内（#70 / #78）。
5. 纯色主题 palette 体系（#21）+ 统一圆角尺度（#24）+ 首运行空态（#38）。
6. 字数统计页脚 UI 落地（#5 的展示层）。
