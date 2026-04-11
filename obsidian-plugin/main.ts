import { App, Notice, Plugin, PluginSettingTab, Setting, WorkspaceLeaf } from "obsidian";
import { credentials, loadPackageDefinition, ServiceError } from "@grpc/grpc-js";
import protoLoader from "@grpc/proto-loader";
import path from "path";
import { fileURLToPath } from "url";

interface MeraContextBridgeSettings {
  grpcAddress: string;
  userId: string;
  sessionId: string;
  sharedSecret: string;
  spaceId: string;
  flushIntervalMs: number;
  heartbeatIntervalMs: number;
}

interface QueuedEvent {
  event_id: string;
  event_type: "open" | "click" | "selection" | "navigate";
  note_path: string;
  note_title?: string;
  selection?: string;
  clicked_target?: string;
  cursor_line?: number;
  event_ts_ms: number;
  metadata?: Record<string, unknown>;
}

const DEFAULT_SETTINGS: MeraContextBridgeSettings = {
  grpcAddress: "127.0.0.1:50051",
  userId: "default-user",
  sessionId: "default",
  sharedSecret: "",
  spaceId: "",
  flushIntervalMs: 1500,
  heartbeatIntervalMs: 5000,
};

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const sidecarProtoPath = path.join(__dirname, "sidecar.proto");

interface SidecarGrpcClient {
  Heartbeat: (
    request: Record<string, unknown>,
    callback: (error: ServiceError | null, response: { status: string; session_id: string }) => void
  ) => void;
  IngestEvent: (
    request: Record<string, unknown>,
    callback: (
      error: ServiceError | null,
      response: { status: string; session_id: string; active_note_path?: string; recent_events?: number }
    ) => void
  ) => void;
  GetSession: (
    request: Record<string, unknown>,
    callback: (
      error: ServiceError | null,
      response: { plugin_connected?: boolean; last_heartbeat_age_ms?: number; active_note_path?: string }
    ) => void
  ) => void;
}

export default class MeraContextBridgePlugin extends Plugin {
  private settings: MeraContextBridgeSettings = DEFAULT_SETTINGS;
  private queue: QueuedEvent[] = [];
  private flushTimer: number | null = null;
  private statusBarEl: HTMLElement | null = null;
  private grpcClient: SidecarGrpcClient | null = null;

  async onload() {
    this.settings = { ...DEFAULT_SETTINGS, ...(await this.loadData()) };
    this.grpcClient = this.createGrpcClient();
    this.statusBarEl = this.addStatusBarItem();
    this.statusBarEl.setText("Mera: connecting");
    this.addSettingTab(new MeraContextBridgeSettingTab(this.app, this));
    this.registerEvent(
      this.app.workspace.on("active-leaf-change", (leaf) => {
        this.queueLeafEvent(leaf, "open");
      })
    );
    this.registerEvent(
      this.app.workspace.on("file-open", (file) => {
        if (file) {
          this.enqueue({
            event_id: this.newId(),
            event_type: "navigate",
            note_path: file.path,
            note_title: file.basename,
            event_ts_ms: Date.now(),
          });
        }
      })
    );
    this.registerDomEvent(document, "click", (event) => {
      const target = event.target as HTMLElement | null;
      const file = this.app.workspace.getActiveFile();
      if (!target || !file) {
        return;
      }
      this.enqueue({
        event_id: this.newId(),
        event_type: "click",
        note_path: file.path,
        note_title: file.basename,
        clicked_target: target.tagName,
        event_ts_ms: Date.now(),
      });
    });

    this.registerInterval(
      window.setInterval(() => {
        this.captureSelectionEvent();
      }, 2000)
    );
    this.registerInterval(
      window.setInterval(() => {
        void this.flushQueue();
      }, this.settings.flushIntervalMs)
    );
    this.registerInterval(
      window.setInterval(() => {
        void this.sendHeartbeat();
      }, this.settings.heartbeatIntervalMs)
    );
    this.registerInterval(
      window.setInterval(() => {
        void this.refreshConnectionStatus();
      }, 3000)
    );
    void this.sendHeartbeat();
    void this.refreshConnectionStatus();
  }

  async onunload() {
    await this.flushQueue();
  }

  private createGrpcClient(): SidecarGrpcClient {
    const pkgDef = protoLoader.loadSync(sidecarProtoPath, {
      keepCase: true,
      longs: String,
      enums: String,
      defaults: true,
      oneofs: true,
    });
    const grpcObj = loadPackageDefinition(pkgDef) as any;
    const ServiceCtor = grpcObj.mera.sidecar.v1.SidecarContextService;
    return new ServiceCtor(this.settings.grpcAddress, credentials.createInsecure()) as SidecarGrpcClient;
  }

