# Install Token Tracker from scratch

This guide assumes you have:

- A Waveshare ESP32-S3 Touch AMOLED 1.75.
- Home Assistant with ESPHome.
- VS Code on the machine where you run Codex and/or Claude Code.
- Access to this git repo.
- Node.js LTS on the machine where the VS Code extension will be built.
- An MQTT broker that Home Assistant can read from, for example the Mosquitto
  broker add-on.

Token Tracker has three parts:

- The ESPHome display in `esphome/round-token-tracker.yaml`.
- Home Assistant packages for OpenRouter / Open WebUI in
  `homeassistant/packages/tokentracker/`.
- The VS Code extension in `vscode-extension/`, which publishes local Codex
  and Claude Code weekly counters to MQTT discovery.

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

Create an MQTT user that the VS Code extension can use, for example:

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

## 4. Build and install the VS Code extension

The extension must be installed in the VS Code instance where Codex / Claude
Code runs.

Go to the extension directory:

```powershell
cd vscode-extension
npm install
npm run compile
npm run package
```

That produces a VSIX, for example:

```text
tokentracker-vscode-1.2.2.vsix
```

Install it in VS Code:

```text
Extensions -> ... -> Install from VSIX...
```

Then add settings in VS Code `settings.json`:

```json
{
  "tokentracker.mqtt.url": "mqtt://homeassistant.local:1883",
  "tokentracker.mqtt.username": "tokentracker",
  "tokentracker.mqtt.password": "mqtt-password",
  "tokentracker.publishIntervalSeconds": 60,
  "tokentracker.codex.enabled": true,
  "tokentracker.claude.enabled": true
}
```

Optionally run:

```text
Developer: Reload Window
TokenTracker: Publish Now
```

After a minute or so Home Assistant should receive MQTT discovery sensors
such as:

```text
sensor.tokentracker_vs_code_codex_tokens_week
sensor.tokentracker_vs_code_claude_code_tokens_week
sensor.tokentracker_vs_code_updated_at_epoch
```

The extension reads local files:

- Codex: `~/.codex/sessions/**/*.jsonl`, falling back to `~/.codex/state_5.sqlite`.
- Claude Code: `~/.claude/projects/**/*.jsonl`.

It publishes weekly counters. The ESP computes the current 5h period itself
using its own baselines.

## 5. Prepare ESPHome secrets

The ESPHome file includes:

```yaml
<<: !include base/base-iot.yaml
```

`esphome/base/base-iot.yaml` requires these secrets in ESPHome:

```yaml
iot_wifi_ssid: "your-iot-wifi"
iot_wifi_password: "wifi-password"
iot_wifi_domain: ".local"
wifi_ap_password: "fallback-ap-password"
api_key: "base64-api-key-from-esphome"
ota_password: "ota-password"
```

In the ESPHome Dashboard you can create a new device just to get an API
encryption key, or generate one yourself according to the ESPHome
documentation.

## 6. Add the ESPHome configuration

Copy these parts to your ESPHome configuration directory:

```text
esphome/round-token-tracker.yaml
esphome/base/base-iot.yaml
esphome/images/
```

Open `round-token-tracker.yaml` and check the substitutions at the top:

```yaml
openai_week_tokens_entity: sensor.tokentracker_vs_code_codex_tokens_week
anthropic_week_tokens_entity: sensor.tokentracker_vs_code_claude_code_tokens_week
vscode_updated_at_epoch_entity: sensor.tokentracker_vs_code_updated_at_epoch
openwebui_tokens_entity: sensor.openwebui_tokens_today
codex_max_ktokens: "250000"
claude_max_ktokens: "250000"
openwebui_max_ktokens: "1250"
```

Change the entity IDs if your HA entities are named differently.

## 7. Flash the display

In the ESPHome Dashboard:

1. Add or open the device `round-token-tracker`.
2. Select `Install`.
3. The first time: use USB to the display.
4. After the first flash, OTA can be used if Wi-Fi / API works.

