# 前端集成清单

## 先适配仓库
- `ADAPT_TO_REPO`: 找出现有 UI 框架（Next.js 或 Vite/React）和组件库。
- 不引入第二套路由/状态库/图表库，复用现有。

## 页面
建议 `/lottery/dlt`：
1. 模型选号
2. 随机选号
3. 预算套餐
4. 历史碰撞
5. 冻结复盘

## 组件
- `NumberBallPicker`: 前区/后区选择、禁用重复、胆拖胆/拖状态。
- `BetExpressionPanel`: 单式/复式/胆拖、追加、倍数、注数和金额。
- `ModelConfigPanel`: 历史窗口、池规模、输出数量、结构过滤。
- `TicketTable`: 号码、分数、N0..N7、结构、操作。
- `CollisionMatrix`: 6x3 的 N_ab 热力表（若现有图表库支持；否则普通表格）。
- `CollisionAggregate`: M_k/U_k。
- `FreezeBanner`: Draft/Frozen/Settled + version + hash。
- `ComparisonPanel`: A/B/C 同期对照。

## UX
- 所有金额在提交前即时计算。
- 非法胆拖/复式立即展示原因。
- 冻结按钮二次确认，确认内容包含 target issue/history cutoff/金额/算法版本。
- Frozen 页面禁止编辑控件，提供“复制为新版本”。
- 显著提示：历史统计不代表未来开奖号码更可能出现。
