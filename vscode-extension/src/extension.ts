import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";
import mqtt, { MqttClient } from "mqtt";
import sqlite3 from "sqlite3";

type SensorClass = "measurement" | "diagnostic";

interface MqttSettings {
  url: string;
  username: string;
  password: string;
  discoveryPrefix: string;
  statePrefix: string;
  intervalSeconds: number;
  codexEnabled: boolean;
  claudeEnabled: boolean;
}

interface SensorConfig {
  id: string;
  name: string;
  unit?: string;
  deviceClass?: string;
  stateClass?: SensorClass;
  icon?: string;
  valueTemplate?: string;
}

interface UsagePayload {
  updated_at: string;
  [key: string]: string | number | boolean;
}

interface CodexUsage {
  codex_tokens_today: number;
}

interface ClaudeUsage {
  claude_tokens_today: number;
}

const legacySensorIds = [
  "codex_tokens_left",
  "codex_usage_percent",
  "codex_current_thread_tokens",
  "codex_threads_today",
  "codex_current_model",
  "codex_current_thread_title",
  "claude_tokens_left",
  "claude_usage_percent",
  "claude_sessions_today",
  "claude_current_project",
  "total_ai_tokens_today",
  "total_ai_tokens_left",
  "total_ai_usage_percent",
  "dominant_tool_today",
  "collector_status",
  "collector_version",
  "collector_updated_at",
];

let client: MqttClient | undefined;
let timer: NodeJS.Timeout | undefined;
let statusItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext) {
  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusItem.text = "TokenTracker: starting";
  statusItem.show();
  context.subscriptions.push(statusItem);

  context.subscriptions.push(
    vscode.commands.registerCommand("tokentracker.publishNow", async () => {
      await publishCycle();
    }),
  );

  connectAndSchedule();
}

export function deactivate() {
  if (timer) clearInterval(timer);
  if (client) client.end(true);
}

function getSettings(): MqttSettings {
  const config = vscode.workspace.getConfiguration("tokentracker");
  return {
    url: config.get("mqtt.url", "mqtt://homeassistant.local:1883"),
    username: config.get("mqtt.username", "tokentracker"),
    password: config.get("mqtt.password", ""),
    discoveryPrefix: config.get("mqtt.discoveryPrefix", "homeassistant"),
    statePrefix: config.get("mqtt.statePrefix", "tokentracker"),
    intervalSeconds: config.get("publishIntervalSeconds", 60),
    codexEnabled: config.get("codex.enabled", true),
    claudeEnabled: config.get("claude.enabled", true),
  };
}

function connectAndSchedule() {
  const settings = getSettings();
  client = mqtt.connect(settings.url, {
    username: settings.username || undefined,
    password: settings.password || undefined,
    clientId: `tokentracker-vscode-${os.hostname().replace(/[^a-zA-Z0-9_-]/g, "_")}`,
    reconnectPeriod: 10_000,
  });

  client.on("connect", async () => {
    statusItem.text = "TokenTracker: MQTT connected";
    await publishDiscovery(settings);
    await publishCycle();
  });

  client.on("error", (error) => {
    statusItem.text = "TokenTracker: MQTT error";
    console.error("TokenTracker MQTT error", error);
  });

  timer = setInterval(() => {
    publishCycle().catch((error) => console.error("TokenTracker publish failed", error));
  }, Math.max(settings.intervalSeconds, 10) * 1000);
}

async function publishCycle() {
  if (!client || !client.connected) {
    statusItem.text = "TokenTracker: MQTT offline";
    return;
  }

  const settings = getSettings();
  const payload: UsagePayload = { updated_at: new Date().toISOString() };

  if (settings.codexEnabled) {
    try {
      const codexUsage = await readCodexUsage();
      Object.assign(payload, codexUsage);
    } catch (error) {
      console.error("TokenTracker Codex read failed", error);
      Object.assign(payload, {
        codex_tokens_today: 0,
      });
    }
  }
  if (settings.claudeEnabled) {
    try {
      const claudeUsage = await readClaudeUsage();
      Object.assign(payload, claudeUsage);
    } catch (error) {
      console.error("TokenTracker Claude read failed", error);
      Object.assign(payload, {
        claude_tokens_today: 0,
      });
    }
  }

  await publishJson(`${settings.statePrefix}/state`, payload, true);
  console.log("TokenTracker published", payload);
  statusItem.text = "TokenTracker: published";
}

