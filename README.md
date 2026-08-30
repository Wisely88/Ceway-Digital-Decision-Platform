# 策维（Ceway）数字决策平台 v1.12.4

Digital Decision Platform  
Powered by CBGO Framework

> 当前 `main` 为正式生产基线。研究能力统一位于 `agent/ceway-v2-research-engine`，不在研究门禁通过前替换生产推荐逻辑。

## 当前生产能力

- 大乐透 / 双色球历史数据维护与走势分析；
- 智能推荐、随机生成、套餐模拟与自选；
- 保存方案、开奖复盘与方案永久归档；
- 单用户云同步；
- GitHub Pages 前端发布；
- 自动开奖数据更新。

策维不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。

## Research

统一研究线：`agent/ceway-v2-research-engine`

当前研究候选为 **CEWAY V2.5 Multi-Regime Exposure**：把号码状态拆为独立 Evidence / Scarcity / Neutral-Coverage 轴，以固定 50% / 30% / 20% 曝光预算生成组合，同时保留 cutoff、防未来数据泄漏、组合级历史碰撞、结构匹配随机、Bootstrap CI、Jaccard / pair-reuse / exposure concentration 等审计层。

V2.5 已完成 60 点 × DLT/SSQ、排除最近 200 期、3 个结构匹配随机 seed 的回顾性压力验证：

- DLT：相对 V9 best-hit uplift +0.3667，95% CI [+0.1500, +0.5667]；相对随机 +0.0722，CI [-0.1111, +0.2500]。
- SSQ：相对 V2.4 best-hit uplift +0.3167，95% CI [+0.0833, +0.5500]；相对随机 +0.1556，CI [-0.0222, +0.3389]。
- DLT / SSQ 组合平均 Jaccard 分别降至 0.0512 / 0.0646，均低于对应结构匹配随机对照。

因此当前研究决策为 **HOLD_RETROSPECTIVE**：V2.5 已改善同质化并优于部分既有候选，但尚未证明对结构匹配随机存在稳定样本外优势，`production_enabled=false`，不得据此进入生产。

详细研究说明：`docs/ceway_v2_research_engine.md`  
固化证据：`research/v25/multiregime-retrospective-stress.json`
