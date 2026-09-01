# Colab batch runner

The Colab runner is for repeatable backend validation and historical research.
It does not replace the web application, local draw-data maintenance, scheduled
delivery, or any production recommendation entry point.

Open [`notebooks/ceway_colab_batch.ipynb`](../notebooks/ceway_colab_batch.ipynb)
in Google Colab and run all cells. The repository is public, so no GitHub token
is required. Google Drive is mounted only to retain generated artifacts.

Outputs are written to:

```text
MyDrive/AI-Projects/ceway/
├── datasets/
├── models/
├── outputs/
└── checkpoints/
```

Each run validates the backend test suite, then produces timestamped DLT and
SSQ backtest JSON files. Parameters such as budget, periods, and history window
are explicit in the notebook and recorded in each result.

The same deterministic batch entry point can be run locally:

```bash
python scripts/run_colab_batch.py \
  --game dlt --budget 20 --periods 100 --window 100 \
  --output outputs/dlt-backtest.json
```

Historical backtests describe past behavior only. They do not improve or prove
future winning probability.
