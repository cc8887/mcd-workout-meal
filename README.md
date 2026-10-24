# 麦当劳 · 练后点餐 Agent Skill（mcd-workout-meal）

麦当劳程序员节创意开发大赛参赛骨架：**根据刚刚完成的健身 / 今日训练计划，本地估算消耗 → 用户确认 → 调用麦当劳 MCP 查营养与套餐 → 按减脂/维持/增肌给出一系列推荐，并迭代约束直到选定。**

- **不依赖任何健身类外部 API**；消耗来自包内 MET 参考表 + 纯标准库 Python 脚本。
- **默认只读推荐**，不自动下单；仅用户明确要求时才涉及订单 Tools。
- 可安装于 WorkBuddy / 支持 MCP + Agent Skill 的客户端。

> 非麦当劳官方产品。输出仅供参考，不构成医疗或营养建议；餐品与价格以 MCP 实时结果为准。详见 `CONTEST_DECLARATION.md`。

## 目录结构

```
mcd-workout-meal-skill/
  README.md
  CONTEST_DECLARATION.md
  MCP_INTEGRATION.md
  SKILL.md                      # 工作流（Agent 主入口）
  references/
    exercises.json              # 动作 → MET（约 60 条）
    targets.json                # 减脂/维持/增肌本餐预算启发式
  scripts/
    calc_burn.py                # 标准库 CLI：会话 → 消耗 JSON
  skills/mcd-workout-meal/
    SKILL.md                    # WorkBuddy 装包路径副本
```

## 目标用户

- 练完或通勤后想吃麦当劳、又想大致对齐今日消耗的上班族 / 程序员。
- 希望 Agent「先算再问再荐」、可加预算与忌口约束的 MCP 玩家。
- 评审 / 复现：无需健身 API Key，有 `MCD_MCP_TOKEN` 即可演示完整链路。

## 安装（WorkBuddy / MCP 连接器）

1. 将本仓库（或本目录）作为 Skill 包加载；确保能读到 `SKILL.md` 或 `skills/mcd-workout-meal/SKILL.md`。
2. 配置麦当劳 MCP（Token 用环境变量，勿写入文件）：

```json
{
  "mcpServers": {
    "mcd": {
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

3. 确认客户端可调用 `list-nutrition-foods` 等官方 kebab-case Tools（说明见 `MCP_INTEGRATION.md`）。
4. 本机有 `python3` 即可运行 `scripts/calc_burn.py`（无 pip 依赖）。

## 使用示例

**用户：** 刚跑步 30 分钟又做了 5 组深蹲，体重 70kg，维持体重，推荐麦当劳怎么吃。

**Agent（按 SKILL 工作流）：**

1. 组装会话并估算：

```bash
python3 scripts/calc_burn.py --weight 70 \
  '[{"name":"跑步","minutes":30},{"name":"深蹲","sets":5}]'
```

2. 展示匹配明细与 `total_kcal`，**请用户确认**。
3. 确认后调用 `list-nutrition-foods`，按 `targets.json` 的 maintain 规则算本餐预算，给出 3–5 套推荐（热量/蛋白与预算对齐说明）。
4. 问是否有心仪项；若无，按新约束（更低热量、更高蛋白、预算、忌口等）继续筛选。
5. 用户未说下单 → 不下单。

## Skill 名称建议

| 语言 | 名称 |
|------|------|
| 中文 | 麦当劳练后点餐 / 练完吃麦当劳 |
| English | McDonald's Post-Workout Meal |
| frontmatter `name` | `mcd-workout-meal` |

## 本地快速自检

```bash
python3 scripts/calc_burn.py --help
python3 scripts/calc_burn.py --weight 70 \
  '[{"name":"HIIT","minutes":20,"intensity":"high"},{"name":"拉伸","minutes":10}]'
```

## 文档索引

- `SKILL.md` — Agent 执行工作流（必读）
- `MCP_INTEGRATION.md` — Tools、顺序、本地 vs MCP 边界
- `CONTEST_DECLARATION.md` — 参赛声明（官方原文）

## License / 声明

参赛作品声明见 `CONTEST_DECLARATION.md`。MET 数据为 Compendium of Physical Activities 等公开资料的**近似整理**，仅供估算演示。
