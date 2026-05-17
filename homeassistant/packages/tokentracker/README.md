# TokenTracker Home Assistant Package

Package version: `1.2.1`

Det här paketet innehåller Home Assistant REST/template-sensorer för de delar som
inte kommer från VS Code-extensionen:

- OpenRouter credits, account balance, multi-key usage och
  activity-tokenhistorik.
- Open WebUI usage/statistik inklusive input/output tokens, modellräkning och
  dagens I/O-procent.

Codex och Claude Code kommer från VS Code-extensionen via MQTT discovery:

- `sensor.tokentracker_vs_code_codex_tokens_week`
- `sensor.tokentracker_vs_code_claude_code_tokens_week`
- `sensor.tokentracker_vs_code_updated_at_epoch`

ESPHome-displayen använder sedan dessa råvärden och sina egna config-entities
för 5h-perioder, maxvärden, tokens kvar och procent.

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

`openrouter.yaml` använder tre endpoints:

- `GET https://openrouter.ai/api/v1/credits`
- `GET https://openrouter.ai/api/v1/key`
- `GET https://openrouter.ai/api/v1/activity`

Lägg till i `/config/secrets.yaml`:

```yaml
openrouter_management_bearer: "Bearer sk-or-v1-..."
openrouter_api_bearer1: "Bearer sk-or-v1-..."
openrouter_api_bearer2: "Bearer sk-or-v1-..."
openrouter_api_bearer3: "Bearer sk-or-v1-..."
openrouter_api_bearer4: "Bearer sk-or-v1-..."
openrouter_api_bearer5: "Bearer sk-or-v1-..."
```

`openrouter_api_bearer1` till `openrouter_api_bearer5` läses var för sig och
slås ihop till de gamla display-entiteterna. Home Assistant kräver att alla
refererade secrets finns. Oanvända slots kan därför peka på samma bearer som
slot 1; templates räknar bara unika key-labels och dubbelräknar inte samma
nyckel.

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

Displayens OpenRouter-detaljsida använder normalt:

- `sensor.openrouter_balance_remaining`
- `sensor.openrouter_key_count`
- `sensor.openrouter_cost_today`
- `sensor.openrouter_cost_month`
- `sensor.openrouter_activity_prompt_tokens`
- `sensor.openrouter_activity_completion_tokens`

Quadrant/overview-ringarna använder normalt:

- `sensor.openrouter_balance_remaining`
- `sensor.openrouter_usage_percent`

OpenRouter `/activity` är historisk tokenstatistik för avslutade UTC-dagar, inte
en live "idag"-räknare. Prompt/completion-värdena används därför som historik på
detaljsidan och I/O Mix, medan account balance/key limit/cost används för live
displayvärden.

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
- `sensor.openwebui_models_today`
- `sensor.openwebui_input_token_percent_today`
- `sensor.openwebui_output_token_percent_today`

Displayen använder normalt:

- `sensor.openwebui_tokens_today`
- `sensor.openwebui_input_tokens_today`
- `sensor.openwebui_output_tokens_today`
- `sensor.openwebui_chats_today`
- `sensor.openwebui_active_users`
- `sensor.openwebui_models_today`
- `sensor.openwebui_output_token_percent_today`

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
