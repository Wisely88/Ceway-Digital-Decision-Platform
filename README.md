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

开发依据：

- [v1.2 Baseline 开发方案](docs/ceway_v1_2_baseline.md)
- [v1.3 开发计划](docs/ceway_v1_3_plan.md)
- [Backlog](docs/backlog.md)
- [数据导入说明](docs/data_import.md)

后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

前端默认读取 `http://localhost:8000`。