  private callGrpc<T>(method: keyof SidecarGrpcClient, request: Record<string, unknown>): Promise<T> {
    if (!this.grpcClient) {
      return Promise.reject(new Error("gRPC client unavailable"));
    }
    return new Promise<T>((resolve, reject) => {
      (this.grpcClient as any)[method](request, (error: ServiceError | null, response: T) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(response);
      });
    });
  }

  private queueLeafEvent(leaf: WorkspaceLeaf | null, eventType: "open") {
    if (!leaf) {
      return;
    }
    const file = this.app.workspace.getActiveFile();
    if (!file) {
      return;
    }
    this.enqueue({
      event_id: this.newId(),
      event_type: eventType,
      note_path: file.path,
      note_title: file.basename,
      event_ts_ms: Date.now(),
      metadata: {
        leaf_type: leaf.getViewState().type,
      },
    });
  }

  private captureSelectionEvent() {
    const file = this.app.workspace.getActiveFile();
    if (!file) {
      return;
    }
    const selection = window.getSelection()?.toString().trim() ?? "";
    if (!selection) {
      return;
    }
    this.enqueue({
      event_id: this.newId(),
      event_type: "selection",
      note_path: file.path,
      note_title: file.basename,
      selection: selection.slice(0, 2000),
      event_ts_ms: Date.now(),
    });
  }

  private enqueue(event: QueuedEvent) {
    this.queue.push(event);
    this.queue = this.queue.slice(-50);
    if (this.queue.length >= 5 && this.flushTimer === null) {
      this.flushTimer = window.setTimeout(() => {
        this.flushTimer = null;
        void this.flushQueue();
      }, 300);
    }
  }

  private async flushQueue() {
    if (!this.queue.length) {
      return;
    }
    const pending = [...this.queue];
    this.queue = [];
    for (const event of pending) {
      try {
        await this.sendEvent(event);
      } catch (_error) {
        // Retry later by requeueing while preserving recency.
        this.queue.push(event);
      }
    }
    this.queue = this.queue.slice(-50);
  }

  private async sendEvent(event: QueuedEvent) {
    await this.callGrpc("IngestEvent", {
      user_id: this.settings.userId,
      space_id: this.settings.spaceId || "",
      session_id: this.settings.sessionId,
      plugin_secret: this.settings.sharedSecret,
      event: {
        ...event,
        metadata_json: JSON.stringify(event.metadata || {}),
      },
    });
  }

  async sendHeartbeat() {
    const activeFile = this.app.workspace.getActiveFile();
    await this.callGrpc("Heartbeat", {
      user_id: this.settings.userId,
      space_id: this.settings.spaceId || "",
      session_id: this.settings.sessionId,
      active_note_path: activeFile?.path || "",
      active_note_title: activeFile?.basename || "",
      plugin_secret: this.settings.sharedSecret,
    });
  }

  async refreshConnectionStatus() {
    try {
      const session = await this.callGrpc<{
        plugin_connected?: boolean;
        last_heartbeat_age_ms?: number;
        active_note_path?: string;
      }>("GetSession", {
        user_id: this.settings.userId,
        space_id: this.settings.spaceId || "",
        session_id: this.settings.sessionId,
      });
      const isLive = Boolean(session.plugin_connected);
      const ageMs = Number(session.last_heartbeat_age_ms || 0);
      const ageSec = Math.max(0, Math.round(ageMs / 1000));
      this.statusBarEl?.setText(isLive ? `Mera: live (${ageSec}s)` : "Mera: stale");
    } catch {
      this.statusBarEl?.setText("Mera: disconnected");
    }
  }

  async updateSettings(next: Partial<MeraContextBridgeSettings>) {
    this.settings = { ...this.settings, ...next };
    await this.saveData(this.settings);
    this.grpcClient = this.createGrpcClient();
    void this.refreshConnectionStatus();
  }

  getSettings(): MeraContextBridgeSettings {
    return this.settings;
  }

  private newId(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

class MeraContextBridgeSettingTab extends PluginSettingTab {
  plugin: MeraContextBridgePlugin;

  constructor(app: App, plugin: MeraContextBridgePlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    const settings = this.plugin.getSettings();
    containerEl.empty();
    containerEl.createEl("h2", { text: "Mera Context Bridge" });

    new Setting(containerEl)
      .setName("gRPC daemon address")
      .setDesc("Local daemon endpoint, for example 127.0.0.1:50051")
      .addText((text) =>
        text
          .setValue(settings.grpcAddress)
          .onChange(async (value) =>
            this.plugin.updateSettings({ grpcAddress: value.trim() || DEFAULT_SETTINGS.grpcAddress })
          )
      );

    new Setting(containerEl)
      .setName("User ID")
      .addText((text) =>
        text
          .setValue(settings.userId)
          .onChange(async (value) => this.plugin.updateSettings({ userId: value.trim() || DEFAULT_SETTINGS.userId }))
      );

    new Setting(containerEl)
      .setName("Session ID")
      .addText((text) =>
        text
          .setValue(settings.sessionId)
          .onChange(async (value) =>
            this.plugin.updateSettings({ sessionId: value.trim() || DEFAULT_SETTINGS.sessionId })
          )
      );

    new Setting(containerEl)
      .setName("Space ID (optional)")
      .addText((text) => text.setValue(settings.spaceId).onChange(async (value) => this.plugin.updateSettings({ spaceId: value.trim() })));

    new Setting(containerEl)
      .setName("Shared secret (optional)")
      .setDesc("Matches OBSIDIAN_PLUGIN_SHARED_SECRET on backend")
      .addText((text) =>
        text
          .setPlaceholder("x-obsidian-plugin-secret")
          .setValue(settings.sharedSecret)
          .onChange(async (value) => this.plugin.updateSettings({ sharedSecret: value.trim() }))
      );

    new Setting(containerEl)
      .setName("Test connection")
      .setDesc("Send one heartbeat and fetch session over gRPC")
      .addButton((button) =>
        button.setButtonText("Send heartbeat").onClick(async () => {
          try {
            await this.plugin.sendHeartbeat();
            await this.plugin.refreshConnectionStatus();
            new Notice("Mera heartbeat sent");
          } catch (error) {
            new Notice(error instanceof Error ? `Mera heartbeat failed: ${error.message}` : "Mera heartbeat failed");
          }
        })
      );
  }
}
