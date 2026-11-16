import { computed, onScopeDispose, ref, watch } from "vue";
import { translate, type MessageKey, type Translate } from "./i18n";
import type { Language, Theme } from "./types";

export interface Preferences { language: Language; theme: Theme }

// 读取界面偏好；浏览器禁用存储时使用浏览器语言和系统主题。
export function readPreferences(storage: Pick<Storage, "getItem">, browserLanguage: string): Preferences {
  let saved: Partial<Preferences> = {};
  try { saved = JSON.parse(storage.getItem("asr-ui-preferences") ?? "{}") as Partial<Preferences>; } catch { /* 使用默认偏好。 */ }
  return {
    language: saved?.language === "en" || saved?.language === "zh-CN" ? saved.language : browserLanguage.startsWith("zh") ? "zh-CN" : "en",
    theme: saved?.theme === "light" || saved?.theme === "dark" ? saved.theme : "system",
  };
}

// 根据显式主题选择或系统设置确定页面配色。
export function isDark(theme: Theme, systemDark: boolean): boolean {
  return theme === "dark" || (theme === "system" && systemDark);
}

// 同步语言、Element Plus 深色类和本机页面偏好。
export function usePreferences(title: MessageKey = "title") {
  const initial = readPreferences({ getItem: key => window.localStorage.getItem(key) }, navigator.language);
  const language = ref(initial.language);
  const theme = ref(initial.theme);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const systemDark = ref(media.matches);
  // 跟随操作系统的配色变化。
  const changed = (event: MediaQueryListEvent): void => { systemDark.value = event.matches; };
  media.addEventListener("change", changed);
  onScopeDispose(() => media.removeEventListener("change", changed));
  const dark = computed(() => isDark(theme.value, systemDark.value));
  const t: Translate = (key, values) => translate(language.value, key, values);
  watch([language, theme, dark], () => {
    document.documentElement.lang = language.value;
    document.documentElement.classList.toggle("dark", dark.value);
    document.title = t(title);
    try { window.localStorage.setItem("asr-ui-preferences", JSON.stringify({ language: language.value, theme: theme.value })); } catch { /* 当前页面继续使用所选偏好。 */ }
  }, { immediate: true });
  return { language, theme, t };
}
