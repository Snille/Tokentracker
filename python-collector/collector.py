"""TokenTracker collector: publishes local Codex and Claude Code weekly token
usage to Home Assistant via MQTT discovery.

Standalone port of vscode-extension/src/extension.ts's data-reading logic.
Reads the same on-disk session logs Claude Code / Codex always write
(~/.claude/projects, ~/.codex/sessions), so it works regardless of whether
Claude Code runs via the VS Code extension, the CLI, or the desktop app.
Meant to be invoked periodically (e.g. every minute via Windows Task
Scheduler) rather than run as a long-lived service.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

CONFIG_PATH = Path(__file__).with_name("config.json")
LOG_PATH = Path(__file__).with_name("collector.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")],
)
log = logging.getLogger("tokentracker")

LEGACY_SENSOR_IDS = [
    "codex_tokens_left", "codex_usage_percent", "codex_current_thread_tokens",
    "codex_threads_today", "codex_current_model", "codex_current_thread_title",
    "claude_tokens_left", "claude_usage_percent", "claude_sessions_today",
    "claude_current_project", "total_ai_tokens_today", "total_ai_tokens_left",
    "total_ai_usage_percent", "dominant_tool_today", "collector_status",
    "collector_version", "collector_updated_at", "codex_tokens_today",
    "codex_input_tokens_today", "codex_cached_input_tokens_today",
    "codex_output_tokens_today", "codex_reasoning_output_tokens_today",
    "claude_tokens_today", "claude_input_tokens_today",
    "claude_cache_creation_input_tokens_today", "claude_cache_read_input_tokens_today",
    "claude_output_tokens_today", "codex_tokens_5h", "codex_input_tokens_5h",
    "codex_cached_input_tokens_5h", "codex_output_tokens_5h",
    "codex_reasoning_output_tokens_5h", "claude_tokens_5h", "claude_input_tokens_5h",
    "claude_cache_creation_input_tokens_5h", "claude_cache_read_input_tokens_5h",
    "claude_output_tokens_5h",
]

# `id` is the key in the published JSON state payload (value_template source).
# `object_id` is the Home Assistant entity object_id and MUST match the names
# the original VS Code extension used, because the ESPHome display
# (storstugan-office-token-tracker-128) and existing HA dashboards read those
# `sensor.tokentracker_vs_code_*` entities. Keep the two columns in sync.
SENSORS = [
    {"id": "updated_at_epoch", "object_id": "tokentracker_vs_code_updated_at_epoch", "name": "Updated At Epoch", "unit": "s", "icon": "mdi:clock-check-outline"},
    {"id": "codex_tokens_week", "object_id": "tokentracker_vs_code_codex_tokens_week", "name": "Codex Tokens Week", "unit": "tokens", "icon": "mdi:calendar-week"},
    {"id": "codex_input_tokens_week", "object_id": "tokentracker_vs_code_codex_input_tokens_week", "name": "Codex Input Tokens Week", "unit": "tokens", "icon": "mdi:arrow-down-bold-circle-outline"},
    {"id": "codex_cached_input_tokens_week", "object_id": "tokentracker_vs_code_codex_cached_input_tokens_week", "name": "Codex Cached Input Tokens Week", "unit": "tokens", "icon": "mdi:cached"},
    {"id": "codex_output_tokens_week", "object_id": "tokentracker_vs_code_codex_output_tokens_week", "name": "Codex Output Tokens Week", "unit": "tokens", "icon": "mdi:arrow-up-bold-circle-outline"},
    {"id": "codex_reasoning_output_tokens_week", "object_id": "tokentracker_vs_code_codex_reasoning_output_tokens_week", "name": "Codex Reasoning Output Tokens Week", "unit": "tokens", "icon": "mdi:head-cog-outline"},
    {"id": "codex_5h_used_percent", "object_id": "tokentracker_vs_code_codex_5h_used_percent", "name": "Codex 5h Used Percent", "unit": "%", "icon": "mdi:gauge"},
    {"id": "codex_5h_resets_at", "object_id": "tokentracker_vs_code_codex_5h_resets_at", "name": "Codex 5h Resets At", "unit": "s", "icon": "mdi:timer-sand"},
    {"id": "codex_weekly_used_percent", "object_id": "tokentracker_vs_code_codex_weekly_used_percent", "name": "Codex Weekly Used Percent", "unit": "%", "icon": "mdi:gauge-full"},
    {"id": "codex_weekly_resets_at", "object_id": "tokentracker_vs_code_codex_weekly_resets_at", "name": "Codex Weekly Resets At", "unit": "s", "icon": "mdi:calendar-refresh-outline"},
    {"id": "codex_plan_type", "object_id": "tokentracker_vs_code_codex_plan_type", "name": "Codex Plan Type", "icon": "mdi:card-account-details-outline"},
    {"id": "claude_tokens_week", "object_id": "tokentracker_vs_code_claude_code_tokens_week", "name": "Claude Code Tokens Week", "unit": "tokens", "icon": "mdi:calendar-week"},
    {"id": "claude_input_tokens_week", "object_id": "tokentracker_vs_code_claude_code_input_tokens_week", "name": "Claude Code Input Tokens Week", "unit": "tokens", "icon": "mdi:arrow-down-bold-circle-outline"},
    {"id": "claude_cache_creation_input_tokens_week", "object_id": "tokentracker_vs_code_claude_code_cache_creation_tokens_week", "name": "Claude Code Cache Creation Tokens Week", "unit": "tokens", "icon": "mdi:database-plus-outline"},
    {"id": "claude_cache_read_input_tokens_week", "object_id": "tokentracker_vs_code_claude_code_cache_read_tokens_week", "name": "Claude Code Cache Read Tokens Week", "unit": "tokens", "icon": "mdi:database-eye-outline"},
    {"id": "claude_output_tokens_week", "object_id": "tokentracker_vs_code_claude_code_output_tokens_week", "name": "Claude Code Output Tokens Week", "unit": "tokens", "icon": "mdi:arrow-up-bold-circle-outline"},
]


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def week_start_ms(now: datetime | None = None) -> float:
    now = now or datetime.now()
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.timestamp() * 1000


def numeric(value) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def parse_timestamp_ms(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value if value > 10_000_000_000 else value * 1000
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000
        except ValueError:
            return None
    return None


def event_timestamp_ms(event) -> float | None:
    if not isinstance(event, dict):
        return None
    for key in ("timestamp", "created_at", "createdAt", "time"):
        parsed = parse_timestamp_ms(event.get(key))
        if parsed is not None:
            return parsed
    message = event.get("message")
    if isinstance(message, dict):
        return event_timestamp_ms(message)
    return None


def walk_files(root: Path, suffix: str):
    if not root.exists():
        return
    for path in root.rglob(f"*{suffix}"):
        if path.is_file():
            yield path


def has_usable_rate_limits(rate_limits) -> bool:
    if not isinstance(rate_limits, dict):
        return False
    return bool(rate_limits.get("primary")) or bool(rate_limits.get("secondary"))


def rate_limits_to_payload(rate_limits) -> dict:
    rate_limits = rate_limits or {}
    primary = rate_limits.get("primary") or {}
    secondary = rate_limits.get("secondary") or {}
    return {
        "codex_5h_used_percent": numeric(primary.get("used_percent")),
        "codex_5h_resets_at": numeric(primary.get("resets_at")),
        "codex_weekly_used_percent": numeric(secondary.get("used_percent")),
        "codex_weekly_resets_at": numeric(secondary.get("resets_at")),
        "codex_plan_type": rate_limits.get("plan_type") if isinstance(rate_limits.get("plan_type"), str) else "",
    }


def codex_usage_delta(current: dict, previous: dict | None) -> dict:
    def non_negative_delta(cur, prev):
        cur_v = numeric(cur)
        if prev is None:
            return cur_v
        prev_v = numeric(prev)
        delta = cur_v - prev_v
        return delta if delta >= 0 else cur_v

    delta = {
        "input_tokens": non_negative_delta(current.get("input_tokens"), previous.get("input_tokens") if previous else None),
        "cached_input_tokens": non_negative_delta(current.get("cached_input_tokens"), previous.get("cached_input_tokens") if previous else None),
        "output_tokens": non_negative_delta(current.get("output_tokens"), previous.get("output_tokens") if previous else None),
        "reasoning_output_tokens": non_negative_delta(current.get("reasoning_output_tokens"), previous.get("reasoning_output_tokens") if previous else None),
        "total_tokens": non_negative_delta(current.get("total_tokens"), previous.get("total_tokens") if previous else None),
    }
    if numeric(delta["total_tokens"]) <= 0:
        delta["total_tokens"] = (
            numeric(delta["input_tokens"]) + numeric(delta["cached_input_tokens"])
            + numeric(delta["output_tokens"]) + numeric(delta["reasoning_output_tokens"])
        )
    return delta


def add_into(target: dict, addition: dict, keys) -> None:
    for key in keys:
        target[key] = numeric(target.get(key)) + numeric(addition.get(key))


CODEX_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def read_codex_session_usage(week_start: float) -> dict:
    sessions_path = Path.home() / ".codex" / "sessions"
    week_bucket: dict = {}
    latest_rate_limits: tuple[dict, float] | None = None

    for file_path in walk_files(sessions_path, ".jsonl"):
        if not file_path.name.startswith("rollout-"):
            continue
        mtime_ms = file_path.stat().st_mtime * 1000
        if mtime_ms >= week_start:
            previous_usage = None
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = event.get("payload") if isinstance(event, dict) else None
                    if not isinstance(payload, dict) or payload.get("type") != "token_count":
                        continue
                    ts = event_timestamp_ms(event) or mtime_ms
                    rate_limits = payload.get("rate_limits")
                    if has_usable_rate_limits(rate_limits) and (latest_rate_limits is None or ts >= latest_rate_limits[1]):
                        latest_rate_limits = (rate_limits, ts)
                    current_usage = (payload.get("info") or {}).get("total_token_usage")
                    if not current_usage:
                        continue
                    delta = codex_usage_delta(current_usage, previous_usage)
                    previous_usage = current_usage
                    if ts >= week_start:
                        add_into(week_bucket, delta, CODEX_KEYS)
        else:
            if latest_rate_limits is None or mtime_ms > latest_rate_limits[1]:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        payload = event.get("payload") if isinstance(event, dict) else None
                        if not isinstance(payload, dict) or payload.get("type") != "token_count":
                            continue
                        rate_limits = payload.get("rate_limits")
                        if not has_usable_rate_limits(rate_limits):
                            continue
                        ts = event_timestamp_ms(event) or mtime_ms
                        if latest_rate_limits is None or ts >= latest_rate_limits[1]:
                            latest_rate_limits = (rate_limits, ts)

    result = {
        "codex_tokens_week": numeric(week_bucket.get("total_tokens")),
        "codex_input_tokens_week": numeric(week_bucket.get("input_tokens")),
        "codex_cached_input_tokens_week": numeric(week_bucket.get("cached_input_tokens")),
        "codex_output_tokens_week": numeric(week_bucket.get("output_tokens")),
        "codex_reasoning_output_tokens_week": numeric(week_bucket.get("reasoning_output_tokens")),
    }
    result.update(rate_limits_to_payload(latest_rate_limits[0] if latest_rate_limits else None))
    return result


def empty_codex_usage() -> dict:
    return {
        "codex_tokens_week": 0, "codex_input_tokens_week": 0, "codex_cached_input_tokens_week": 0,
        "codex_output_tokens_week": 0, "codex_reasoning_output_tokens_week": 0,
        "codex_5h_used_percent": 0, "codex_5h_resets_at": 0,
        "codex_weekly_used_percent": 0, "codex_weekly_resets_at": 0, "codex_plan_type": "",
    }


def read_codex_usage() -> dict:
    week_start = week_start_ms()
    try:
        session_usage = read_codex_session_usage(week_start)
    except OSError:
        return empty_codex_usage()

    if session_usage["codex_tokens_week"] > 0:
        return session_usage

    db_path = Path.home() / ".codex" / "state_5.sqlite"
    if not db_path.exists():
        return session_usage

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(
                "select tokens_used from threads where updated_at >= ?",
                (int(week_start / 1000),),
            )
            tokens_week = sum(row[0] or 0 for row in cur.fetchall())
        finally:
            conn.close()
    except sqlite3.Error:
        return session_usage

    session_usage["codex_tokens_week"] = tokens_week
    return session_usage


def find_usage_objects(value, found=None) -> list:
    if found is None:
        found = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            usage = item.get("usage")
            if isinstance(usage, dict):
                found.append(usage)
            for child in item.values():
                if isinstance(child, (dict, list)):
                    stack.append(child)
    return found


CLAUDE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def read_claude_usage() -> dict:
    projects_path = Path.home() / ".claude" / "projects"
    week_bucket = {key: 0 for key in CLAUDE_KEYS}
    if not projects_path.exists():
        return _claude_payload(week_bucket)

    week_start = week_start_ms()
    for file_path in walk_files(projects_path, ".jsonl"):
        try:
            mtime_ms = file_path.stat().st_mtime * 1000
        except OSError:
            continue
        if mtime_ms < week_start:
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = event_timestamp_ms(event) or mtime_ms
            if ts < week_start:
                continue
            for usage in find_usage_objects(event):
                add_into(week_bucket, usage, CLAUDE_KEYS)

    return _claude_payload(week_bucket)


def _claude_payload(bucket: dict) -> dict:
    total = sum(numeric(bucket.get(key)) for key in CLAUDE_KEYS)
    return {
        "claude_tokens_week": total,
        "claude_input_tokens_week": numeric(bucket.get("input_tokens")),
        "claude_cache_creation_input_tokens_week": numeric(bucket.get("cache_creation_input_tokens")),
        "claude_cache_read_input_tokens_week": numeric(bucket.get("cache_read_input_tokens")),
        "claude_output_tokens_week": numeric(bucket.get("output_tokens")),
    }


def build_payload(config: dict) -> dict:
    now = datetime.now().astimezone()
    payload = {
        "updated_at": now.isoformat(),
        "updated_at_epoch": int(now.timestamp()),
    }
    if config.get("codex_enabled", True):
        try:
            payload.update(read_codex_usage())
        except Exception as error:  # noqa: BLE001 - best-effort collector, mirrors extension.ts behaviour
            log.error("Codex read failed: %s", error)
            payload.update(empty_codex_usage())
    if config.get("claude_enabled", True):
        try:
            payload.update(read_claude_usage())
        except Exception as error:  # noqa: BLE001
            log.error("Claude read failed: %s", error)
            payload.update(_claude_payload({key: 0 for key in CLAUDE_KEYS}))
    return payload


def discovery_payload(sensor: dict, state_topic: str) -> dict:
    object_id = sensor["object_id"]
    return {
        "name": sensor["name"],
        "unique_id": object_id,
        "object_id": object_id,
        "state_topic": state_topic,
        "value_template": sensor.get("value_template", f"{{{{ value_json.{sensor['id']} }}}}"),
        "unit_of_measurement": sensor.get("unit"),
        "icon": sensor.get("icon"),
        "device": {
            "identifiers": ["tokentracker_vscode"],
            "name": "TokenTracker",
            "manufacturer": "Snille",
            "model": "Python MQTT Collector",
        },
    }


def main() -> None:
    config = load_config()
    mqtt_cfg = config["mqtt"]
    parsed = urlparse(mqtt_cfg["url"])
    discovery_prefix = mqtt_cfg.get("discovery_prefix", "homeassistant")
    state_prefix = mqtt_cfg.get("state_prefix", "tokentracker")
    state_topic = f"{state_prefix}/state"

    payload = build_payload(config)

    client = mqtt.Client(client_id=f"tokentracker-python-{os.environ.get('COMPUTERNAME', 'host')}")
    if mqtt_cfg.get("username"):
        client.username_pw_set(mqtt_cfg["username"], mqtt_cfg.get("password") or None)
    client.connect(parsed.hostname, parsed.port or 1883, keepalive=30)
    client.loop_start()
    try:
        for sensor in SENSORS:
            topic = f"{discovery_prefix}/sensor/{sensor['object_id']}/config"
            client.publish(topic, json.dumps(discovery_payload(sensor, state_topic)), qos=0, retain=True)
        client.publish(state_topic, json.dumps(payload), qos=0, retain=True)
        time.sleep(1.5)  # let the loop thread flush publishes before disconnecting
    finally:
        client.loop_stop()
        client.disconnect()

    log.info("Published: %s", payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - last-resort log so a hidden/pythonw run isn't silent
        log.exception("Collector run failed")
        raise
