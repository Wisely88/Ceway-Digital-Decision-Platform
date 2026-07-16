# 策维（Ceway）数字决策平台 v1.11

Digital Decision Platform  
Powered by CBGO Framework

当前版本为“精简选号工作台”，已支持大乐透 DLT 与双色球 SSQ 的智能推荐、纯随机生成、套餐模拟、自选号码和当期开奖复盘。

产品主线：选号只是入口，决策解释和风险控制才是核心。系统会说明本期实际支出、组合覆盖、投注倍率、资金暴露、近 30 日投入、连续加码迹象和历史回测表现。

策维不预测开奖结果，不承诺提高中奖概率。历史评分和回测只能描述历史匹配，不能证明未来收益。

## 目录

```text
ceway/
├── frontend/
├── backend/
├── config/
├── dataset/
├── engine/
└── docs/
```

## 本地启动

推荐一键启动：

```bash
./scripts/start-local.sh
```

启动后打开：

- 前端页面：`http://localhost:5173`
- 后端接口文档：`http://127.0.0.1:8000/docs`

如果页面打不开，通常是前端服务没有运行；重新执行上面的脚本即可。

开发依据：

- [v1.2 Baseline 开发方案](docs/ceway_v1_2_baseline.md)
- [v1.3 开发计划](docs/ceway_v1_3_plan.md)
- [v1.6 决策风控说明](docs/ceway_v1_6_decision_risk.md)
- [v1.7 套餐评估说明](docs/ceway_v1_7_package_evaluation.md)
- [v1.8 验证闭环说明](docs/ceway_v1_8_validation_loop.md)
- [v1.9 行为风控说明](docs/ceway_v1_9_behavior_risk.md)
- [v1.10 单用户云同步说明](docs/ceway_v1_10_cloud_sync.md)
- [v1.11 精简选号工作台](docs/ceway_v1_11_simplified_workbench.md)
- [Backlog](docs/backlog.md)
- [数据导入说明](docs/data_import.md)

手动启动后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

手动启动前端：

```bash
cd frontend
npm install
npm run dev
```

前端默认读取 `http://localhost:8000`。

## 单用户云同步

云同步不提供公开注册。首次启用时，在 Supabase 控制台完成两步初始化：

1. 在 SQL Editor 执行 [`supabase/setup.sql`](supabase/setup.sql)。
2. 在 Authentication > Users 新建并确认内部用户 `ceway-sync@ceway.local`，设置仅自己知道的同步密码。

之后在 DLT 或 SSQ 左侧进入“云端同步”，所有自用设备输入同一个同步密码即可。公开发布密钥可以存在前端；数据访问由表级 RLS 限制。不要把 Supabase secret key 或 service role key放入仓库。

## 验证

```bash
cd frontend
npm test
npm run build:pages

cd ..
backend/.venv/bin/python -m unittest discover -s backend/tests -v

# 先启动静态演示前端，再执行 390x844 的 DLT/SSQ 手机主流程验收
backend/.venv/bin/python scripts/mobile_smoke.py
```

当前数据快照：

- 大乐透：2897 期，最新 `26079`（2026-07-15）。
- 双色球：3477 期，最新 `2026080`（2026-07-14）。
- 两份数据均通过当前期号范围连续性检查。

每期实际奖金快照：

- 大乐透：2897 期。
- 双色球：2038 期。
- 复盘页只在奖级金额数据完整时显示净收益与 ROI；不完整时明确标记待补，避免用估算值冒充实际奖金。

## 开奖日自动更新

macOS 定时任务按北京时间检查最新开奖：

- 大乐透：每周一、三、六的 `22:30`、`23:30`，以及次日 `00:30`。
- 双色球：每周二、四、日的 `22:30`、`23:30`，以及次日 `00:30`。

定时任务统一从 `78500.cn` 的大乐透和双色球数据库读取最新开奖。GitHub 云端 IP 会被该站拒绝，因此由本机 LaunchAgent 在 `~/Library/Caches/Ceway-Automation` 的专用工作副本中执行抓取，验证通过后自动提交 GitHub 并重新发布 Pages。

任务只在发现新期号且数据校验通过时更新 CSV、提交主分支并重新发布 GitHub Pages。任一数据源失败、号码越界、期号重复或历史记录异常时，任务会失败并保留原数据。休市日没有新期号时不会产生提交。

每次任务会把最终状态写入 `~/Library/Caches/Ceway-Automation/status/latest.json`。更新失败时同时发送 macOS 通知中心提醒，因此失败原因不再只存在于 LaunchAgent 日志中。

电脑需要开机且已连网。关机期间错过检查时间时，下一个开奖日检查会通过期号去重自动补齐。

手动验证全部场景：

```bash
python3 scripts/run_draw_update.py --game all
```

## 同时公网展示 ClawScore 与策维

最优方案是只开一个本地统一入口，再用一个 ngrok 地址暴露：

```text
/clawscore  -> ClawScore
/ceway/     -> 策维
/api        -> ClawScore API
/ceway-api  -> 策维 API
```

前置条件：

- ClawScore 已在 `127.0.0.1:4321` 运行。
- 策维后端已在 `127.0.0.1:8000` 运行。

启动统一入口：

```bash
./scripts/start-public-gateway.sh
```

本地验证：

```text
http://127.0.0.1:8788/clawscore
http://127.0.0.1:8788/ceway/
```

同一局域网内其他设备访问时，使用 Mac 的局域网 IP：

```bash
ipconfig getifaddr en1
```

例如 Mac IP 为 `192.168.31.34`：

```text
http://192.168.31.34:8788/clawscore
http://192.168.31.34:8788/ceway/
```

如果手机和 Mac 不在同一网段，例如一个是 `192.168.31.x`、另一个是 `192.168.2.x`，需要把副路由改成 AP/桥接模式，或继续使用 ngrok/Tailscale。

启动公网地址：

```bash
ngrok http 8788
```
