# Codex Task — 策维大乐透实验室

## 1. 目标
在不影响策维现有股票系统的前提下，新增大乐透统计实验模块。核心差异化能力不是“单号冷热”，而是**每一个完整候选组合与历史所有开奖逐期比较的组合级碰撞统计**。

## 2. 非目标
- 不提供自动购彩、代购、出票、支付接口。
- 不声称历史低碰撞、冷热、遗漏能提高未来开奖概率。
- 不因接入本模块迁移现有前后端技术栈。
- 不用目标期或未来数据参与生成/回测。

## 3. 实施前必须完成
- 读取根目录 `AGENTS.md` / README / Makefile / pyproject / package.json。
- 定位 FastAPI app、SQLAlchemy/Alembic、前端路由、测试框架。
- 搜索是否已有 `lottery`、`dlt`、`大乐透`、`backtest`、`freeze`、`audit` 相关模块，优先复用。
- 记录真实目录映射，替换本文所有 `ADAPT_TO_REPO`。

## 4. 建议模块
> 仅为逻辑边界，路径按仓库适配。

- `domain/lottery/dlt_rules.py`：玩法规则、验证。
- `domain/lottery/dlt_types.py`：Draw/Ticket/Run/CollisionProfile。
- `domain/lottery/dlt_collision.py`：bitmask + N_ab/N_k/M_k/U_k。
- `domain/lottery/dlt_statistics.py`：冷热、遗漏、结构趋势。
- `domain/lottery/dlt_generator.py`：模型、随机、套餐。
- `domain/lottery/dlt_betting.py`：复式/胆拖注数、金额。
- `services/lottery/dlt_runs.py`：运行、冻结、复盘编排。
- `apps/api/.../dlt.py`：HTTP API。
- `apps/web/.../lottery/dlt/*`：UI。

## 5. 功能优先级
### P0
- 历史开奖存储与截止期查询
- 碰撞引擎
- 模型/随机/套餐生成器
- 投注校验与金额
- 冻结版本化
- 开奖复盘
- 单元测试

### P1
- Web UI
- 碰撞矩阵、趋势表、A/B/C 对照
- CSV 导入与导出

### P2
- 定时同步官方开奖（如现有系统已有调度器再接；MVP 可人工导入）
- 大批量碰撞缓存/并行优化

## 6. Definition of Done
- `N_ab`、`N_k`、`M_k`、`U_k` 数学结果通过固定夹具测试。
- 复式/胆拖/金额计算通过边界测试。
- 冻结记录不可被 update；只能创建新 version。
- 同一历史数据 + 同一参数 + 同一 seed 的测试运行可复现。
- production random 不依赖固定 seed。
- `history_cutoff_issue` 之后的数据不会进入模型。
- 新增路由与页面不会破坏现有股票系统。
- 全仓现有测试通过。
