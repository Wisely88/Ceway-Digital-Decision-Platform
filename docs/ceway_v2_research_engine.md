# CEWAY-FWD-V2 Research Engine

状态：开发分支 Phase 1–2 已完成，Phase 3 冻结持久化底座开发中  
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

当前提供：

- Jaccard similarity；
- symmetric-difference distance。

用于避免有限预算内的多注组合高度重复、有效覆盖不足。

### Bootstrap

`bootstrap_mean_ci(...)`

用于计算 CEWAY 相对结构匹配随机基线的 uplift 95% Bootstrap CI。

### 冻结 manifest

`build_freeze_manifest(...)`

冻结记录至少包含：

- game；
- target_issue；
- history_cutoff_issue；
- algorithm_version；
- parameters；
- 完整展开 tickets；
- budget；
- seed；
- SHA-256。

任何号码或参数变化都必须产生不同 SHA-256。

## Phase 2：V2 Rolling Backtest（已完成）

实现位置：`backend/backtest.py`

现有 v1.12.4 的滚动回测入口已在开发分支升级为 V2 验证链，同时保留原 API 形态。

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

## Phase 3：冻结持久化与完整性（底座已加入）

实现位置：`backend/freeze_v2.py`

已加入：

- `attach_plan_v2_metadata(...)`：给正式方案生成 freeze manifest、SHA、cutoff、碰撞审计与多样性指标；
- `verify_freeze_manifest(...)`：验证 manifest 自身 SHA；
- `verify_plan_freeze(...)`：同时验证当前票面是否仍与冻结票面一致；
- `ensure_plan_v2_metadata(...)`：已有合法冻结则保留，已有非法冻结则拒绝重新覆盖，避免把篡改后的方案“重新洗白”。

现有记录结构把完整 `plan` 存入 SQLite `plan_json`；前端 IndexedDB、Supabase `ceway_sync_state.payload` 和 JSON 备份也都保存完整 record 对象。因此 V2 元数据可以嵌入 plan 后沿现有归档/云同步链传播，无需第一阶段修改 Supabase 表结构。

下一步是把 `ensure_plan_v2_metadata(...)` 接到正式方案保存入口，并在开奖复盘结果中展示 `freeze_integrity`。

## CI / 验证

开发分支新增：`.github/workflows/v2-research-tests.yml`

PR 修改 backend 时会在 GitHub Actions 使用 Python 3.12 自动执行全部后端 unittest。

第一轮 V2 CI 已通过现有生产测试与 V2 原语测试；第二轮进一步加入 DLT / SSQ V2 滚动回测集成测试后也通过。冻结完整性测试随后加入 CI。

## 与 v1.12.4 的关系

现有生产模块仍然是：

- `backend/engine.py`：Statistics Engine；
- `backend/scorer.py`：Score Engine；
- `backend/generator.py`：Combination Engine；
- `backend/capital.py`：Capital Engine；
- `backend/backtest.py`：滚动历史回测；
- `backend/review.py`：开奖复盘。

V2 在开发分支逐层接管验证能力，但当前不改变线上 `main`、GitHub Pages、Supabase 表结构和开奖自动更新链。

## 后续门禁

在 V2 替换正式推荐链之前，还需要：

1. 冻结 metadata 接入方案保存与复盘完整性验证；
2. 用真实完整 DLT / SSQ 历史跑多窗口 × 多 seed 回测；
3. 加入 worst-window 与参数敏感性；
4. 建立 Promote / Hold / Reject 参数晋升规则；
5. 通过后端、前端与移动端验收后再考虑合并到 `main`。

## 生产发布原则

- `main` 继续作为当前正式使用版；
- GitHub Pages `gh-pages` 继续提供线上界面；
- Supabase 云同步结构当前不变；
- 自动开奖数据更新链不变；
- V2 开发分支未通过测试和回测门禁之前，不替换线上推荐器；
- 不以单期命中结果作为参数升级依据。

## 免责声明

CEWAY-FWD-V2 是统计研究与决策审计框架，不证明随机彩票存在可预测规律，也不承诺提高中奖概率或投资回报。