# Cleanup Old TokenTracker Entities

The current setup uses:

- MQTT discovery from the VS Code extension for Codex and Claude Code.
- REST/template packages for OpenRouter and Open WebUI.
- ESPHome config entities for max values and display settings.

Old `command_line`- and helper-based entities are no longer needed.

## Remove old package files

If you still have older package files in Home Assistant, remove them before
restarting HA. Look in particular for old `command_line` solutions that
created entities such as:

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

Keep, on the other hand:

```text
/config/packages/tokentracker/openrouter.yaml
/config/packages/tokentracker/openwebui.yaml
```

## Remove old MQTT discovery sensors

VS Code extension `1.1.0` publishes tombstones for old MQTT discovery sensors,
so Home Assistant should clean up the legacy sensors itself after the
extension restarts and reconnects to MQTT.

If any old entity is still left:

```text
Settings -> Devices & services -> Entities
```

Search for `tokentracker` and remove disabled/unavailable entities that no
longer have an active integration behind them.
