# 策维（Ceway）数字决策平台

## v1.2 MVP 开发方案（Baseline）

产品名称：策维（Ceway）  
英文副标题：Digital Decision Platform  
框架标识：Powered by CBGO Framework

CBGO Framework 是底层决策框架，全称为 Crowd Behavior Game Optimization Framework。用户主要看到的是产品品牌“策维（Ceway）”和应用场景。

## 项目定位

策维不是彩票预测系统、算号软件或大师推荐工具。

策维是一个帮助用户建立可解释、可控制预算、可持续优化的数字决策平台。

## v1.2 Baseline 范围

必须完成：

- Scene Center。
- 大乐透 DLT Module。
- Dashboard。
- 历史 CSV 数据导入。
- 走势分析：冷热号、遗漏值、奇偶比、大小比、和值。
- 号码评分：Heat x 0.4 + Missing x 0.3 + Balance x 0.3。
- 单式推荐。
- 胆拖推荐。
- 预算控制。
- Anti-Martingale 资金状态机。
- 推荐方案复制。

不开发：

- AI。
- 论坛与舆情。
- 外部热度分析。
- 外部数据 API。
- 双色球正式支持。
- 回测平台。
- 自动更新开奖。

所有新增想法统一进入 Backlog，等 v1.2 完成并验证后再进入后续版本。

## 场景中心

| 场景 | 状态 |
| --- | --- |
| 大乐透 DLT | 已上线 |
| 双色球 SSQ | 开发中 |
| 快乐8 | 规划中 |
| 自定义分析 | 规划中 |

## 系统流程

启动系统 -> Scene Center -> 选择大乐透 -> Dashboard -> 导入历史数据 -> 走势分析 -> 号码评分 -> 预算设置 -> 组合生成 -> 资金管理 -> 输出方案。

## API

- `GET /scenes`
- `GET /dashboard/dlt`
- `POST /plan/dlt`
- `POST /data/dlt/import`

## 技术架构

- Frontend：React、Recharts。
- Backend：FastAPI、Python。
- Storage：CSV、JSON。

## 后续版本

- v1.3：Decision Pipeline，完成评分链路、预算生成器、资金状态机和决策解释。
- v1.4：SQLite、开奖管理、历史记录、推荐方案持久化。
- v1.5：历史回测、资金曲线、ROI、覆盖率。
- v2.0：行为分析、AI 评分、Attention、论坛、公众号、外部公开数据。

## v1.2 MVP 盘点

v1.2 已完成 MVP 第一阶段。

- Scene Center：已达到产品入口要求。
- 大乐透模块：MVP 可运行。
- Dashboard：页面结构成熟。
- 趋势分析：具备基础分析能力。
- 数据导入：CSV 入口已预留。
- 推荐流程：已形成完整链路。
- 资金管理：UI 已有，逻辑待完善。
- 历史记录与数据库存储：进入后续版本。

## 固定声明

策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。彩票具有随机性，请理性参与。
