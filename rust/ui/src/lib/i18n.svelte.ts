// Übersetzungen: gemeinsame Python-Locales + Rust-spezifische Ergänzungen.
import baseDe from "@locales/de.json";
import baseEn from "@locales/en.json";
import extraDe from "./locales/de.json";
import extraEn from "./locales/en.json";

export type Language = "de" | "en";

const catalogs: Record<Language, Record<string, string>> = {
  de: { ...baseDe, ...extraDe },
  en: { ...baseEn, ...extraEn },
};

const locale = $state<{ language: Language }>({ language: "de" });

export function setLanguage(language: string): void {
  locale.language = language === "en" ? "en" : "de";
  document.documentElement.lang = locale.language;
}

export function currentLanguage(): Language {
  return locale.language;
}

/** Python-`str.format`-kompatible Platzhalter: `{name}` und `{name:.2f}`. */
function format(template: string, values: Record<string, unknown>): string {
  return template.replace(/\{(\w+)(?::\.(\d+)f)?\}/g, (match, name: string, digits?: string) => {
    if (!(name in values)) return match;
    const value = values[name];
    if (digits !== undefined && typeof value === "number") return value.toFixed(Number(digits));
    return String(value);
  });
}

export function tr(key: string, values: Record<string, unknown> = {}): string {
  const template = catalogs[locale.language][key] ?? catalogs.en[key] ?? key;
  return format(template, values);
}

export function modCount(count: number): string {
  return tr(count === 1 ? "common.mod_count.one" : "common.mod_count.other", { count });
}
