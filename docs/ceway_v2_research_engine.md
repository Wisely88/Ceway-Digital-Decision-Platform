# CEWAY-FWD-V2 Research Engine

状态：Phase 1–3 已完成；Phase 4 真实历史验证已定位组合覆盖缺陷；Phase 4.2 覆盖感知组合器 A/B 中  
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

## Phase 1：Research Primitives（已完成）

实现位置：`backend/research_v2.py`

### 防未来数据闸门

`history_through_issue(history, history_cutoff_issue)`

V2 的研究、特征、评分和回测必须显式声明 `history_cutoff_issue`。目标期之后的数据不得进入特征计算。

### 组合级历史碰撞

`collision_profile(...)` 对完整候选组合 C 与每一期历史开奖 H_t 计算：

`k_t = |C ∩ H_t|`

并形成 `N_0, N_1, ...` 分布。

`combination_collision_audit(...)` 进一步汇总所有“候选完整票 × 历史开奖”的组合-期次对；大乐透与双色球均分别统计主区、后区/蓝球，并记录联合命中分布。

### 超几何理论基线

`theoretical_collision_distribution(...)`

随机组合恰好命中 k 个号码的理论概率：

`P(K=k) = C(m,k) * C(N-m,m-k) / C(N,m)`

据此计算历史期数下的理论期望次数与描述性 Z-score，避免仅凭“历史碰中过多少次”判断稀缺或异常。组合池之间存在依赖，因此聚合 Z-score 只作为尺度描述，不作为预测显著性的正式证明。

### Conditional Random

`structure_matched_random_plan(...)`

V2 不再用完全无约束随机票作为主要对照，而是逐票匹配 CEWAY 票的：

- 分区数量；
- 奇偶数量；
- 和值带；
- 连号组数上限。

胆拖先展开成完整单票，再逐票生成匹配结构的随机对照，因此 CEWAY 与 baseline 的票数和预算保持可比。

### 组合多样性

`diversity_summary(...)`

当前提供 Jaccard similarity 与 symmetric-difference distance，用于避免有限预算内的多注组合高度重复、有效覆盖不足。

### Bootstrap

`bootstrap_mean_ci(...)` 用于计算 CEWAY 相对结构匹配随机基线的 uplift 95% Bootstrap CI。

## Phase 2：V2 Rolling Backtest（已完成）

实现位置：`backend/backtest.py`

每个历史预测点现在执行：

1. 声明 `history_cutoff_issue`；
2. 仅取 cutoff 及以前历史；
3. 运行现有 Statistics → Score → Combination Engine；
4. 将 CEWAY 方案展开为完整票；
5. 生成多个 seed 的逐票结构匹配 Conditional Random；
6. 记录 CEWAY 组合级历史碰撞审计；
7. 为当时方案生成 freeze SHA-256；
8. 用下一期开奖验证；
9. 汇总 best-hit uplift 与 record-hit uplift；
10. 输出 Bootstrap 95% CI 与 win/loss/tie rate。

当前 `v2_validation.status` 仅允许：

- `positive_candidate`：当前区间 best-hit uplift 的 95% CI 高于 0；
- `inconclusive`：CI 跨过 0；
- `negative`：CI 整体低于 0。

`positive_candidate` 不是自动 Promote，更不等于证明彩票可预测。

## Phase 3：冻结持久化与开奖后完整性验证（已完成）

实现位置：`backend/freeze_v2.py`、`backend/engine.py`、`backend/review.py`

正式保存 DLT / SSQ 方案时，`save_dlt_record(...)` 与 `save_ssq_record(...)` 会在写入 SQLite 之前自动冻结：

- game；
- target_issue；
- history_cutoff_issue；
- algorithm_version；
- parameters；
- 完整展开 tickets；
- budget；
- seed（如有）；
- SHA-256；
- 组合级历史碰撞审计；
- 前后区组合多样性。

冻结信息嵌入 `plan.v2_research`。现有 SQLite `plan_json`、浏览器 IndexedDB、Supabase `ceway_sync_state.payload` 与 JSON 备份都保存完整 record 对象，因此无需第一阶段修改 Supabase 表结构即可自然携带 V2 冻结信息。

开奖复盘时：

- `verify_freeze_manifest(...)` 重算 manifest SHA；
- `verify_plan_freeze(...)` 同时把当前方案展开成完整票，与冻结票面逐票比较；
- 新 V2 记录返回 `freeze_integrity.status = valid / invalid`；
- 历史老记录没有 V2 元数据时返回 `legacy`，不影响原有复盘；
- 已存在但非法的 V2 manifest 不允许通过重新冻结覆盖，避免把开奖后的改票“洗白”。

## Phase 4：真实历史多窗口 × 多 Seed 基准（第一轮完成）

实现位置：

- `scripts/run_v2_benchmark.py`
- `scripts/run_v2_diagnostics.py`
- `.github/workflows/v2-real-history-benchmark.yml`

第一轮真实数据：

