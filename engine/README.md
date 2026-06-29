# Engine

v1.2 Baseline 的引擎代码目前位于 `backend/`：

- Statistics Engine：`backend/engine.py`
- Score Engine：`backend/scorer.py`
- Combination Engine：`backend/generator.py`
- Capital Engine：`backend/capital.py`

后续版本可以在不改变 API 合同的前提下，将这些模块迁移到独立 `engine/` 包。
