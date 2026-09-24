# 后续预测取数协议

1. 先读取 GitHub main 分支 odds_sources/status/latest.json 和 odds_sources/data/latest.json，确认 GitHub Actions 最近执行成功。前者只给源站健康检查，后者才可能有行情。
2. 当前文件 is_fresh 必须为 true；当前时间距 checked_at_utc 和每条 quoted_at_utc 不超过 45 分钟，kickoff_utc 未过，比赛身份完整。否则视为无可用实时盘口。
3. 核对 sources.json 内的实际源站、官方/第三方属性。授权 feed 的来源自报不能视为体彩官方认证，页面上出现“竞彩官方”同样应独立核查官方销售状态。
4. 用 fixture_id、竞彩日期与比赛编号、主客队双向核对：足球网页经常主队在前，篮球经常客队在前，统一仅使用 home_team/away_team 字段。
5. line 采用主队视角：负号主让、正号主受让。足球胜平负与让球胜平负、篮球普通胜负与让分、大小分、胜分差不可混用赔率和比分分布。
6. 盘口更新时保留赔率时刻；不同来源或日期出现冲突则标记待核。HTTP 200、出现当天日期、抓取时刻都不能证明赔率发布时刻。
7. 独立建立球队实力、伤停、赛程、足球净胜球及篮球分差/总分分布，再比较盘口；模型估价永远不当作体彩 SP。
8. data/latest.json 为空、过期或只剩 examples/ 历史数据时，回到 sources.json 指向的实际网站重新核对，而不是编造当日盘口。
