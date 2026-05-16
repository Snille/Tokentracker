# Token Tracker

Project version: `0.2.0`

Token Tracker är en personlig AI-usage-display för Waveshare ESP32-S3 Touch
AMOLED 1.75, Home Assistant och en liten VS Code-extension.

Den är byggd runt min miljö, men strukturen går att återanvända om man byter
ut entity-id:n, MQTT-inställningar och API-secrets.

## Delar

- `esphome/round-token-tracker.yaml` - ESPHome-displayen.
- `homeassistant/packages/tokentracker/` - Home Assistant packages för
  OpenRouter och Open WebUI.
- `vscode-extension/` - VS Code-extension som publicerar lokala Codex- och
  Claude Code-tokenräknare till MQTT discovery.

## Versions

- Project: `0.2.0` (`VERSION`)
- ESPHome display: `1.8.1`
- Home Assistant package: `1.2.1`
- VS Code extension: `1.2.1`

Se `HISTORY.md` för ändringshistorik.

## Datamodell

Displayen hämtar råvärden från Home Assistant och räknar själv ut max, kvar och
procent. Maxvärden justeras som config-entities på ESPHome-enheten.

| Källa | HA-entity | Ansvar |
| --- | --- | --- |
| Codex | `sensor.tokentracker_vs_code_codex_tokens_today` | VS Code-extension läser lokala Codex sessions/SQLite och publicerar tokens idag via MQTT |
| Claude Code | `sensor.tokentracker_vs_code_claude_code_tokens_today` | VS Code-extension läser lokala Claude JSONL-loggar och publicerar tokens idag via MQTT |
| Open WebUI | `sensor.openwebui_tokens_today` | HA REST package hämtar tokens idag från Open WebUI analytics |
| OpenRouter | `sensor.openrouter_key_limit_remaining`, `sensor.openrouter_key_usage_percent` | HA REST package hämtar credits/key-data från flera OpenRouter-nycklar |

VS Code-extensionen är medvetet "raw-only": den skickar bara dagens tokenvärden
och underfält för input/output/cache/reasoning där källan har dem.
`tokens left`, usage-percent och maxgränser ligger i ESPHome/HA så de kan ändras
på Token Tracker-enheten.

## ESPHome-display

Nuvarande ESPHome-version: `1.8.1`.

Displayen visar:

- Klocka.
- Codex med input/output/cache/reasoning.
- Claude Code med input/output/cache.
- OpenRouter med account balance, key-count, key usage och activity-historik.
- Open WebUI med input/output, chats, aktiva användare och modellräkning.
- Quadrant overview med Codex, Claude Code, OpenRouter, Open WebUI och analog
  klocka.
- I/O Mix med input/output/cache/reasoning över alla källor.
- Today med dagens live-tokenvärden, OpenRouter-kostnad, chats och key-count.

Styrning:

- Swipe vänster/höger byter skärm.
- Kort tryck på fysiska toppknappen pausar/återupptar auto-rotate-timern.
- Långt tryck på toppknappen släcker/tänder displayen.
- `Next Screen` och `Previous Screen` finns också som HA-knappar.

Visuella ringar:

- Yttre usage-ring visar användning mot maxvärde.
- Mörkblå inre timer-ring visar tid kvar till nästa auto-rotate och släcks när
  auto-rotate är pausad.
- Klocksidan använder yttre ringen som sekundvisare.

Viktiga config-entities på ESPHome-enheten:

- `Codex Max` i ktokens.
- `Claude Max` i ktokens.
- `WebUI Max` i ktokens.
- `Display Brightness Percent`.
- `Screen Interval` för singel-skärmarna.
- `Overview Screen Interval` för quadrant-, I/O Mix- och Today-skärmarna.
- `Display Rotation`.
- `Auto Orientation`.
- `Auto Rotate Screens`.
- `Show Clock`, `Show Codex`, `Show Claude Code`, `Show OpenRouter`,
  `Show Open WebUI`, `Show Overview`.

Substitutions i början av `esphome/round-token-tracker.yaml` styr entity-id:n och
slider-maxvärden. Exempel:

```yaml
openai_tokens_entity: sensor.tokentracker_vs_code_codex_tokens_today
anthropic_tokens_entity: sensor.tokentracker_vs_code_claude_code_tokens_today
openwebui_tokens_entity: sensor.openwebui_tokens_today
codex_max_ktokens: "250000"
claude_max_ktokens: "250000"
openwebui_max_ktokens: "1250"
```

## Home Assistant

Kopiera `homeassistant/packages/tokentracker/` till:

```text
/config/packages/tokentracker/
```

Se till att `configuration.yaml` laddar packages:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Detaljer om secrets, endpoints och sensorer finns i
`homeassistant/packages/tokentracker/README.md`.

## VS Code-extension

Extensionen finns i `vscode-extension/`.

Installera en byggd VSIX via:

```text
Extensions -> ... -> Install from VSIX...
```

Bygg en installerbar VSIX vid behov med:

```powershell
cd vscode-extension
npm install
npm run compile
npm run package
```

Extensionen kör bara när VS Code körs. Den publicerar MQTT discovery och state
till samma broker som Home Assistant använder.

## Secrets och repo

Detta repo bör inte innehålla riktiga API-nycklar eller tokens. Lokala filer som
`.ai-tokens`, `.ha-token`, VSIX-filer, `node_modules`, `dist` och lokala VS
Code-inställningar ligger i `.gitignore`. Byggda VSIX-filer är lokala artifacts
och ska inte checkas in.

Om detta läggs upp publikt bör det beskrivas som ett exempelprojekt eller en
referensimplementation. Andra kan använda det, men behöver minst ändra:

- Home Assistant entity-id:n.
- MQTT broker och credentials.
- OpenRouter secrets.
- Open WebUI URL:er och admin bearer.
- ESPHome Wi-Fi/base-konfiguration.

## Hårdvara

Konfigurationen är byggd för Waveshare ESP32-S3 Touch AMOLED 1.75:

- CO5300 AMOLED, 466x466, QSPI.
- CST9217 touch.
- QMI8658 IMU för auto-orientation.
- GPIO38/4/5/6/7 för QSPI-display.
- GPIO12 CS, GPIO39 display reset.
- GPIO14/GPIO15 I2C.
- GPIO11 touch interrupt, GPIO40 touch reset.

Referenser:

- https://www.waveshare.com/wiki/ESP32-S3-Touch-AMOLED-1.75
- https://devices.esphome.io/devices/waveshare-esp32-s3-touch-amoled-1.75/
- https://esphome.io/components/touchscreen/
