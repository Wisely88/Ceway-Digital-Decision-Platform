#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT_DIR = Path(os.environ.get("CEWAY_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()
FRONTEND_DIR = ROOT_DIR / "frontend"
DATA_FILES = [
    Path("backend/data/dlt_history.csv"),
    Path("backend/data/ssq_history.csv"),
    Path("backend/data/dlt_prizes.json"),
    Path("backend/data/ssq_prizes.json"),
]
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
DLT_DRAW_WEEKDAYS = {0, 2, 5}
SSQ_DRAW_WEEKDAYS = {1, 3, 6}
AUTOMATION_PATH = ":".join(
    [
        str(Path.home() / ".npm-global/bin"),
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
)
STATUS_FILE = Path(
    os.environ.get(
        "CEWAY_STATUS_FILE",
        Path.home() / "Library/Caches/Ceway-Automation/status/latest.json",
    )
).expanduser()


def log(message: str) -> None:
    timestamp = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def write_run_status(status: str, game: str, message: str, status_file: Path | None = None) -> Path:
    target = status_file or STATUS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = {}
    if target.exists():
        try:
            previous = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    updated_at = datetime.now(SHANGHAI_TZ).isoformat()
    payload = {
        "status": status,
        "game": game,
        "message": message,
        "updated_at": updated_at,
        "last_success_at": previous.get("last_success_at"),
        "last_failure_at": previous.get("last_failure_at"),
        "last_failure_message": previous.get("last_failure_message"),
    }
    if status == "ok":
        payload["last_success_at"] = updated_at
    elif status == "failed":
        payload["last_failure_at"] = updated_at
        payload["last_failure_message"] = message
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def send_failure_notification(game: str, message: str) -> None:
    if sys.platform != "darwin" or not shutil.which("osascript"):
        return
    title = json.dumps(f"策维 {game.upper()} 数据更新失败", ensure_ascii=False)
    body = json.dumps(message[:180], ensure_ascii=False)
    try:
        subprocess.run(
            ["osascript", "-e", f"display notification {body} with title {title}"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def run(
    command: list[str],
    *,
    cwd: Path = ROOT_DIR,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = AUTOMATION_PATH
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr, flush=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"命令执行失败（{result.returncode}）：{' '.join(command)}")
    return result


def run_with_retry(
    command: list[str],
    *,
    cwd: Path = ROOT_DIR,
    timeout: int = 120,
    attempts: int = 3,
    delay: int = 4,
) -> subprocess.CompletedProcess[str]:
    last_result = None
    for attempt in range(1, attempts + 1):
        last_result = run(command, cwd=cwd, timeout=timeout, check=False)
        if last_result.returncode == 0:
            return last_result
        if attempt < attempts:
            log(f"命令失败，{delay} 秒后重试（{attempt}/{attempts}）：{' '.join(command)}")
            time.sleep(delay)
    raise RuntimeError(f"命令连续失败 {attempts} 次：{' '.join(command)}")


def scheduled_game(now: datetime | None = None) -> str | None:
    local_now = now.astimezone(SHANGHAI_TZ) if now else datetime.now(SHANGHAI_TZ)
    draw_day = local_now.date()
    if local_now.hour < 2:
        draw_day -= timedelta(days=1)
    if draw_day.weekday() in DLT_DRAW_WEEKDAYS | SSQ_DRAW_WEEKDAYS:
        return "all"
    return None


def ensure_safe_worktree() -> None:
    result = run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        check=True,
    )
    allowed = {str(path) for path in DATA_FILES}
    unsafe = []
    for line in result.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path not in allowed:
            unsafe.append(path)
    if unsafe:
        raise RuntimeError("工作区存在未处理变更，为避免误提交已停止自动更新：" + "、".join(unsafe))


def refresh_checkout() -> None:
    if data_changed():
        log("检测到上次未完成的数据更新，先继续本地恢复流程")
        return
    run_with_retry(["git", "fetch", "origin", "main"], timeout=120)
    run(["git", "merge", "--ff-only", "origin/main"])
    ahead = run(["git", "rev-list", "--count", "origin/main..HEAD"]).stdout.strip()
    if ahead and int(ahead) > 0:
        run_with_retry(["git", "push", "origin", "main"], timeout=120)


def update_history(game: str) -> None:
    commands = {
        "dlt": [sys.executable, "scripts/update_dlt_history.py", "--source", "78500", "--mode", "append"],
        "ssq": [sys.executable, "scripts/update_ssq_history.py", "--source", "78500", "--mode", "append"],
    }
    games = ["dlt", "ssq"] if game == "all" else [game]
    for selected in games:
        log(f"从 78500.cn 更新 {selected.upper()} 历史数据")
        run(commands[selected], timeout=30)
    run([sys.executable, "scripts/validate_lottery_history.py"], timeout=30)
    run([sys.executable, "scripts/update_prize_data.py", "--game", game], timeout=60)


def data_changed() -> bool:
    result = run(
        ["git", "diff", "--quiet", "--", *[str(path) for path in DATA_FILES]],
        check=False,
    )
    return result.returncode != 0


def commit_data(game: str) -> None:
    run(["git", "config", "user.name", "Ceway Data Updater"])
    run(["git", "config", "user.email", "ceway-updater@local.invalid"])
    run(["git", "add", *[str(path) for path in DATA_FILES]])
    today = datetime.now(SHANGHAI_TZ).date().isoformat()
    run(["git", "commit", "-m", f"Update {game} lottery history ({today})"])
    run_with_retry(["git", "push", "origin", "main"], timeout=120)


def frontend_dependencies_are_stale(frontend_dir: Path = FRONTEND_DIR) -> bool:
    node_modules = frontend_dir / "node_modules"
    package_lock = frontend_dir / "package-lock.json"
    return (
        not node_modules.exists()
        or (package_lock.exists() and package_lock.stat().st_mtime > node_modules.stat().st_mtime)
    )


def build_pages() -> None:
    npm = shutil.which("npm", path=AUTOMATION_PATH)
    if not npm:
        raise RuntimeError("未找到 npm，无法构建 GitHub Pages")
    node_modules = FRONTEND_DIR / "node_modules"
    if frontend_dependencies_are_stale():
        log("前端依赖有更新，执行 npm ci")
        run([npm, "ci"], cwd=FRONTEND_DIR, timeout=600)
    run([npm, "run", "build:pages"], cwd=FRONTEND_DIR, timeout=300)


def replace_pages_files(pages_dir: Path) -> None:
    for child in pages_dir.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in (FRONTEND_DIR / "dist").iterdir():
        target = pages_dir / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def github_repo_slug(remote: str) -> str:
    normalized = remote.strip().removesuffix(".git")
    if normalized.startswith("git@github.com:"):
        return normalized.split(":", 1)[1]
    marker = "github.com/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]
    raise RuntimeError(f"无法从远程地址识别 GitHub 仓库：{remote}")


def trigger_pages_build(remote: str) -> None:
    gh = shutil.which("gh", path=AUTOMATION_PATH)
    if not gh:
        raise RuntimeError("未找到 gh，无法触发 GitHub Pages 构建")
    repo = github_repo_slug(remote)
    run_with_retry(
        [gh, "api", "--method", "POST", f"repos/{repo}/pages/builds"],
        timeout=30,
    )
    log("GitHub Pages 构建已触发")


def publish_pages() -> None:
    remote = run(["git", "remote", "get-url", "origin"]).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="ceway-pages-") as temp_dir:
        pages_dir = Path(temp_dir) / "site"
        run_with_retry(
            ["git", "clone", "--depth", "1", "--branch", "gh-pages", remote, str(pages_dir)],
            cwd=ROOT_DIR,
            timeout=120,
        )
        replace_pages_files(pages_dir)
        run(["git", "add", "-A"], cwd=pages_dir)
        changed = run(["git", "diff", "--cached", "--quiet"], cwd=pages_dir, check=False).returncode != 0
        if not changed:
            log("GitHub Pages 已是最新版本")
            return
        run(["git", "config", "user.name", "Ceway Data Updater"], cwd=pages_dir)
        run(["git", "config", "user.email", "ceway-updater@local.invalid"], cwd=pages_dir)
        run(["git", "commit", "-m", "Publish latest lottery history"], cwd=pages_dir)
        run_with_retry(["git", "push", "origin", "HEAD:gh-pages"], cwd=pages_dir, timeout=120)
        trigger_pages_build(remote)
        log("GitHub Pages 已发布")


def main() -> int:
    parser = argparse.ArgumentParser(description="按开奖日更新策维历史数据并发布网页")
    parser.add_argument("--game", choices=["auto", "dlt", "ssq", "all"], default="auto")
    args = parser.parse_args()

    lock_path = Path("/tmp/ceway-lottery-update.lock")
    with lock_path.open("w") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            message = "已有一个更新任务在运行，本次跳过"
            log(message)
            write_run_status("skipped", args.game, message)
            return 0

        game = scheduled_game() if args.game == "auto" else args.game
        if not game:
            message = "当前不属于大乐透或双色球开奖检查时段，本次跳过"
            log(message)
            write_run_status("skipped", args.game, message)
            return 0

        try:
            ensure_safe_worktree()
            refresh_checkout()
            update_history(game)
            if data_changed():
                log("发现新期号，保存历史数据到 GitHub")
                commit_data(game)
            else:
                log("未发现新期号")
            build_pages()
            publish_pages()
            message = "自动更新任务完成"
            log(message)
            write_run_status("ok", game, message)
            return 0
        except Exception as exc:
            message = f"自动更新失败：{exc}"
            log(message)
            write_run_status("failed", game, message)
            send_failure_notification(game, message)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
