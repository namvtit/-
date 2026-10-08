export type JobStatus =
  | "RECEIVED"
  | "GENERATING_SCRIPT"
  | "PREPARING_MATERIALS"
  | "RENDERING"
  | "COMPLETED"
  | "FAILED";
export type VideoInput = {
  topic: string;
  language: "vi" | "en" | "zh";
  duration: number;
  aspect_ratio: "9:16" | "16:9";
  script?: string;
  footage_source: "pixabay" | "pexels" | "coverr" | "local";
  local_materials: string[];
};
export type Job = {
  id: string;
  input: VideoInput;
  status: JobStatus;
  progress: number;
  created_at: string;
  updated_at: string;
  error: string | null;
  preview_url: string | null;
  download_url: string | null;
  metadata: {
    duration: number;
    width: number;
    height: number;
    size_bytes: number;
  } | null;
};
export type Material = { id: string; name: string; size_bytes: number };
export type Connection = {
  status: "connected" | "unreachable" | "missing_configuration" | "not_checked";
  detail: string;
};
export type StockProvider = {
  id: "pixabay" | "pexels" | "coverr";
  name: string;
  configured: boolean;
  missing_keys: string[];
  connection: Connection;
};
export type Config = {
  llm_base_url: string;
  llm_model: string;
  llm_configured: boolean;
  llm_connection: Connection;
  renderer: string;
  renderer_connection: Connection;
  stock_configured: boolean;
  stock_providers: StockProvider[];
  default_footage_source: StockProvider["id"];
  tts: string;
  setup_issues: string[];
};
export async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const error = await response.json();
      if (typeof error.detail === "string") message = error.detail;
      else if (Array.isArray(error.detail))
        message = error.detail
          .map((item: { msg: string; loc?: (string | number)[] }) =>
            `${item.loc?.filter((part) => part !== "body").join(".") || "Input"}: ${item.msg}`,
          )
          .join(" ");
    } catch {
      /* Keep a readable error for non-JSON gateway responses. */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export const labels: Record<JobStatus, string> = {
  RECEIVED: "Queued",
  GENERATING_SCRIPT: "Writing script",
  PREPARING_MATERIALS: "Preparing footage & voice",
  RENDERING: "Rendering video",
  COMPLETED: "Ready",
  FAILED: "Failed",
};
