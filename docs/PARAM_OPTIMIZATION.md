# 参数优化方案

> 当前状态：已实现网格搜索(grid search)，粒子群(PSO)和遗传算法(GA)作为后续扩展。

---

## 1. 为什么需要参数优化

当前趋势突破策略有 10+ 个可调参数。手动调参效率低、容易过拟合。

优化目标：
- 在样本内找到好参数组合
- 在样本外验证参数稳定性
- 避免参数过拟合（in-sample很好但out-of-sample崩溃）

## 2. 当前已实现

### 2.1 网格搜索 (Grid Search)

```bash
python scripts/param_robustness.py --mode grid --start 2022-01-01 --end 2024-12-31
```

对关键参数组合穷举搜索，找出收益-回撤综合评分最高的组合。

评分函数：`score = total_return - 0.5 * |max_drawdown|`

参数搜索空间：
- breakout_days: [15, 20, 25]
- ma_days: [15, 20, 30]
- top_n: [3, 5, 10]
- max_weight: [0.10, 0.15, 0.20]
- 共 3×3×3×3 = 81 组合

### 2.2 敏感性分析

```bash
python scripts/param_robustness.py --mode sensitivity
```

每次只变一个参数，观察收益变化幅度：
- 变化 < 20% → 低敏感（参数稳定）
- 变化 20-50% → 中敏感
- 变化 > 50% → 高敏感（可能过拟合）

## 3. 后续扩展

### 3.1 粒子群算法 (PSO)

粒子群优化适合连续参数空间，收敛速度快。

```python
# 伪代码
class PSOOptimizer:
    def __init__(self, param_bounds, n_particles=30, n_iterations=50):
        self.bounds = param_bounds  # {param: (min, max)}
        self.n_particles = n_particles
        self.n_iterations = n_iterations
    
    def optimize(self, objective_fn):
        # objective_fn(params) -> score
        particles = [random_params() for _ in range(n_particles)]
        velocities = [zero_velocity() for _ in range(n_particles)]
        global_best = None
        
        for iteration in range(n_iterations):
            for i, p in enumerate(particles):
                score = objective_fn(p)
                update_personal_best(p, score)
                update_global_best(p, score)
            
            for i in range(n_particles):
                velocities[i] = w * velocities[i] \
                    + c1 * r1 * (personal_best[i] - particles[i]) \
                    + c2 * r2 * (global_best - particles[i])
                particles[i] += velocities[i]
                particles[i] = clamp(particles[i], bounds)
        
        return global_best
```

实现要点：
- 整数参数（如top_n）取整后评估
- 每轮迭代对最佳粒子做更精细回测
- 早停：连续N轮无改善则退出

### 3.2 遗传算法 (GA)

遗传算法适合离散+连续混合参数空间，不容易陷入局部最优。

```python
# 伪代码
class GAOptimizer:
    def __init__(self, param_bounds, population_size=50, n_generations=30):
        self.bounds = param_bounds
        self.pop_size = population_size
        self.n_generations = n_generations
        self.mutation_rate = 0.1
        self.crossover_rate = 0.7
    
    def optimize(self, objective_fn):
        population = [random_individual() for _ in range(self.pop_size)]
        
        for gen in range(self.n_generations):
            # Evaluate
            fitness = [objective_fn(ind) for ind in population]
            
            # Selection (tournament)
            parents = tournament_select(population, fitness)
            
            # Crossover + Mutation
            offspring = []
            for p1, p2 in pairs(parents):
                if random() < self.crossover_rate:
                    child = crossover(p1, p2)
                else:
                    child = random.choice([p1, p2])
                
                if random() < self.mutation_rate:
                    child = mutate(child, self.bounds)
                
                offspring.append(child)
            
            # Elitism: keep best from previous generation
            population = [best_from(population)] + offspring[:-1]
        
        return best_from(population)
```

### 3.3 防止过拟合

无论用哪种优化算法，必须做：

1. **时间序列交叉验证**
   - 训练集: 2022-2023
   - 验证集: 2024
   - 测试集: 2025-2026

2. **Walk-forward 分析**
   - 每年重新优化参数
   - 用前一年最优参数跑下一年
   - 看逐年表现是否稳定

3. **参数稳定区检查**
   - 最优参数附近 ±20% 范围内，收益变化应该 < 30%
   - 如果最优参数是孤岛，大概率过拟合

4. **市场分段测试**
   - 牛市(2024.09-)、熊市(2022)、震荡(2023)分段看
   - 如果在某段特别好、另一段特别差 → 过拟合

## 4. 建议实施优先级

| 优先级 | 任务 | 理由 |
|--------|------|------|
| 1 | 网格搜索（已完成） | 最直观，覆盖所有组合 |
| 2 | Walk-forward 验证 | 防止过拟合的核心方法 |
| 3 | PSO 粒子群 | 参数多(10+)时比网格快很多 |
| 4 | GA 遗传算法 | 混合参数空间的最佳选择 |
