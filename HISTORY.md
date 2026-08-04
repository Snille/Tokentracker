# History

## 0.7.0 - 2026-08-04

### rtk token savings

- `python-collector/` (version `1.2.0`): publishes eleven new rtk sensors read
  from `rtk gain --all --format json` (lifetime/today/week saved tokens, savings
  percent and command counts, plus lifetime raw and filtered token totals).
  rtk's Monday-Sunday week matches the collector's own week windows.
  `total_input` = `total_output` + `total_saved`, i.e. raw command output = what
  reached the model + what [rtk](https://github.com/rtk-ai/rtk) stripped.
- rtk is optional: the collector resolves the binary with `shutil.which()` and
  skips both the discovery configs and the payload keys when it is not
  installed, so non-rtk users do not get a row of permanently-zero entities. Two
  new `config.json` keys, `rtk_enabled` (default `true`) and `rtk_command`
  (default `"rtk"`), cover the cases where rtk is installed but unwanted, or
  installed somewhere off `PATH`.
- The rtk subprocess call passes `CREATE_NO_WINDOW` on Windows, so the scheduled
  `pythonw.exe` run does not flash a console window every minute, and decodes
  output as UTF-8 rather than the ANSI code page.
- rtk support is **only** in the Python collector. rtk's stats are
  machine-global and unrelated to VS Code, and the extension's discovery would
  produce `vs_code`-prefixed entity IDs that would not match.
- Documented a Home Assistant behaviour that had been misunderstood: HA builds
  MQTT entity IDs from the **device name plus the sensor's friendly name**, not
  from `object_id`. That is why `object_id: tokentracker_rtk_input_tokens_total`
  surfaces as `sensor.tokentracker_rtk_raw_tokens_total`, and why the older
  sensors are `sensor.tokentracker_*` rather than the `..._vs_code_*` their
  `object_id`s suggest — the infix came from the extension's old device name.

### The VS Code extension was removed

- `vscode-extension/` is gone. It was no longer installed anywhere, the
  scheduled Python collector had been the live source for some time, and the
  extension had not kept up — it published neither the rtk sensors nor the
  Claude rate-limit sensors.
- It also actively caused confusion: its MQTT device name was
  `TokenTracker VS Code`, which is where the `..._vs_code_*` entity IDs came
  from. Those entities no longer exist in Home Assistant, but several docs in
  this repo still referenced them; all such references have been corrected to
  the real `sensor.tokentracker_*` names.
- Removed the unused `LEGACY_SENSOR_IDS` list from `collector.py` — dead code
  from a migration that has long since completed.
- The extension is in the git history if it is ever wanted back.

### Repo split: the display moved out

- **Breaking / structural.** `esphome/` was removed. This repo is now the data
  pipeline only — collectors plus the Home Assistant packages — and the ESPHome
  device config lives solely in the private ESPHome repository, where it is
  actually built and flashed. Keeping a second copy here is what let the repo
  drift out of step with the hardware.
- The config that was removed, `esphome/round-token-tracker.yaml`, targeted the
  466x466 Waveshare AMOLED 1.75. That screen has been repurposed. The live
  device is now the 240x240 Waveshare ESP32-S3-Touch-LCD-1.28, whose config
  (`storstugan-office-token-tracker-128.yaml`, version `1.3.0`) gained the same
  rtk screen plus an rtk savings rate in the middle of the 2x2 overview.
- The removed AMOLED config was also stale in a way that had gone unnoticed: it
  subscribed to `sensor.tokentracker_vs_code_*` entities that no longer exist in
  Home Assistant.
- Everything the display needs from this repo is the MQTT sensor contract in
  `README.md`. It is still in the git history if the AMOLED config is ever
  wanted back.

## 0.6.0 - 2026-07-08

- `python-collector/` (version `1.1.0`): the collector now publishes the **real**
  Claude subscription rate-limit percentages. New function `fetch_claude_oauth_usage()`
  queries `GET https://api.anthropic.com/api/oauth/usage` (the same source Claude Code
  uses) with the OAuth access token from `~/.claude/.credentials.json`, mapping
  `five_hour`/`seven_day` `utilization` + ISO `resets_at` to four new sensors
  (`claude_5h_used_percent`, `claude_5h_resets_at`, `claude_weekly_used_percent`,
  `claude_weekly_resets_at`). This is headless — no Claude Code statusline or terminal
  session needed — and falls back to the last cached response (`~/.claude/claude_rate_limits.json`)
  when the token is briefly expired/offline. The statusline-based prototype was removed.
- `claude_tokens_week` no longer counts **cache-read** tokens (`CLAUDE_TOTAL_KEYS` =
  input + output + cache-creation). Cache reads dwarfed everything (>95% of the raw sum)
  and are billed at ~0.1×, so the headline total is now meaningful for the display gauge;
  cache-read is still published to its own `claude_cache_read_input_tokens_week` sensor.
- `.gitignore`: also ignore rotated logs (`*.log.*`).

## 0.5.1 - 2026-07-07

- Fixed `python-collector/` (version `1.0.1`): it did **not** actually publish
  the same Home Assistant entity IDs as the VS Code extension, despite the
  0.5.0 note claiming so. It built object_ids as `tokentracker_<id>`, missing
  the `vs_code` infix and using `claude_*` instead of `claude_code_*` (and
  keeping `input` in the cache sensor names). As a result the ESPHome display
  (`sensor.tokentracker_vs_code_*`) and existing HA dashboards saw no data
  after switching from the extension to the Python collector.
- Each `SENSORS` entry now carries an explicit `object_id` matching the VS
  Code extension's exact entity names; `discovery_payload` and the discovery
  config topic use it. The JSON state payload keys (`id`) are unchanged, so
  `value_template` still resolves. The 16 old, wrongly-named discovery configs
  must be cleared with empty retained payloads when upgrading (done on the
  affected host).

## 0.5.0 - 2026-07-07

- Added `python-collector/` (version `1.0.0`): a standalone Python port of
  the VS Code extension's Codex/Claude Code MQTT publishing logic. Reads the
  same local session logs (`~/.codex/sessions`, `~/.claude/projects`) but
  does not depend on VS Code being open — meant to be invoked periodically
  (e.g. every minute) by an external scheduler such as a Windows Scheduled
  Task, so tracking keeps working when Codex/Claude Code run via a CLI or
  desktop app instead of the VS Code extension.
- Publishes to the same MQTT discovery topics and entity IDs as the VS Code
  extension, so `esphome/round-token-tracker.yaml` and the Home Assistant
  packages need no changes when switching collectors.
- Documented both collectors as alternatives (pick one) in `README.md` and
  `INSTALL.md`; the VS Code extension is unchanged and still supported for
  anyone who prefers it.

## 0.4.0 - 2026-05-19

- Bumped ESPHome display to `1.11.0`.
- Bumped VS Code extension to `1.3.1`.
- VS Code extension: read the live `rate_limits` block out of Codex rollout
  sessions (`~/.codex/sessions/**/*.jsonl`) and publish five new MQTT
  discovery sensors:
  - `codex_5h_used_percent`, `codex_5h_resets_at`
  - `codex_weekly_used_percent`, `codex_weekly_resets_at`
  - `codex_plan_type` (text sensor)
- VS Code extension: skip `limit_id: "premium"` events where `primary` and
  `secondary` are null so the percentage sensors do not get blanked at the end
  of a Codex session.
- VS Code extension: walk older rollouts when this week has no events yet so
  the freshest rate-limit snapshot still reaches Home Assistant.
- ESPHome: Codex 5h ring and weekly ring now read directly from
  `codex_5h_used_percent` / `codex_weekly_used_percent`. Reset labels come from
  the matching `*_resets_at` epochs instead of a synthetic
  `goal × 33.6`-derived target.
- ESPHome: Codex 5h baselines for the input/output/cache/reasoning breakdown
  now re-anchor whenever `codex_5h_resets_at` changes, so the per-5h numbers
  follow Codex's own sliding window. The old `Codex 5h Start Hour/Minute`
  sliders and `codex_period_anchor_ts` / `codex_period_index` globals were
  removed.
- ESPHome: when `codex_5h_resets_at` (or `codex_weekly_resets_at`) is in the
  past the corresponding ring is forced to 0%, so a long Codex pause no
  longer leaves a stale percentage on the display.
- ESPHome: VS Code stale badge renamed from `VS Code stale` to
  `VS Code offline`. When the data is older than 10 minutes the "Upd …" label
  switches to `Last HH:MM` showing the wall-clock time of the most recent
  publish.
- ESPHome: split-usage ring now takes `usage_5h_percent` and
  `weekly_usage_percent` as direct arguments so callers can supply the real
  Codex rate-limit values; Claude keeps its synthetic
  `goal × 33.6` weekly calculation since Anthropic does not expose Pro/Max
  rate limits publicly.
- ESPHome: renamed `Max Codex / 5h` and `Max Claude / 5h` to
  `Max Codex per 5h` and `Max Claude per 5h` to avoid the ESPHome 2026.7
  warning about `/` in entity names.
- ESPHome: nudged the upper Codex/Claude tiles on the quadrant overview
  outwards (`cx=138` / `cx=328`) so the value text no longer overlaps the
  `Wk` bars; Router/WebUI stay at the original `cx=148` / `cx=318`.
- ESPHome: new `reset_label_from_epoch` helper formats an epoch as `HH:MM`
  inside 24h and `Ddd HH:MM` further out, used for both the Codex 5h reset and
  the future weekly reset label.

## 0.3.0 - 2026-05-17

- Bumped ESPHome display to `1.10.0`.
- Bumped VS Code extension to `1.2.2`.
- Changed Codex and Claude Code tracking from day totals to week totals.
- Updated the ESPHome Codex/Claude usage rings to use 5h usage while showing
  week totals on the detail and overview screens.
- Added ESPHome config inputs for Codex/Claude 5h start time. The display now
  derives its current 5h bucket from weekly counters and local reset baselines.
- Added MQTT discovery sensors for Codex/Claude `*_week` values and tombstoned
  the old Codex/Claude `*_today` and rolling `*_5h` sensors.
- Fixed the OpenRouter quadrant to show account balance remaining and remaining
  percent instead of API-key limit remaining and key-limit usage percent.
- Split the Codex and Claude detail rings into an upper 5h usage half and a
  lower blue weekly usage half.
- Tuned the round display spacing for WebUI, input/output labels, quadrant
  center bars and the 5h + Week title.
- Changed the lower quadrant center bars to show OpenRouter cost today and Open
  WebUI output share instead of duplicating the quadrant arcs.
- Added reset-time, last-updated/stale status, weekly pace, quadrant tap targets
  and clearer Codex/Claude `/5h` max slider labels.
- Added tap-to-return from provider detail screens back to the quadrant overview.
- Renamed max sliders to sort together in ESPHome integrations.
- Added VS Code `updated_at_epoch` publishing so the ESP display can detect
  stale local collector data.

## 0.2.0 - 2026-05-17

### ESPHome Display

- Bumped ESPHome display to `1.8.1`.
- Reworked the Codex, Claude Code, OpenRouter and Open WebUI screens into
  richer provider dashboards with input/output/cache/cost details.
- Tuned the provider, Today and I/O Mix layouts for the round 466x466 display:
  smaller logos and headline values, tighter lower metrics and thinner I/O bars.
- Added two overview screens:
  - I/O Mix across Codex, Claude Code, Open WebUI and OpenRouter activity.
  - Today summary with local tokens, self-hosted tokens, router cost, chats and
    key count.
- Expanded the carousel from 6 to 8 screens while keeping one Show Overview
  switch for all overview pages.

### Home Assistant

- Bumped Home Assistant package to `1.2.1`.
- Added OpenRouter support for five tracked API-key slots,
  `openrouter_api_bearer1` through `openrouter_api_bearer5`, with combined
  legacy display sensors for key limit, remaining credit and daily/weekly/monthly
  cost.
- Added OpenRouter `/activity` sensors for prompt, completion, reasoning and
  total token history where OpenRouter exposes it.
- Added Open WebUI model-count and input/output percentage sensors for today's
  local analytics.

### VS Code Extension

- Bumped VS Code extension to `1.2.1`.
- Added detailed Codex MQTT sensors for input, cached input, output and
  reasoning output tokens from local Codex rollout session logs.
- Added detailed Claude Code MQTT sensors for input, cache creation, cache read
  and output tokens from local Claude JSONL logs.
- Kept the existing aggregate `tokens_today` sensors for compatibility.

## 0.1.0 - 2026-05-16

Initial public-ready snapshot of Token Tracker.

### ESPHome Display

- Built the round ESPHome UI for Waveshare ESP32-S3 Touch AMOLED 1.75.
- Added screens for clock, Codex, Claude Code, OpenRouter, Open WebUI and an
  overview/quadrant screen.
- Added outer usage rings for account screens.
- Added dark-blue inner auto-rotate timer ring, including pause behaviour.
- Added analog clock in the overview center.
- Added Home Assistant config entities for:
  - `Screen Interval`
  - `Overview Screen Interval`
  - `Display Brightness Percent`
  - `Display Rotation`
  - `Codex Max`
  - `Claude Max`
  - `WebUI Max`
  - show/hide switches per screen
- Moved Codex, Claude Code and Open WebUI max values into ESPHome config
  entities so they can be adjusted from the Token Tracker device in Home
  Assistant.
- Changed max values to ktokens so Home Assistant sliders are usable.
- Added substitutions for slider maximums:
  - `codex_max_ktokens`
  - `claude_max_ktokens`
  - `openwebui_max_ktokens`
- Added display brightness control from Home Assistant.
- Added physical top-button behaviour:
  - short press pauses/resumes auto-rotate
  - long press toggles display on/off
- Removed double-click handling.
- Added touch swipe navigation with rotation-aware direction handling.
- Tuned swipe threshold, gesture timeout and display update behaviour for a
  more responsive touch feel.
- Added auto-orientation using QMI8658 IMU.
- Hid noisy IMU sensors/logging from normal Home Assistant and ESP logs.
- Added separate overview/quadrant dwell time.
- ESPHome project version: `1.7.5`.

### Home Assistant

- Added package files for OpenRouter and Open WebUI:
  - `homeassistant/packages/tokentracker/openrouter.yaml`
  - `homeassistant/packages/tokentracker/openwebui.yaml`
- OpenRouter package reads:
  - account credits
  - API-key limit
  - usage percent
  - day/week/month usage
- Open WebUI package reads:
  - total users
  - active users
  - chat counts
  - top model
  - tokens today
  - input/output tokens today
- Reworked Open WebUI from active-user based display value to daily token usage,
  which is more useful for a one-person instance.
- Removed dependency on old command_line/template token packages.
- Documented cleanup of stale Home Assistant entities.
- Home Assistant package version: `1.1.0`.

### VS Code Extension

- Added a VS Code extension that reads local Codex and Claude Code usage data.
- Publishes MQTT discovery sensors to Home Assistant.
- Changed extension to raw-only publishing:
  - `codex_tokens_today`
  - `claude_tokens_today`
  - `updated_at`
- Removed legacy extension-side `tokens_left`, usage percent, totals, current
  thread/project and collector status sensors.
- Added MQTT discovery tombstones for old legacy sensors so Home Assistant can
  clean them up.
- Added `.vscodeignore` to keep local source/build files out of packaged VSIX.
- VS Code extension version: `1.1.0`.

### Repository Cleanup

- Added root project version file.
- Added `.gitignore` for local tokens, logs, `node_modules`, `dist`, VSIX files
  and local VS Code settings.
- Removed local scratch notes that contained real secrets.
- Added documentation for ESPHome, Home Assistant packages and the VS Code
  extension.
