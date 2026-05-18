# FAILURE_RECOVERY

## Push 失败

如果网络导致 push 失败：

```bash
git status --short
git log --oneline origin/main..main
mkdir -p handoff/git_backup
git bundle create handoff/git_backup/qts_unpushed_latest.bundle origin/main..main
```

不要 reset，不要重复 commit。

## 实验失败

```text
保留报告
写入 EXECUTION.md
更新 HANDOFF.md 状态
不要继续调参包装失败结果
```

## 数据接口失败

```text
确认是否 token / 网络 / 限流 / schema 改变
只做 verify-only
不要写 raw parquet
```

## 会话上下文不足

读取：

```text
CLAUDE.md
TASK.md
HANDOFF.md
EXECUTION.md
FILE_INVENTORY.md
```
