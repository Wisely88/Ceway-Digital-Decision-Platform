# 策维（Ceway）大乐透功能 Codex 改造包

目标：把“大乐透选号 + 历史组合碰撞分析 + 随机/复式/胆拖/预算套餐 + 冻结复盘”作为独立模块接入现有策维系统。

## 先读
1. `CODEX_PROMPT.txt`：直接复制给 Codex 的主指令。
2. `CODEX_TASK.md`：实施范围、顺序、DoD。
3. `docs/PRODUCT_SPEC.md`：产品逻辑与页面。
4. `docs/ALGORITHM_SPEC.md`：核心公式与组合级历史碰撞统计。
5. `docs/API_CONTRACT.md`：建议 API。
6. `DB_SCHEMA.sql`：PostgreSQL 参考表结构（需用现有 Alembic 适配）。
7. `config/dlt_game_rules.json`：玩法约束。
8. `config/dlt_model.default.json`：模型默认配置。
9. `reference/dlt_engine_reference.py`：可直接搬运/改造成 domain/service 的纯 Python 参考实现。
10. `tests/test_dlt_engine_reference.py`：核心算法单测。
11. `tests/ACCEPTANCE_TESTS.md`：端到端验收。

## 重要约束
- **不要重构现有策维技术栈**。Codex 必须先检测真实仓库；本包中的 `apps/api`、`apps/web`、`packages/*` 只是与既有项目规范兼容的建议落点。
- 若现有前端是 Next.js，则沿用 Next.js；若是 Vite/React，则沿用 Vite/React。
- 后端优先复用现有 FastAPI / SQLAlchemy / Alembic / PostgreSQL 设施。
- 新模块不得影响股票系统现有路由、任务、数据库对象与测试。
- 彩票模块是统计实验与选号辅助工具，不承诺提高中奖概率，不提供自动购彩/代购功能。
- 所有模型运行必须有 `history_cutoff_issue`，禁止使用目标期或未来数据，防止前视偏差。

## 建议命名空间
- URL：`/api/v1/lottery/dlt/*`
- DB：`lottery_*` / `dlt_*`
- 前端路由：`/lottery/dlt`
- Python 包：`packages/lottery_dlt` 或按现有仓库 domain/service 规范适配。
