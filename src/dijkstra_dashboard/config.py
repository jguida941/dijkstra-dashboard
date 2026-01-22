import json
import os
from pathlib import Path
from typing import Any, Dict

CONFIG_VERSION = 1
ENV_PREFIX = "DIJKSTRA_DASHBOARD_"

_DEFAULT_CONFIG: Dict[str, Any] = {
    "version": CONFIG_VERSION,
    "theme": "cyberpunk",
    "output_format": "table",
    "steps_mode": "delta",
    "animation_speed": 1.0,
    "directed_default": False,
}


def default_config() -> Dict[str, Any]:
    return dict(_DEFAULT_CONFIG)


def get_config_path() -> Path:
    env_path = os.getenv(f"{ENV_PREFIX}CONFIG")
    if env_path:
        return Path(env_path)

    if os.name == "nt":
        base_dir = os.getenv("APPDATA")
        if not base_dir:
            base_dir = str(Path.home() / "AppData" / "Roaming")
        return Path(base_dir) / "dijkstra-dashboard" / "config.json"

    return Path.home() / ".config" / "dijkstra-dashboard" / "config.json"


def _load_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Config file must be a JSON object.")

    return data


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_config() -> Dict[str, Any]:
    data: Dict[str, Any] = {}

    theme = os.getenv(f"{ENV_PREFIX}THEME")
    if theme:
        data["theme"] = theme

    output_format = os.getenv(f"{ENV_PREFIX}OUTPUT_FORMAT")
    if output_format:
        data["output_format"] = output_format

    steps_mode = os.getenv(f"{ENV_PREFIX}STEPS_MODE")
    if steps_mode:
        data["steps_mode"] = steps_mode

    animation_speed = os.getenv(f"{ENV_PREFIX}ANIMATION_SPEED")
    if animation_speed:
        data["animation_speed"] = float(animation_speed)

    directed_default = os.getenv(f"{ENV_PREFIX}DIRECTED_DEFAULT")
    if directed_default:
        data["directed_default"] = _parse_bool(directed_default)

    return data


def validate_config(config: Dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("Config must be a dictionary.")

    version = config.get("version")
    if version != CONFIG_VERSION:
        raise ValueError(f"Unsupported config version: {version}")

    if not isinstance(config.get("theme"), str):
        raise ValueError("Config theme must be a string.")
    if not isinstance(config.get("output_format"), str):
        raise ValueError("Config output_format must be a string.")
    if not isinstance(config.get("steps_mode"), str):
        raise ValueError("Config steps_mode must be a string.")

    animation_speed = config.get("animation_speed")
    if not isinstance(animation_speed, (int, float)):
        raise ValueError("Config animation_speed must be a number.")

    directed_default = config.get("directed_default")
    if not isinstance(directed_default, bool):
        raise ValueError("Config directed_default must be a bool.")


def load_config(path: Path | None = None) -> Dict[str, Any]:
    config_path = path or get_config_path()
    data = default_config()
    data.update(_load_config_file(config_path))
    validate_config(data)
    return data


def save_config(config: Dict[str, Any], path: Path | None = None) -> None:
    validate_config(config)
    config_path = path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def resolve_config(overrides: Dict[str, Any] | None = None,
                   path: Path | None = None) -> Dict[str, Any]:
    config = load_config(path)
    config.update(env_config())
    if overrides:
        config.update(overrides)
    validate_config(config)
    return config
