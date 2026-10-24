---
name: mcd-workout-meal
description: >-
  用户刚完成健身/有今日训练计划，想按消耗与目标（减脂/维持/增肌）从麦当劳选套餐时使用。
  先本地估算并确认训练消耗，再调麦当劳 MCP 查营养与可选餐品，迭代约束直到用户选定。
  Use when the user finished a workout or has a training plan and wants McDonald's
  meal recommendations aligned to estimated burn and goal (cut/maintain/bulk).
---

# 麦当劳 · 练后点餐（Workout → Meal）工作流

面向 Agent 执行的**工作流**，不是功能清单。前提：麦当劳 MCP（`https://mcp.mcd.cn`）已配置且 Token 可用；**不依赖任何健身类外部 API**——训练消耗仅来自本包 `references/` + `scripts/calc_burn.py`。

输出仅供参考，不构成医疗/营养建议；餐品热量、价格、供应以 MCP 实时结果为准。

---

## 何时启用

- 用户说「刚跑完」「练完想吃麦当劳」「按今天训练量推荐套餐」等。
- 用户给出健身计划（动作 + 时长/组数），希望对齐减脂/维持/增肌目标选餐。

---

## 工作流（严格顺序）

### 步骤 1 — 收集训练信息

引导用户说出「刚刚完成的健身项目」或「今日健身计划」：

| 字段 | 必需 | 说明 |
|------|------|------|
| 动作 | 是 | 中/英文名或俗称（脚本会模糊匹配 aliases） |
| 时长或组数 | 是 | `minutes` / `sets`（组数类用 JSON 的 `per_set_min` 估时） |
| 强度 | 否 | `low` / `moderate` / `high`（默认 moderate） |
| 体重 kg | 否 | 默认 70；有则用于公式 |
| 目标 | 否 | 减脂 / 维持 / 增肌；**默认维持** |
| 额外约束 | 否 | 预算、忌口、不要甜品等（可在步骤 5 再补） |

用自然语言追问补齐缺失字段；不要跳过确认直接查餐。

### 步骤 2 — 本地匹配与消耗估算 → **待用户确认**

1. 读取 `references/exercises.json`（动作 MET 表）与可选 `references/targets.json`（目标启发式）。
2. 调用计算脚本（路径相对本 Skill 包根目录）：

```bash
python3 scripts/calc_burn.py --exercises-json references/exercises.json --weight <kg> \
  '[{"name":"<动作>","minutes":<n>},{"name":"<动作>","sets":<n>,"intensity":"high"}]'
```

也可把会话 JSON 从 stdin 传入。脚本**仅标准库**，公式：

`kcal = MET * body_weight_kg * duration_hours`

3. 向用户展示：
   - 每条匹配：`name_zh` / `matched_id` / 有效 MET / 时长说明 / kcal
   - `total_kcal`
   - `unmatched`（若有）：请用户改名或补充，重新跑脚本
4. **明确等待用户确认**（例如「消耗估算是否 OK？确认后我再查麦当劳套餐」）。  
   **未确认不得进入步骤 3。**

### 步骤 3 — 调用麦当劳 MCP 查营养与可选餐

用户确认消耗后：

1. **至少**调用 `list-nutrition-foods`（无入参）获取常见餐品能量(kcal)、蛋白等（响应可能为紧凑 TOON 格式，按字段解析）。
2. 若用户需要「当前门店可售 / 套餐组成 / 价格」等点餐约束，再按需调用（官方 kebab-case）：
   - `query-nearby-stores` / `delivery-query-stores`（需要门店时）
   - `query-meals`（当前可售列表）
   - `query-meal-detail`（套餐组成、可替换项）
   - `calculate-price`（预算对齐）
3. 训练消耗**不是** MCP 提供的；不要假装来自麦当劳接口。

### 步骤 4 — 按目标给出 3–5 套推荐

读取 `references/targets.json`，默认目标 `maintain`：

```
meal_kcal_budget = round(confirmed_burn_kcal * burn_ratio + base_meal_window_kcal)
```

| 目标 | burn_ratio | base_meal_window_kcal | 蛋白倾向 |
|------|------------|----------------------|----------|
| 减脂 cut | 0.55 | 280 | ≥25g，偏低热量优先 |
| 维持 maintain | 0.75 | 350 | ≥20g |
| 增肌 bulk | 0.95 | 450 | ≥35g 优先 |

推荐 **3–5 套**，每套包含：

- 餐品/套餐组合名称与大致组成
- 热量 kcal、蛋白质 g（及其他可得营养）
- 相对 `meal_kcal_budget` 的对齐说明（建议落在 ±15% 内；超出须标明偏差）
- 若有价格/预算，简要对齐说明

规则可改：用户或宿主可覆盖 `targets.json` 参数；改后在回复中说明所用规则。

### 步骤 5 — 询问心仪项；无则收集约束并循环

问：「这一系列里有没有心仪的？」

- **有** → 进入步骤 6（确认选定，默认只读）。
- **无** → 收集新约束后回到筛选（可再次 `list-nutrition-foods` / `query-meals` 等），例如：
  - 更低热量 / 更高蛋白
  - 不要某品类（炸鸡、甜品、含乳等）
  - 预算金额上限
  - 忌口/过敏
  - 只要早餐或只要小食

循环直到用户选出，或用户明确放弃。

### 步骤 6 — 默认只读；下单需明确授权

- **默认**：只输出推荐与对比，**不**调用 `create-order`。
- 仅当用户**明确要求下单**（如「就这个，帮我下单」）时，才说明并使用订单相关工具（`calculate-price` → `create-order` 等），并再次确认门店、就餐方式、商品编码。
- 不要主动推销下单。

---

## 本地资源路径

| 路径 | 用途 |
|------|------|
| `references/exercises.json` | 动作 id / 中英文名 / aliases / MET / 可选 per_set_min |
| `references/targets.json` | 减脂/维持/增肌本餐预算启发式 |
| `scripts/calc_burn.py` | CLI：读 JSON + 会话 → 消耗与匹配明细 JSON |

Skill 副本路径（WorkBuddy 装包常用）：`skills/mcd-workout-meal/SKILL.md`（内容与根 `SKILL.md` 一致）。

---

## Agent 执行要点

1. 先确认消耗，再调 MCP。  
2. MCP 工具名使用官方 **kebab-case**（如 `list-nutrition-foods`）。  
3. 匹配失败进 `unmatched` → 问用户，不要静默丢掉。  
4. 中文为主回复；数字带单位（kcal、g、kg、分钟）。  
5. 每次推荐系列后停下来问用户是否心仪，再决定是否加约束继续筛。
