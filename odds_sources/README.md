# 策维 · 足球/篮球体彩盘口数据源与时效巡检

本目录是与现有大乐透/双色球业务隔离的**独立资料层**，不修改原有选号、模型、数据库或部署逻辑。初次整理：2026-09-24。最新检查结果在 [status/latest.json](status/latest.json)，**已经通过实时校验的报价（如果有）**在 [data/latest.json](data/latest.json)。这两个文件不能混用。

## 目前登记的来源

[sources.json](sources.json) 登记足球/篮球官网与第三方完整入口、支持玩法、页面访问方式、首次人工核验证据、自动采集状态。

| 渠道 | 足球 | 篮球 | 本次确认及注意事项 |
|---|---|---|---|
| [中国竞彩网](https://www.sporttery.cn/) | [胜平负/让球](https://www.sporttery.cn/jc/jsq/zqspf/) | [让分](https://www.sporttery.cn/jc/jsq/lqrfsf/) · [大小分](https://www.sporttery.cn/jc/jsq/lqdxf/) | 官方发布网站；部分页面动态加载，页面可访问不代表抓取到 SP |
| [澳客](https://www.okooo.com/) | [竞彩足球](https://www.okooo.com/jingcai/) | [竞彩篮球混合过关](https://www.okooo.com/jingcailanqiu/hunhe/) | 公开网页有赛程及盘口；篮球可能返回旧缓存 |
| [Honghuo66](https://model.honghuo66.com/) | 截图展示竞彩官方切换 | 截图展示让分和大小分 | 具体 JSON API 和篮球上游来源尚未核实，用户截图存于 examples/ |
| 500网 | [足球奖金走势](https://zx.500star.com/jczq/jjzs.php?play=1) | [篮球奖金走势](https://zx.500star.com/jclq/jjzs.php?play=2&type=2) | 足球当日数据可在网页看到；篮球本次出现旧日期，只作历史辅助 |
| [中国足彩网](https://www.zgzcw.com/) | 赛程与赔率辅助 | 具体页面待核 | 仅登记站点入口，不能谎称本次验证了可用实时接口 |

历史截图 [2026-09-24 Honghuo66 篮球示例](examples/2026-09-24-honghuo66-basketball-screenshot.json) 明确标记为历史证据；不能自动晋升为最新盘口。不同站可能共享上游，不应误以为报价一致就是独立核验。海外公司赔率、交易所指数和模型估算赔率不等于体彩官方 SP。

## 定时检查：时效分层

[GitHub Actions 工作流](../.github/workflows/odds-source-monitor.yml) 在默认分支计划运行：

- 北京时间约 **03:17、09:17、15:17、21:17** 对登记来源做 HTTP 健康检查及网页当日/次日赛程日期信号检查，结果写入 status/latest.json。HTTP 200、网页包含日期都**不等于已验证赔率实时性**；赔率时间一律保留 not_verified。
- 如已配置合法授权、带逐条赔率时间戳的 JSON feed，每小时 **UTC :23** 检查并将完整且不超过 **45 分钟**的快照写入 data/latest.json。时间戳过期、盘口结构不完整、比赛已开赛太久、来源缺失则判为不可用；不会用旧赔率顶替。
- 403/429、验证码、需要登录或动态加载不绕过；记录不可用并保留原始 URL。GitHub cron 执行可能延迟，公共仓库长期无提交时可能自动禁用。
- 工作流需要 Actions 开启、GITHUB_TOKEN 拥有仓库 Contents 写权限。首次部署后须检查 Actions 最近一次实际执行结果。

## 实时赔率 feed 的接入要求

**当前还没有一个经过授权、实际验证能稳定提供体彩足球和篮球逐条实时报价时间戳的公开 API。** 因此目前自动健康监测可以运转，data/latest.json 初始为空。不能把这个空文件说成已经抓取了官方盘口。

拿到明确授权的商业或自维护 JSON feed 后，在 GitHub Settings → Secrets and variables → Actions 配置 ODDS_FEED_URL，若需鉴权则另配 ODDS_FEED_BEARER。响应示例（**只示范结构，不是实时数据**）：

~~~json
{
  "generated_at_utc": "2026-09-24T08:00:00Z",
  "quotes": [{
    "source_id": "licensed_feed",
    "fixture_id": "2026-09-24-4302",
    "sport": "basketball",
    "market": "basketball_spread",
    "away_team": "墨尔本联",
    "home_team": "墨凤凰",
    "kickoff_utc": "2026-09-24T09:25:00Z",
    "quoted_at_utc": "2026-09-24T07:58:00Z",
    "line": 2.5,
    "selection_odds": {"away": 1.65, "home": 1.75}
  }]
}
~~~

盘口始终使用**主队视角**：负数主让、正数主受让；足球让球整数。不让球足球使用 football_1x2 及 home/draw/away，篮球让分用 basketball_spread 及 home/away，篮球大小分用 basketball_total 及 over/under。授权 feed 的 source_id 属于自报，自动校验始终保留 is_official_confirmed=false，必须另行核实真正体彩来源与票面。

## 后续比赛预测

见 [INTEGRATION.md](INTEGRATION.md)。每次必须先检查最近的 GitHub Actions 运行，再读取 data/latest.json；只有 is_fresh=true、生成和逐条报价不超过 45 分钟、主客名称/编号/比赛时间/玩法/盘口符号一致时，才把它作为**带来源标记的报价快照**用于分析。没有有效报价就返回原站核查；严禁混用不同玩法 SP 或拿 ClawScore 旧版 estimated 赔率冒充体彩报价。
