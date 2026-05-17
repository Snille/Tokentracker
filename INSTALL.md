# Installera Token Tracker från scratch

Den här guiden utgår från att du har:

- Waveshare ESP32-S3 Touch AMOLED 1.75.
- Home Assistant med ESPHome.
- VS Code på datorn där du kör Codex och/eller Claude Code.
- Tillgång till detta git-repo.
- Node.js LTS på datorn där VS Code-extensionen ska byggas.
- En MQTT-broker som Home Assistant kan läsa från, till exempel Mosquitto
  broker add-on.

Token Tracker består av tre delar:

- ESPHome-displayen i `esphome/round-token-tracker.yaml`.
- Home Assistant packages för OpenRouter/Open WebUI i
  `homeassistant/packages/tokentracker/`.
- VS Code-extensionen i `vscode-extension/`, som publicerar lokala Codex- och
  Claude Code-veckoräknare till MQTT discovery.

## 1. Klona repot

På din dator:

```powershell
git clone <repo-url> Tokentracker
cd Tokentracker
```

## 2. Förbered Home Assistant

### MQTT

Installera och starta en MQTT-broker om du inte redan har en. I Home Assistant är
det enklast med:

```text
Settings -> Add-ons -> Mosquitto broker
```

Skapa en MQTT-användare som VS Code-extensionen får använda, till exempel:

```text
username: tokentracker
password: <ett eget lösenord>
```

Se till att Home Assistant har MQTT-integrationen aktiv:

```text
Settings -> Devices & services -> MQTT
```

### Packages

Kopiera repo-katalogen:

```text
homeassistant/packages/tokentracker/
```

till Home Assistant:

```text
/config/packages/tokentracker/
```

Se till att `/config/configuration.yaml` laddar packages:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Starta om Home Assistant efter ändringen.

## 3. Lägg in Home Assistant secrets

Öppna `/config/secrets.yaml` i Home Assistant.

### OpenRouter

Om du vill använda OpenRouter-sidorna, lägg till:

```yaml
openrouter_management_bearer: "Bearer sk-or-v1-..."
openrouter_api_bearer1: "Bearer sk-or-v1-..."
openrouter_api_bearer2: "Bearer sk-or-v1-..."
openrouter_api_bearer3: "Bearer sk-or-v1-..."
openrouter_api_bearer4: "Bearer sk-or-v1-..."
openrouter_api_bearer5: "Bearer sk-or-v1-..."
```

Home Assistant kräver att alla fem `openrouter_api_bearer*` finns. Om du bara
har en nyckel kan alla fem peka på samma bearer; templates räknar unika key
labels och dubbelräknar inte samma nyckel.

Om du inte vill använda OpenRouter alls behöver du antingen ta bort/inte kopiera
`openrouter.yaml`, eller lägga in dummy-secrets och acceptera att sensorerna blir
noll/unavailable.

### Open WebUI

Om du vill använda Open WebUI-sidorna, lägg till:

```yaml
openwebui_bearer: "Bearer eyJhbGciOi..."
openwebui_users_url: "http://din-openwebui:8080/api/v1/users/"
openwebui_chats_url: "http://din-openwebui:8080/api/v1/chats/all/db"
openwebui_analytics_url: "http://din-openwebui:8080/api/v1/analytics/users"
openwebui_tokens_today_url: >-
  http://din-openwebui:8080/api/v1/analytics/tokens?start_date={{ now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() | int }}&end_date={{ now().timestamp() | int }}
```

Om du inte vill använda Open WebUI behöver du antingen ta bort/inte kopiera
`openwebui.yaml`, eller lägga in dummy-secrets/URL:er och acceptera att
sensorerna blir noll/unavailable.

Starta om Home Assistant efter att secrets och packages är på plats.

## 4. Bygg och installera VS Code-extensionen

Extensionen måste installeras i den VS Code där Codex/Claude Code körs.

Gå till extension-katalogen:

```powershell
cd vscode-extension
npm install
npm run compile
npm run package
```

Det skapar en VSIX, till exempel:

```text
tokentracker-vscode-1.2.2.vsix
```

Installera den i VS Code:

```text
Extensions -> ... -> Install from VSIX...
```

Lägg sedan in inställningar i VS Code `settings.json`:

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

Kör gärna:

```text
Developer: Reload Window
TokenTracker: Publish Now
```

Efter någon minut bör Home Assistant få MQTT discovery-sensorer som:

```text
sensor.tokentracker_vs_code_codex_tokens_week
sensor.tokentracker_vs_code_claude_code_tokens_week
sensor.tokentracker_vs_code_updated_at_epoch
```

Extensionen läser lokala filer:

- Codex: `~/.codex/sessions/**/*.jsonl`, fallback `~/.codex/state_5.sqlite`.
- Claude Code: `~/.claude/projects/**/*.jsonl`.

Den skickar veckoräknare. ESP:n räknar själv fram aktuell 5h-period med egna
baselines.

## 5. Förbered ESPHome secrets

ESPHome-filen inkluderar:

```yaml
<<: !include base/base-iot.yaml
```

`esphome/base/base-iot.yaml` kräver dessa secrets i ESPHome:

