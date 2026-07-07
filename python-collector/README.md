# TokenTracker Python Collector

Version: 1.0.0

Standalone alternative to `vscode-extension/`. Publishes the same local Codex
and Claude Code weekly token counters to Home Assistant via MQTT discovery,
but as a plain Python script instead of a VS Code extension, so it keeps
running whether Claude Code / Codex are used through VS Code, a CLI, or a
desktop app. Pick **one** of the two collectors, not both (running both at
once is harmless — they publish to the same retained topics — but redundant).

It publishes the same sensors as the extension:

- `sensor.tokentracker_vs_code_codex_tokens_week`
- `sensor.tokentracker_vs_code_codex_input_tokens_week`
- `sensor.tokentracker_vs_code_codex_cached_input_tokens_week`
- `sensor.tokentracker_vs_code_codex_output_tokens_week`
- `sensor.tokentracker_vs_code_codex_reasoning_output_tokens_week`
- `sensor.tokentracker_vs_code_codex_5h_used_percent`
- `sensor.tokentracker_vs_code_codex_5h_resets_at`
- `sensor.tokentracker_vs_code_codex_weekly_used_percent`
- `sensor.tokentracker_vs_code_codex_weekly_resets_at`
- `sensor.tokentracker_vs_code_codex_plan_type`
- `sensor.tokentracker_vs_code_claude_code_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_input_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_cache_creation_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_cache_read_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_output_tokens_week`
- `sensor.tokentracker_vs_code_updated_at_epoch`

The entity IDs still say `vs_code` on purpose — that keeps the same Home
Assistant entities regardless of which collector publishes to them, so
`esphome/round-token-tracker.yaml` and the Home Assistant packages need no
changes when switching collectors.

## Data sources

Same as the extension:

- Codex: reads `~/.codex/sessions/**/*.jsonl` (`rollout-*.jsonl`), sums
  `token_count` deltas for the current week, and falls back to
  `~/.codex/state_5.sqlite` (`threads.tokens_used`) if the session files have
  no token events. Also forwards the freshest `rate_limits` snapshot
  (`primary` = 5h window, `secondary` = weekly window, plus `plan_type`).
- Claude Code: reads `~/.claude/projects/**/*.jsonl`, sums `usage.input_tokens`,
  `usage.output_tokens`, `usage.cache_creation_input_tokens` and
  `usage.cache_read_input_tokens` for events from the current week (Monday
  00:00 local time).

Unlike the extension, this script does **not** run continuously. It is meant
to be invoked periodically (e.g. every minute) by an external scheduler —
connect, publish, disconnect — since there is no long-lived host process like
VS Code to keep it alive.

## Manual installation (Windows)

### 1. Create a virtual environment and install dependencies

```powershell
cd python-collector
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Create `config.json`

Copy `config.example.json` to `config.json` (gitignored — this is where your
real MQTT password goes) and fill in your broker:

```powershell
Copy-Item config.example.json config.json
```

```json
{
  "mqtt": {
    "url": "mqtt://homeassistant.local:1883",
    "username": "tokentracker",
    "password": "your-mqtt-password",
    "discovery_prefix": "homeassistant",
    "state_prefix": "tokentracker"
  },
  "codex_enabled": true,
  "claude_enabled": true
}
```

### 3. Test it once

```powershell
.\.venv\Scripts\python.exe collector.py
```

This should print/log a `Published: {...}` line with your current weekly
token counts, and `collector.log` (next to the script, rotated at 1 MB × 2
backups) should show the same. Within a minute or so Home Assistant should
show the `sensor.tokentracker_vs_code_*` entities updating.

### 4. Schedule it to run every minute

The script does one publish cycle and exits, so it needs a scheduler to call
it repeatedly. On Windows, `schtasks` works without administrator rights for
a task that runs only in your own session (use full, absolute paths — adjust
if you cloned the repo elsewhere):

```powershell
$exe = "C:\path\to\Tokentracker\python-collector\.venv\Scripts\pythonw.exe"
$script = "C:\path\to\Tokentracker\python-collector\collector.py"
schtasks /Create /TN "TokenTrackerCollector" /TR "`"$exe`" `"$script`"" /SC MINUTE /MO 1 /F
```

`pythonw.exe` (instead of `python.exe`) runs without popping up a console
window. Check it fired and succeeded:

```powershell
schtasks /Query /TN "TokenTrackerCollector" /V /FO LIST
```

`Last Result` should be `0`. Errors and every publish are logged to
`collector.log`.

To remove it later:

```powershell
schtasks /Delete /TN "TokenTrackerCollector" /F
```

Note: `Register-ScheduledTask` (the PowerShell cmdlet) can fail with
"Access is denied" in some environments even for a task that only runs in
your own session — `schtasks.exe` does not have that restriction and is what
the commands above use.

### Other platforms / schedulers

Any scheduler that can run `python collector.py` once a minute works — cron
on Linux/macOS, a systemd timer, Task Scheduler on Windows, etc. The script
itself is platform-independent; only the scheduling mechanism above is
Windows-specific.

## Troubleshooting

- **No sensors in Home Assistant**: run `collector.py` manually once and
  check `collector.log` for connection errors; confirm the MQTT integration
  is active in Home Assistant and the broker URL/credentials in `config.json`
  are correct.
- **Sensors stop updating**: check the scheduled task's `Last Result` — a
  non-zero value means the last run failed; check `collector.log` for the
  exception.
- **`codex_tokens_week` is `0` but Codex rate-limit percentages show a stale
  value**: expected if you have not run Codex this week — the weekly token
  count is genuinely zero, while the 5h/weekly percent sensors keep the last
  known snapshot from Codex's own rate-limit reporting until Codex runs again
  (the ESPHome display already zeroes those rings once their `resets_at`
  epoch is in the past).
