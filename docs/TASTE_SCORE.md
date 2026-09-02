# DesktopNote Taste Score

> 一份给「多智能体夜间竞争」用的 Taste 评分标准。**结论先行**：分数分两层——
> **结构分**（correctness gate，0–100，静态可判）和**感知分**（aesthetics，0–100，截图评审）。
> 结构分只判「坏没坏」，感知分才是「好不好看」，后者是**竞争指标**。这套划分不是偷懒，是
> **古德哈特定律**的防御：能被静态符号数刷出来的 taste 分，agents 会去刷它，而不是改进真实品味。

---

## 为什么必须分层：古德哈特定律

Goodhart's Law：当分数成为目标，它就不再是好分数。第一版是一份**纯静态** taste 分，用
`tools/taste_mutation.py` 植入回归做敏感性测试，结果：

```
M4 added-trackmouse    +2.0  ← 往渲染器塞一行死代码 TrackMouseEvent 就 +2 分
M7/M8 WS_POPUP / DPI   不下降 ← count(DipToPixel)>=3 这种计数，删 60 个还剩 7 照样过
```

M4 是决定性证据：**数源码符号判审美必然可刷**。所以凡是靠 `count(...)` 判审美的检查
必须拆掉——taste 里可静态判定的（对不对）归结构分，不可静态判定的（好不好看）归感知分。

---

## 两层架构

### 第 1 层：结构分（correctness gate，0–100，静态、headless 可并行）

只判**事实**，每个检查「要么成立要么不成立」，作用域限定到拥有该属性的文件：

| 维度 | 权重 | 检查（全部是事实，不是计数） |
|---|---|---|
| build | 15 | build+ctest 全绿；挂了 = 0 并封顶总分 |
| platform | 20 | `RenderTargetProperties` 用窗口真实 DPI（不是 96，作用域限定到该块）；renderer 里有 `UpdateLayeredWindow`+`ULW_ALPHA`；命名互斥量；note 窗口 `WS_POPUP`+`RegisterClass` 在 `note_window.cpp`；WorkerW 回退 |
| coherence | 25 | 默认背景非纯黑；单 accent 色相；chrome 无 AI 紫；对比度 ≥AA；源码无破折号 |
| polish | 25 | 状态徽章存在；缩放把手存在；损坏恢复路径存在 |
| type | 15 | 平台字体（非 web 字体）；字号用 DIP；行距/边距用 DIP |

`python3 tools/taste_score.py`（静态）/ `--build`（加硬闸）/ `--json`。
**结果标签是 `STRUCTURE SCORE`**。当前基线 **100/100**——因为它只问「坏没坏」。
**别把它当竞争指标**：会让 everyone 在 100 打平。

### 第 2 层：感知分（perception referee，0–100，真正的 taste 仲裁）—— 已落地

`tools/taste_referee.py` 对**真实渲染截图**打分，分两层子分：

- **objective（像素推导，防作弊锚点）**：对比度（文字 vs 背景，硬算 WCAG）、背景是否纯黑
  （depth loss）、chrome 是否有紫/靛 AI-glow、文字是否渲染（contrast-to-bg，不是「r<120」）、
  accent 条是否存在。像素事实无法用假 JPEG 刷过。当前基线 **100**（off-black bg、白字、
  橙色 accent、对比度 AAA、无 violet）。
- **aesthetic（1–5 rubric，需人/LLM 真正看图）**：平台一致、颜色统一、状态反馈、几何节奏、
  文字质感 5 项，加**隐藏子集**（agent 不知道的项，防针对性排练）。

```
python3 tools/taste_referee.py --png <screenshot>     # 打分
python3 tools/taste_referee.py --capture <pid>        # 抓活窗口 + 打分
python3 tools/taste_referee.py --rubric-only          # 打印 rubric 模板
```

**已验证敏感性**（对合成缺陷图的判定，`taste_referee.py` 自己也要敏感）：

```
缺陷图                          objective
good (control)                       100
pure-black bg (depth loss)           57
violet ai-glow chrome                68
no text (blank surface)              82
no accent bar                        94
```

每项都低于 control —— 证明感知分能区分好坏，不是「永远 100」。

---

## 竞争一键跑：`tools/taste_runner.py`

把整条管线打成一条命令供 agent lane / cron 调用：

```
python3 tools/taste_runner.py                     # 全流程
python3 tools/taste_runner.py --no-build          # 跳过 build 硬闸
python3 tools/taste_runner.py --png <file>        # 用已有截图
python3 tools/taste_runner.py --json
```

顺序：build 硬闸 → 结构分 → mutation 审计 → 抓截图 → 感知分。verdict = `ACCEPT`（结构分干净，
去比感知分）或 `REJECT`（结构/构建挂）。**夜间最优循环**：agents 提升感知分，绝不回退结构分。

---

## 古德哈特防御三件套

1. **Mutation audit（`tools/taste_mutation.py`）** —— 敏感性测试。植入 8 个回归：
   - `structure` tier（断 DPI、丢原生窗口、纯黑、web 字体）**必须**让结构分下降；没抓到 =
     该检查可刷。已验证全抓到。
   - `perception` tier（圆角乱、死代码、色卡塌缩）**应当**对结构分无影响——因为它们归感知层；
     若反而下降，说明结构分在越权判审美。
   - 硬闸：`python3 tools/taste_mutation.py --fail-on-no-change`（可刷则非零退出）。
2. **Structure = gate，perception = metric。** 让 agents 追感知分，结构分当淘汰线。
3. **Anti-overfit 规则**：任何维度不得回退；结构分单次跳变 > +8 触发人工/感知复查；
   感知评审有**隐藏子集**，裁判握有未公开项。

---

## 相关命令

```bash
python3 tools/taste_score.py           # 结构分（correctness gate）
python3 tools/taste_score.py --build   # 加 build+ctest 硬闸
python3 tools/taste_mutation.py        # 古德哈特敏感性测试
python3 tools/taste_referee.py --capture <pid>   # 感知分（需桌面会话）
python3 tools/taste_runner.py          # 整条管线一键
```

注意：本机 bash 的 `python` 是 2.7，一律用 `python3`（3.13）。

---

## 诚实声明

- **结构分 100/100 表示「没坏」，不是「好看」。** 竞争指标必须是感知分。
- **感知分需要桌面会话**（截图抓 `DesktopNote.NoteWindow.v2` 活窗口）；headless CI 无交互
  桌面，`NoteWindowTests` 会跳过。所以夜间竞争要么在桌面机跑感知分，要么 headless 只跑结构分
  并标注「未做感知评审」。
- 感知分的 **aesthetic rubric 需人/LLM 真正看图**；objective 子分是像素推导、可自动、
  是防作弊锚点。塞 canned 分数进去毫无价值。
