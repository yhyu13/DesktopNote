# 全局热键快速捕捉（Quick-Capture）设计

结论：给 DesktopNote 增加两个全局热键——从任意窗口一键新建并聚焦便签（快速捕捉），一键显示/隐藏全部便签。当前程序没有任何应用级/全局键盘快捷路径：托盘菜单里的 "Ctrl+N / Ctrl+T" 只是菜单文字（`application.cpp:355`、`application.cpp:390`），仓库里既无 `ACCELERATORS` 资源，也无 `RegisterHotKey` / `WM_HOTKEY` / `HACCEL` / `LoadAccelerators`（全仓库 grep 0 命中；RichEdit 内建的 Ctrl+C/V/X/Z 属编辑快捷键，不在本设计范围）。这是便签类应用最高频的日常缺口。

## 是什么 / 不是什么

- 是：系统级全局热键（`RegisterHotKey`），程序不在前台也生效；一键新建并聚焦便签；一键显示/隐藏全部便签。
- 不是：热键自定义 UI（本期用固定默认值）；便签内部的编辑快捷键（那是 RichEdit 自身的职责）；跨便签搜索（下一期）。

## 方案

### 默认热键契约

| 动作 | 组合键 | 备注 |
|---|---|---|
| 新建便签（快速捕捉） | `Ctrl+Alt+N` | 与托盘「新建便签」走同一 `CreateNewNote` 路径 |
| 显示/隐藏全部 | `Ctrl+Alt+H` | 与托盘「显示/隐藏全部」走同一 `ToggleAllWindows` |

选型理由：`Win+N` 已被 Windows 通知占用；`Ctrl+Alt+N` 全局无常见冲突。两组都加 `MOD_NOREPEAT` 避免按住重复触发。

### 新模块：`src/hotkey.h` / `src/hotkey.cpp`

放进 `desktopnote_core`（`CMakeLists.txt:13-18`），这样 `DesktopNoteTests` 能链接它做单元测试，不必链接整个窗口应用。`hotkey.cpp` 用到 `user32`（`RegisterHotKey`/`UnregisterHotKey`），故在 `CMakeLists.txt:23` 的 `target_link_libraries(desktopnote_core …)` 里补上 `user32`，与现有显式链接约定一致。对外接口：

- `enum class GlobalHotkey : int { NewNote = 0x01, ToggleAll = 0x02 }` — `WM_HOTKEY` 的 `wParam` 标识。
- `struct HotkeyBinding { GlobalHotkey action; UINT modifiers; UINT virtual_key; }`
- `std::vector<HotkeyBinding> DefaultHotkeyBindings()` — 上面的默认契约，纯函数，可确定性单测。
- `bool RegisterGlobalHotkey(HWND, int, UINT, UINT)` / `bool UnregisterGlobalHotkey(HWND, int)` — 薄封装 `RegisterHotKey` / `UnregisterHotKey`，`HWND` 原样透传（传 `nullptr` 表示绑定到当前线程，合法）。

### 接线（`Application`）

- 注册：在 `Run()` 进入消息循环前调用 `RegisterHotkeys()`（`application.cpp:136` 之前），此时 `controller_window_`（117）、`windows_`（124）、`state_ready_=true`（126）都已就绪，`CreateNewNote` 可用。用 `controller_window_` 作为热键窗口，`WM_HOTKEY` 会投递到 `ControllerProcedure`。
- 分发：在 `HandleControllerMessage` 的 `switch (message)`（`application.cpp:566`）里加 `case WM_HOTKEY`，按 `wParam` 分发到 `CreateNewNote(active_window_)` 或 `ToggleAllWindows()`。
- 注销：`UnregisterHotkeys()` 必须做成 `controller_window_` 空安全，且在 `Exit()`（`application.cpp:278-287`）与析构（`application.cpp:81-90`）里都在 `DestroyWindow` 之前调用——显式释放全局键绑定，避免残留（`RegisterHotKey` 绑定虽会随线程/进程终止自动释放，显式注销仍是正确清理）。

### 测试

在 `tests/test_main.cpp` 增加 `TestGlobalHotkeys`：

1. `DefaultHotkeyBindings` 契约完整性（确定性，无 OS 依赖）：恰 2 条绑定、`action` 互异、组合键与 `MOD_NOREPEAT` 符合契约。这是钉死用户可感知契约的规格测试（期望值来自本设计文档，独立于实现）。
2. `RegisterGlobalHotkey` 生命周期（OS 依赖，跳过守卫）：传 `nullptr` 句柄，用冷门组合 `Ctrl+Alt+F24` 注册→再注册同组合返回 false（证明真实注册）→注销→再注册返回 true（证明注销释放）。若首次注册失败（无交互桌面/无权限），打印一行说明并直接返回成功。注意 `test_main.cpp` 的 harness（`test_main.cpp:360-388`）只输出 `[PASS]`/`[FAIL]`，跳过场景会以 `[PASS]` 计数、由测试内的说明行标注跳过原因——这是诚实的降级，与 `note_window_test.cpp:374` 的 `FindDesktopHost` 跳过精神一致（结构不同：那是单测试 main 级守卫，这是多测试向量内返回）。

### 文档

- `USER_GUIDE.md` 增加「全局热键」小节。
- `CHANGELOG.md` 记一条。
- 注：托盘菜单 "新建便签 (Ctrl+N)" 的 `Ctrl+N` 是死标签（无加速键），本设计不改它，仅在 JOURNEY 标注为已知遗留，避免范围膨胀。

## 成功标准

- 单元测试 `DesktopNoteTests` 全绿（新增 `TestGlobalHotkeys`）。
- Release 构建无警告；`ctest` 3 套件全绿。
- 运行验证：`debug.log` 显示两条热键注册成功；发送 `Ctrl+Alt+N` 后便签数 +1（`data.json` 或日志可证）。
- 基准：快速捕捉从「0 条应用级键盘路径」变为「1 键直达」；启动注册 2/2 条（日志可证）。

## 风险

- `RegisterHotKey` 在无交互桌面（CI headless）会失败 → 测试跳过守卫兜底；应用侧注册失败仅记日志、不影响运行。
- 热键冲突（用户已占用 `Ctrl+Alt+N`）→ 注册失败记日志，程序照常运行；配置化留待后续。
