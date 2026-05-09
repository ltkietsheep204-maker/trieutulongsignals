from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from env_loader import read_env_file, write_env_file


APP_DIR = Path(__file__).resolve().parent
ENV_PATH = APP_DIR / ".env"
IMAGE_NAME = "trieu-tu-long-signal-bot"
CONTAINER_NAME = "trieu-tu-long-signal-bot-local"


class BotLauncher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Telegram Signal Bot Tool")
        self.root.geometry("1160x760")
        self.root.minsize(960, 620)

        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.build_in_progress = False

        self.status_var = tk.StringVar(value="Chưa chạy")
        self.config_status_var = tk.StringVar(value="Chưa đọc cấu hình")
        self.process_var = tk.StringVar(value="PID: -")
        self.mode_var = tk.StringVar(value="Mode: -")
        self.python_var = tk.StringVar(value=f"Docker CLI: {self._detect_docker_bin()}")
        self.env_var = tk.StringVar(value=f".env: {ENV_PATH}")
        self.token_var = tk.StringVar()
        self.chat_id_var = tk.StringVar()
        self.show_token_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.load_config_to_form(initial=True)
        self.root.after(150, self._flush_logs)
        self.root.after(500, self._poll_process)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        root_frame = ttk.Frame(self.root, padding=16)
        root_frame.pack(fill="both", expand=True)
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(1, weight=1)

        header = ttk.Frame(root_frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Telegram Signal Bot Tool",
            font=("SF Pro Text", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Điều khiển bot local, cấu hình Telegram và theo dõi log realtime.",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        status_bar = ttk.Frame(header)
        status_bar.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Label(status_bar, text="Bot:").grid(row=0, column=0, sticky="e", padx=(0, 6))
        ttk.Label(status_bar, textvariable=self.status_var).grid(row=0, column=1, sticky="w")
        ttk.Label(status_bar, textvariable=self.process_var).grid(row=1, column=1, sticky="w")
        ttk.Label(status_bar, textvariable=self.mode_var).grid(row=2, column=1, sticky="w")

        content = ttk.Panedwindow(root_frame, orient="horizontal")
        content.grid(row=1, column=0, sticky="nsew")

        left_panel = ttk.Frame(content, padding=4)
        right_panel = ttk.Frame(content, padding=4)
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(3, weight=1)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        content.add(left_panel, weight=1)
        content.add(right_panel, weight=2)

        config_frame = ttk.LabelFrame(left_panel, text="Cấu hình Telegram", padding=12)
        config_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        config_frame.columnconfigure(1, weight=1)

        ttk.Label(config_frame, text="Bot Token").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.token_entry = ttk.Entry(
            config_frame,
            textvariable=self.token_var,
            show="*",
        )
        self.token_entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(config_frame, text="Chat ID").grid(row=1, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(config_frame, textvariable=self.chat_id_var).grid(
            row=1, column=1, sticky="ew", pady=(0, 8)
        )

        ttk.Checkbutton(
            config_frame,
            text="Hiện token",
            variable=self.show_token_var,
            command=self._toggle_token_visibility,
        ).grid(row=2, column=1, sticky="w", pady=(0, 10))

        config_actions = ttk.Frame(config_frame)
        config_actions.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(config_actions, text="Lưu cấu hình", command=self.save_config).pack(
            side="left"
        )
        ttk.Button(
            config_actions,
            text="Đọc lại .env",
            command=self.load_config_to_form,
        ).pack(side="left", padx=(8, 0))

        ttk.Label(
            config_frame,
            textvariable=self.config_status_var,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        controls_frame = ttk.LabelFrame(left_panel, text="Điều khiển Bot", padding=12)
        controls_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self.start_service_button = ttk.Button(
            controls_frame,
            text="Start Service",
            command=lambda: self.start_bot("service"),
        )
        self.start_service_button.grid(row=0, column=0, sticky="ew")

        self.run_once_button = ttk.Button(
            controls_frame,
            text="Run Once",
            command=lambda: self.start_bot("once"),
        )
        self.run_once_button.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.stop_button = ttk.Button(
            controls_frame,
            text="Stop",
            command=self.stop_bot,
            state="disabled",
        )
        self.stop_button.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.clear_button = ttk.Button(
            controls_frame,
            text="Clear Log",
            command=self._clear_logs,
        )
        self.clear_button.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)

        runtime_frame = ttk.LabelFrame(left_panel, text="Thông tin Runtime", padding=12)
        runtime_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        runtime_frame.columnconfigure(0, weight=1)

        ttk.Label(runtime_frame, textvariable=self.python_var).grid(row=0, column=0, sticky="w")
        ttk.Label(runtime_frame, textvariable=self.env_var).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Label(runtime_frame, textvariable=self.process_var).grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Label(runtime_frame, textvariable=self.mode_var).grid(
            row=3, column=0, sticky="w", pady=(6, 0)
        )

        notes_frame = ttk.LabelFrame(left_panel, text="Lịch chạy", padding=12)
        notes_frame.grid(row=3, column=0, sticky="nsew")
        notes_frame.columnconfigure(0, weight=1)

        notes = (
            "Service\n"
            "- Quét ngay khi khởi động\n"
            "- Quét 4H vào 00/04/08/12/16/20 UTC\n"
            "- Tổng hợp D1 vào 00:00 UTC\n\n"
            "Run Once\n"
            "- Chạy một vòng rồi thoát\n"
            "- Nếu rơi vào 00:00 UTC sẽ gửi thêm tổng hợp D1"
        )
        ttk.Label(notes_frame, text=notes, justify="left").grid(row=0, column=0, sticky="nw")

        log_header = ttk.Frame(right_panel)
        log_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        log_header.columnconfigure(0, weight=1)
        ttk.Label(
            log_header,
            text="Log Runtime",
            font=("SF Pro Text", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            log_header,
            text="Luồng stdout/stderr của bot sẽ hiển thị ở đây.",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.log_box = scrolledtext.ScrolledText(
            right_panel,
            wrap="word",
            font=("Menlo", 12),
            state="disabled",
            padx=12,
            pady=12,
        )
        self.log_box.grid(row=1, column=0, sticky="nsew")
        self._append_log("Tool sẵn sàng.")

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _append_system_log(self, message: str) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_log(f"{now} [SYSTEM] {message}")

    def _clear_logs(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._append_system_log("Log đã được xoá.")

    def _toggle_token_visibility(self) -> None:
        self.token_entry.configure(show="" if self.show_token_var.get() else "*")

    def load_config_to_form(self, initial: bool = False) -> None:
        env_values = read_env_file(ENV_PATH)
        self.token_var.set(env_values.get("TELEGRAM_TOKEN", ""))
        self.chat_id_var.set(env_values.get("TELEGRAM_CHAT_ID", ""))

        if self.token_var.get().strip() and self.chat_id_var.get().strip():
            self.config_status_var.set("Đã nạp cấu hình Telegram từ .env")
        else:
            self.config_status_var.set("Thiếu TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID trong .env")

        if initial:
            self._append_system_log("Đã nạp cấu hình từ file .env.")
        else:
            self._append_system_log("Đã đọc lại cấu hình từ file .env.")

    def save_config(self) -> None:
        token = self.token_var.get().strip()
        chat_id = self.chat_id_var.get().strip()
        if not token or not chat_id:
            messagebox.showerror(
                "Thiếu cấu hình",
                "Cần nhập đầy đủ TELEGRAM_TOKEN và TELEGRAM_CHAT_ID.",
            )
            return

        values = read_env_file(ENV_PATH)
        values["TELEGRAM_TOKEN"] = token
        values["TELEGRAM_CHAT_ID"] = chat_id
        write_env_file(ENV_PATH, values)
        self.config_status_var.set("Đã lưu cấu hình Telegram vào .env")
        self._append_system_log("Đã lưu cấu hình Telegram vào .env.")

    def _read_effective_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["TELEGRAM_TOKEN"] = self.token_var.get().strip()
        env["TELEGRAM_CHAT_ID"] = self.chat_id_var.get().strip()
        return env

    def _set_process_pid(self, value: str) -> None:
        self.root.after(0, lambda: self.process_var.set(value))

    def _detect_docker_bin(self) -> str:
        return "docker"

    def _docker_available(self) -> bool:
        try:
            check = subprocess.run(
                ["docker", "--version"],
                cwd=APP_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError:
            return False
        return check.returncode == 0

    def _run_command(
        self,
        cmd: list[str],
        *,
        capture_process: bool = False,
    ) -> int:
        self._append_system_log(f"Exec: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            cwd=APP_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if capture_process:
            self.process = process
            self._set_process_pid(f"PID: {process.pid}")

        assert process.stdout is not None
        for line in process.stdout:
            self.log_queue.put(line)
        process.stdout.close()
        return process.wait()

    def _remove_existing_container(self) -> None:
        cleanup_cmd = ["docker", "rm", "-f", CONTAINER_NAME]
        subprocess.run(
            cleanup_cmd,
            cwd=APP_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def _run_docker_lifecycle(self, mode: str) -> None:
        try:
            self.build_in_progress = True
            self._remove_existing_container()

            build_cmd = ["docker", "build", "-t", IMAGE_NAME, "."]
            build_code = self._run_command(build_cmd)
            self.build_in_progress = False
            if build_code != 0:
                self.log_queue.put(
                    f"{datetime.now():%Y-%m-%d %H:%M:%S} [SYSTEM] Docker build failed với mã {build_code}.\n"
                )
                self.process = None
                self._set_process_pid("PID: -")
                return

            run_cmd = [
                "docker",
                "run",
                "--rm",
                "--name",
                CONTAINER_NAME,
                "--env-file",
                str(ENV_PATH),
                IMAGE_NAME,
            ]
            if mode == "once":
                run_cmd.append("--once")

            run_code = self._run_command(run_cmd, capture_process=True)
            self.log_queue.put(
                f"{datetime.now():%Y-%m-%d %H:%M:%S} [SYSTEM] Container đã thoát với mã {run_code}.\n"
            )
            self.process = None
            self._set_process_pid("PID: -")
        except FileNotFoundError:
            self.build_in_progress = False
            self.process = None
            self._set_process_pid("PID: -")
            self.log_queue.put(
                f"{datetime.now():%Y-%m-%d %H:%M:%S} [SYSTEM] Không tìm thấy Docker CLI.\n"
            )

    def _validate_config(self, env: dict[str, str]) -> list[str]:
        missing: list[str] = []
        for key in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"):
            if not env.get(key, "").strip():
                missing.append(key)
        return missing

    def start_bot(self, mode: str) -> None:
        if self.build_in_progress or (self.process and self.process.poll() is None):
            self._append_system_log("Bot đang chạy, bỏ qua lệnh Start.")
            return

        env = self._read_effective_env()
        missing = self._validate_config(env)
        if missing:
            self.status_var.set("Thiếu cấu hình")
            self._append_system_log(
                "Thiếu biến cấu hình trong .env hoặc môi trường: "
                + ", ".join(missing)
            )
            return

        if self.token_var.get().strip() and self.chat_id_var.get().strip():
            self.save_config()

        if not self._docker_available():
            self.status_var.set("Thiếu Docker")
            self._append_system_log("Docker CLI chưa sẵn sàng. Cần mở Docker Desktop trước.")
            return

        self.status_var.set("Đang build/running")
        self.process_var.set("PID: preparing")
        self.mode_var.set(f"Mode: {mode}")
        self.start_service_button.configure(state="disabled")
        self.run_once_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        thread = threading.Thread(
            target=self._run_docker_lifecycle,
            args=(mode,),
            daemon=True,
        )
        thread.start()

    def stop_bot(self) -> None:
        if self.build_in_progress:
            self._append_system_log("Đang build image Docker, chưa thể stop an toàn.")
            return

        process = self.process
        if process is None or process.poll() is not None:
            self._append_system_log("Không có tiến trình bot nào đang chạy.")
            self._mark_stopped()
            return

        self._append_system_log("Đang stop Docker container...")
        subprocess.Popen(
            ["docker", "stop", CONTAINER_NAME],
            cwd=APP_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.root.after(4000, self._force_kill_if_needed)

    def _force_kill_if_needed(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return
        self._append_system_log("Container chưa thoát, force remove.")
        subprocess.run(
            ["docker", "rm", "-f", CONTAINER_NAME],
            cwd=APP_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if process.poll() is None:
            if sys.platform == "win32":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()

    def _mark_stopped(self) -> None:
        self.start_service_button.configure(state="normal")
        self.run_once_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_var.set("Đã dừng")
        self.process_var.set("PID: -")
        self.mode_var.set("Mode: -")

    def _flush_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)
        self.root.after(150, self._flush_logs)

    def _poll_process(self) -> None:
        process = self.process
        if not self.build_in_progress and process is not None and process.poll() is not None:
            code = process.returncode
            self._append_system_log(f"Docker run đã thoát với mã {code}.")
            self.process = None
            self._mark_stopped()
        elif not self.build_in_progress and process is None and self.stop_button["state"] == "normal":
            self._mark_stopped()
        self.root.after(500, self._poll_process)

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            self.stop_bot()
        self.root.after(300, self.root.destroy)


def main() -> None:
    root = tk.Tk()
    BotLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
