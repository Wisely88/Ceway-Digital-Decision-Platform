#!/usr/bin/env node
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");
const { URL } = require("url");

const ROOT_DIR = path.resolve(__dirname, "..");
const CEWAY_DIST = path.join(ROOT_DIR, "frontend", "dist");
const PORT = Number(process.env.PUBLIC_GATEWAY_PORT || 8788);
const CLAWSCORE_TARGET = process.env.CLAWSCORE_TARGET || "http://127.0.0.1:4321";
const CEWAY_API_TARGET = process.env.CEWAY_API_TARGET || "http://127.0.0.1:8000";

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ico": "image/x-icon",
};

function send(res, status, body, headers = {}) {
  res.writeHead(status, {
    "Content-Type": "text/html; charset=utf-8",
    ...headers,
  });
  res.end(body);
}

function landing(res) {
  send(res, 200, `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Wisely Public Gateway</title>
  <style>
    body{margin:0;background:#07111f;color:#eef6ff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    main{max-width:920px;margin:0 auto;padding:56px 20px}
    h1{font-size:34px;margin:0 0 10px}
    p{color:#a9bdd2;line-height:1.7}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:28px}
    a{display:block;border:1px solid rgba(100,150,210,.35);border-radius:8px;padding:22px;background:#0d1d31;color:#fff;text-decoration:none}
    strong{display:block;font-size:22px;margin-bottom:8px}
    span{color:#a9bdd2}
  </style>
</head>
<body>
  <main>
    <h1>统一公网展示入口</h1>
    <p>一个 ngrok 地址同时展示 ClawScore 和策维（Ceway）。</p>
    <div class="grid">
      <a href="/clawscore"><strong>ClawScore</strong><span>足球数据分析平台</span></a>
      <a href="/ceway/"><strong>策维（Ceway）</strong><span>数字决策平台</span></a>
    </div>
  </main>
</body>
</html>`);
}

function serveCeway(req, res) {
  const requestUrl = new URL(req.url, `http://${req.headers.host}`);
  let relativePath = decodeURIComponent(requestUrl.pathname.replace(/^\/ceway\/?/, ""));
  if (!relativePath || relativePath.endsWith("/")) {
    relativePath = `${relativePath}index.html`;
  }
  const resolvedPath = path.normalize(path.join(CEWAY_DIST, relativePath));
  if (!resolvedPath.startsWith(CEWAY_DIST)) {
    send(res, 403, "Forbidden");
    return;
  }
  const filePath = fs.existsSync(resolvedPath) && fs.statSync(resolvedPath).isFile()
    ? resolvedPath
    : path.join(CEWAY_DIST, "index.html");
  fs.readFile(filePath, (error, data) => {
    if (error) {
      send(res, 404, "Not Found");
      return;
    }
    const ext = path.extname(filePath);
    res.writeHead(200, { "Content-Type": MIME_TYPES[ext] || "application/octet-stream" });
    res.end(data);
  });
}

function proxyHttp(req, res, targetBase, stripPrefix = "") {
  const target = new URL(targetBase);
  const incoming = new URL(req.url, `http://${req.headers.host}`);
  const targetPath = stripPrefix
    ? incoming.pathname.replace(new RegExp(`^${stripPrefix}`), "") || "/"
    : incoming.pathname;
  const options = {
    hostname: target.hostname,
    port: target.port || 80,
    method: req.method,
    path: `${targetPath}${incoming.search}`,
    headers: {
      ...req.headers,
      host: target.host,
    },
  };
  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
    proxyRes.pipe(res);
  });
  proxyReq.on("error", (error) => {
    send(res, 502, `上游服务不可用：${error.message}`);
  });
  req.pipe(proxyReq);
}

function proxyWebSocket(req, socket, head, targetBase) {
  const target = new URL(targetBase);
  const upstream = net.connect(Number(target.port || 80), target.hostname, () => {
    upstream.write(
      `${req.method} ${req.url} HTTP/${req.httpVersion}\r\n`
      + Object.entries({ ...req.headers, host: target.host })
        .map(([key, value]) => `${key}: ${value}`)
        .join("\r\n")
      + "\r\n\r\n"
    );
    if (head && head.length > 0) upstream.write(head);
    socket.pipe(upstream);
    upstream.pipe(socket);
  });
  upstream.on("error", () => socket.destroy());
}

const server = http.createServer((req, res) => {
  const requestUrl = new URL(req.url, `http://${req.headers.host}`);
  if (requestUrl.pathname === "/") {
    landing(res);
    return;
  }
  if (requestUrl.pathname === "/clawscore" || requestUrl.pathname === "/clawscore/") {
    req.url = "/dashboard";
    proxyHttp(req, res, CLAWSCORE_TARGET);
    return;
  }
  if (requestUrl.pathname.startsWith("/ceway-api/")) {
    proxyHttp(req, res, CEWAY_API_TARGET, "/ceway-api");
    return;
  }
  if (requestUrl.pathname.startsWith("/ceway")) {
    serveCeway(req, res);
    return;
  }
  if (requestUrl.pathname.startsWith("/api/") || requestUrl.pathname === "/dashboard" || requestUrl.pathname === "/health") {
    proxyHttp(req, res, CLAWSCORE_TARGET);
    return;
  }
  send(res, 404, "Not Found");
});

server.on("upgrade", (req, socket, head) => {
  const requestUrl = new URL(req.url, `http://${req.headers.host}`);
  if (requestUrl.pathname === "/ws") {
    proxyWebSocket(req, socket, head, CLAWSCORE_TARGET);
    return;
  }
  socket.destroy();
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`统一入口：http://127.0.0.1:${PORT}`);
  console.log(`ClawScore：http://127.0.0.1:${PORT}/clawscore`);
  console.log(`策维：http://127.0.0.1:${PORT}/ceway/`);
});
