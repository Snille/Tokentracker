# TokenTracker Python Collector

Version: 1.3.0

Token Tracker's collector. Publishes local Codex, Claude Code and rtk usage to
Home Assistant via MQTT discovery. It reads the session logs those tools write
anyway, so it works whether they run through a CLI, a desktop app, or an editor.

A VS Code extension used to be an alternative collector; it was retired in 0.7.0
and this is now the only one.

It publishes:

- `sensor.tokentracker_codex_tokens_week`
- `sensor.tokentracker_codex_input_tokens_week`
- `sensor.tokentracker_codex_cached_input_tokens_week`
- `sensor.tokentracker_codex_output_tokens_week`
- `sensor.tokentracker_codex_reasoning_output_tokens_week`
- `sensor.tokentracker_codex_5h_used_percent`
- `sensor.tokentracker_codex_5h_resets_at`
- `sensor.tokentracker_codex_weekly_used_percent`
- `sensor.tokentracker_codex_weekly_resets_at`
- `sensor.tokentracker_codex_plan_type`
- `sensor.tokentracker_claude_code_tokens_week`
- `sensor.tokentracker_claude_code_input_tokens_week`
- `sensor.tokentracker_claude_code_cache_creation_tokens_week`
- `sensor.tokentracker_claude_code_cache_read_tokens_week`
- `sensor.tokentracker_claude_code_output_tokens_week`
- `sensor.tokentracker_claude_code_5h_used_percent`
- `sensor.tokentracker_claude_code_5h_resets_at`
- `sensor.tokentracker_claude_code_weekly_used_percent`
- `sensor.tokentracker_claude_code_weekly_resets_at`
- `sensor.tokentracker_updated_at_epoch`

Plus three sensors reporting on the collector itself:

- `sensor.tokentracker_status` — `ok`, `degraded` or `error`
- `sensor.tokentracker_problem` — the text to show, naming the remediation
- `sensor.tokentracker_problem_count`

Plus eleven sensors for [rtk](https://github.com/rtk-ai/rtk):

- `sensor.tokentracker_rtk_saved_tokens_total`
- `sensor.tokentracker_rtk_saved_tokens_today`
- `sensor.tokentracker_rtk_saved_tokens_week`
- `sensor.tokentracker_rtk_saved_percent_total`
- `sensor.tokentracker_rtk_saved_percent_today`
- `sensor.tokentracker_rtk_saved_percent_week`
- `sensor.tokentracker_rtk_commands_total`
- `sensor.tokentracker_rtk_commands_today`
- `sensor.tokentracker_rtk_commands_week`
- `sensor.tokentracker_rtk_raw_tokens_total`
- `sensor.tokentracker_rtk_filtered_tokens_total`

Home Assistant derives these entity IDs from the device name plus each sensor's
friendly name, **not** from the MQTT `object_id` — which is why the sensor whose
`object_id` is `tokentracker_rtk_input_tokens_total` shows up as
`sensor.tokentracker_rtk_raw_tokens_total`. Check the real name in Home
Assistant before pointing a display at a newly added sensor.

## Data sources

Codex and Claude Code:

- Codex: reads `~/.codex/sessions/**/*.jsonl` (`rollout-*.jsonl`), sums
  `token_count` deltas for the current week, and falls back to
  `~/.codex/state_5.sqlite` (`threads.tokens_used`) if the session files have
  no token events. Also forwards the freshest `rate_limits` snapshot
  (`primary` = 5h window, `secondary` = weekly window, plus `plan_type`).
- Claude Code: reads `~/.claude/projects/**/*.jsonl`, sums `usage.input_tokens`,
  `usage.output_tokens`, `usage.cache_creation_input_tokens` and
  `usage.cache_read_input_tokens` for events from the current week (Monday
  00:00 local time).

And rtk:

- rtk: runs `rtk gain --all --format json` and maps the lifetime `summary`
  block plus the `daily` row for today and the `weekly` row containing today.
  rtk maintains these stats itself, so this is a plain CLI read rather than a
  log walk. rtk's week runs Monday-Sunday, same as the windows above.
  `total_input` = `total_output` + `total_saved`, i.e. raw command output = what
  actually reached the model + what rtk stripped; the display's Sent/Saved bar
  is that split.

This script does **not** run continuously. It is meant
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
  "claude_enabled": true,
  "rtk_enabled": true,
  "rtk_command": "rtk"
}
```

rtk needs no setup: the collector resolves `rtk_command` with `shutil.which()`
and, when it finds nothing, publishes neither the rtk discovery configs nor the
rtk payload keys — so a machine without rtk never grows eleven zero-valued
entities. Set `"rtk_enabled": false` to skip rtk even when it is installed, or
point `"rtk_command"` at an absolute path if rtk is not on the `PATH` that your
scheduler hands the script (Task Scheduler does not always inherit your
interactive `PATH`).

### 3. Test it once

```powershell
.\.venv\Scripts\python.exe collector.py
```

This should print/log a `Published: {...}` line with your current weekly
token counts, and `collector.log` (next to the script, rotated at 1 MB × 2
backups) should show the same. Within a minute or so Home Assistant should
show the `sensor.tokentracker_*` entities updating.

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
