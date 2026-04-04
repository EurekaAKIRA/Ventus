export function parseDateValue(value: unknown): Date | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDateTime(value: unknown, fallback = "-"): string {
  const parsed = parseDateValue(value);
  return parsed ? parsed.toLocaleString() : fallback;
}

export function formatTime(value: unknown, fallback = "-"): string {
  const parsed = parseDateValue(value);
  return parsed ? parsed.toLocaleTimeString() : fallback;
}
