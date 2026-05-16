# TokenTracker Home Assistant Package

Package version: `1.1.0`

Det här paketet innehåller Home Assistant REST/template-sensorer för de delar som
inte kommer från VS Code-extensionen:

- OpenRouter credits och key-usage.
- Open WebUI usage/statistik.

Codex och Claude Code kommer från VS Code-extensionen via MQTT discovery:

- `sensor.tokentracker_vs_code_codex_tokens_today`
- `sensor.tokentracker_vs_code_claude_code_tokens_today`

ESPHome-displayen använder sedan dessa råvärden och sina egna config-entities
för maxvärden, tokens kvar och procent.

## Installation

Kopiera katalogen till:

```text
/config/packages/tokentracker/
```

Se till att `configuration.yaml` laddar packages:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Starta om Home Assistant efter ändringar i package-filerna.

## OpenRouter

`openrouter.yaml` använder två endpoints:

- `GET https://openrouter.ai/api/v1/credits`
- `GET https://openrouter.ai/api/v1/key`

Lägg till i `/config/secrets.yaml`:

```yaml
openrouter_management_bearer: "Bearer sk-or-v1-..."
openrouter_api_bearer: "Bearer sk-or-v1-..."
```

Om du bara använder en OpenRouter-nyckel kan båda secrets peka på samma bearer.

Exponerade sensorer:

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
- `sensor.openrouter_key_label`
- `sensor.openrouter_limit_reset`

Displayen använder normalt:

- `sensor.openrouter_key_limit_remaining`
- `sensor.openrouter_key_usage_percent`

## Open WebUI

`openwebui.yaml` kräver en bearer från ett Open WebUI-admin-konto.

Lägg till i `/config/secrets.yaml`:

```yaml
openwebui_bearer: "Bearer eyJhbGciOi..."
openwebui_users_url: "http://llm.example.net:8080/api/v1/users/"
openwebui_chats_url: "http://llm.example.net:8080/api/v1/chats/all/db"
openwebui_analytics_url: "http://llm.example.net:8080/api/v1/analytics/users"
openwebui_tokens_today_url: >-
  http://llm.example.net:8080/api/v1/analytics/tokens?start_date={{ now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() | int }}&end_date={{ now().timestamp() | int }}
```

Endpoints som används:

- `GET /api/v1/users/`
- `GET /api/v1/chats/all/db`
- `GET /api/v1/analytics/users`
- `GET /api/v1/analytics/tokens`

Exponerade sensorer:

- `sensor.openwebui_total_users`
- `sensor.openwebui_active_users`
- `sensor.openwebui_total_chats`
- `sensor.openwebui_chats_today`
- `sensor.openwebui_top_model`
- `sensor.openwebui_models_used_week`
- `sensor.openwebui_messages_total`
- `sensor.openwebui_tokens_total`
- `sensor.openwebui_tokens_today`
- `sensor.openwebui_input_tokens_today`
- `sensor.openwebui_output_tokens_today`

Displayen använder normalt:

- `sensor.openwebui_tokens_today`
- `sensor.openwebui_chats_today`

`/chats/all/db` kan vara tung på stora installationer och pollas därför var 5:e
minut. Open WebUI har ingen ren "currently connected users"-endpoint, så
`active_users` räknas från `last_active_at` de senaste 5 minuterna.

## Gamla entiteter

Det gamla command_line-baserade paketet är borttaget. VS Code-data går via MQTT
discovery, och max/left/procent räknas på ESPHome-enheten.

Om Home Assistant fortfarande visar gamla entiteter från tidigare iterationer:

1. Kontrollera att nya package-filer är installerade.
2. Starta om Home Assistant.
3. Gå till `Settings -> Devices & services -> Entities`.
4. Ta bort gamla disabled/unavailable TokenTracker-entiteter manuellt om de inte
   längre har en aktiv integration bakom sig.
