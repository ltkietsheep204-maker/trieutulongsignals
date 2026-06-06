from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import webbrowser
from collections import deque
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from env_loader import read_env_file, write_env_file
from telegram import Bot


APP_DIR = Path(__file__).resolve().parent
BOT_PATH = APP_DIR / "bot.py"
ENV_PATH = APP_DIR / ".env"
HOST = "127.0.0.1"
PORT = 8765


HTML_PAGE = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Telegram Signal Bot Local UI</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f1115;
      --panel: #171a21;
      --panel-2: #1f2430;
      --border: #2b3140;
      --text: #e6e8ee;
      --muted: #9aa3b2;
      --accent: #4da3ff;
      --good: #2fbf71;
      --warn: #ffb020;
      --bad: #ff5d5d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .app {
      max-width: 1440px;
      margin: 0 auto;
      padding: 20px;
      display: grid;
      gap: 16px;
    }
    .header, .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
    }
    .header {
      padding: 18px 20px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
    }
    .title h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 700;
    }
    .title p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 14px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(110px, 1fr));
      gap: 10px;
      min-width: 340px;
    }
    .stat {
      padding: 12px;
      background: var(--panel-2);
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .stat .label {
      color: var(--muted);
      font-size: 12px;
    }
    .stat .value {
      margin-top: 6px;
      font-size: 14px;
      font-weight: 600;
    }
    .grid {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      gap: 16px;
    }
    .panel {
      padding: 16px;
      min-width: 0;
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 16px;
    }
    .stack {
      display: grid;
      gap: 16px;
      min-width: 0;
    }
    label {
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 13px;
    }
    input[type="text"], input[type="password"] {
      width: 100%;
      padding: 10px 12px;
      background: #0e1218;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-size: 14px;
    }
    .row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: stretch;
    }
    .row > * {
      min-width: 0;
    }
    .button-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
    }
    .button-grid > * {
      width: 100%;
      min-width: 0;
    }
    button {
      appearance: none;
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 14px;
      cursor: pointer;
      white-space: normal;
      overflow-wrap: anywhere;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: white; }
    button.good { background: var(--good); border-color: var(--good); color: white; }
    button.warn { background: var(--warn); border-color: var(--warn); color: #111; }
    button.bad { background: var(--bad); border-color: var(--bad); color: white; }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    .status-line {
      color: var(--muted);
      font-size: 13px;
      min-height: 18px;
    }
    .runtime-list {
      display: grid;
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .runtime-item strong {
      display: block;
      color: var(--text);
      font-size: 14px;
      margin-top: 4px;
    }
    pre {
      margin: 0;
      min-height: 620px;
      max-height: 70vh;
      overflow: auto;
      background: #0c0f14;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .muted {
      color: var(--muted);
      font-size: 13px;
    }
    @media (max-width: 1000px) {
      .grid {
        grid-template-columns: 1fr;
      }
      .header {
        flex-direction: column;
      }
      .stats {
        min-width: 0;
        width: 100%;
      }
    }
    @media (max-width: 720px) {
      .app {
        padding: 12px;
      }
      .panel {
        padding: 12px;
      }
      .row {
        display: grid;
        grid-template-columns: 1fr;
      }
      .row > * {
        width: 100%;
      }
      .button-grid {
        grid-template-columns: 1fr;
      }
      button {
        width: 100%;
      }
      pre {
        min-height: 420px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <section class="header">
      <div class="title">
        <h1>Telegram Signal Bot Local UI</h1>
        <p>Localhost control panel cho bot chạy trực tiếp theo logic trong bot.py.</p>
      </div>
      <div class="stats">
        <div class="stat"><div class="label">Trạng thái</div><div class="value" id="bot-status">-</div></div>
        <div class="stat"><div class="label">PID</div><div class="value" id="bot-pid">-</div></div>
        <div class="stat"><div class="label">Mode</div><div class="value" id="bot-mode">-</div></div>
      </div>
    </section>

    <div class="grid">
      <div class="stack">
        <section class="panel">
          <h2>Cấu hình Telegram</h2>
          <div>
            <label for="token">Bot Token</label>
            <input id="token" type="password" autocomplete="off">
          </div>
          <div style="margin-top: 12px;">
            <label for="chat-id">Chat ID</label>
            <input id="chat-id" type="text" autocomplete="off">
          </div>
          <div class="button-grid" style="margin-top: 12px;">
            <button id="toggle-token">Hiện token</button>
            <button id="save-config" class="primary">Lưu cấu hình</button>
            <button id="reload-config">Đọc lại .env</button>
            <button id="test-telegram" class="warn">Test Telegram</button>
          </div>
          <div id="config-status" class="status-line" style="margin-top: 12px;"></div>
        </section>

        <section class="panel">
          <h2>Điều khiển Bot</h2>
          <div class="button-grid">
            <button id="start-service" class="good">Start Service</button>
            <button id="run-once" class="warn">Run Once</button>
            <button id="stop-bot" class="bad">Stop</button>
            <button id="clear-log">Clear Log</button>
          </div>
          <div id="action-status" class="status-line" style="margin-top: 12px;"></div>
        </section>

        <section class="panel">
          <h2>Runtime</h2>
          <div class="runtime-list">
            <div class="runtime-item">Interpreter<strong id="runtime-python">-</strong></div>
            <div class="runtime-item">Config file<strong id="runtime-env">-</strong></div>
            <div class="runtime-item">Entrypoint<strong id="runtime-entry">python bot.py</strong></div>
          </div>
        </section>

        <section class="panel">
          <h2>Nhắc nhanh</h2>
          <div class="muted">
            Service sẽ quét ngay khi khởi động rồi giữ scheduler 4H/D1.<br>
            Run Once sẽ quét một vòng rồi thoát.<br>
            Log bên phải là stdout/stderr trực tiếp của bot.py.
          </div>
        </section>
      </div>

      <section class="panel">
        <h2>Log Runtime</h2>
        <pre id="log-box"></pre>
      </section>
    </div>
  </div>

  <script>
    const stateEls = {
      status: document.getElementById("bot-status"),
      pid: document.getElementById("bot-pid"),
      mode: document.getElementById("bot-mode"),
      token: document.getElementById("token"),
      chatId: document.getElementById("chat-id"),
      runtimePython: document.getElementById("runtime-python"),
      runtimeEnv: document.getElementById("runtime-env"),
      logBox: document.getElementById("log-box"),
      configStatus: document.getElementById("config-status"),
      actionStatus: document.getElementById("action-status"),
    };

    let tokenVisible = false;

    async function request(path, options = {}) {
      const res = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Request failed");
      }
      return data;
    }

    function setButtons(state) {
      const running = state.running;
      document.getElementById("start-service").disabled = running;
      document.getElementById("run-once").disabled = running;
      document.getElementById("stop-bot").disabled = !running;
    }

    function renderState(data) {
      stateEls.status.textContent = data.status;
      stateEls.pid.textContent = data.pid || "-";
      stateEls.mode.textContent = data.mode || "-";
      stateEls.runtimePython.textContent = data.python;
      stateEls.runtimeEnv.textContent = data.env_path;
      stateEls.configStatus.textContent = data.config_status;

      if (document.activeElement !== stateEls.token) {
        stateEls.token.value = data.telegram_token || "";
      }
      if (document.activeElement !== stateEls.chatId) {
        stateEls.chatId.value = data.telegram_chat_id || "";
      }

      const nextLog = data.logs.join("\\n");
      if (stateEls.logBox.textContent !== nextLog) {
        const nearBottom =
          stateEls.logBox.scrollTop + stateEls.logBox.clientHeight >= stateEls.logBox.scrollHeight - 24;
        stateEls.logBox.textContent = nextLog;
        if (nearBottom) {
          stateEls.logBox.scrollTop = stateEls.logBox.scrollHeight;
        }
      }

      setButtons(data);
    }

    async function refreshState() {
      try {
        const data = await request("/api/state", { method: "GET", headers: {} });
        renderState(data);
      } catch (err) {
        stateEls.actionStatus.textContent = err.message;
      }
    }

    async function saveConfig() {
      try {
        const data = await request("/api/config", {
          method: "POST",
          body: JSON.stringify({
            telegram_token: stateEls.token.value.trim(),
            telegram_chat_id: stateEls.chatId.value.trim()
          })
        });
        stateEls.actionStatus.textContent = data.message;
        await refreshState();
      } catch (err) {
        stateEls.actionStatus.textContent = err.message;
      }
    }

    async function testTelegram() {
      try {
        const data = await request("/api/test-telegram", {
          method: "POST",
          body: JSON.stringify({
            telegram_token: stateEls.token.value.trim(),
            telegram_chat_id: stateEls.chatId.value.trim()
          })
        });
        stateEls.actionStatus.textContent = data.message;
        await refreshState();
      } catch (err) {
        stateEls.actionStatus.textContent = err.message;
      }
    }

    async function startBot(mode) {
      try {
        const data = await request("/api/start", {
          method: "POST",
          body: JSON.stringify({
            mode,
            telegram_token: stateEls.token.value.trim(),
            telegram_chat_id: stateEls.chatId.value.trim()
          })
        });
        stateEls.actionStatus.textContent = data.message;
        await refreshState();
      } catch (err) {
        stateEls.actionStatus.textContent = err.message;
      }
    }

    async function stopBot() {
      try {
        const data = await request("/api/stop", {
          method: "POST",
          body: JSON.stringify({})
        });
        stateEls.actionStatus.textContent = data.message;
        await refreshState();
      } catch (err) {
        stateEls.actionStatus.textContent = err.message;
      }
    }

    async function clearLog() {
      try {
        const data = await request("/api/logs/clear", {
          method: "POST",
          body: JSON.stringify({})
        });
        stateEls.actionStatus.textContent = data.message;
        await refreshState();
      } catch (err) {
        stateEls.actionStatus.textContent = err.message;
      }
    }

    document.getElementById("save-config").addEventListener("click", saveConfig);
    document.getElementById("reload-config").addEventListener("click", refreshState);
    document.getElementById("test-telegram").addEventListener("click", testTelegram);
    document.getElementById("start-service").addEventListener("click", () => startBot("service"));
    document.getElementById("run-once").addEventListener("click", () => startBot("once"));
    document.getElementById("stop-bot").addEventListener("click", stopBot);
    document.getElementById("clear-log").addEventListener("click", clearLog);
    document.getElementById("toggle-token").addEventListener("click", () => {
      tokenVisible = !tokenVisible;
      stateEls.token.type = tokenVisible ? "text" : "password";
    });

    refreshState();
    setInterval(refreshState, 1500);
  </script>
</body>
</html>
"""


class BotRuntime:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.mode = "-"
        self.status = "Chưa chạy"
        self.logs: deque[str] = deque(maxlen=4000)
        self.python_bin = sys.executable
        self._append_system_log("Web UI sẵn sàng.")

    def _append_system_log(self, message: str) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.lock:
            self.logs.append(f"{now} [SYSTEM] {message}")

    def _effective_env_values(self) -> dict[str, str]:
        values = read_env_file(ENV_PATH)
        return {
            "TELEGRAM_TOKEN": values.get("TELEGRAM_TOKEN", ""),
            "TELEGRAM_CHAT_ID": values.get("TELEGRAM_CHAT_ID", ""),
        }

    def load_config(self) -> dict[str, str]:
        return self._effective_env_values()

    def save_config(self, telegram_token: str, telegram_chat_id: str) -> None:
        values = read_env_file(ENV_PATH)
        values["TELEGRAM_TOKEN"] = telegram_token.strip()
        values["TELEGRAM_CHAT_ID"] = telegram_chat_id.strip()
        write_env_file(ENV_PATH, values)
        self._append_system_log("Đã lưu TELEGRAM_TOKEN và TELEGRAM_CHAT_ID vào .env.")

    def test_telegram(self, telegram_token: str, telegram_chat_id: str) -> None:
        telegram_token = telegram_token.strip()
        telegram_chat_id = telegram_chat_id.strip()
        if not telegram_token or not telegram_chat_id:
            raise RuntimeError("Thiếu TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID.")

        self.save_config(telegram_token, telegram_chat_id)

        message = (
            "TEST TELEGRAM\n\n"
            f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            "Nguon gui: localhost web_ui.py\n"
            "Muc dich: xac nhan bot gui duoc tin nhan."
        )

        try:
            asyncio.run(self._send_test_message(telegram_token, telegram_chat_id, message))
        except Exception as exc:
            self._append_system_log(f"Test Telegram lỗi: {exc}")
            raise RuntimeError(f"Gửi test Telegram thất bại: {exc}") from exc

        self._append_system_log("Đã gửi tin nhắn test Telegram thành công.")

    async def _send_test_message(
        self,
        telegram_token: str,
        telegram_chat_id: str,
        message: str,
    ) -> None:
        bot = Bot(token=telegram_token)
        await bot.send_message(chat_id=telegram_chat_id, text=message)

    def clear_logs(self) -> None:
        with self.lock:
            self.logs.clear()
        self._append_system_log("Log đã được xoá.")

    def snapshot(self) -> dict[str, Any]:
        config = self.load_config()
        with self.lock:
            process = self.process
            running = process is not None and process.poll() is None
            pid = str(process.pid) if running else "-"
            logs = list(self.logs)

        token_present = bool(config["TELEGRAM_TOKEN"].strip())
        chat_present = bool(config["TELEGRAM_CHAT_ID"].strip())
        config_status = (
            "Đã nạp cấu hình Telegram từ .env"
            if token_present and chat_present
            else "Thiếu TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID trong .env"
        )

        return {
            "running": running,
            "status": self.status,
            "pid": pid,
            "mode": self.mode,
            "python": self.python_bin,
            "env_path": str(ENV_PATH),
            "telegram_token": config["TELEGRAM_TOKEN"],
            "telegram_chat_id": config["TELEGRAM_CHAT_ID"],
            "config_status": config_status,
            "logs": logs,
        }

    def start(self, mode: str, telegram_token: str, telegram_chat_id: str) -> None:
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError("Bot đang chạy.")

        telegram_token = telegram_token.strip()
        telegram_chat_id = telegram_chat_id.strip()
        if not telegram_token or not telegram_chat_id:
            raise RuntimeError("Thiếu TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID.")

        self.save_config(telegram_token, telegram_chat_id)

        env = os.environ.copy()
        env["TELEGRAM_TOKEN"] = telegram_token
        env["TELEGRAM_CHAT_ID"] = telegram_chat_id

        cmd = [self.python_bin, str(BOT_PATH)]
        if mode == "once":
            cmd.append("--once")

        process = subprocess.Popen(
            cmd,
            cwd=APP_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        with self.lock:
            self.process = process
            self.mode = mode
            self.status = "Đang chạy"
            self.logs.append(
                f"{datetime.now():%Y-%m-%d %H:%M:%S} [SYSTEM] Khởi chạy: {' '.join(cmd)}"
            )

        threading.Thread(target=self._stream_output, args=(process,), daemon=True).start()
        threading.Thread(target=self._watch_process, args=(process,), daemon=True).start()

    def _stream_output(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            with self.lock:
                self.logs.append(line.rstrip())
        process.stdout.close()

    def _watch_process(self, process: subprocess.Popen[str]) -> None:
        code = process.wait()
        with self.lock:
            if self.process is process:
                self.logs.append(
                    f"{datetime.now():%Y-%m-%d %H:%M:%S} [SYSTEM] Bot đã thoát với mã {code}."
                )
                self.process = None
                self.mode = "-"
                self.status = "Đã dừng"

    def stop(self) -> None:
        with self.lock:
            process = self.process

        if process is None or process.poll() is not None:
            raise RuntimeError("Không có tiến trình bot nào đang chạy.")

        self._append_system_log("Đang gửi tín hiệu dừng bot...")
        process.terminate()

        def force_stop() -> None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._append_system_log("Bot chưa thoát, kill cưỡng bức.")
                process.kill()

        threading.Thread(target=force_stop, daemon=True).start()


runtime = BotRuntime()


class BotRequestHandler(BaseHTTPRequestHandler):
    server_version = "BotLocalUI/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        if self.path == "/":
            self._send_html(HTML_PAGE)
            return
        if self.path == "/api/state":
            self._send_json(runtime.snapshot())
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self._send_json({"error": "JSON body không hợp lệ."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            if self.path == "/api/config":
                runtime.save_config(
                    str(payload.get("telegram_token", "")),
                    str(payload.get("telegram_chat_id", "")),
                )
                self._send_json({"message": "Đã lưu cấu hình Telegram."})
                return

            if self.path == "/api/start":
                runtime.start(
                    str(payload.get("mode", "service")),
                    str(payload.get("telegram_token", "")),
                    str(payload.get("telegram_chat_id", "")),
                )
                self._send_json({"message": "Bot đã được khởi chạy."})
                return

            if self.path == "/api/test-telegram":
                runtime.test_telegram(
                    str(payload.get("telegram_token", "")),
                    str(payload.get("telegram_chat_id", "")),
                )
                self._send_json({"message": "Đã gửi tin nhắn test Telegram."})
                return

            if self.path == "/api/stop":
                runtime.stop()
                self._send_json({"message": "Đã gửi tín hiệu dừng bot."})
                return

            if self.path == "/api/logs/clear":
                runtime.clear_logs()
                self._send_json({"message": "Đã xoá log."})
                return
        except RuntimeError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # pragma: no cover - defensive runtime surface
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), BotRequestHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"Local UI đang chạy tại {url}")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            runtime.stop()
        except RuntimeError:
            pass
        server.server_close()


if __name__ == "__main__":
    main()
