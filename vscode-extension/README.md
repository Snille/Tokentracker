# TokenTracker VS Code Extension

Version: 1.2.2

Publishes local Codex and Claude Code token counters to Home Assistant via
MQTT discovery.

The extension is intentionally "raw-only". It publishes local token values
for the current week:

- `sensor.tokentracker_vs_code_codex_tokens_week`
- `sensor.tokentracker_vs_code_codex_input_tokens_week`
- `sensor.tokentracker_vs_code_codex_cached_input_tokens_week`
- `sensor.tokentracker_vs_code_codex_output_tokens_week`
- `sensor.tokentracker_vs_code_codex_reasoning_output_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_input_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_cache_creation_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_cache_read_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_output_tokens_week`
- `sensor.tokentracker_vs_code_updated_at_epoch`

Max limits, tokens remaining and percent are computed in ESPHome/HA via the
Token Tracker device's own config entities. The Token Tracker display's
configurable 5h periods are computed on the ESP from the weekly sensors and
the saved reset baselines.

## MQTT Payload

State is published retained to:

```text
tokentracker/state
```

Example:

```json
{
  "updated_at": "2026-05-16T10:14:13.138Z",
  "updated_at_epoch": 1778948053,
  "codex_tokens_week": 37195161,
  "codex_input_tokens_week": 37001234,
  "codex_cached_input_tokens_week": 36000000,
  "codex_output_tokens_week": 193927,
  "codex_reasoning_output_tokens_week": 42100,
  "claude_tokens_week": 17443145,
  "claude_input_tokens_week": 120000,
  "claude_cache_creation_input_tokens_week": 3400000,
  "claude_cache_read_input_tokens_week": 13200000,
  "claude_output_tokens_week": 723145
}
```

If Codex or Claude is disabled in settings, the matching fields are omitted.
If a local log/database cannot be read, `0` is published for that source and
the error is logged in the VS Code developer console.

## Settings

Add to your VS Code settings:

```json
{
  "tokentracker.mqtt.url": "mqtt://homeassistant.local:1883",
  "tokentracker.mqtt.username": "tokentracker",
  "tokentracker.mqtt.password": "your-password",
  "tokentracker.publishIntervalSeconds": 60,
  "tokentracker.codex.enabled": true,
  "tokentracker.claude.enabled": true
}
```

`publishIntervalSeconds` has a minimum of 10 seconds.

## Data sources

Codex:

- Reads `~/.codex/sessions/**/*.jsonl`.
- Counts deltas between `token_count` events and sums up the current week.
- Falls back to `~/.codex/state_5.sqlite` and `threads.tokens_used` if the
  session files lack token events.

Claude Code:

- Reads `~/.claude/projects/**/*.jsonl`.
- Sums `usage.input_tokens`, `usage.output_tokens`,
  `usage.cache_creation_input_tokens` and `usage.cache_read_input_tokens` for
  events from the current week.

The extension only runs while VS Code is running.

## Legacy Cleanup

On MQTT connect, the extension publishes empty retained discovery configs for
older sensors that are no longer used, for example:

- `tokens_left`
- `usage_percent`
- current thread/model/project
- totals
- collector status/version
- old Codex/Claude `*_today` sensors
- previous rolling Codex/Claude `*_5h` sensors

This lets Home Assistant clean up the old MQTT discovery entities.

## Build

```powershell
npm install
npm run compile
npm run package
```

The built VSIX ends up locally in the extension directory and is ignored by
Git:

```text
tokentracker-vscode-1.2.2.vsix
```

Install in VS Code via:

```text
Extensions -> ... -> Install from VSIX...
```
