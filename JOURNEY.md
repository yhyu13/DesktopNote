# JOURNEY.md — DesktopNote 全局热键快速捕捉

> 本项目缘起·经过·结果：用户要求「build and install and run this app, then tell me do we have something better to add」，AI 先完成构建/安装/运行验证并给出评估，随后用户一句「go」拍板，AI 按 software-dev-loop 全流程实现了「全局热键快速捕捉」。结果：两个全局热键（`Ctrl+Alt+N` 新建便签、`Ctrl+Alt+H` 显示/隐藏全部）落地，15/15 单测 + 2 集成套件全绿，端到端验证通过，设计文档经两轮 critic 加固（0 blocking）。

ME = 用户，YOU = AI。日期 2026-08-29 ~ 2026-08-30。

## 风险与待办

| 风险 / 待办 | 所属阶段 |
|---|---|
| 托盘菜单 "新建便签 (Ctrl+N)" / "置顶模式 (Ctrl+T)" 是死标签（无加速键资源），本次未修 | 评估 / 实现 |
| `RegisterHotKey` 在无交互桌面（CI headless）会失败 → 单测用 `SkippedTest` 跳过守卫兜底；应用侧失败仅记日志 | 实现 |
| 热键固定默认值，无自定义 UI；若用户已占用 `Ctrl+Alt+N`/`Ctrl+Alt+H`，注册静默失败 | 规划 |
| 待办：跨便签搜索（全仓库无搜索）、纯文本/Markdown 模式、导出/导入、热键自定义 | 评估 |

## 阶段

### 1. 起步：构建 · 安装 · 运行 · 评估

| ME | YOU |
|---|---|
| build and install and run this app, then tell me do we have something better to add, or can we create some thing even better | 读 README/ARCHITECTURE/CMake，确认工具链（CMake 3.31 + VS2022 Community），`cmake --preset msvc-release` 构建成功，3 套件 `ctest` 全绿，安装出单个 700 KiB `DesktopNote.exe`，运行验证（消息循环进入、托盘图标、`data.json` 落盘）。 |

### 2. 评估：缺口排序

| ME | YOU |
|---|---|
| （等待评估） | 全仓库 grep 发现：无 `RegisterHotKey`/`WM_HOTKEY`/`ACCELERATORS`/`HACCEL`，托盘 "Ctrl+N/Ctrl+T" 是纯文字死标签。给出缺口优先级：①全局热键快速捕捉 ②跨便签搜索 ③开机自启（后发现已存在，纠正自己的误判）④导出/导入 ⑤Markdown/纯文本。并诚实指出「自动启动」其实已实现。 |

### 3. 选型：一句「go」拍板

| ME | YOU |
|---|---|
| go | 把「go」解释为「按我的推荐先做快速捕捉」，不追问、按默认解释执行。 |

### 4. 规划：设计文档 + 第一轮 critic

| ME | YOU |
|---|---|
| （无） | 写 `docs/quick-capture-hotkey.md`（结论先行，逐条 file:line 锚点），派 1 个 critic 子代理核对源码。critic 返回 0 blocking / 8 minor，逐条复查后应用（switch 行号、nullptr 透传、user32 链接、注销顺序等）。 |

### 5. 实现：TDD 红→绿

| ME | YOU |
|---|---|
| （无） | 先写 `hotkey.h` + 桩 `hotkey.cpp`（返回空/返回 false）+ 契约单测 → 红（`bindings.size() == 2` 断言失败）。再实现真 `hotkey.cpp` → 绿。15/15 通过。踩坑：`RegisterHotKey(nullptr,…)` 在无消息队列的控制台线程失败，`PeekMessageW` 强制建队列后从 SKIP 变 PASS。 |

### 6. 接线 + 端到端验证

| ME | YOU |
|---|---|
| （无） | `Application` 接线：`Run()` 进消息循环前注册、`Exit()`+析构 `DestroyWindow` 前注销、`WM_HOTKEY` 分发到 `CreateNewNote`/`ToggleAllWindows`。端到端实测：发 `Ctrl+Alt+N` 便签数 1→2，发 `Ctrl+Alt+H` 可见窗口 2→0→2。 |

### 7. 实现 critic + 收尾

| ME | YOU |
|---|---|
| （无） | 第二轮 critic 子代理审 diff：0 blocking / 7 minor。全部应用（枚举值对齐文档、测试 harness 加 `SkippedTest` 三态跳过、RAII 清理、防御日志、`DefaultHotkeyBindings` 返回 const 引用、契约测试钉死 id 数值）。重构建 15/15（0 skipped），终版二进制再端到端发 `Ctrl+Alt+N` 便签数 2→3。写 `KNOWLEDGE.md`（长期记忆）+ 本文。 |