async function publishDiscovery(settings: MqttSettings) {
  const sensors: SensorConfig[] = [
    { id: "codex_tokens_today", name: "Codex Tokens Today", unit: "tokens", icon: "mdi:counter" },
    { id: "claude_tokens_today", name: "Claude Code Tokens Today", unit: "tokens", icon: "mdi:counter" },
  ];

  for (const sensorId of legacySensorIds) {
    const objectId = `tokentracker_${sensorId}`;
    await publishRaw(`${settings.discoveryPrefix}/sensor/${objectId}/config`, "", true);
  }

  for (const sensor of sensors) {
    const objectId = `tokentracker_${sensor.id}`;
    const configTopic = `${settings.discoveryPrefix}/sensor/${objectId}/config`;
    const configPayload = {
      name: sensor.name,
      unique_id: objectId,
      object_id: objectId,
      state_topic: `${settings.statePrefix}/state`,
      value_template: sensor.valueTemplate ?? `{{ value_json.${sensor.id} }}`,
      unit_of_measurement: sensor.unit,
      icon: sensor.icon,
      device: {
        identifiers: ["tokentracker_vscode"],
        name: "TokenTracker VS Code",
        manufacturer: "Snille",
        model: "VS Code MQTT Collector",
      },
    };
    await publishJson(configTopic, configPayload, true);
  }
}

async function readCodexUsage(): Promise<CodexUsage> {
  const dbPath = path.join(os.homedir(), ".codex", "state_5.sqlite");
  if (!fs.existsSync(dbPath)) {
    return {
      codex_tokens_today: 0,
    };
  }

  const startOfDay = Math.floor(new Date().setHours(0, 0, 0, 0) / 1000);
  const rows = await sqliteAll<{
    tokens_used: number;
  }>(
    dbPath,
    "select tokens_used from threads where updated_at >= ?",
    [startOfDay],
  );

  const tokensToday = rows.reduce((sum, row) => sum + (row.tokens_used || 0), 0);

  return {
    codex_tokens_today: tokensToday,
  };
}

async function readClaudeUsage(): Promise<ClaudeUsage> {
  const projectsPath = path.join(os.homedir(), ".claude", "projects");
  if (!fs.existsSync(projectsPath)) {
    return {
      claude_tokens_today: 0,
    };
  }

  const startOfDayMs = new Date().setHours(0, 0, 0, 0);
  let totalTokens = 0;

  for (const filePath of walkFiles(projectsPath, ".jsonl")) {
    const stat = fs.statSync(filePath);
    if (stat.mtimeMs < startOfDayMs) continue;

    const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/);
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const event = JSON.parse(line);
        for (const usage of findUsageObjects(event)) {
          totalTokens += numeric(usage.input_tokens);
          totalTokens += numeric(usage.output_tokens);
          totalTokens += numeric(usage.cache_creation_input_tokens);
          totalTokens += numeric(usage.cache_read_input_tokens);
        }
      } catch {
        // Ignore partial/corrupt log lines.
      }
    }
  }

  return {
    claude_tokens_today: totalTokens,
  };
}

function findUsageObjects(value: unknown): Array<Record<string, unknown>> {
  const found: Array<Record<string, unknown>> = [];
  const stack = [value];
  while (stack.length) {
    const item = stack.pop();
    if (Array.isArray(item)) {
      stack.push(...item);
    } else if (item && typeof item === "object") {
      const obj = item as Record<string, unknown>;
      if (obj.usage && typeof obj.usage === "object" && !Array.isArray(obj.usage)) {
        found.push(obj.usage as Record<string, unknown>);
      }
      for (const child of Object.values(obj)) {
        if (child && typeof child === "object") stack.push(child);
      }
    }
  }
  return found;
}

function numeric(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function walkFiles(root: string, suffix: string): string[] {
  const result: string[] = [];
  const entries = fs.readdirSync(root, { withFileTypes: true });
  for (const entry of entries) {
    const entryPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      result.push(...walkFiles(entryPath, suffix));
    } else if (entry.isFile() && entry.name.endsWith(suffix)) {
      result.push(entryPath);
    }
  }
  return result;
}

function sqliteAll<T>(dbPath: string, sql: string, params: unknown[]): Promise<T[]> {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY, (error) => {
      if (error) reject(error);
    });
    db.all(sql, params, (error, rows: T[]) => {
      db.close();
      if (error) reject(error);
      else resolve(rows);
    });
  });
}

function publishJson(topic: string, payload: unknown, retain: boolean): Promise<void> {
  return publishRaw(topic, JSON.stringify(payload), retain);
}

function publishRaw(topic: string, payload: string, retain: boolean): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!client) {
      reject(new Error("MQTT client is not connected"));
      return;
    }
    client.publish(topic, payload, { qos: 0, retain }, (error) => {
      if (error) {
        console.error("TokenTracker publish error", topic, error);
        reject(error);
      } else {
        console.log("TokenTracker MQTT publish", topic);
        resolve();
      }
    });
  });
}
