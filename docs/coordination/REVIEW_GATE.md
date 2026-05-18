# REVIEW_GATE

## QA Gate

检查：

```text
任务范围是否越界
是否改了禁止文件
是否存在未来函数
数据口径是否一致
交易假设是否变化
测试/冒烟是否运行
文档是否更新
```

结论只能是：

```text
APPROVE
REQUEST_CHANGES
REJECT
```

## Safety Gate

必须检查：

```text
token / key / password
.env 是否 gitignored
broker API
真实下单
危险命令
删除 raw 数据
绕过风控
```

## Data Gate

数据任务必须检查：

```text
source
schema
coverage
missing
复权口径
未来函数
是否写 raw
是否可复现
```

## Research Gate

研究任务必须检查：

```text
样本量
分年稳定性
成本后收益
回撤/MAE
换手率
是否依赖单一年份
是否值得进入下一阶段
```
