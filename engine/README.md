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
- V2 design note：`docs/ceway_v2_research_engine.md`

V2 第一阶段保持现有 API 合同不变，先增加 history cutoff、防未来数据、组合级历史碰撞、理论基线、Conditional Random、组合多样性、Bootstrap 和冻结 manifest / SHA-256。通过测试与 walk-forward 晋升门禁后，再逐步接管正式回测和推荐链。