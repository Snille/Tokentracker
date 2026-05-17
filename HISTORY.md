# History

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
