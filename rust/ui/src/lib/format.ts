import { currentLanguage } from "./i18n.svelte";

export function formatSize(bytes: number | null): string {
  if (bytes === null) return "–";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 ? 0 : 1;
  return `${value.toLocaleString(currentLanguage(), { maximumFractionDigits: digits })} ${units[unit]}`;
}

export function formatDate(seconds: number | null): string {
  if (seconds === null) return "–";
  return new Date(seconds * 1000).toLocaleString(currentLanguage(), {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
