"""TokenTracker collector: publishes local Codex, Claude Code and rtk token
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
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

CONFIG_PATH = Path(__file__).with_name("config.json")
LOG_PATH = Path(__file__).with_name("collector.log")

# Real Claude subscription rate limits (the numbers `/usage` and the Claude Code
# statusline show) come from an authenticated endpoint, NOT the session logs. This
# is the same source Claude Code itself uses (its `fetchUtilization`). Querying it
# directly makes the % fully headless — no statusline, no terminal session, works
# regardless of whether Claude Code runs via the desktop app, CLI, or not at all.
# Claude Code's live credentials, refreshed in place whenever the CLI runs. This
# is the runtime copy and the primary source.
CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
# Fallback: the canonical copy in the central secret store, per the house rule
# that every credential has a verified copy under C:\Users\eripet\Coding\_secrets_.
#   SECRET_REF: C:\Users\eripet\Coding\_secrets_\claude-code\.credentials.json
# The runtime file gets blanked (accessToken set to "") when the CLI login is
# dropped, which is exactly when the fallback earns its keep. It is a backup, not
# a live source, so its token expires like any other -- it buys a diagnosable
# error instead of silence, not immunity from re-login.
CANONICAL_CREDENTIALS_PATH = (
    Path.home() / "Coding" / "_secrets_" / "claude-code" / ".credentials.json"
)
RATE_LIMIT_CACHE_PATH = Path.home() / ".claude" / "claude_rate_limits.json"
OAUTH_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

# Home Assistant caps a sensor's state at 255 characters; anything longer is
# rejected outright, so the problem sensor truncates rather than losing the state.
MAX_STATE_LENGTH = 255
# The ESPHome display builds its fonts with an explicit glyph list, and a
# character outside it renders as nothing -- silently eating part of the message.
# Problem text is therefore reduced to this set, which mirrors the `glyphs:` line
# in storstugan-office-token-tracker-128.yaml. Keep the two in step.
DISPLAY_GLYPHS = set(
    "!%()+,-_.:/0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ"
    "abcdefghijklmnopqrstuvwxyzåäö"
    "$€ "
)
# Separator between problems. Space-slash-space is in the glyph set; the more
# obvious "|" is not.
PROBLEM_SEPARATOR = " / "
# What the problem sensor reads when there is nothing wrong. An empty string would
# land in Home Assistant as `unknown`, which is indistinguishable from a collector
# that never ran -- exactly the confusion these sensors exist to remove.
NO_PROBLEM = "OK"

# /api/oauth/usage is asked on every run, once a minute. It answers HTTP 429 most
# of the time at that rate, but measured over two days of logs it still lets
# 23-43% of requests through, so a refresh lands every few minutes -- better
# freshness than any slower fixed interval would give, since a rarer request is
# not a likelier one. The 429s are therefore expected noise covered by the cache,
# and are logged at INFO; anything else stays a warning.

# How long a cached response may keep being republished before the log starts
# saying so. Past this the sensors are showing yesterday's numbers, which looks
# identical to "nothing is happening" from Home Assistant.
OAUTH_USAGE_STALE_SECONDS = 3600

# rtk (https://github.com/rtk-ai/rtk) keeps its own lifetime savings stats and
# exposes them as JSON, so reading it is a plain CLI call rather than a log walk.
# `--all` adds the daily/weekly/monthly breakdowns on top of the lifetime summary.
RTK_GAIN_ARGS = ("gain", "--all", "--format", "json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")],
)
log = logging.getLogger("tokentracker")

# `id` is the key in the published JSON state payload (value_template source).
# `object_id` is the MQTT discovery object_id.
#
# Note that Home Assistant does NOT derive the entity_id from `object_id` here:
# it slugs the device name plus the sensor's `name`, so this table's `name`
# column is what actually determines the entity IDs the display subscribes to.
# `tokentracker_rtk_input_tokens_total` below, for example, surfaces as
# `sensor.tokentracker_rtk_raw_tokens_total`. Check the real entity ID in Home
# Assistant before pointing a display at a newly added sensor.
#
# `group` marks the rtk rows as optional: main() only publishes their discovery
# configs when rtk is actually installed.
SENSORS = [
    {"id": "updated_at_epoch", "object_id": "tokentracker_vs_code_updated_at_epoch", "name": "Updated At Epoch", "unit": "s", "icon": "mdi:clock-check-outline"},
    # Collector health. `Status` is the one to drive an icon or colour from
    # (ok/degraded/error); `Problem` carries the text to show, already ordered so
    # the problem needing a human comes first.
    {"id": "collector_status", "object_id": "tokentracker_status", "name": "Status", "icon": "mdi:heart-pulse"},
    {"id": "collector_problem", "object_id": "tokentracker_problem", "name": "Problem", "icon": "mdi:alert-circle-outline"},
    {"id": "collector_problem_count", "object_id": "tokentracker_problem_count", "name": "Problem Count", "unit": "problems", "icon": "mdi:counter"},
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
    {"id": "claude_5h_used_percent", "object_id": "tokentracker_vs_code_claude_code_5h_used_percent", "name": "Claude Code 5h Used Percent", "unit": "%", "icon": "mdi:gauge"},
    {"id": "claude_5h_resets_at", "object_id": "tokentracker_vs_code_claude_code_5h_resets_at", "name": "Claude Code 5h Resets At", "unit": "s", "icon": "mdi:timer-sand"},
    {"id": "claude_weekly_used_percent", "object_id": "tokentracker_vs_code_claude_code_weekly_used_percent", "name": "Claude Code Weekly Used Percent", "unit": "%", "icon": "mdi:gauge-full"},
    {"id": "claude_weekly_resets_at", "object_id": "tokentracker_vs_code_claude_code_weekly_resets_at", "name": "Claude Code Weekly Resets At", "unit": "s", "icon": "mdi:calendar-refresh-outline"},
    {"group": "rtk", "id": "rtk_saved_tokens_total", "object_id": "tokentracker_rtk_saved_tokens_total", "name": "RTK Saved Tokens Total", "unit": "tokens", "icon": "mdi:content-save-cog-outline"},
    {"group": "rtk", "id": "rtk_saved_tokens_today", "object_id": "tokentracker_rtk_saved_tokens_today", "name": "RTK Saved Tokens Today", "unit": "tokens", "icon": "mdi:calendar-today"},
    {"group": "rtk", "id": "rtk_saved_tokens_week", "object_id": "tokentracker_rtk_saved_tokens_week", "name": "RTK Saved Tokens Week", "unit": "tokens", "icon": "mdi:calendar-week"},
    {"group": "rtk", "id": "rtk_saved_percent_total", "object_id": "tokentracker_rtk_saved_percent_total", "name": "RTK Saved Percent Total", "unit": "%", "icon": "mdi:gauge"},
    {"group": "rtk", "id": "rtk_saved_percent_today", "object_id": "tokentracker_rtk_saved_percent_today", "name": "RTK Saved Percent Today", "unit": "%", "icon": "mdi:gauge"},
    {"group": "rtk", "id": "rtk_saved_percent_week", "object_id": "tokentracker_rtk_saved_percent_week", "name": "RTK Saved Percent Week", "unit": "%", "icon": "mdi:gauge-full"},
    {"group": "rtk", "id": "rtk_commands_total", "object_id": "tokentracker_rtk_commands_total", "name": "RTK Commands Total", "unit": "commands", "icon": "mdi:console"},
    {"group": "rtk", "id": "rtk_commands_today", "object_id": "tokentracker_rtk_commands_today", "name": "RTK Commands Today", "unit": "commands", "icon": "mdi:console"},
    {"group": "rtk", "id": "rtk_commands_week", "object_id": "tokentracker_rtk_commands_week", "name": "RTK Commands Week", "unit": "commands", "icon": "mdi:console"},
    {"group": "rtk", "id": "rtk_input_tokens_total", "object_id": "tokentracker_rtk_input_tokens_total", "name": "RTK Raw Tokens Total", "unit": "tokens", "icon": "mdi:arrow-down-bold-circle-outline"},
    {"group": "rtk", "id": "rtk_output_tokens_total", "object_id": "tokentracker_rtk_output_tokens_total", "name": "RTK Filtered Tokens Total", "unit": "tokens", "icon": "mdi:arrow-up-bold-circle-outline"},
]


# Problems found during one run, oldest first. Collected rather than only logged,
# so Home Assistant can show what is wrong and what to do about it: a frozen
# sensor is otherwise indistinguishable from a quiet one, which is what let a
# dropped Claude login sit unnoticed for nine hours.
PROBLEMS: list[tuple[str, str]] = []


def display_safe(text: str) -> str:
    """`text` reduced to characters the display can actually draw.

    Anything outside the font's glyph list becomes a space, and runs of spaces
    collapse, so a stray backtick or an exception's punctuation cannot silently
    swallow part of the message on the screen.
    """
    cleaned = "".join(ch if ch in DISPLAY_GLYPHS else " " for ch in text)
    return " ".join(cleaned.split())


def report_problem(severity: str, text: str) -> None:
    """Register a short, user-facing problem for the status sensors.

    `severity` is "error" (something needs a human) or "warn" (degraded but
    self-healing). `text` should name the fix, not just the symptom -- it is what
    the display will show. Duplicates are dropped so one run reports each distinct
    problem once.
    """
    entry = (severity, display_safe(text))
    if entry not in PROBLEMS:
        PROBLEMS.append(entry)


def status_payload() -> dict:
    """The three status sensors, derived from whatever `PROBLEMS` holds."""
    if not PROBLEMS:
        return {
            "collector_status": "ok",
            "collector_problem": NO_PROBLEM,
            "collector_problem_count": 0,
        }
    # Errors first: with several problems at once, the one needing a human should
    # be the one the display has room for.
    ordered = [text for severity, text in PROBLEMS if severity == "error"]
    ordered += [text for severity, text in PROBLEMS if severity != "error"]
    return {
        "collector_status": "error" if any(s == "error" for s, _ in PROBLEMS) else "degraded",
        "collector_problem": PROBLEM_SEPARATOR.join(ordered)[:MAX_STATE_LENGTH],
        "collector_problem_count": len(PROBLEMS),
    }


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


# A window this long or shorter is the short (5h) limit; anything longer is the
# weekly one. Real values seen are 300 minutes (5h) and 10080 (7 days), so the
# threshold sits far from both.
CODEX_SHORT_WINDOW_MAX_MINUTES = 720


def rate_limits_to_payload(rate_limits) -> dict:
    """Map Codex's `primary`/`secondary` rate-limit windows onto the sensors.

    Which window lands in which slot depends on the plan, so position cannot be
    trusted: an individual plan sends the 5h window as `primary` and the weekly as
    `secondary`, but a team plan sends a single *weekly* window as `primary` and
    leaves `secondary` null. Reading by position filed team weekly usage under the
    5h sensor and left the weekly sensor stuck at 0. Classify each window by its
    own `window_minutes` instead, falling back to the positional guess only when
    the field is absent.
    """
    rate_limits = rate_limits or {}
    plan_type = rate_limits.get("plan_type")
    payload = {
        "codex_5h_used_percent": 0,
        "codex_5h_resets_at": 0,
        "codex_weekly_used_percent": 0,
        "codex_weekly_resets_at": 0,
        "codex_plan_type": plan_type if isinstance(plan_type, str) else "",
    }
    for slot, positional in (("primary", "5h"), ("secondary", "weekly")):
        window = rate_limits.get(slot)
        if not isinstance(window, dict):
            continue
        minutes = numeric(window.get("window_minutes"))
        if minutes:
            key = "5h" if minutes <= CODEX_SHORT_WINDOW_MAX_MINUTES else "weekly"
        else:
            key = positional
        payload[f"codex_{key}_used_percent"] = numeric(window.get("used_percent"))
        payload[f"codex_{key}_resets_at"] = numeric(window.get("resets_at"))
    return payload


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
# Keys that count toward the headline `claude_tokens_week` total. Cache-read is
# deliberately excluded: it dwarfs everything else (often >95% of the raw sum)
# and cache reads are billed at ~0.1x, so including them at full weight makes the
# total meaningless for the display's usage gauge. It is still collected into its
# own `claude_cache_read_input_tokens_week` sensor below.
CLAUDE_TOTAL_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens")


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
    total = sum(numeric(bucket.get(key)) for key in CLAUDE_TOTAL_KEYS)
    return {
        "claude_tokens_week": total,
        "claude_input_tokens_week": numeric(bucket.get("input_tokens")),
        "claude_cache_creation_input_tokens_week": numeric(bucket.get("cache_creation_input_tokens")),
        "claude_cache_read_input_tokens_week": numeric(bucket.get("cache_read_input_tokens")),
        "claude_output_tokens_week": numeric(bucket.get("output_tokens")),
    }


def empty_claude_rate_limits() -> dict:
    return {
        "claude_5h_used_percent": 0, "claude_5h_resets_at": 0,
        "claude_weekly_used_percent": 0, "claude_weekly_resets_at": 0,
    }


def _iso_to_epoch(value) -> float:
    if not isinstance(value, str) or not value.strip():
        return 0
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def _token_from(path: Path) -> str | None:
    """The `claudeAiOauth.accessToken` in one credentials file, or None.

    A blank `accessToken` is a real state, not just a missing file: Claude Code
    rewrites the credentials file with empty token strings when the CLI login is
    dropped, keeping the surrounding metadata. That case used to return None
    silently, so the collector went on republishing a stale cache with nothing in
    the log to say why -- indistinguishable from a healthy run.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        return None
    except json.JSONDecodeError as error:
        log.warning("Claude credentials at %s are not valid JSON: %s", path, error)
        return None
    token = (data.get("claudeAiOauth") or {}).get("accessToken")
    return token if isinstance(token, str) and token else None


