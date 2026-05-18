# CHECKLISTS

## 提交前

```bash
git status --short
git diff --stat
git diff --cached --stat
```

确认：

```text
没有 git add .
没有 .env/token
没有 handoff/ backup
没有临时 CSV/debug/smoke
没有 data/raw 意外写入
```

## 数据任务

```text
字段 schema
coverage
missing list
复权口径
token 安全
验证报告
```

## 策略研究

```text
offline first
T+1 next open
分年
成本
回撤
换手
stop condition
```

## 文档任务

```text
README 总览
HANDOFF 当前状态
TASK 唯一任务
EXECUTION 执行记录
FILE_INVENTORY 文件地图
```
