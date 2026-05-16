# TokenTracker VS Code Extension

Version: 1.2.1

Publicerar lokala Codex- och Claude Code-tokenräknare till Home Assistant via
MQTT discovery.

Extensionen är medvetet "raw-only". Den publicerar dagens lokala tokenvärden:

- `sensor.tokentracker_vs_code_codex_tokens_today`
- `sensor.tokentracker_vs_code_codex_input_tokens_today`
- `sensor.tokentracker_vs_code_codex_cached_input_tokens_today`
- `sensor.tokentracker_vs_code_codex_output_tokens_today`
- `sensor.tokentracker_vs_code_codex_reasoning_output_tokens_today`
- `sensor.tokentracker_vs_code_claude_code_tokens_today`
- `sensor.tokentracker_vs_code_claude_code_input_tokens_today`
- `sensor.tokentracker_vs_code_claude_code_cache_creation_tokens_today`
- `sensor.tokentracker_vs_code_claude_code_cache_read_tokens_today`
- `sensor.tokentracker_vs_code_claude_code_output_tokens_today`

Maxgränser, tokens kvar och procent räknas i ESPHome/HA via Token
Tracker-enhetens egna config-entities.

## MQTT Payload

State publiceras retained till:

```text
tokentracker/state
```

Exempel:

```json
{
  "updated_at": "2026-05-16T10:14:13.138Z",
  "codex_tokens_today": 37195161,
  "codex_input_tokens_today": 37001234,
  "codex_cached_input_tokens_today": 36000000,
  "codex_output_tokens_today": 193927,
  "codex_reasoning_output_tokens_today": 42100,
  "claude_tokens_today": 17443145,
  "claude_input_tokens_today": 120000,
  "claude_cache_creation_input_tokens_today": 3400000,
  "claude_cache_read_input_tokens_today": 13200000,
  "claude_output_tokens_today": 723145
}
```

Om Codex eller Claude är avstängt i inställningarna utelämnas motsvarande fält.
Om en lokal logg/databas inte kan läsas publiceras `0` för den källan och felet
loggas i VS Code developer console.

## Settings

Lägg in i VS Code settings:

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

`publishIntervalSeconds` har minimum 10 sekunder.

## Datakällor

Codex:

- Läser `~/.codex/sessions/**/*.jsonl`.
- Summerar senaste `total_token_usage` per rollout-fil uppdaterad sedan lokal
  midnatt.
- Faller tillbaka till `~/.codex/state_5.sqlite` och `threads.tokens_used` om
  sessionsfilerna saknar token events.

Claude Code:

- Läser `~/.claude/projects/**/*.jsonl`.
- Summerar `usage.input_tokens`, `usage.output_tokens`,
  `usage.cache_creation_input_tokens` och `usage.cache_read_input_tokens` för
  filer ändrade sedan lokal midnatt.

Extensionen kör bara medan VS Code körs.

## Legacy Cleanup

På MQTT-connect skickar extensionen tomma retained discovery-configs för äldre
sensorer som inte längre används, exempelvis:

- `tokens_left`
- `usage_percent`
- current thread/model/project
- totals
- collector status/version

Det gör att Home Assistant kan städa bort de gamla MQTT discovery-entiteterna.

## Build

```powershell
npm install
npm run compile
npm run package
```

Byggd VSIX hamnar lokalt i extension-katalogen och ignoreras av Git:

```text
tokentracker-vscode-1.2.1.vsix
```

Installera i VS Code via:

```text
Extensions -> ... -> Install from VSIX...
```
