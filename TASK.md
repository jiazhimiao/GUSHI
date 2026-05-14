# TASK.md — 下一会话任务

## 标题: 代码提交前审查

### 背景

- Candidate B 升级为 new_candidate_baseline (score_high=0.80, atr_bear=0.89)
- 3 次跨进程可复现性验证通过（全部指标一致）
- Phase 1a/1b/1c + Phase 2-mini 全部完成
- 正式大 GA 暂缓

### 任务

1. 分类未提交文件：确认哪些进入 git、哪些进入 .gitignore
2. 清理不需要的临时文件
3. 准备 git commit 的文件清单
4. 可选：更新 .gitignore

### 禁止事项

- 不跑正式 GA
- 不继续 Phase 2/Phase 3
- 不改策略逻辑、撮合、风控、手续费、滑点
- 不打开 pullback/rank_buffer
- 不重建数据
- 不为了 2023 年单独加规则

### 历史

- 2026-05-13: baseline control 对齐 + smoke x2
- 2026-05-13: pilot (pop=12, gen=3) 通过
- 2026-05-13/14: Phase 1a/1b/1c 单参数扫描
- 2026-05-14: Phase 2-mini 三维网格
- 2026-05-14: Candidate B 验证 + 2023 诊断
- 2026-05-14: Candidate B 升级为 new_candidate_baseline
- 2026-05-14: Candidate B 3次跨进程可复现验证通过
