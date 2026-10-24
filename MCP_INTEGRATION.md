# MCP 集成说明

## 诚实边界

| 能力 | 来源 | 说明 |
|------|------|------|
| 训练动作匹配与消耗估算 | **本地** `references/exercises.json` + `scripts/calc_burn.py` | MET 近似表 + `kcal = MET × kg × hours`；**非**麦当劳 MCP，**不**调用任何健身 API |
| 餐品营养（热量/蛋白等） | 麦当劳 MCP `list-nutrition-foods` | 常见餐品营养列表；可能为紧凑 TOON 格式 |
| 可售菜单 / 套餐详情 / 计价 / 下单 | 麦当劳 MCP 其他 Tools | 仅在有门店与点餐约束、或用户明确下单时使用 |

本 Skill 的业务价值 = **本地练后消耗工作流** + **官方餐品营养/点餐 MCP**，而非「健身 MCP」。

## 前提配置

- MCP Server：`https://mcp.mcd.cn`（Streamable HTTP）
- 请求头：`Authorization: Bearer ${MCD_MCP_TOKEN}`（配置里用环境变量占位，**勿**把真实 Token 写入仓库）
- 客户端已能列出并调用 Tools（WorkBuddy / Cursor / 其他 MCP Client）

示例连接器片段（占位符）：

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

## 本工作流实际用到的 Tools

官方工具名为 **kebab-case**。

### 核心（推荐路径几乎总会用）

1. **`list-nutrition-foods`**
   - 入参：无
   - 时机：用户**确认**本地消耗估算之后
   - 用途：按本餐热量预算与蛋白倾向筛选、组装 3–5 套推荐

### 按需（有点餐/门店/预算约束时）

2. **`query-nearby-stores`** / **`delivery-query-stores`** / **`delivery-query-addresses`**  
   需要落地到某家店或外送时。
3. **`query-meals`**  
   当前门店可售列表（分类、编码、标签）；用于「只要现在能点的」。
4. **`query-meal-detail`**  
   套餐组成与可替换项；细化推荐组合。
5. **`calculate-price`**  
   用户给出预算或比较实付时。

### 默认不用；仅用户明确要求下单时

6. **`create-order`**（及后续 `query-order` / `cancel-order` 等）  
   Skill 默认**只读推荐**。Agent 不得在未获明确下单意图时调用。

## 建议调用顺序

```
[本地] 收集训练 → calc_burn.py → 展示匹配与 total_kcal → 用户确认
    ↓
list-nutrition-foods
    ↓
(可选) 门店类 Tools → query-meals → query-meal-detail → calculate-price
    ↓
给出 3–5 套推荐 → 问是否心仪 → 新约束则回到筛选
    ↓
(仅明确下单) calculate-price → create-order
```

## 业务价值（参赛陈述可用）

- **场景闭环**：程序员/上班族练完或通勤活动后，用自然语言完成「消耗对齐 → 麦当劳怎么吃」。
- **低风险默认**：只读营养与推荐；下单需二次确认，符合 MCP 开放平台安全习惯。
- **可离线估算**：无健身 API Key、无网络依赖即可完成步骤 1–2，适合 Skill 包分发与评审复现。
- **可扩展**：同一工作流可换 `targets.json` 启发式，或扩展 `exercises.json` 条目，无需改 MCP。

## 非目标

- 不做个性化医疗营养处方。
- 不把 MET 估算结果当作官方麦当劳数据。
- 不在仓库中提交真实 Token 或个人账号信息。