- DLT：2909 期，截止 `26091`；
- SSQ：3490 期，截止 `2026093`；
- 每个配置最近 50 个 walk-forward 点；
- 评分历史窗口 50 / 100 / 200；
- 每个预测点 3 个结构匹配随机 seed；
- 20 元预算；
- balanced 策略。

### 第一轮总门禁

当前 v1.12.4 核心评分 + 组合生成逻辑，在三个窗口的 best-of-budget 指标上均显著低于结构匹配随机：

- DLT：`REJECT`，三个窗口 best-hit uplift 均为负，窗口均值约 -0.82；
- SSQ：`REJECT`，三个窗口 best-hit uplift 均为负，窗口均值约 -1.05。

这不是 V2 自身失败，而是 V2 验证层成功识别出当前生产候选算法没有通过随机对照门禁。

### 拆因诊断：主要缺陷是 coverage concentration

为了避免把“号码评分质量”和“组合覆盖质量”混为一谈，第二轮在完全相同历史点上拆开测：

1. 每张 CEWAY 票的平均命中数 vs 与其结构匹配的随机票；
2. 整个预算组合的 best-hit；
3. 多注前区平均 Jaccard。

结果六个配置全部诊断为 `coverage_concentration`：

#### DLT

- 单票平均命中 uplift：
  - window 50：+0.0987，95% CI [-0.1013, +0.3180]
  - window 100：-0.0473，95% CI [-0.2153, +0.1273]
  - window 200：-0.0340，95% CI [-0.1953, +0.1333]
- 三个 CI 全部跨 0：当前评分器没有显示稳定正优势，但也没有证据说明它显著劣于结构匹配随机。
- CEWAY 前区平均 Jaccard 恒定约 0.5873；随机对照约 0.1118–0.1442。
- best-hit uplift 约 -0.75 至 -0.95，95% CI 均完全低于 0。

#### SSQ

- 单票平均命中 uplift：
  - window 50：-0.0267，95% CI [-0.2333, +0.1827]
  - window 100：-0.0227，95% CI [-0.2067, +0.1780]
  - window 200：-0.1000，95% CI [-0.3107, +0.1233]
- 三个 CI 同样全部跨 0。
- CEWAY 红球平均 Jaccard 恒定约 0.6429；随机对照约 0.1582–0.1631。
- best-hit uplift 约 -1.00 至 -1.07，95% CI 均完全低于 0。

因此当前优先级不是调热号/遗漏权重，也不是立刻引入 LSTM/Transformer，而是先修 Combination Engine 的组合集中问题。

## Phase 4.2：Coverage-aware Combination Engine（A/B 中）

实验实现：`backend/generator_v2.py`

旧生成器通过对排序号码做逐位 rotate，再取前 5 / 6 个号码；这种做法使有限预算内的多注高度共享核心号码。V2 实验组合器保持 `scorer.py` 输出完全不变，只改变“高分号码如何组装成多注”。

当前实验策略：

- 在高分候选带中枚举完整前区组合；
- 保留组合评分质量；
- 对与已选票的最大 Jaccard / 重叠数施加惩罚；
- 奖励新号码覆盖和低使用次数；
- DLT 后区不再因号码标签与前区相同而人为排除，因为前后区是独立号码空间；
- SSQ 蓝球在高分候选带中轮换，避免所有注固定同一个蓝球；
- 生产 `backend/generator.py` 暂不替换。

A/B 脚本：`scripts/run_v2_generator_ablation.py`

同一历史点同时比较：

1. v1.12.4 legacy generator；
2. V2 coverage-aware generator；
3. 基于 V2 方案逐票生成的结构匹配随机 baseline。

开发样本仍使用最近 50 个点，只用于验证“组合器修复是否有效”，即使结果为正也不能直接上线；后续必须使用不重叠历史区间做 holdout。

## CI / 验证

开发分支 CI 使用 Python 3.12 自动执行全部后端 unittest。现有测试覆盖：

- 原 v1.12.4 保存、复盘、奖金、数据同步、开奖自动更新逻辑；
- V2 理论碰撞、Conditional Random、多样性、Bootstrap；
- DLT / SSQ V2 rolling backtest 集成；
- 冻结 SHA 稳定性；
- 修改票面后的完整性失败；
- 非法 manifest 拒绝重新冻结；
- API 保存后自动冻结；
- 待开奖与已开奖复盘均验证 freeze integrity；
- coverage-aware generator 的组合多样性必须优于 legacy generator。

## 生产发布原则

- `main` 继续作为当前正式使用版；
- GitHub Pages `gh-pages` 继续提供线上界面；
- Supabase 云同步结构当前不变；
- 自动开奖数据更新链不变；
- V2 开发分支未通过测试、开发 A/B 与独立 holdout 门禁之前，不替换线上推荐器；
- 不以单期命中结果作为参数升级依据；
- 不把开发诊断区间的改进直接当作样本外优势。

## 免责声明

CEWAY-FWD-V2 是统计研究与决策审计框架，不证明随机彩票存在可预测规律，也不承诺提高中奖概率或投资回报。