## 这个项目如何教 vibe coding with AI

### 人的工作（decide / correct / kill）

- 「go」——一个词把方向定死，AI 按推荐执行、不再追问。锚点：阶段 3。
- 强调诚实证据（内存里的用户画像：拒绝「刷绿」的 tracker）。锚点：AI 在 harness 里把「跳过」从「冒充 PASS」改成三态 `[SKIP]`，正是对这一偏好的兑现。阶段 7。

### AI 的工作（instrument / falsify / report honestly）

- 自我纠错：评估阶段发现「自动启动已实现」，立刻收回自己先前那条建议，而不是将错就错。阶段 2。
- 端到端测量，不用「应该能用」：真正发 `Ctrl+Alt+N`/`Ctrl+Alt+H`，数 `data.json` 便签数、数可见窗口，用数字证明。阶段 6/7。
- 红绿分开：先让测试真实红（空桩断言失败），再绿，不把编译错误当红。阶段 5。

### 可复用的规则

1. 一句「go」= 按上一轮推荐执行，别反问。锚点：阶段 3。
2. 评估类任务也要 grep 验证，别凭印象列「缺失功能」——自动启动差点被误判为缺失。锚点：阶段 2。
3. 全局热键在控制台测试线程需要消息队列，`PeekMessageW` 一行即可。锚点：阶段 5。
4. 测试报告要诚实：跳过就是 `[SKIP]`，不能混进 PASS 分母。锚点：阶段 7。
5. critic 子代理的每条 minor 也要复查来源再改，不盲从。锚点：阶段 4/7。

### 一句话总结

用户定方向、AI 定证据——方向一句「go」，证据靠真实构建、真实按键、真实计数。

---

## 会话 2（2026-09-01）——修复光标漂移 + 100 条增强点子脑暴 + P0 落地

ME = 用户，YOU = AI。

| 阶段 | ME | YOU |
|---|---|---|
| 0 起点 | 「cursor drift when docking to side on windows (or cursor in note drift in general)；用 web design taste 技能脑暴 100 条 P0–P2 增强；审 P0、去烂点子；执行 P0」 | 先建基线：`cmake --preset msvc-release` + 构建 + `ctest` 3/3 绿。定位：`note_window.cpp`（DetectScreenEdge/CollapseToEdge）+ `rich_edit_host.cpp`（插入符）+ `note_renderer.cpp`。 |
| 1 诊断 | （等待） | 用 120 DPI 渲染目标做回归测试，实测文字 bbox [51,268]×[59,144]（应是 [40,220]×[40,120]）——证实 RichEdit 客户区被存成设备像素、与 DIP 渲染目标/插入符错配，DPI≠96 时文字被放大、插入符漂移。 |
| 2 修复 | （无） | 全链路统一 DIP：`UpdateEditorBounds` 客户区像素→DIP、`Draw` prcView 用 DIP 的 bounds_、插入符同 DIP 绘制、`TxGetExtent` 基=96。120 DPI 回归测试转绿。 |
| 3 脑暴 | （无） | 写 `docs/enhancements-100-ideas.md`：把 web-design taste 词汇转译到原生 Win32/Direct2D 便签的 7 大类 100 条 P0/P1/P2；剔除 6 条烂/越界点子，留 14 条 P0（cull 在文末）。 |
| 4 执行 P0 | （无） | 落地代码可行且可测的 P0：Ctrl+B/I/U 真 toggle（`ToggleCharacterFormat` 读现状再翻转）+ 中英文字数统计（`CharacterCount/WordCount`，CJK 按字、拉丁按空白）。其余 UI 重 P0（总览/peek/工作区感知/空态/palette）记入 STATUS 下一轮。 |
| 5 收尾 | （无） | `ctest` 3/3 绿；写 KNOWLEDGE.md（长期记忆）、buglog bug-001、cerebrum（学习+决策+勿再犯）、STATUS（✅/🚀）、memory 日志、anatomy 更新到 docs/。git diff：src+tests 5 文件 +275/14。 |

### 主线教训（本会话）
- **先建基线再动代码**：构建/测试全绿后才碰 bug，避免把环境问题当代码问题。
- **用非 96 DPI 的回归测试把 DPI 错配钉死**：96 DPI 单向基线（旧测试）抓不到「像素客户区 vs DIP 渲染目标」的漂移，这是 polish 评分（基线 73.8/100，polish 55）与用户抱怨的共同根因。
- **坐标系一次性统一**：只修 `prcView` 不够（实测仍溢出）；客户区 + prcView + 插入符 + extent 必须同为 DIP。
- **用工具写含 `\r`/`\n` 的宽字符字面量会被 JSON 解码成真实 CR** → 多字符字面量编译错；改用 Python 按字节写。
