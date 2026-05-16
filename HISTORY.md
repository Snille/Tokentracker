# History

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
- Current ESPHome project version: `1.7.5`.

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
- Current Home Assistant package version: `1.1.0`.

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
- Current VS Code extension version: `1.1.0`.

### Repository Cleanup

- Added root project version file.
- Added `.gitignore` for local tokens, logs, `node_modules`, `dist`, VSIX files
  and local VS Code settings.
- Removed local scratch notes that contained real secrets.
- Added documentation for ESPHome, Home Assistant packages and the VS Code
  extension.
