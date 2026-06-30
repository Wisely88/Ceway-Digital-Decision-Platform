# 策维（Ceway）数字决策平台

Digital Decision Platform  
Powered by CBGO Framework

v1.2 MVP 是本项目的 Baseline 冻结版本，面向大乐透 DLT Module 完成历史数据分析、号码评分、预算控制、组合生成与资金管理。

策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。

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
