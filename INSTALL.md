# Install Token Tracker from scratch

This guide covers the data pipeline: getting your AI usage into Home Assistant.
The display that renders it is a separate ESPHome device and is not part of this
repo — see step 5.

It assumes you have:

- Home Assistant.
- The machine where you run Codex and/or Claude Code (via a CLI, a desktop app,
  or an editor).
- Access to this git repo.
- Python 3.10+ on the machine that will run the collector.
- An MQTT broker that Home Assistant can read from, for example the Mosquitto
  broker add-on.
- Optionally [rtk](https://github.com/rtk-ai/rtk) on the same machine, to get
  the rtk savings sensors.

Token Tracker has two parts:

- The collector in `python-collector/`, which publishes local Codex, Claude Code
  and rtk counters to MQTT discovery. It is scheduled externally, e.g. every
  minute via a Windows Scheduled Task.
- Home Assistant packages for OpenRouter / Open WebUI in
  `homeassistant/packages/tokentracker/`.

## 1. Clone the repo

On your machine:

```powershell
git clone <repo-url> Tokentracker
cd Tokentracker
```

## 2. Prepare Home Assistant

### MQTT

Install and start an MQTT broker if you do not already have one. In Home
Assistant the easiest option is:

```text
Settings -> Add-ons -> Mosquitto broker
```

Create an MQTT user that the collector can use, for example:

```text
username: tokentracker
password: <your own password>
```

Make sure Home Assistant has the MQTT integration active:

```text
Settings -> Devices & services -> MQTT
```

### Packages

Copy the repo directory:

```text
homeassistant/packages/tokentracker/
```

to Home Assistant:

```text
/config/packages/tokentracker/
```

Make sure `/config/configuration.yaml` loads packages:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant after the change.

## 3. Add Home Assistant secrets

Open `/config/secrets.yaml` in Home Assistant.

### OpenRouter

If you want to use the OpenRouter pages, add:

```yaml
openrouter_management_bearer: "Bearer sk-or-v1-..."
openrouter_api_bearer1: "Bearer sk-or-v1-..."
openrouter_api_bearer2: "Bearer sk-or-v1-..."
openrouter_api_bearer3: "Bearer sk-or-v1-..."
openrouter_api_bearer4: "Bearer sk-or-v1-..."
openrouter_api_bearer5: "Bearer sk-or-v1-..."
```

Home Assistant requires all five `openrouter_api_bearer*` to exist. If you
only have one key, all five can point at the same bearer; the templates count
unique key labels and do not double-count the same key.

If you do not want to use OpenRouter at all, either skip / remove
`openrouter.yaml`, or add dummy secrets and accept that the sensors will be
zero / unavailable.

### Open WebUI

If you want to use the Open WebUI pages, add:

```yaml
openwebui_bearer: "Bearer eyJhbGciOi..."
openwebui_users_url: "http://your-openwebui:8080/api/v1/users/"
openwebui_chats_url: "http://your-openwebui:8080/api/v1/chats/all/db"
openwebui_analytics_url: "http://your-openwebui:8080/api/v1/analytics/users"
openwebui_tokens_today_url: >-
  http://your-openwebui:8080/api/v1/analytics/tokens?start_date={{ now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() | int }}&end_date={{ now().timestamp() | int }}
```

If you do not want to use Open WebUI, either skip / remove `openwebui.yaml`,
or add dummy secrets / URLs and accept that the sensors will be zero /
unavailable.

Restart Home Assistant after secrets and packages are in place.

## 4. Install the collector

The script does one publish cycle and exits, so it needs an external scheduler
to call it repeatedly (e.g. every minute).

```powershell
cd python-collector
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config.example.json config.json
```

Edit `config.json` with your MQTT broker, then test it once:

```powershell
.\.venv\Scripts\python.exe collector.py
```

Then schedule it to run every minute on Windows (works without admin rights
for a task in your own session — adjust the paths to where you cloned the
repo):

```powershell
$exe = "C:\path\to\Tokentracker\python-collector\.venv\Scripts\pythonw.exe"
$script = "C:\path\to\Tokentracker\python-collector\collector.py"
schtasks /Create /TN "TokenTrackerCollector" /TR "`"$exe`" `"$script`"" /SC MINUTE /MO 1 /F
```

`pythonw.exe` avoids a flashing console window. Check it fired successfully
with `schtasks /Query /TN "TokenTrackerCollector" /V /FO LIST` (`Last Result`
should be `0`), and check `python-collector/collector.log` for details. See
`python-collector/README.md` for more, including non-Windows schedulers.

### Sensors published by the collector

After a minute or so Home Assistant should receive MQTT discovery sensors
such as:

```text
sensor.tokentracker_codex_tokens_week
sensor.tokentracker_codex_5h_used_percent
sensor.tokentracker_codex_5h_resets_at
sensor.tokentracker_codex_weekly_used_percent
sensor.tokentracker_codex_weekly_resets_at
sensor.tokentracker_codex_plan_type
sensor.tokentracker_claude_code_tokens_week
sensor.tokentracker_updated_at_epoch
```

The Python collector adds eleven `sensor.tokentracker_rtk_*` entities when
[rtk](https://github.com/rtk-ai/rtk) is installed, e.g.:

```text
sensor.tokentracker_rtk_saved_tokens_total
sensor.tokentracker_rtk_saved_tokens_today
sensor.tokentracker_rtk_saved_percent_total
sensor.tokentracker_rtk_commands_total
```

These feed the display's rtk page. They need no setup — the collector looks for
the `rtk` binary on `PATH` and skips them silently when it is not there. If your
scheduler runs with a `PATH` that does not include rtk, set `"rtk_command"` in
`config.json` to the absolute path.

Note that Home Assistant derives these entity IDs from the device name plus each
sensor's friendly name rather than from the MQTT `object_id`, so check the real
names in Home Assistant before wiring anything to them.

The collector reads these local files:

- Codex: `~/.codex/sessions/**/*.jsonl`, falling back to `~/.codex/state_5.sqlite`.
- Claude Code: `~/.claude/projects/**/*.jsonl`.

It publishes weekly counters plus Codex's live `rate_limits` snapshot (current
5h percent + reset epoch and weekly percent + reset epoch). Claude's equivalent
comes from the authenticated `/api/oauth/usage` endpoint, using the OAuth token
in `~/.claude/.credentials.json` — the same source Claude Code itself uses. When
that call fails the collector falls back to the last cached response in
`~/.claude/claude_rate_limits.json`.

## 5. The display

The ESPHome device is not part of this repo. Token Tracker publishes the MQTT
sensors listed above; anything that can read Home Assistant entities can render
them.

My own display is a Waveshare ESP32-S3-Touch-LCD-1.28 (round 240x240 GC9A01)
whose ESPHome config lives in my private ESPHome repository as
`storstugan-office-token-tracker-128.yaml`, and is built and flashed from there.
If you want to build your own, the entity IDs in the previous section are the
whole contract between the pipeline and the screen.


## 6. Check that everything works

In Home Assistant you should see:

```text
sensor.tokentracker_codex_tokens_week
sensor.tokentracker_codex_input_tokens_week
sensor.tokentracker_codex_cached_input_tokens_week
sensor.tokentracker_codex_output_tokens_week
sensor.tokentracker_codex_reasoning_output_tokens_week
sensor.tokentracker_codex_5h_used_percent
sensor.tokentracker_codex_5h_resets_at
sensor.tokentracker_codex_weekly_used_percent
sensor.tokentracker_codex_weekly_resets_at
sensor.tokentracker_codex_plan_type
sensor.tokentracker_claude_code_tokens_week
sensor.tokentracker_claude_code_input_tokens_week
sensor.tokentracker_claude_code_cache_creation_tokens_week
sensor.tokentracker_claude_code_cache_read_tokens_week
sensor.tokentracker_claude_code_output_tokens_week
sensor.tokentracker_updated_at_epoch
```

With the Python collector and rtk installed, also:

```text
sensor.tokentracker_rtk_saved_tokens_total
sensor.tokentracker_rtk_saved_tokens_today
sensor.tokentracker_rtk_saved_tokens_week
sensor.tokentracker_rtk_saved_percent_total
sensor.tokentracker_rtk_saved_percent_today
sensor.tokentracker_rtk_saved_percent_week
sensor.tokentracker_rtk_commands_total
sensor.tokentracker_rtk_commands_today
sensor.tokentracker_rtk_commands_week
sensor.tokentracker_rtk_raw_tokens_total
sensor.tokentracker_rtk_filtered_tokens_total
```

For OpenRouter:

```text
sensor.openrouter_balance_remaining
sensor.openrouter_usage_percent
sensor.openrouter_cost_today
sensor.openrouter_cost_month
sensor.openrouter_activity_prompt_tokens
sensor.openrouter_activity_completion_tokens
```

For Open WebUI:

```text
sensor.openwebui_tokens_today
sensor.openwebui_input_tokens_today
sensor.openwebui_output_tokens_today
sensor.openwebui_chats_today
sensor.openwebui_active_users
sensor.openwebui_models_today
sensor.openwebui_output_token_percent_today
```

## 7. Troubleshooting

### Collector sensors are missing

- Run `.\.venv\Scripts\python.exe collector.py` manually and check the output
  / `python-collector/collector.log` for connection errors.
- Check `config.json` has the right MQTT broker/credentials.
- Check that the MQTT integration in HA is active.
- Check the scheduled task actually ran: `schtasks /Query /TN
  "TokenTrackerCollector" /V /FO LIST` — `Last Result` should be `0`.
- If a sensor exists but under a different name than you expected, remember that
  Home Assistant builds the entity ID from the device name plus the sensor's
  friendly name, not from the MQTT `object_id`.

### The display shows the collector as offline

- The collector has not published recently.
- The scheduled task stopped running, or MQTT lost connection.
- Check `sensor.tokentracker_updated_at_epoch` — it is the freshness signal the
  display watches.
- Run `collector.py` manually and check the scheduled task status.

### The Claude percentages are stale

- `collector.log` will show `oauth/usage fetch failed`. The collector then falls
  back to the last cached response in `~/.claude/claude_rate_limits.json`, so
  the display holds the previous value rather than dropping to zero.
- `HTTP Error 401` usually means the OAuth token in
  `~/.claude/.credentials.json` has expired — run Claude Code once to refresh it.
- `HTTP Error 429` means the endpoint is rate-limiting the poll.

### OpenRouter / Open WebUI shows zero

- Check `secrets.yaml`.
- Check that HA can reach the endpoints.
- Restart Home Assistant after package / secrets changes.
- Look in the Home Assistant logs for REST sensor errors.

### Old entities are still around

Retained MQTT discovery configs outlive the sensors that created them, and HA
keeps disabled/unavailable entities around. Remove them manually here:

```text
Settings -> Devices & services -> Entities
```

Anything named `sensor.tokentracker_vs_code_*` is from the retired VS Code
extension and can go.

## Updating later

When the repo changes:

1. Pull the latest code.
2. Re-run `pip install -r requirements.txt` if
   `python-collector/requirements.txt` changed. No need to touch the scheduled
   task unless the script's path changed.
3. Copy the Home Assistant package files again if `homeassistant/packages/`
   changed.
