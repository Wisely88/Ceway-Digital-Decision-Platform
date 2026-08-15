# CEWAY-FWD-V2 Research Engine

状态：开发分支第一阶段  
分支：`agent/ceway-v2-research-engine`  
生产基线：`main` / Ceway v1.12.4

## 目标

V2 不推翻现有 Ceway 数字决策平台。现有 DLT/SSQ 数据维护、推荐、套餐、自选、方案归档、Supabase 单用户云同步、开奖复盘和 GitHub Pages 发布链全部保留。

V2 的目标是在现有 CBGO / Ceway 引擎之上增加一层可审计的研究与验证框架，用于回答：

1. 当前候选完整组合在历史中的碰撞轨迹如何？
2. 这些碰撞相对纯随机理论基线是否异常？
3. Ceway 相对“满足相同结构约束的随机组合”是否存在稳定 uplift？
4. 这种 uplift 在 walk-forward、多窗口、多 seed 和 Bootstrap 置信区间下是否仍然成立？
5. 每次正式冻结是否能够证明当时只使用了 cutoff 之前的数据，并且开奖后无法原地篡改？

## 第一阶段已加入

实现位置：`backend/research_v2.py`

### 1. 防未来数据闸门

`history_through_issue(history, history_cutoff_issue)`

V2 的研究、特征、评分和回测必须显式声明 `history_cutoff_issue`。目标期之后的数据不得进入特征计算。

### 2. 组合级历史碰撞

`collision_profile(...)`

对完整候选组合 C 与每一期历史开奖 H_t 计算：

`k_t = |C ∩ H_t|`

并形成 `N_0, N_1, ...` 分布。

`joint_collision_profile(...)` 同时记录主区与后区/蓝球命中，例如大乐透 `(front_hits, back_hits)`。

### 3. 超几何理论基线

`theoretical_collision_distribution(...)`

随机组合恰好命中 k 个号码的理论概率：

`P(K=k) = C(m,k) * C(N-m,m-k) / C(N,m)`

据此可计算历史期数下的理论期望次数与 Z-score，避免仅凭“历史碰中过多少次”判断稀缺或异常。

### 4. Conditional Random

`conditional_random_tickets(...)`

随机基线必须与 Ceway 使用相同的结构条件，例如：

- 三区比
- 奇偶比
- 和值区间
- 连号组数上限

这样比较的是算法本身，而不是“有约束选号 vs 完全随机选号”的不公平差异。

### 5. 组合多样性

`diversity_summary(...)`

当前提供：

- Jaccard similarity
- symmetric-difference distance

用于避免有限预算内的多注组合高度重复、有效覆盖不足。

### 6. Bootstrap

`bootstrap_mean_ci(...)`

后续 walk-forward uplift 将至少报告：

- mean uplift
- 95% bootstrap CI
- win rate
- worst window
- multi-seed stability

只有稳定通过晋升门槛的参数才允许进入生产推荐链。

### 7. 冻结 manifest

`build_freeze_manifest(...)`

正式冻结记录至少包含：

- game
- target_issue
- history_cutoff_issue
- algorithm_version
- parameters
- tickets
- budget
- seed
- SHA-256

冻结后不得原地修改。任何号码或参数变化都必须产生新的 manifest / SHA-256，并保留旧版本用于开奖后复盘。

## 与 v1.12.4 的关系

现有生产模块仍然是：

- `backend/engine.py`：Statistics Engine
- `backend/scorer.py`：Score Engine
- `backend/generator.py`：Combination Engine
- `backend/capital.py`：Capital Engine
- `backend/backtest.py`：滚动历史回测
- `backend/review.py`：开奖复盘

V2 第一阶段不改变这些模块的 API 合同。

下一阶段将把 `backend/backtest.py` 的无条件随机对照升级为 Conditional Random，并增加：

1. history cutoff 审计字段；
2. 每个预测点的组合碰撞特征；
3. CEWAY vs conditional-random uplift；
4. Bootstrap 95% CI；
5. 多 seed / 多窗口稳定性；
6. Promote / Hold / Reject 参数晋升门禁。

## 生产发布原则

- `main` 继续作为当前正式使用版。
- GitHub Pages `gh-pages` 继续提供线上界面。
- Supabase 云同步结构第一阶段不变。
- 自动开奖数据更新链不变。
- V2 开发分支未通过测试和回测门禁之前，不替换线上推荐器。
- 不以单期命中结果作为参数升级依据。

## 免责声明

CEWAY-FWD-V2 是统计研究与决策审计框架，不证明随机彩票存在可预测规律，也不承诺提高中奖概率或投资回报。