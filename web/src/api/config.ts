/** Single place for API configuration. Dev uses the Vite proxy (same-origin /api). */
export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const POLL_MS = 700;
