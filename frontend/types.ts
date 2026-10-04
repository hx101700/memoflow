export type Language = "zh-CN" | "en";
export type Theme = "system" | "light" | "dark";
export type UploadKind = "audio" | "hotwords";
export type DirectoryKind = "json" | "document";
export type SessionPhase = "editing" | "preview" | "handed_off" | "expired" | "cancelled";
export type Phase = "loading" | "editing" | "validating" | "preview" | "returning" | "handed_off" | "expired" | "cancelled" | "unavailable";
export type EnhancementMode = "none" | "hotwords" | "context" | "both";

export interface Limits {
  audio_bytes: number; hotwords_bytes: number; upload_bytes: number; audio_seconds: number;
  hotwords_count: number; context_chars: number; speaker_min: number; speaker_max: number;
}
export interface Receipt {
  session_id: string; job_id: string; config_path: string; json_directory: string; document_directory: string;
  auth_mode: "console" | "api_key"; execution_started: false;
}
export interface SessionDescription {
  session_id: string; phase: SessionPhase; expires_at: string;
  model: string; region: string; limits: Limits; audio_suffixes: string[];
  languages: string[]; output_defaults: Record<DirectoryKind, string>;
  preview: (ValidationResult & EditableSnapshot) | null;
  terminal: SessionEnd | null;
}
export interface Configuration {
  auth_mode: "console" | "api_key"; audio_upload_id: string | null; diarization_enabled: boolean;
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
export interface HotwordRow { text: CellValue; weight: CellValue; invalid_fields?: HotwordField[] }
export interface EditorRow extends HotwordRow { key: number; row: number }
export interface HotwordValidation { issues: ErrorDetail[]; warnings: string[]; count: number }
export interface HotwordImport { name: string; size_bytes: number; rows: HotwordRow[]; issues: ErrorDetail[]; warnings: string[] }
export interface Summary {
  auth_mode: "console" | "api_key";
  audio: { name: string; duration_seconds: number; size_bytes: number; format_name: string; channels: number; sample_rate: number };
  enhancement: { mode: EnhancementMode; count: number; context_chars: number };
  json_directory: string; document_directory: string; warnings: string[];
}
export interface ValidationResult { validation_id: string; summary: Summary }
export interface Preview { id: string; summary: Summary; configuration: Configuration; ready: boolean }
export interface UploadState { status: "empty" | "uploading" | "ready" | "failed"; id: string | null; name: string; size: number }
export interface Picker { id: string; kind: DirectoryKind; cancelling: boolean }
export interface Model {
  phase: Phase; revision: number; preview: Preview | null; receipt: Receipt | null;
  session: SessionDescription | null; directories: Record<DirectoryKind, string>;
  uploads: Record<UploadKind, UploadState>;
  hotwords: { issues: ErrorDetail[]; warnings: string[]; checking: boolean; revision: number; validatedRevision: number };
  auth: { revision: number; status: "idle" | "loading" | "saving" | "ready" | "dirty" | "failed" };
  picker: Picker | null; downloadingTemplate: boolean; statusMessage: "changed" | "";
}
export interface ErrorDetail { row?: number; field?: string; message: string }
export interface ErrorPayload { error?: string; ok?: boolean; field?: string; details?: ErrorDetail[] }
export interface UploadResult { upload_id: string; name: string; size_bytes: number }
export interface EditableSnapshot { configuration: Configuration; audio: UploadResult }
export interface SessionEnd { state: "handed_off" | "expired" | "cancelled"; receipt: Receipt | null }
export type DirectoryResult = { cancelled: true } | { cancelled: false; path: string };
export interface Endpoints {
  "/api/session": SessionDescription;
  "/api/api-key": { value: string };
  "/api/save-api-key": { ok: true };
  "/api/upload-audio": UploadResult;
  "/api/upload-hotwords": HotwordImport;
  "/api/validate-hotwords": HotwordValidation;
  "/api/select-directory": DirectoryResult;
  "/api/cancel-directory": { ok: true };
  "/api/validate": ValidationResult;
  "/api/preview-ready": { ok: true };
  "/api/edit": EditableSnapshot & { ok: true };
}
export interface Api {
  request<K extends keyof Endpoints>(path: K, payload?: object, file?: File): Promise<Endpoints[K]>;
  template(): Promise<Blob>;
  listen(ended: (result: SessionEnd) => void, disconnected: () => void): () => void;
}