def _oauth_access_token() -> str | None:
    """The OAuth access token to authenticate /api/oauth/usage with, or None.

    Prefers the live credentials Claude Code maintains; falls back to the
    canonical copy in the central secret store. Exhausting both is logged, since
    it means the rate-limit sensors are about to freeze.
    """
    for path in (CREDENTIALS_PATH, CANONICAL_CREDENTIALS_PATH):
        token = _token_from(path)
        if token:
            if path is CANONICAL_CREDENTIALS_PATH:
                log.info("using canonical credentials copy: %s", path)
                report_problem("warn", "Claude: using backup credentials, refresh _secrets_ copy")
            return token
    log.warning(
        "no usable Claude accessToken in %s or %s -- rate-limit percentages stay "
        "frozen until the Claude Code CLI is logged in again (run `claude` in a "
        "terminal, then /login)",
        CREDENTIALS_PATH,
        CANONICAL_CREDENTIALS_PATH,
    )
    report_problem("error", "Claude login lost: run claude then /login")
    return None


def fetch_claude_oauth_usage() -> dict | None:
    """GET /api/oauth/usage for the real subscription rate limits. Returns None on
    any failure (missing/expired token, offline) so the caller can fall back to the
    last cached value. The endpoint reports `utilization` (percent) and an ISO-8601
    `resets_at`; we map those to the percent + epoch the display already expects."""
    token = _oauth_access_token()
    if not token:
        return None
    req = urllib.request.Request(
        OAUTH_USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as error:
        # 429 is the normal cost of asking every minute; the cache covers it and
        # the next run usually gets through. Keeping it out of WARNING is what
        # makes a real 401 visible instead of buried in hundreds of look-alikes.
        log.log(
            logging.INFO if error.code == 429 else logging.WARNING,
            "oauth/usage fetch failed: %s",
            error,
        )
        return None
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
        log.warning("oauth/usage fetch failed: %s", error)
        return None
    five = body.get("five_hour") or {}
    seven = body.get("seven_day") or {}
    return {
        "claude_5h_used_percent": numeric(five.get("utilization")),
        "claude_5h_resets_at": _iso_to_epoch(five.get("resets_at")),
        "claude_weekly_used_percent": numeric(seven.get("utilization")),
        "claude_weekly_resets_at": _iso_to_epoch(seven.get("resets_at")),
    }


def _read_rate_limit_cache() -> tuple[dict, float]:
    """The cached `/api/oauth/usage` response and the epoch it was fetched at.

    Returns `({}, 0)` when there is no usable cache. Caches written before
    `fetched_at` existed report age 0, so they are treated as stale and refetched.
    """
    try:
        with open(RATE_LIMIT_CACHE_PATH, "r", encoding="utf-8") as f:
            cached = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}, 0
    if not isinstance(cached, dict):
        return {}, 0
    return cached, numeric(cached.get("fetched_at"))


