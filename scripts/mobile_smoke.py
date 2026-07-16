#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets


DEFAULT_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class CdpClient:
    def __init__(self, websocket_url: str) -> None:
        self.websocket_url = websocket_url
        self.socket = None
        self.next_id = 1

    async def __aenter__(self) -> "CdpClient":
        self.socket = await websockets.connect(self.websocket_url, max_size=8 * 1024 * 1024)
        return self

    async def __aexit__(self, *_args) -> None:
        if self.socket:
            await self.socket.close()

    async def call(self, method: str, params: dict | None = None) -> dict:
        request_id = self.next_id
        self.next_id += 1
        await self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            response = json.loads(await self.socket.recv())
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise RuntimeError(f"CDP {method} 失败：{response['error']}")
            return response.get("result", {})

    async def evaluate(self, expression: str):
        result = await self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        exception = result.get("exceptionDetails")
        if exception:
            raise RuntimeError(exception.get("text", "页面脚本执行失败"))
        return result.get("result", {}).get("value")


def wait_for_debugger(port: int, timeout: float = 8) -> str:
    deadline = time.monotonic() + timeout
    endpoint = f"http://127.0.0.1:{port}/json"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(endpoint, timeout=1) as response:
                targets = json.load(response)
            page = next(item for item in targets if item.get("type") == "page")
            return page["webSocketDebuggerUrl"]
        except (OSError, StopIteration, ValueError):
            time.sleep(0.15)
    raise RuntimeError("Chrome 调试端口未就绪")


async def wait_for_text(client: CdpClient, text: str, timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    encoded = json.dumps(text, ensure_ascii=False)
    while time.monotonic() < deadline:
        found = await client.evaluate(f"document.body.innerText.includes({encoded})")
        if found:
            return
        await asyncio.sleep(0.15)
    raise AssertionError(f"页面未出现文字：{text}")


async def click_text(client: CdpClient, text: str, selector: str = "button") -> None:
    encoded_text = json.dumps(text, ensure_ascii=False)
    encoded_selector = json.dumps(selector)
    clicked = await client.evaluate(
        """
        (() => {
          const target = [...document.querySelectorAll(%s)]
            .find((node) => node.textContent.trim().includes(%s) && !node.disabled);
          if (!target) return false;
          target.scrollIntoView({block: 'center'});
          target.click();
          return true;
        })()
        """ % (encoded_selector, encoded_text)
    )
    if not clicked:
        raise AssertionError(f"找不到可点击控件：{text}")
    await asyncio.sleep(0.25)


async def assert_no_document_overflow(client: CdpClient, context: str) -> None:
    metrics = await client.evaluate(
        "({clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth})"
    )
    if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
        raise AssertionError(f"{context} 横向溢出：{metrics}")


async def run_scene_flow(client: CdpClient, scene_name: str) -> dict:
    await click_text(client, scene_name, ".scene-tile")
    await wait_for_text(client, "选号工作台")
    await assert_no_document_overflow(client, f"{scene_name}工作台")
    await click_text(client, "选号工作台", ".side-nav-item")
    await wait_for_text(client, "生成智能推荐")
    await click_text(client, "生成智能推荐")
    await wait_for_text(client, "本期已选号码组合")
    await click_text(client, "保存方案")
    await wait_for_text(client, "已加入当期复盘")
    await click_text(client, "随机生成")
    await click_text(client, "生成随机号码")
    await wait_for_text(client, "纯随机号码已生成")
    await click_text(client, "套餐模拟")
    await wait_for_text(client, "随机模拟套餐出票")
    await click_text(client, "随机模拟套餐出票")
    await wait_for_text(client, "本期已选号码组合")
    await click_text(client, "自选号码")
    await wait_for_text(client, "生成点评")
    await click_text(client, "当期复盘", ".side-nav-item")
    await wait_for_text(client, "当期开奖号码与方案复盘")
    await assert_no_document_overflow(client, f"{scene_name}复盘页")
    result = await client.evaluate(
        "({title: document.querySelector('.workspace-topbar h1')?.textContent.trim(), width: innerWidth})"
    )
    await click_text(client, "返回场景")
    await wait_for_text(client, "选择彩种")
    return result


async def run_test(websocket_url: str, url: str) -> dict:
    async with CdpClient(websocket_url) as client:
        await client.call("Page.enable")
        await client.call("Runtime.enable")
        await client.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True},
        )
        await client.call("Page.navigate", {"url": url})
        await wait_for_text(client, "选择彩种")
        await client.evaluate("localStorage.clear()")
        await assert_no_document_overflow(client, "场景选择页")
        dlt = await run_scene_flow(client, "大乐透")
        ssq = await run_scene_flow(client, "双色球")
        return {"viewport": "390x844", "dlt": dlt, "ssq": ssq, "status": "ok"}


def main() -> int:
    parser = argparse.ArgumentParser(description="策维 DLT/SSQ 手机端主流程验收")
    parser.add_argument("--url", default="http://127.0.0.1:5173/")
    parser.add_argument("--chrome", type=Path, default=DEFAULT_CHROME)
    parser.add_argument("--port", type=int, default=9333)
    args = parser.parse_args()
    if not args.chrome.exists():
        raise SystemExit(f"未找到 Chrome：{args.chrome}")

    with tempfile.TemporaryDirectory(prefix="ceway-mobile-smoke-") as profile:
        process = subprocess.Popen(
            [
                str(args.chrome),
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--remote-debugging-port={args.port}",
                f"--user-data-dir={profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            websocket_url = wait_for_debugger(args.port)
            result = asyncio.run(run_test(websocket_url, args.url))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
