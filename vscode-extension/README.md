# TokenTracker VS Code Extension

Version: 1.2.2

Publicerar lokala Codex- och Claude Code-tokenräknare till Home Assistant via
MQTT discovery.

Extensionen är medvetet "raw-only". Den publicerar lokala tokenvärden för
aktuell vecka:

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

Maxgränser, tokens kvar och procent räknas i ESPHome/HA via Token
Tracker-enhetens egna config-entities. Token Tracker-displayens konfigurerbara
5h-perioder räknas på ESP:n från veckosensorerna och de sparade reset-baselines.

## MQTT Payload

State publiceras retained till:

```text
tokentracker/state
```

Exempel:

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
- Räknar deltan mellan `token_count`-händelser och summerar aktuell vecka.
- Faller tillbaka till `~/.codex/state_5.sqlite` och `threads.tokens_used` om
  sessionsfilerna saknar token events.

Claude Code:

- Läser `~/.claude/projects/**/*.jsonl`.
- Summerar `usage.input_tokens`, `usage.output_tokens`,
  `usage.cache_creation_input_tokens` och `usage.cache_read_input_tokens` för
  händelser från aktuell vecka.

Extensionen kör bara medan VS Code körs.

## Legacy Cleanup

På MQTT-connect skickar extensionen tomma retained discovery-configs för äldre
sensorer som inte längre används, exempelvis:

- `tokens_left`
- `usage_percent`
- current thread/model/project
- totals
- collector status/version
- gamla Codex/Claude `*_today`-sensorer
- tidigare rullande Codex/Claude `*_5h`-sensorer

Det gör att Home Assistant kan städa bort de gamla MQTT discovery-entiteterna.

## Build

```powershell
npm install
npm run compile
npm run package
```

Byggd VSIX hamnar lokalt i extension-katalogen och ignoreras av Git:

```text
tokentracker-vscode-1.2.2.vsix
```

Installera i VS Code via:

```text
Extensions -> ... -> Install from VSIX...
```