def read_claude_rate_limits() -> dict:
    """Real Claude subscription rate-limit % for the display. Primary source is the
    authenticated `/api/oauth/usage` endpoint (headless — no statusline/terminal).

    The endpoint is asked on every run. On failure (rate-limited, or the token
    expired or was cleared while Claude Code sat idle, or offline) the last cached
    response is served so the display holds the last known value instead of
    dropping to 0. A cache that keeps being served past
    `OAUTH_USAGE_STALE_SECONDS` is logged, because frozen sensors otherwise look
    exactly like a healthy collector from Home Assistant's side.
    """
    cached, fetched_at = _read_rate_limit_cache()
    now = datetime.now().timestamp()
    age = now - fetched_at if fetched_at else None

    fresh = fetch_claude_oauth_usage()
    if fresh is not None:
        try:
            RATE_LIMIT_CACHE_PATH.write_text(
                json.dumps({**fresh, "fetched_at": int(now)}), encoding="utf-8"
            )
        except OSError as error:
            log.warning("could not write rate-limit cache: %s", error)
        return fresh

    if not cached:
        log.warning("no cached rate limits to fall back on; publishing zeroes")
        report_problem("error", "Claude usage % unavailable and never cached")
        return empty_claude_rate_limits()
    if age is None or age > OAUTH_USAGE_STALE_SECONDS:
        when = (
            datetime.fromtimestamp(fetched_at).isoformat(timespec="seconds")
            if fetched_at else "unknown"
        )
        log.warning(
            "serving stale Claude rate limits (last refreshed %s); the %% sensors "
            "are frozen until a fetch succeeds",
            when,
        )
        hours = int(age // 3600) if age else None
        report_problem(
            "warn",
            f"Claude usage % frozen for {hours}h" if hours else "Claude usage % frozen",
        )
    return {key: numeric(cached.get(key)) for key in empty_claude_rate_limits()}


def empty_rtk_usage() -> dict:
    return {
        "rtk_saved_tokens_total": 0, "rtk_saved_tokens_today": 0, "rtk_saved_tokens_week": 0,
        "rtk_saved_percent_total": 0, "rtk_saved_percent_today": 0, "rtk_saved_percent_week": 0,
        "rtk_commands_total": 0, "rtk_commands_today": 0, "rtk_commands_week": 0,
        "rtk_input_tokens_total": 0, "rtk_output_tokens_total": 0,
    }


def rtk_binary(config: dict) -> str | None:
    """Resolved path to the rtk executable, or None when rtk is disabled or not
    installed. Absence is not an error: rtk is an optional extra, so the collector
    simply omits its sensors instead of publishing a row of zeroes."""
    if not config.get("rtk_enabled", True):
        return None
    return shutil.which(config.get("rtk_command", "rtk"))


def read_rtk_usage(binary: str) -> dict:
    """Token savings reported by `rtk gain --all --format json`.

    The summary block is lifetime; `daily`/`weekly` only contain buckets that saw
    activity, so a missing row for today genuinely means zero commands today. rtk
    counts a week as Monday-Sunday, matching this collector's own week windows.
    """
    completed = subprocess.run(
        [binary, *RTK_GAIN_ARGS],
        capture_output=True,
        text=True,
        # rtk writes UTF-8; without this Python would decode using the Windows
        # ANSI code page and mangle any non-ASCII path in the output.
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        # The scheduled task runs under pythonw.exe precisely to avoid console
        # windows, so don't let the child pop one up every minute. The flag only
        # exists on Windows; everywhere else this is a no-op 0.
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        log.warning("rtk gain exited %d: %s", completed.returncode, completed.stderr.strip())
        report_problem("warn", f"rtk gain exited {completed.returncode}")
        return empty_rtk_usage()

    report = json.loads(completed.stdout)
    summary = report.get("summary") or {}
    today = datetime.now().strftime("%Y-%m-%d")
    daily = next((row for row in report.get("daily") or [] if row.get("date") == today), {})
    # ISO dates compare correctly as plain strings, so no parsing is needed to find
    # the week bucket that contains today.
    weekly = next(
        (
            row for row in report.get("weekly") or []
            if str(row.get("week_start", "")) <= today <= str(row.get("week_end", ""))
        ),
        {},
    )

    return {
        "rtk_saved_tokens_total": numeric(summary.get("total_saved")),
        "rtk_saved_tokens_today": numeric(daily.get("saved_tokens")),
        "rtk_saved_tokens_week": numeric(weekly.get("saved_tokens")),
        "rtk_saved_percent_total": round(numeric(summary.get("avg_savings_pct")), 1),
        "rtk_saved_percent_today": round(numeric(daily.get("savings_pct")), 1),
        "rtk_saved_percent_week": round(numeric(weekly.get("savings_pct")), 1),
        "rtk_commands_total": numeric(summary.get("total_commands")),
        "rtk_commands_today": numeric(daily.get("commands")),
        "rtk_commands_week": numeric(weekly.get("commands")),
        "rtk_input_tokens_total": numeric(summary.get("total_input")),
        "rtk_output_tokens_total": numeric(summary.get("total_output")),
    }


def build_payload(config: dict, rtk_bin: str | None) -> dict:
    PROBLEMS.clear()
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
            report_problem("error", f"Codex read failed: {error}")
            payload.update(empty_codex_usage())
    if config.get("claude_enabled", True):
        try:
            payload.update(read_claude_usage())
        except Exception as error:  # noqa: BLE001
            log.error("Claude read failed: %s", error)
            report_problem("error", f"Claude token read failed: {error}")
            payload.update(_claude_payload({key: 0 for key in CLAUDE_KEYS}))
        try:
            payload.update(read_claude_rate_limits())
        except Exception as error:  # noqa: BLE001
            log.error("Claude rate-limit read failed: %s", error)
            report_problem("error", f"Claude usage read failed: {error}")
            payload.update(empty_claude_rate_limits())
    if rtk_bin:
        try:
            payload.update(read_rtk_usage(rtk_bin))
        except Exception as error:  # noqa: BLE001
            log.error("rtk read failed: %s", error)
            report_problem("warn", f"rtk read failed: {error}")
            payload.update(empty_rtk_usage())
    # Last, so it reflects every problem the reads above found.
    payload.update(status_payload())
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

    rtk_bin = rtk_binary(config)
    payload = build_payload(config, rtk_bin)
    # Skip the rtk discovery configs entirely when rtk is not in use, so those
    # entities never show up as permanently-zero sensors in Home Assistant.
    sensors = [sensor for sensor in SENSORS if sensor.get("group") != "rtk" or rtk_bin]

    client = mqtt.Client(client_id=f"tokentracker-python-{os.environ.get('COMPUTERNAME', 'host')}")
    if mqtt_cfg.get("username"):
        client.username_pw_set(mqtt_cfg["username"], mqtt_cfg.get("password") or None)
    client.connect(parsed.hostname, parsed.port or 1883, keepalive=30)
    client.loop_start()
    try:
        for sensor in sensors:
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
