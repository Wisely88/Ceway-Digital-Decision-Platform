# 策维 Prediction V9

## 定位

`CEWAY-PRED-V9.0` 是建立在现有 v1.12.4 / CEWAY-FWD-V2 研究层之上的**预测研究层**，默认不替换生产推荐器。

它解决当前评分器“热度 + 遗漏 + 固定结构分”过于粗糙、组合器容易集中、以及历史窗口没有形成统一证据链的问题。

## V9 核心

1. **多窗口频率**：20 / 50 / 100 / 200 期，按实际可用历史自动收缩。
2. **Beta-Binomial shrinkage**：号码频率向理论均匀先验收缩，避免短窗口极端热冷号把排名拉爆。
3. **指数衰减近期信号**：近期表现单独建模，不直接等同于“遗漏越大越该出”。
4. **动量**：短窗口与长窗口后验率差异，用于识别近期变化。
5. **稳定性**：多个窗口之间越一致，证据强度越高。
6. **遗漏只做弱描述变量**：权重仅 4%，避免把随机间隔误当成预测规律。
7. **组合级评分**：和值、分区、奇偶、连号仅作软约束，不做硬过滤。
8. **预算内组合优化**：同时考虑票面质量、号码曝光、号码对复用、票间 Jaccard 和最大重叠。
9. **前后区分离**：DLT 后区、SSQ 蓝球单独优化，避免把前区与后区混成同一个号码空间。
10. **冻结**：输出 `history_cutoff_issue`、算法版本、完整票面和 SHA-256，便于开奖后验证。

## 防未来数据

V9 接受 `history_cutoff_issue`。设置后，只使用不晚于 cutoff 的历史数据，并按数字期号排序，避免 `"100"` 与 `"20"` 这样的字符串排序错误。

正式研究点统一采用：

`features <= history_cutoff_issue < target_issue`

开奖后禁止修改同一冻结对象；需要新版本时创建新的 freeze manifest。

## 输出

每个号码提供：

- `frequency_score`
- `recency_score`
- `momentum_score`
- `stability_score`
- `gap_score`
- `total_score`
- `evidence_strength`
- `rank`

组合输出提供：

- `score`
- `portfolio.front_diversity`
- `portfolio.back_diversity`
- `candidate_band`
- `freeze_manifest.sha256`

## 使用

```bash
cd backend
python ../scripts/run_prediction_v9.py --game dlt --budget 20 --seed ceway-v9
python ../scripts/run_prediction_v9.py --game ssq --budget 20 --seed ceway-v9
```

API 扩展通过 `backend/main_v9.py` 提供：

```bash
cd backend
uvicorn main_v9:app --reload --port 8001
```

新增：

- `GET /prediction/v9/dlt`
- `GET /prediction/v9/ssq`

## 验证原则

V9 不能因为单期命中就升级。进入生产前至少需要：

- 多窗口 walk-forward；
- 与结构匹配 Conditional Random 对照；
- 多 seed；
- Bootstrap 95% CI；
- 非重叠 holdout；
- freeze 完整性验证。

如果单票平均命中没有稳定 uplift，但组合 best-hit 提升，应优先解释为组合覆盖改善，而不是号码预测能力提升。

## 免责声明

V9 是统计研究与组合构造工具，不证明彩票开奖结果可预测，不承诺提高中奖概率或收益。
