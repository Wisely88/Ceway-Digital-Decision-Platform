# CEWAY-FWD-V2 Research Engine

状态：统一 Research 线；V2.5 Multi-Regime Exposure 已完成回顾性压力验证，当前结论 HOLD_RETROSPECTIVE。  
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

## 已确立的研究基础

- 所有研究特征与回测显式使用 `history_cutoff_issue`，禁止未来数据泄漏。
- 组合级历史碰撞统计对每个完整候选票与历史开奖计算交集分布，并分别统计主区、后区/蓝球与联合命中。
- 使用超几何理论碰撞基线、结构匹配 Conditional Random、Jaccard/对称差多样性与 Bootstrap 95% CI。
- 冻结记录包含算法版本、参数、完整 tickets、seed、cutoff、SHA-256、组合碰撞审计与多样性；开奖后验证 manifest 和票面完整性。
- 生产 `main`、Supabase 与 GitHub Pages 在研究门禁通过前保持隔离。

## 既有诊断

第一轮真实历史验证确认，旧 v1.12.4 组合器的主要问题不是单票评分稳定显著劣势，而是预算组合高度集中：DLT 前区平均 Jaccard 曾约 0.5873，SSQ 红球约 0.6429，导致 best-hit 相对结构匹配随机显著为负。

V2.1 `score-exposure-balanced-v2.1` 通过全号码池曝光预算、pair reuse 与 overlap 惩罚大幅降低组合集中；V2.3 对无稳定证据的 SSQ 号码排名收缩为中性；V2.4 固定 100 期窗口作为后续候选验证。

## V2.5：Multi-Regime Exposure

### 问题来源

近期复盘显示，V9 的 frequency / recency / momentum / stability 虽名义上是多个特征，实际上高度同源于“近期出现状态”；gap 权重又很弱。组合器虽然已解决票面重复，但候选认知仍存在特征同质化。

因此 V2.5 不再把所有特征压成单一排名，而是预注册三个独立预算角色：

- Evidence：50% 槽位；
- Scarcity：30% 槽位；
- Neutral/Coverage：20% 槽位。

Scarcity 仅表示覆盖状态，不解释为未来中奖概率。

### Evidence 轴

固定权重：

- 100期长期频率百分位：0.25；
- 衰减近期状态：0.15；
- 20期相对100期动量：0.10；
- 多窗口稳定性：0.10。

以上仅在 Evidence 轴内部归一，不再与 Scarcity 混成唯一 total score。

### Scarcity 轴

固定权重：

- 最近3期低频：0.30；
- 最近7期低频：0.20；
- 最近20期低频：0.15；
- 当前 gap 百分位：0.15；
- 长窗正常、短窗沉寂的 divergence：0.20。

Neutral 轴优先覆盖 Evidence 与 Scarcity 均不过度极端的中间状态。

### 组合器

V2.5 以固定 50/30/20 角色槽位生成预算组合，并继续惩罚：

- 单号过度曝光；
- pair reuse；
- 注间 overlap / Jaccard；
- 覆盖集中。

参数在压力验证前固定，未按开奖结果搜索权重。

实现：`backend/multiregime_v25.py`  
测试：`backend/tests/test_multiregime_v25.py`  
压力评估：`scripts/run_v25_multiregime_stress.py`  
CI：`.github/workflows/v25-multiregime-validation.yml`  
证据：`research/v25/multiregime-retrospective-stress.json`

## V2.5 回顾性压力验证

设置：每个游戏 60 个 walk-forward 点；排除最近 200 期；20 元预算；3 个结构匹配随机 seed。由于近期稀缺复盘已经用于提出 V2.5 假设，这一块只算 retrospective stress evidence，不属于可直接 Promote 的 fresh evidence。

### DLT

- V2.5 mean best-hit：2.5667；V2.4：2.3500；V9：2.2000；结构匹配随机：2.4944。
- V2.5 vs V9 best-hit uplift：+0.3667，95% CI [+0.1500, +0.5667]。
- V2.5 vs V2.4：+0.2167，95% CI [-0.0500, +0.4833]。
- V2.5 vs 随机：+0.0722，95% CI [-0.1111, +0.2500]。
- mean-ticket vs 随机：+0.0050，95% CI [-0.0578, +0.0667]。
- record-hit vs 随机：+0.0944，95% CI [-0.0444, +0.2389]。
- 前区平均 Jaccard：0.0512，低于随机 0.0807。
- 实际开奖前区每期平均有 1.20 个号码落在 Scarcity 前25%。

结论：V2.5 相对 V9 的 improvement 明确，组合异质性明显改善；但对结构匹配随机没有统计上稳定优势，故 HOLD_RETROSPECTIVE。

### SSQ

- V2.5 mean best-hit：2.7667；V2.4：2.4500；V9：2.5333；结构匹配随机：2.6111。
- V2.5 vs V2.4 best-hit uplift：+0.3167，95% CI [+0.0833, +0.5500]。
- V2.5 vs V9：+0.2333，95% CI [-0.0167, +0.4833]。
- V2.5 vs 随机：+0.1556，95% CI [-0.0222, +0.3389]。
- mean-ticket vs 随机：+0.0050，95% CI [-0.0533, +0.0622]。
- record-hit vs 随机：+0.0889，95% CI [-0.0333, +0.2167]。
- 红球平均 Jaccard：0.0646，低于随机 0.1009。
- 实际开奖红球每期平均有 1.2167 个号码落在 Scarcity 前25%。

结论：V2.5 相对 V2.4 有明确 improvement，且对随机的点估计转正，但 CI 仍跨 0，因此仍为 HOLD_RETROSPECTIVE。

## 当前研究决策

V2.5 的修改解决了这次复盘指出的“特征同质化 + 覆盖同质化”问题：

- Evidence / Scarcity / Neutral 不再共用一个强制总排名；
- 稀缺池从单一遗漏升级为 3/7/20 + gap + divergence；
- 50/30/20 曝光预算让低 Evidence 但高 Scarcity 的号码有独立进入路径；
- 组合 Jaccard 已低于结构匹配随机，说明不是简单扩大重复选号；
- DLT 显著优于 V9，SSQ 显著优于 V2.4。

但 V2.5 尚未证明优于结构匹配随机：两个游戏 best-hit、mean-ticket、record-hit 的随机对照 CI 都仍跨 0。因此当前唯一合规结论是 `HOLD_RETROSPECTIVE`，不得进入生产，也不得根据本次结果继续微调同一组权重来追求显著性。

## 生产发布原则

- `main` 继续作为正式使用版；
- V2.5 `production_enabled=false`；
- GitHub Pages、Supabase、自动开奖数据更新链保持不变；
- 不以单期命中结果作为参数升级依据；
- 不把回顾性 improvement 当成样本外预测优势；
- 后续任何可用于 Promote 的证据必须保持本版参数不变并来自预先冻结的 prospective shadow 或真正未消费样本。

## 免责声明

CEWAY-FWD-V2 / V2.5 是统计研究与决策审计框架，不证明随机彩票存在可预测规律，也不承诺提高中奖概率或投资回报。
