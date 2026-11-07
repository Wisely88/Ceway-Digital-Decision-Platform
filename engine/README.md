# Engine

当前正式版引擎代码位于 `backend/`：

- Statistics Engine：`backend/engine.py`
- Score Engine：`backend/scorer.py`
- Combination Engine：`backend/generator.py`
- Capital Engine：`backend/capital.py`
- Backtest Engine：`backend/backtest.py`
- Review Engine：`backend/review.py`

CEWAY-FWD-V2 开发分支新增：

- Research / Validation primitives：`backend/research_v2.py`
- Freeze / Integrity layer：`backend/freeze_v2.py`
- Experimental coverage-aware Combination Engine：`backend/generator_v2.py`
- V2 design and validation notes：`docs/ceway_v2_research_engine.md`

V2 保持生产 API 合同和 `main` / `gh-pages` 不变，在开发分支逐步增加 history cutoff、防未来数据、组合级历史碰撞、理论基线、Conditional Random、组合多样性、Bootstrap、冻结 manifest / SHA-256 和开奖后完整性验证。

真实历史第一轮验证显示，当前 v1.12.4 评分器的单票命中表现相对结构匹配随机没有显著差异，但 legacy Combination Engine 的多注组合高度集中，导致 best-of-budget 表现显著落后。`generator_v2.py` 因此只针对覆盖集中问题做独立 A/B，不在验证通过前替换生产组合器。