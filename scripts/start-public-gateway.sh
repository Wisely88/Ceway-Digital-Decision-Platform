#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.logs"
FRONTEND_DIR="$ROOT_DIR/frontend"
GATEWAY_PORT="${PUBLIC_GATEWAY_PORT:-8788}"
GATEWAY_HOST="${PUBLIC_GATEWAY_HOST:-0.0.0.0}"

mkdir -p "$LOG_DIR"

lan_ip() {
  for iface in en0 en1 en2 en3 en4 en5 en6 en7 en8; do
    local ip
    ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    if [[ -n "$ip" ]]; then
      echo "$ip"
      return
    fi
  done
  ifconfig | awk '/inet / && $2 !~ /^127\\./ && $2 !~ /^169\\.254\\./ { print $2; exit }'
}

port_is_open() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

require_port() {
  local port="$1"
  local name="$2"
  if ! port_is_open "$port"; then
    echo "$name 未运行，缺少端口 $port"
    return 1
  fi
}

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "未找到 frontend/node_modules，请先执行：cd frontend && npm install"
  exit 1
fi

echo "检查本地服务..."
require_port 4321 "ClawScore" || {
  echo "请先在 /Volumes/wisely/clawscore 启动：docker compose up -d"
  exit 1
}
require_port 8000 "策维后端" || {
  echo "请先启动策维：./scripts/start-local.sh"
  exit 1
}

echo "构建策维公网版本..."
(
  cd "$FRONTEND_DIR"
  VITE_API_BASE=/ceway-api npx vite build --base /ceway/
)

if port_is_open "$GATEWAY_PORT"; then
  echo "统一入口已运行：http://127.0.0.1:$GATEWAY_PORT"
else
  PUBLIC_GATEWAY_HOST="$GATEWAY_HOST" nohup node "$ROOT_DIR/scripts/public-gateway.js" > "$LOG_DIR/public-gateway.log" 2>&1 &
  sleep 1
  echo "统一入口已启动：http://127.0.0.1:$GATEWAY_PORT"
fi

LAN_IP="$(lan_ip)"

echo
echo "本地验证："
echo "  http://127.0.0.1:$GATEWAY_PORT/"
echo "  http://127.0.0.1:$GATEWAY_PORT/clawscore"
echo "  http://127.0.0.1:$GATEWAY_PORT/ceway/"
if [[ -n "$LAN_IP" ]]; then
  echo
  echo "局域网访问："
  echo "  http://$LAN_IP:$GATEWAY_PORT/"
  echo "  http://$LAN_IP:$GATEWAY_PORT/clawscore"
  echo "  http://$LAN_IP:$GATEWAY_PORT/ceway/"
fi
echo
echo "公网展示："
echo "  ngrok http $GATEWAY_PORT"
