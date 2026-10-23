# TokenTracker Home Assistant Package

Package version: `1.3.0`

This package contains Home Assistant REST/template sensors for the part that
does not come from the local collector:

- OpenRouter credits, account balance, multi-key usage and activity token
  history.

Codex, Claude Code and rtk come from `python-collector/` via MQTT discovery:

- `sensor.tokentracker_codex_tokens_week`
- `sensor.tokentracker_claude_code_tokens_week`
- `sensor.tokentracker_rtk_saved_tokens_total`
- `sensor.tokentracker_updated_at_epoch`

The ESPHome display then uses these raw values together with its own config
entities for 5h periods, max values, tokens remaining and percent.

## Installation

Copy the directory to:

```text
/config/packages/tokentracker/
```

Make sure `configuration.yaml` loads packages:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant after changes to the package files.

## OpenRouter

`openrouter.yaml` uses three endpoints:

- `GET https://openrouter.ai/api/v1/credits`
- `GET https://openrouter.ai/api/v1/key`
- `GET https://openrouter.ai/api/v1/activity`

Add to `/config/secrets.yaml`:

```yaml
openrouter_management_bearer: "Bearer sk-or-v1-..."
openrouter_api_bearer1: "Bearer sk-or-v1-..."
openrouter_api_bearer2: "Bearer sk-or-v1-..."
openrouter_api_bearer3: "Bearer sk-or-v1-..."
openrouter_api_bearer4: "Bearer sk-or-v1-..."
openrouter_api_bearer5: "Bearer sk-or-v1-..."
```

`openrouter_api_bearer1` through `openrouter_api_bearer5` are read separately
and merged into the legacy display entities. Home Assistant requires every
referenced secret to exist. Unused slots can therefore point at the same
bearer as slot 1; the templates only count unique key labels and do not
double-count the same key.

Exposed sensors:

- `sensor.openrouter_balance_remaining`
- `sensor.openrouter_total_credits`
- `sensor.openrouter_total_usage`
- `sensor.openrouter_usage_percent`
- `sensor.openrouter_key_limit_remaining`
- `sensor.openrouter_key_limit`
- `sensor.openrouter_key_total_usage`
- `sensor.openrouter_key_usage_percent`
- `sensor.openrouter_cost_today`
- `sensor.openrouter_cost_week`
- `sensor.openrouter_cost_month`
- `sensor.openrouter_key_count`
- `sensor.openrouter_key_label`
- `sensor.openrouter_key_1_label`
- `sensor.openrouter_key_2_label`
- `sensor.openrouter_key_3_label`
- `sensor.openrouter_key_4_label`
- `sensor.openrouter_key_5_label`
- `sensor.openrouter_limit_reset`
- `sensor.openrouter_activity_prompt_tokens`
- `sensor.openrouter_activity_completion_tokens`
- `sensor.openrouter_activity_reasoning_tokens`
- `sensor.openrouter_activity_tokens`
- `sensor.openrouter_activity_requests`
- `sensor.openrouter_activity_cost`
- `sensor.openrouter_activity_latest_date`

The display's OpenRouter detail page normally uses:

- `sensor.openrouter_balance_remaining`
- `sensor.openrouter_key_count`
- `sensor.openrouter_cost_today`
- `sensor.openrouter_cost_month`
- `sensor.openrouter_activity_prompt_tokens`
- `sensor.openrouter_activity_completion_tokens`

The quadrant/overview rings normally use:

- `sensor.openrouter_balance_remaining`
- `sensor.openrouter_usage_percent`

OpenRouter `/activity` is historical token statistics for completed UTC days,
not a live "today" counter. The prompt/completion values are therefore used as
history on the detail page and I/O Mix, while account balance / key limit /
cost are used for live display values.

## Old entities

The old command_line-based package has been removed. VS Code data goes via
MQTT discovery, and max/left/percent are computed on the ESPHome device.

If Home Assistant still shows old entities from earlier iterations:

1. Check that the new package files are installed.
2. Restart Home Assistant.
3. Go to `Settings -> Devices & services -> Entities`.
4. Manually remove old disabled/unavailable TokenTracker entities if they no
   longer have an active integration behind them.
