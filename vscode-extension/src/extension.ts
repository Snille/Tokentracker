import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as readline from "readline";
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
  updated_at_epoch: number;
  [key: string]: string | number | boolean;
}

interface CodexUsage {
  codex_tokens_week: number;
  codex_input_tokens_week: number;
  codex_cached_input_tokens_week: number;
  codex_output_tokens_week: number;
  codex_reasoning_output_tokens_week: number;
}

interface ClaudeUsage {
  claude_tokens_week: number;
  claude_input_tokens_week: number;
  claude_cache_creation_input_tokens_week: number;
  claude_cache_read_input_tokens_week: number;
  claude_output_tokens_week: number;
}

interface CodexTokenUsage {
  input_tokens?: number;
  cached_input_tokens?: number;
  output_tokens?: number;
  reasoning_output_tokens?: number;
  total_tokens?: number;
}

interface UsageWindows {
  weekStartMs: number;
}

interface CodexUsageBuckets {
  week: CodexTokenUsage;
}

interface ClaudeUsageBucket {
  inputTokens: number;
  cacheCreationInputTokens: number;
  cacheReadInputTokens: number;
  outputTokens: number;
}

interface ClaudeUsageBuckets {
  week: ClaudeUsageBucket;
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
  "codex_tokens_today",
  "codex_input_tokens_today",
  "codex_cached_input_tokens_today",
  "codex_output_tokens_today",
  "codex_reasoning_output_tokens_today",
  "claude_tokens_today",
  "claude_input_tokens_today",
  "claude_cache_creation_input_tokens_today",
  "claude_cache_read_input_tokens_today",
  "claude_output_tokens_today",
  "codex_tokens_5h",
  "codex_input_tokens_5h",
  "codex_cached_input_tokens_5h",
  "codex_output_tokens_5h",
  "codex_reasoning_output_tokens_5h",
  "claude_tokens_5h",
  "claude_input_tokens_5h",
  "claude_cache_creation_input_tokens_5h",
  "claude_cache_read_input_tokens_5h",
  "claude_output_tokens_5h",
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
  const now = new Date();
  const payload: UsagePayload = {
    updated_at: now.toISOString(),
    updated_at_epoch: Math.floor(now.getTime() / 1000),
  };

  if (settings.codexEnabled) {
    try {
      const codexUsage = await readCodexUsage();
      Object.assign(payload, codexUsage);
    } catch (error) {
      console.error("TokenTracker Codex read failed", error);
      Object.assign(payload, {
        codex_tokens_week: 0,
        codex_input_tokens_week: 0,
        codex_cached_input_tokens_week: 0,
        codex_output_tokens_week: 0,
        codex_reasoning_output_tokens_week: 0,
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
        claude_tokens_week: 0,
        claude_input_tokens_week: 0,
        claude_cache_creation_input_tokens_week: 0,
        claude_cache_read_input_tokens_week: 0,
        claude_output_tokens_week: 0,
      });
    }
  }

  await publishJson(`${settings.statePrefix}/state`, payload, true);
  console.log("TokenTracker published", payload);
  statusItem.text = "TokenTracker: published";
}

