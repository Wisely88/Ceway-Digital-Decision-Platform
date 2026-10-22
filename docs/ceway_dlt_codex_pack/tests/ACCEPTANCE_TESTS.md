# Acceptance Tests

## A. 规则
- [ ] 单式必须恰好5前+2后、区内无重复、范围合法。
- [ ] 复式 `6前+3后` 展开18注。
- [ ] 前区胆拖/后区胆拖/双区胆拖合法和非法边界覆盖。
- [ ] 倍数1与99合法，0/100非法。
- [ ] 追加金额 = 每基本注+1元；基础每注2元。
- [ ] 超过配置的单票金额上限拒绝。

## B. 碰撞核心
固定3期历史 + 2张票，人工计算期望：
- [ ] 每票 N_ab 总和=3。
- [ ] 每票 N_k 总和=3。
- [ ] M_k=两票N_k逐项相加。
- [ ] U_k=两票中该Nk>0的票数。
- [ ] M_ab/U_ab 同理。
- [ ] scarcity_key 顺序 N7,N6,...N1。

## C. 防前视
- [ ] 历史中加入 target_issue 之后的一张“与候选全中”的未来开奖，target 运行输出完全不变。
- [ ] 缺 history_cutoff 时模型生成拒绝。

## D. 随机
- [ ] 注内无重复。
- [ ] 默认同批无完全重复。
- [ ] 测试seed可复现。
- [ ] production random 路径不固定seed。

## E. 冻结
- [ ] freeze 后原 run/tickets 不可修改。
- [ ] 修改参数必须 clone/new version。
- [ ] 相同冻结payload计算相同SHA-256。
- [ ] freeze记录包含history cutoff/model version/config/tickets/cost。

## F. 复盘
- [ ] settle 自动读取 target issue 开奖。
- [ ] 无开奖时返回明确状态，不伪造。
- [ ] 输出每票front_hits/back_hits和整run号码池覆盖。
- [ ] A/B/C 比较支持同注数或同预算口径。

## G. 回归
- [ ] 现有股票页面/API/worker测试不受影响。
- [ ] 全仓 lint/typecheck/test 通过。
