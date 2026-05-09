from __future__ import annotations

from pathlib import Path


def read_env_file(path: str | Path) -> dict[str, str]:
    """Đọc file .env đơn giản dạng KEY=VALUE."""
    env_map: dict[str, str] = {}
    env_path = Path(path)
    if not env_path.exists():
        return env_map

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if key.startswith("export "):
            key = key[len("export ") :].strip()

        if key:
            env_map[key] = value

    return env_map


def load_env_file(path: str | Path, override: bool = False) -> dict[str, str]:
    """Nạp các biến từ file .env vào process env."""
    import os

    env_map = read_env_file(path)
    for key, value in env_map.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return env_map


def write_env_file(path: str | Path, values: dict[str, str]) -> None:
    """Ghi file .env đơn giản, mỗi dòng KEY=VALUE."""
    env_path = Path(path)
    lines = [f"{key}={value}" for key, value in values.items()]
    content = "\n".join(lines).rstrip() + "\n"
    env_path.write_text(content, encoding="utf-8")
