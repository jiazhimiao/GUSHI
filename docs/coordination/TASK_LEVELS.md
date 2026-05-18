# TASK_LEVELS — 任务等级

| 等级 | 说明 | 示例 | 要求 |
|---|---|---|---|
| L0 | 只读查询 | 读取状态、解释报告 | 不改文件 |
| L1 | 低风险小改 | 文档小修、脚本 typo | 自查，输出 diff |
| L2 | 中高风险研究/数据/文档体系 | 新 evaluator、数据资产、重要文档重构 | 计划 + QA review |
| L3 | 实盘/安全/破坏性 | broker、真实下单、删除 raw、token | 用户确认 + QA + Safety |

当前 B1 Industry Rotation 属于 L2。

L2/L3 任务完成后必须停止，等待用户确认。
