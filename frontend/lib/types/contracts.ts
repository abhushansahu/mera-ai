export type ContextSourceType = 'FILE' | 'DIRECTORY' | 'URL' | 'API' | 'DATABASE' | 'MEMORY' | 'OBSIDIAN';

export interface ContextSourceContract {
  type: ContextSourceType;
  path: string;
  extra?: Record<string, any>;
}

export type ObsidianEventType = 'open' | 'click' | 'selection' | 'navigate';

export interface ObsidianContextEventContract {
  event_id?: string;
  event_type: ObsidianEventType;
  note_path: string;
  note_title?: string;
  selection?: string;
  clicked_target?: string;
  cursor_line?: number;
  event_ts_ms?: number;
  metadata?: Record<string, any>;
  received_at?: string;
}

export interface ObsidianContextSessionContract {
  session_id: string;
  user_id: string;
  space_id?: string | null;
  active_note_path?: string | null;
  active_note_title?: string | null;
  active_selection?: string | null;
  recent_events: ObsidianContextEventContract[];
  last_event_at?: string | null;
  plugin_connected?: boolean;
  last_heartbeat_at?: string | null;
  last_heartbeat_age_ms?: number | null;
}

export interface SpaceContract {
  space_id: string;
  name: string;
  owner_id: string;
  status: string;
  monthly_token_budget: number;
  monthly_api_calls: number;
  preferred_model: string;
}

export interface FeatureFlagsContract {
  threading: boolean;
  per_message_model: boolean;
  secure_provider_settings: boolean;
  obsidian_advanced: boolean;
  rpi_compact_layout: boolean;
  obsidian_event_sync: boolean;
}
