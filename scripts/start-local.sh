#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.logs"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

mkdir -p "$LOG_DIR"

port_is_open() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

start_backend() {
  if port_is_open 8000; then
    echo "后端已运行：http://127.0.0.1:8000"
    return
  fi

  if [[ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]]; then
    echo "未找到 backend/.venv/bin/uvicorn，请先按 README 安装后端依赖。"
    exit 1
  fi

  (
    cd "$BACKEND_DIR"
    nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
  )
  echo "后端已启动：http://127.0.0.1:8000"
}

start_frontend() {
  if port_is_open 5173; then
    echo "前端已运行：http://localhost:5173"
    return
  fi

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "未找到 frontend/node_modules，请先执行：cd frontend && npm install"
    exit 1
  fi

  (
    cd "$FRONTEND_DIR"
    nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
  )
  echo "前端已启动：http://localhost:5173"
}

start_backend
start_frontend

echo
echo "策维本地页面：http://localhost:5173"
echo "后端接口文档：http://127.0.0.1:8000/docs"
echo "日志目录：$LOG_DIR"
