# Cleanup Old TokenTracker Entities

Nuvarande lösning använder:

- MQTT discovery från VS Code-extensionen för Codex och Claude Code.
- REST/template packages för OpenRouter och Open WebUI.
- ESPHome config-entities för maxvärden och displayinställningar.

Gamla `command_line`- och helper-baserade entiteter behövs inte längre.

## Ta bort gamla package-filer

Om du fortfarande har äldre package-filer i Home Assistant, ta bort dem innan du
startar om HA. Leta särskilt efter gamla `command_line`-lösningar som skapade
entiteter för:

```text
openai_tokens
openai_usage
anthropic_tokens
anthropic_usage
openrouter_tokens
openrouter_balance
openrouter_usage
ai_token_tracker
```

Behåll däremot:

```text
/config/packages/tokentracker/openrouter.yaml
/config/packages/tokentracker/openwebui.yaml
```

## Ta bort gamla MQTT discovery-sensorer

VS Code-extension `1.1.0` skickar tombstones för gamla MQTT discovery-sensorer,
så Home Assistant bör själv rensa bort legacy-sensorerna efter att extensionen
startat om och anslutit till MQTT.

Om någon gammal entity ändå ligger kvar:

```text
Settings -> Devices & services -> Entities
```

Sök på `tokentracker` och ta bort disabled/unavailable entiteter som inte längre
har en aktiv integration bakom sig.