```yaml
iot_wifi_ssid: "ditt-iot-wifi"
iot_wifi_password: "wifi-lösenord"
iot_wifi_domain: ".local"
wifi_ap_password: "fallback-ap-lösenord"
api_key: "base64-api-key-från-esphome"
ota_password: "ota-lösenord"
```

I ESPHome Dashboard kan du skapa en ny device bara för att få en API encryption
key, eller generera en själv enligt ESPHome-dokumentationen.

## 6. Lägg in ESPHome-konfigurationen

Kopiera dessa delar till din ESPHome-konfigurationskatalog:

```text
esphome/round-token-tracker.yaml
esphome/base/base-iot.yaml
esphome/images/
```

Öppna `round-token-tracker.yaml` och kontrollera substitutions i början:

```yaml
openai_week_tokens_entity: sensor.tokentracker_vs_code_codex_tokens_week
anthropic_week_tokens_entity: sensor.tokentracker_vs_code_claude_code_tokens_week
vscode_updated_at_epoch_entity: sensor.tokentracker_vs_code_updated_at_epoch
openwebui_tokens_entity: sensor.openwebui_tokens_today
codex_max_ktokens: "250000"
claude_max_ktokens: "250000"
openwebui_max_ktokens: "1250"
```

Ändra entity-id:n om dina HA-entiteter heter något annat.

## 7. Flasha displayen

I ESPHome Dashboard:

1. Lägg till eller öppna device `round-token-tracker`.
2. Välj `Install`.
3. Första gången: använd USB till displayen.
4. Efter första flashen kan OTA användas om Wi-Fi/API fungerar.

Konfigurationen använder external component för touch-drivern:

```text
https://github.com/shelson/esphome-cst9217
```

ESPHome behöver därför internet vid build om komponenten inte redan är cachad.

## 8. Konfigurera displayen i Home Assistant

När ESP:n är ansluten dyker Token Tracker upp som en ESPHome-enhet i Home
Assistant. Ställ in de viktigaste config-entiteterna:

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

Codex/Claude max-värden är i ktokens per 5h-period.

`Codex/Claude 5h Start Hour` är `0-24`. `0` betyder `00:00`, och `24` behandlas
som `00:00`. Minute är `0-59`.

När du ändrar en 5h-starttid sparar ESP:n aktuell veckoräknare som baseline.
Efter det fortsätter den räkna perioder var femte timme.

## 9. Kontrollera att allt fungerar

I Home Assistant bör du se:

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

För OpenRouter:

```text
sensor.openrouter_balance_remaining
sensor.openrouter_usage_percent
sensor.openrouter_cost_today
sensor.openrouter_cost_month
sensor.openrouter_activity_prompt_tokens
sensor.openrouter_activity_completion_tokens
```

För Open WebUI:

```text
sensor.openwebui_tokens_today
sensor.openwebui_input_tokens_today
sensor.openwebui_output_tokens_today
sensor.openwebui_chats_today
sensor.openwebui_active_users
sensor.openwebui_models_today
sensor.openwebui_output_token_percent_today
```

På displayen:

- Swipe vänster/höger byter sida.
- Tryck på en individuell provider-skärm hoppar tillbaka till quadrant-sidan.
- Kort tryck på toppknappen pausar/återupptar auto-rotate.
- Långt tryck på toppknappen släcker/tänder displayen.
- På quadrant-sidan kan du trycka på en kvadrant för att hoppa till respektive
  detaljsida.

## 10. Felsökning

### VS Code-sensorer saknas

- Kontrollera att VSIX är installerad och att VS Code är reloadad.
- Kontrollera MQTT-inställningarna i VS Code.
- Kör `TokenTracker: Publish Now`.
- Kontrollera att MQTT integrationen i HA är aktiv.
- Kom ihåg att extensionen bara kör när VS Code körs.

### ESP visar `VS Code stale`

- VS Code-extensionen publicerar inte längre eller VS Code är stängt.
- Kontrollera `sensor.tokentracker_vs_code_updated_at_epoch`.
- Kör `TokenTracker: Publish Now`.

### ESPHome build misslyckas

- Kontrollera ESPHome secrets.
- Kontrollera att `images/` finns bredvid YAML-filen.
- Kontrollera att ESPHome kan hämta external component från GitHub.
- Första flashen kan behöva göras via USB.

### OpenRouter/Open WebUI visar noll

- Kontrollera `secrets.yaml`.
- Kontrollera att HA kan nå endpoints.
- Starta om Home Assistant efter package/secrets-ändringar.
- Titta i Home Assistant logs efter REST-sensorfel.

### Gamla entiteter ligger kvar

VS Code-extensionen tombstonar äldre MQTT discovery-entiteter, men HA kan ibland
behålla disabled/unavailable entities. Ta bort dem manuellt här:

```text
Settings -> Devices & services -> Entities
```

## Uppdatering senare

När repot ändras:

1. Pull:a senaste kod.
2. Bygg ny VSIX om `vscode-extension/` ändrats.
3. Installera ny VSIX och reload:a VS Code.
4. Uppdatera ESPHome om `esphome/round-token-tracker.yaml` ändrats.
5. Kopiera om Home Assistant package-filer om `homeassistant/packages/` ändrats.
