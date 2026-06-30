# 数据导入说明

v1.4 开始，系统使用 SQLite 作为本地数据底座。CSV 仍然是最稳定、最可审计的数据交换格式。

走势分析实际读取：

```text
backend/data/ceway.sqlite3
```

CSV 导入和更新脚本会同步维护：

```text
backend/data/dlt_history.csv
```

## CSV 格式

```csv
issue,date,f1,f2,f3,f4,f5,b1,b2
2025001,2025-01-01,3,7,18,22,31,4,11
```

字段说明：

- `issue`：期号。
- `date`：开奖日期。
- `f1` 到 `f5`：大乐透前区号码，范围 1-35，不重复。
- `b1` 到 `b2`：大乐透后区号码，范围 1-12，不重复。

## 页面导入

1. 准备最新大乐透历史开奖 CSV。
2. 进入 DLT Module。
3. 点击“导入最新CSV”。
4. 系统校验 CSV 后写入 SQLite。
5. Dashboard 自动基于新数据重新计算冷热号、遗漏、奇偶比、大小比、和值和评分。

## 脚本更新

脚本入口：

```bash
python3 scripts/update_dlt_history.py --source csv --csv /path/to/dlt_history.csv --mode replace
```

支持的数据源：

```bash
python3 scripts/update_dlt_history.py --source sporttery --limit 100
python3 scripts/update_dlt_history.py --source 78500
python3 scripts/update_dlt_history.py --source csv --csv /path/to/dlt_history.csv
```

说明：

- `sporttery`：尝试读取中国体彩网公开历史开奖接口。部分环境会被 WAF 拦截。
- `78500`：尝试读取用户提供的 78500 数据脚本。该站点 CDN 可能拒绝后端脚本请求。
- `csv`：推荐的稳定方式。适合人工下载或整理后的全量历史数据。

网络源失败时，脚本会记录同步失败，但不会破坏现有数据库。

## 完整性检查

系统会按同一年内的期号连续性检查缺失：

- `样例数据`：开奖数据量少于或等于 30 期。
- `存在缺口`：已导入范围内存在缺失期号。
- `连续完整`：已导入范围内未发现缺口。

完整性状态会显示在 Dashboard 的“数据管理”模块中。

如果无法稳定自动下载历史数据，优先使用可信 CSV 做全量导入。