async function publishDiscovery(settings: MqttSettings) {
  const sensors: SensorConfig[] = [
    { id: "updated_at_epoch", name: "Updated At Epoch", unit: "s", icon: "mdi:clock-check-outline" },
    { id: "codex_tokens_week", name: "Codex Tokens Week", unit: "tokens", icon: "mdi:calendar-week" },
    { id: "codex_input_tokens_week", name: "Codex Input Tokens Week", unit: "tokens", icon: "mdi:arrow-down-bold-circle-outline" },
    { id: "codex_cached_input_tokens_week", name: "Codex Cached Input Tokens Week", unit: "tokens", icon: "mdi:cached" },
    { id: "codex_output_tokens_week", name: "Codex Output Tokens Week", unit: "tokens", icon: "mdi:arrow-up-bold-circle-outline" },
    { id: "codex_reasoning_output_tokens_week", name: "Codex Reasoning Output Tokens Week", unit: "tokens", icon: "mdi:head-cog-outline" },
    { id: "claude_tokens_week", name: "Claude Code Tokens Week", unit: "tokens", icon: "mdi:calendar-week" },
    { id: "claude_input_tokens_week", name: "Claude Code Input Tokens Week", unit: "tokens", icon: "mdi:arrow-down-bold-circle-outline" },
    { id: "claude_cache_creation_input_tokens_week", name: "Claude Code Cache Creation Tokens Week", unit: "tokens", icon: "mdi:database-plus-outline" },
    { id: "claude_cache_read_input_tokens_week", name: "Claude Code Cache Read Tokens Week", unit: "tokens", icon: "mdi:database-eye-outline" },
    { id: "claude_output_tokens_week", name: "Claude Code Output Tokens Week", unit: "tokens", icon: "mdi:arrow-up-bold-circle-outline" },
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
  const windows = currentUsageWindows();
  const sessionUsage = await readCodexSessionUsage(windows);
  if (sessionUsage.codex_tokens_week > 0) {
    return sessionUsage;
  }

  const dbPath = path.join(os.homedir(), ".codex", "state_5.sqlite");
  if (!fs.existsSync(dbPath)) {
    return emptyCodexUsage();
  }

  const rows = await sqliteAll<{
    tokens_used: number;
  }>(
    dbPath,
    "select tokens_used from threads where updated_at >= ?",
    [Math.floor(windows.weekStartMs / 1000)],
  );

  const tokensWeek = rows.reduce((sum, row) => sum + (row.tokens_used || 0), 0);

  return {
    ...emptyCodexUsage(),
    codex_tokens_week: tokensWeek,
  };
}

async function readCodexSessionUsage(windows: UsageWindows): Promise<CodexUsage> {
  const sessionsPath = path.join(os.homedir(), ".codex", "sessions");
  const buckets: CodexUsageBuckets = {
    week: {},
  };

  if (!fs.existsSync(sessionsPath)) {
    return emptyCodexUsage();
  }

  for (const filePath of walkFiles(sessionsPath, ".jsonl")) {
    if (!path.basename(filePath).startsWith("rollout-")) continue;

    const stat = fs.statSync(filePath);
    if (stat.mtimeMs < windows.weekStartMs) continue;

    const fileBuckets = await readCodexTokenUsageBuckets(filePath, windows, stat.mtimeMs);
    addCodexUsage(buckets.week, fileBuckets.week);
  }

  return {
    codex_tokens_week: numeric(buckets.week.total_tokens),
    codex_input_tokens_week: numeric(buckets.week.input_tokens),
    codex_cached_input_tokens_week: numeric(buckets.week.cached_input_tokens),
    codex_output_tokens_week: numeric(buckets.week.output_tokens),
    codex_reasoning_output_tokens_week: numeric(buckets.week.reasoning_output_tokens),
  };
}

async function readCodexTokenUsageBuckets(filePath: string, windows: UsageWindows, fallbackTimestampMs: number): Promise<CodexUsageBuckets> {
  const buckets: CodexUsageBuckets = {
    week: {},
  };
  let previousUsage: CodexTokenUsage | undefined;
  const reader = readline.createInterface({
    input: fs.createReadStream(filePath, { encoding: "utf8" }),
    crlfDelay: Infinity,
  });

  for await (const line of reader) {
    if (!line.trim()) continue;
    try {
      const event = JSON.parse(line);
      if (event?.payload?.type !== "token_count") continue;
      const currentUsage = event.payload.info?.total_token_usage;
      if (!currentUsage) continue;
      const eventTimestampMs = timestampMs(event) ?? fallbackTimestampMs;
      const delta = codexUsageDelta(currentUsage, previousUsage);
      previousUsage = currentUsage;
      if (eventTimestampMs >= windows.weekStartMs) addCodexUsage(buckets.week, delta);
    } catch {
      // Ignore partial/corrupt log lines.
    }
  }

  return buckets;
}

async function readClaudeUsage(): Promise<ClaudeUsage> {
  const projectsPath = path.join(os.homedir(), ".claude", "projects");
  if (!fs.existsSync(projectsPath)) {
    return emptyClaudeUsage();
  }

  const windows = currentUsageWindows();
  const buckets: ClaudeUsageBuckets = {
    week: emptyClaudeBucket(),
  };

  for (const filePath of walkFiles(projectsPath, ".jsonl")) {
    const stat = fs.statSync(filePath);
    if (stat.mtimeMs < windows.weekStartMs) continue;

    const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/);
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const event = JSON.parse(line);
        const eventTimestampMs = timestampMs(event) ?? stat.mtimeMs;
        if (eventTimestampMs < windows.weekStartMs) continue;
        for (const usage of findUsageObjects(event)) {
          const delta: ClaudeUsageBucket = {
            inputTokens: numeric(usage.input_tokens),
            outputTokens: numeric(usage.output_tokens),
            cacheCreationInputTokens: numeric(usage.cache_creation_input_tokens),
            cacheReadInputTokens: numeric(usage.cache_read_input_tokens),
          };
          addClaudeUsage(buckets.week, delta);
        }
      } catch {
        // Ignore partial/corrupt log lines.
      }
    }
  }

  return {
    claude_tokens_week: claudeTotal(buckets.week),
    claude_input_tokens_week: buckets.week.inputTokens,
    claude_cache_creation_input_tokens_week: buckets.week.cacheCreationInputTokens,
    claude_cache_read_input_tokens_week: buckets.week.cacheReadInputTokens,
    claude_output_tokens_week: buckets.week.outputTokens,
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

function currentUsageWindows(now = new Date()): UsageWindows {
  const weekStart = new Date(now);
  const daysSinceMonday = (weekStart.getDay() + 6) % 7;
  weekStart.setHours(0, 0, 0, 0);
  weekStart.setDate(weekStart.getDate() - daysSinceMonday);
  return {
    weekStartMs: weekStart.getTime(),
  };
}

function emptyCodexUsage(): CodexUsage {
  return {
    codex_tokens_week: 0,
    codex_input_tokens_week: 0,
    codex_cached_input_tokens_week: 0,
    codex_output_tokens_week: 0,
    codex_reasoning_output_tokens_week: 0,
  };
}

function emptyClaudeUsage(): ClaudeUsage {
  return {
    claude_tokens_week: 0,
    claude_input_tokens_week: 0,
    claude_cache_creation_input_tokens_week: 0,
    claude_cache_read_input_tokens_week: 0,
    claude_output_tokens_week: 0,
  };
}

function emptyClaudeBucket(): ClaudeUsageBucket {
  return {
    inputTokens: 0,
    cacheCreationInputTokens: 0,
    cacheReadInputTokens: 0,
    outputTokens: 0,
  };
}

function codexUsageDelta(current: CodexTokenUsage, previous: CodexTokenUsage | undefined): CodexTokenUsage {
  const delta = {
    input_tokens: nonNegativeDelta(current.input_tokens, previous?.input_tokens),
    cached_input_tokens: nonNegativeDelta(current.cached_input_tokens, previous?.cached_input_tokens),
    output_tokens: nonNegativeDelta(current.output_tokens, previous?.output_tokens),
    reasoning_output_tokens: nonNegativeDelta(current.reasoning_output_tokens, previous?.reasoning_output_tokens),
    total_tokens: nonNegativeDelta(current.total_tokens, previous?.total_tokens),
  };
  if (numeric(delta.total_tokens) <= 0) {
    delta.total_tokens =
      numeric(delta.input_tokens) +
      numeric(delta.cached_input_tokens) +
      numeric(delta.output_tokens) +
      numeric(delta.reasoning_output_tokens);
  }
  return delta;
}

function nonNegativeDelta(current: unknown, previous: unknown): number {
  const currentValue = numeric(current);
  if (previous === undefined) return currentValue;
  const previousValue = numeric(previous);
  const delta = currentValue - previousValue;
  return delta >= 0 ? delta : currentValue;
}

function addCodexUsage(target: CodexTokenUsage, addition: CodexTokenUsage) {
  target.input_tokens = numeric(target.input_tokens) + numeric(addition.input_tokens);
  target.cached_input_tokens = numeric(target.cached_input_tokens) + numeric(addition.cached_input_tokens);
  target.output_tokens = numeric(target.output_tokens) + numeric(addition.output_tokens);
  target.reasoning_output_tokens = numeric(target.reasoning_output_tokens) + numeric(addition.reasoning_output_tokens);
  target.total_tokens = numeric(target.total_tokens) + numeric(addition.total_tokens);
}

function addClaudeUsage(target: ClaudeUsageBucket, addition: ClaudeUsageBucket) {
  target.inputTokens += addition.inputTokens;
  target.cacheCreationInputTokens += addition.cacheCreationInputTokens;
  target.cacheReadInputTokens += addition.cacheReadInputTokens;
  target.outputTokens += addition.outputTokens;
}

function claudeTotal(bucket: ClaudeUsageBucket): number {
  return bucket.inputTokens + bucket.cacheCreationInputTokens + bucket.cacheReadInputTokens + bucket.outputTokens;
}

function timestampMs(value: unknown): number | undefined {
  if (!value || typeof value !== "object") return undefined;
  const obj = value as Record<string, unknown>;
  for (const key of ["timestamp", "created_at", "createdAt", "time"]) {
    const parsed = parseTimestampMs(obj[key]);
    if (parsed !== undefined) return parsed;
  }
  const message = obj.message;
  if (message && typeof message === "object") {
    return timestampMs(message);
  }
  return undefined;
}

function parseTimestampMs(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value > 10_000_000_000 ? value : value * 1000;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
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
