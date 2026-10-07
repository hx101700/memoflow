export type Language = "zh-CN" | "en";
export type Theme = "system" | "light" | "dark";
export type DirectoryKind = "json" | "document";
export type SessionPhase = "editing" | "preview" | "handed_off" | "expired" | "cancelled";
export type Phase = "loading" | "editing" | "validating" | "preview" | "returning" | "handed_off" | "expired" | "cancelled" | "unavailable";
export type EnhancementMode = "none" | "hotwords" | "context" | "both";

export interface Limits {
  hotwords_bytes: number; upload_bytes: number; audio_seconds: number;
  hotwords_count: number; context_chars: number; speaker_min: number; speaker_max: number;
}
export interface Receipt {
  session_id: string; job_id: string; config_path: string; json_directory: string; document_directory: string;
  auth_mode: "console" | "api_key"; execution_started: false;
}
export interface SessionDescription {
  session_id: string; phase: SessionPhase; expires_at: string;
  audio: AudioSelection | null; audio_error: LocalizedText | null;
  model: string; region: string; limits: Limits; audio_suffixes: string[];
  languages: string[]; output_defaults: Record<DirectoryKind, string>;
  preview: (ValidationResult & EditableSnapshot) | null;
  terminal: SessionEnd | null;
}
export interface Configuration {
  auth_mode: "console" | "api_key"; audio_id: string | null; diarization_enabled: boolean;
  enhancement_mode: EnhancementMode; hotword_rows: HotwordRow[]; context: string;
  language_hint: string | null; speaker_count: number | null;
  json_directory: string; document_directory: string;
}
export interface FormValues {
  useApiKey: boolean; diarizationEnabled: boolean; hotwordsEnabled: boolean; contextEnabled: boolean;
  context: string; language: string; speaker: string; hotwordRows: EditorRow[];
}
export type CellValue = string | number | boolean | null;
export type HotwordField = "text" | "weight";
export interface LocalizedText { zh: string; en: string }
export interface HotwordRow { text: CellValue; weight: CellValue; invalid_fields?: HotwordField[] }
export interface EditorRow extends HotwordRow { key: number; row: number }
export interface HotwordImport { name: string; rows: HotwordRow[]; warnings: LocalizedText[] }
export interface Summary {
  auth_mode: "console" | "api_key";
  audio: { name: string; path: string; duration_seconds: number; size_bytes: number; format_name: string; channels: number; sample_rate: number };
  enhancement: { mode: EnhancementMode; count: number; context_chars: number };
  json_directory: string; document_directory: string; warnings: LocalizedText[];
}
export interface ValidationResult { validation_id: string; summary: Summary }
export interface Preview { id: string; summary: Summary; configuration: Configuration; ready: boolean }
export interface ImportState { status: "empty" | "importing" | "ready" | "failed"; name: string }
export interface Picker { id: string; kind: DirectoryKind | "audio"; cancelling: boolean }
export interface Model {
  phase: Phase; preview: Preview | null; receipt: Receipt | null;
  session: SessionDescription | null; directories: Record<DirectoryKind, string>;
  audio: AudioSelection | null; hotwordImport: ImportState;
  hotwords: { issues: EditorIssue[]; warnings: LocalizedText[] };
  auth: { revision: number; status: "idle" | "loading" | "saving" | "ready" | "dirty" | "failed" };
  picker: Picker | null; downloadingTemplate: boolean;
}
export interface ErrorDetail { row?: number; field?: string; message: LocalizedText; duplicate_group?: number }
export interface EditorIssue extends ErrorDetail { key?: number }
export interface ErrorPayload { error?: LocalizedText; ok?: boolean; field?: string; details?: ErrorDetail[] }
export interface AudioSelection { audio_id: string; name: string; path: string; size_bytes: number }
export interface EditableSnapshot { configuration: Configuration; audio: AudioSelection }
export interface SessionEnd { state: "handed_off" | "expired" | "cancelled"; receipt: Receipt | null }
export type DirectoryResult = { cancelled: true } | { cancelled: false; path: string };
export type AudioSelectionResult = { cancelled: true } | (AudioSelection & { ok: true; cancelled: false });
export interface Endpoints {
  "/api/session": SessionDescription;
  "/api/api-key": { value: string };
  "/api/save-api-key": { ok: true };
  "/api/select-audio": AudioSelectionResult;
  "/api/import-hotwords": HotwordImport;
  "/api/select-directory": DirectoryResult;
  "/api/cancel-picker": { ok: true };
  "/api/validate": ValidationResult;
  "/api/preview-ready": { ok: true };
  "/api/edit": EditableSnapshot & { ok: true };
}
export interface Api {
  request<K extends keyof Endpoints>(path: K, payload?: object, file?: File): Promise<Endpoints[K]>;
  template(): Promise<Blob>;
  listen(ended: (result: SessionEnd) => void, disconnected: () => void): () => void;
}
