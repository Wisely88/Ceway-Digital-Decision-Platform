# API Contract（建议）
Base: `/api/v1/lottery/dlt`

> Pydantic 命名和响应 envelope 按策维现有 API 风格适配。

## GET /rules
返回当前规则配置、版本、号码范围、金额约束。

## GET /draws
Query: `start_issue`, `end_issue`, `limit`

## POST /draws/import
CSV/JSON 导入；必须校验期号唯一、号码范围、前后区数量、区内无重复。

## GET /statistics/numbers
Query: `history_cutoff_issue`, `window`
返回前后区每号 frequency_short/mid/long、omission、zscore、trend label。

## POST /collisions/analyze
Request:
```json
{
  "history_cutoff_issue":"26089",
  "window":{"mode":"all_history"},
  "tickets":[{"front":[5,8,17,22,31],"back":[2,9]}]
}
```
Response 每票：`n_total_hits[0..7]`, `n_front_back[6][3]`, `max_total_hits`, `scarcity_key`。
批量另返回 `m_total_hits`, `u_total_hits`, `m_front_back`, `u_front_back`。

## POST /generate/model
关键字段：
- target_issue
- history_cutoff_issue
- history_window
- front_pool_size/back_pool_size 或 fixed pools
- output_count
- hard_filters（可选）
- model_config_version

返回 run + tickets + score breakdown + collision profile。

## POST /generate/random
```json
{
  "target_issue":"26090",
  "count":10,
  "bet_expression":{"type":"single"},
  "addon":false,
  "multiplier":1,
  "seed":null
}
```
生产 API 不建议向普通 UI 暴露 seed；仅实验模式可用。

## POST /generate/package
```json
{
  "target_issue":"26090",
  "budget_yuan":100,
  "template":"mixed",
  "sources":{"model":0.5,"random":0.3,"scarcity":0.2},
  "addon":false,
  "multiplier":1
}
```
必须返回 `spent`, `unspent`, 组成明细与每项展开注数。

## POST /bet/calculate
支持 single/compound/dantuo；仅计算合法性、注数、金额，不产生购彩动作。

## POST /runs/{run_id}/freeze
创建不可变 freeze version；返回 sha256。

## GET /runs/{run_id}
返回参数、票、碰撞、状态、冻结信息。

## POST /runs/{run_id}/settle
默认根据 `target_issue` 从 draws 中读取实际开奖；若不存在返回409，不允许手填覆盖已有官方/已导入数据。

## GET /compare
Query: target range/model variants
返回 A/B/C 覆盖与命中统计，不输出未经统计验证的“提升中奖率”文案。