The configuration uses an external component for the touch driver:

```text
https://github.com/shelson/esphome-cst9217
```

ESPHome therefore needs internet access at build time unless the component
is already cached.

## 8. Configure the display in Home Assistant

When the ESP connects, Token Tracker appears as an ESPHome device in Home
Assistant. Configure the most important config entities:

- `Max Codex / 5h`
- `Max Claude / 5h`
- `Max WebUI`
- `Codex 5h Start Hour`
- `Codex 5h Start Minute`
- `Claude 5h Start Hour`
- `Claude 5h Start Minute`
- `Display Brightness Percent`
- `Screen Interval`
- `Overview Screen Interval`
- `Auto Rotate Screens`
- `Show Clock`, `Show Codex`, `Show Claude Code`, `Show OpenRouter`,
  `Show Open WebUI`, `Show Overview`

Codex/Claude max values are in ktokens per 5h period.

`Codex/Claude 5h Start Hour` is `0-24`. `0` means `00:00`, and `24` is treated
as `00:00`. Minute is `0-59`.

When you change a 5h start time, the ESP saves the current weekly counter as
its baseline. After that it keeps counting periods every five hours.

## 9. Check that everything works

In Home Assistant you should see:

```text
sensor.tokentracker_vs_code_codex_tokens_week
sensor.tokentracker_vs_code_codex_input_tokens_week
sensor.tokentracker_vs_code_codex_cached_input_tokens_week
sensor.tokentracker_vs_code_codex_output_tokens_week
sensor.tokentracker_vs_code_codex_reasoning_output_tokens_week
sensor.tokentracker_vs_code_claude_code_tokens_week
sensor.tokentracker_vs_code_claude_code_input_tokens_week
sensor.tokentracker_vs_code_claude_code_cache_creation_tokens_week
sensor.tokentracker_vs_code_claude_code_cache_read_tokens_week
sensor.tokentracker_vs_code_claude_code_output_tokens_week
sensor.tokentracker_vs_code_updated_at_epoch
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

On the display:

- Swipe left/right to change page.
- Tapping an individual provider screen jumps back to the quadrant page.
- A short press on the top button pauses/resumes auto-rotate.
- A long press on the top button turns the display off/on.
- On the quadrant page you can tap a quadrant to jump to the matching detail
  page.

## 10. Troubleshooting

### VS Code sensors are missing

- Check that the VSIX is installed and that VS Code has been reloaded.
- Check the MQTT settings in VS Code.
- Run `TokenTracker: Publish Now`.
- Check that the MQTT integration in HA is active.
- Remember that the extension only runs while VS Code is running.

### The ESP shows `VS Code stale`

- The VS Code extension is no longer publishing, or VS Code is closed.
- Check `sensor.tokentracker_vs_code_updated_at_epoch`.
- Run `TokenTracker: Publish Now`.

### ESPHome build fails

- Check ESPHome secrets.
- Check that `images/` is next to the YAML file.
- Check that ESPHome can fetch the external component from GitHub.
- The first flash may need to be done via USB.

### OpenRouter / Open WebUI shows zero

- Check `secrets.yaml`.
- Check that HA can reach the endpoints.
- Restart Home Assistant after package / secrets changes.
- Look in the Home Assistant logs for REST sensor errors.

### Old entities are still around

The VS Code extension tombstones old MQTT discovery entities, but HA can
sometimes keep disabled/unavailable entities. Remove them manually here:

```text
Settings -> Devices & services -> Entities
```

## Updating later

When the repo changes:

1. Pull the latest code.
2. Build a new VSIX if `vscode-extension/` changed.
3. Install the new VSIX and reload VS Code.
4. Update ESPHome if `esphome/round-token-tracker.yaml` changed.
5. Copy the Home Assistant package files again if `homeassistant/packages/`
   changed.
