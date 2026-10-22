# 策维大乐透实验室

大乐透实验室是现有 DLT 场景中的统计实验模块，不替代原有选号工作台、历史数据和当期复盘。模块以完整 `5+2` 组合为分析单位，所有使用历史数据的运行都必须保存目标期与历史截止期。

## 使用入口

进入大乐透后，点击左侧“大乐透实验室”。页面包含五个页签：

1. 模型选号：按历史碰撞稀缺字典序排序，再以号码趋势、历史结构和多注分散度做次排序。
2. 随机选号：生产运行使用系统安全随机源；实验测试可传入 seed 复现。
3. 预算套餐：按预算组合真实的单式、复式或胆拖结构。“套餐”只是预算模板，不是官方新增玩法。
4. 历史碰撞：输入完整 `5+2` 号码，查看 `N0..N7` 和 `6x3 N_ab`。
5. 冻结复盘：草稿冻结后不可原地修改，只能复制为新版本；目标期开奖后从本地开奖表自动结算。

## 数学口径

候选组合 `C` 与历史开奖 `H_t` 逐期比较：

- `a = 前区交集数`，范围 `0..5`
- `b = 后区交集数`，范围 `0..2`
- `k = a + b`，范围 `0..7`
- `N_ab(C)`：单个候选的前后区命中二维分布
- `N_k(C)`：单个候选的总命中位数分布
- `M_k / M_ab`：整个候选批次的组合期次对数量
- `U_k / U_ab`：至少发生一次相应碰撞的不同候选数

模型默认按 `(N7,N6,N5,N4,N3,N2,N1)` 升序排序。历史碰撞稀缺只描述过去，不代表未来开奖号码更可能出现。

## 投注表达

支持：

- 单式
- 前区复式、后区复式、双区复式
- 前区胆拖、后区胆拖、双区胆拖
- 追加投注
- 1 至 99 倍

复式注数：`C(nf,5) * C(nb,2)`。

胆拖注数：`C(Tf,5-Df) * C(Tb,2-Db)`。前区胆码为 `0..4`，后区胆码为 `0..1`；声明为胆拖的分区必须有胆码，且胆码与拖码总数超过基本选号数量。

金额：`展开注数 * (2 + 追加时1) * 倍数`，并按规则配置校验单票金额上限。

## 数据与冻结

SQLite 新增以下独立表，不修改原有推荐记录：

- `dlt_lab_runs`
- `dlt_lab_tickets`
- `dlt_lab_aggregates`
- `dlt_lab_freezes`
- `dlt_lab_settlements`

全候选碰撞档案保存在 `dlt_lab_aggregates.candidate_profiles_json`，最终 Top K 投注票保存在 `dlt_lab_tickets`。冻结负载包含目标期、数据截止期、算法版本、参数、票、金额、整批碰撞指纹和 SHA-256。

迁移文件：

- 升级：`backend/migrations/001_dlt_lab_up.sql`
- 回滚：`backend/migrations/001_dlt_lab_down.sql`

仓库沿用现有 SQLite 幂等初始化方式；`backend/dlt_lab/storage.py` 是运行时迁移入口，没有引入 SQLAlchemy 或 Alembic。

运行规则和模型默认参数分别位于 `config/dlt_game_rules.json` 与 `config/dlt_model.default.json`。

## API

基础路径：`/api/v1/lottery/dlt`

- `GET /rules`
- `GET /draws`
- `POST /draws/import`
- `GET /statistics/numbers`
- `POST /collisions/analyze`
- `POST /generate/model`
- `POST /generate/random`
- `POST /generate/package`
- `POST /bet/calculate`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/candidates`
- `POST /runs/{run_id}/freeze`
- `POST /runs/{run_id}/clone`
- `POST /runs/{run_id}/settle`
- `GET /compare`

## 验证

```bash
backend/.venv/bin/python -m unittest backend.tests.test_dlt_lab -v
backend/.venv/bin/python -m unittest discover -s backend/tests -v

cd frontend
npm test -- --run
npm run build
npm run build:pages
```

核心测试覆盖参考碰撞夹具、全部候选汇总、复式/胆拖边界、单票金额上限、seed 复现、安全随机路径、无数据、未来数据泄漏、冻结不可变、复制版本、自动结算、OpenAPI 与迁移回滚。
