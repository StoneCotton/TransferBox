// Shared type definitions for TransferBox application

export interface LogEntry {
  id: string;
  message: string;
  timestamp: string;
  level: "info" | "warning" | "error" | "success";
}

export interface AppMetadata {
  appName: string;
  version: string;
  author: string;
  description: string;
  license: string;
  platform: string;
}

export interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface BackendTransferProgress {
  current_file: string;
  file_number: number;
  total_files: number;
  bytes_transferred: number;
  total_bytes: number;
  total_transferred: number;
  total_size: number;
  current_file_progress: number;
  overall_progress: number;
  status: string;
  proxy_progress: number;
  proxy_file_number: number;
  proxy_total_files: number;
  speed_bytes_per_sec: number;
  eta_seconds: number;
  total_elapsed: number;
  file_elapsed: number;
  checksum_elapsed: number;
  source_drive_name: string;
  source_drive_path: string;
}

export interface TutorialStep {
  id: string;
  title: string;
  description: string;
  stepType?: "info" | "destination" | "card_detection" | "monitoring";
  requiresCompletion?: boolean; // Whether the step must be completed before proceeding
  image?: string; // Optional image for the tutorial step
}

export interface PathValidationResult {
  is_valid: boolean;
  error_message?: string;
  sanitized_path?: string;
}

export interface ApiResponse<T = Record<string, unknown>> {
  success: boolean;
  message?: string;
  data?: T;
  path?: string;
}

export type StatusType = "info" | "warning" | "error" | "success";
export type TransferState = "idle" | "transferring" | "completed" | "failed";
