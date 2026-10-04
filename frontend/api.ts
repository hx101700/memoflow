import type { Api, Endpoints, ErrorDetail, ErrorPayload, Language, LocalizedText, SessionEnd } from "./types";
import { localize, type Translate } from "./i18n";

export class UiError extends Error {
  // 保存公开错误说明、字段位置与明确的 HTTP 状态。
  constructor(private text: LocalizedText | (() => string), public field?: string, public httpStatus?: number, public details: ErrorDetail[] = []) {
    super(typeof text === "function" ? text() : text.zh);
    this.name = "UiError";
  }

  // 按当前界面语言呈现已取得的错误，保留检查时的内容和位置。
  describe(language: Language): string {
    return typeof this.text === "function" ? this.text() : localize(this.text, language);
  }
}

// 将未知异常转换为可显示的错误对象，保留服务端字段与状态。
export function uiError(error: unknown, fallback: () => string, field?: string): UiError {
  if (error instanceof UiError) {
    if (field) error.field = field;
    return error;
  }
  return new UiError(fallback, field);
}

// 创建使用同源会话 Cookie 的本机接口与一次性结束通知。
export function createApi(fetchRequest: typeof fetch, language: () => Language, t: Translate,
  eventSource: (url: string) => EventSource = url => new EventSource(url)): Api {
  // 构造本机请求头和缓存策略。
  function options(): RequestInit {
    return { headers: { "Accept-Language": language() },
      cache: "no-store", credentials: "same-origin" };
  }
  return {
    // 发送 JSON 或文件字节，并传递明确的错误状态。
    async request<K extends keyof Endpoints>(path: K, payload?: object, file?: File): Promise<Endpoints[K]> {
      const init = options();
      const headers = new Headers(init.headers);
      init.headers = headers;
      if (file) {
        init.method = "POST";
        headers.set("Content-Type", "application/octet-stream");
        headers.set("X-File-Name", encodeURIComponent(file.name));
        init.body = file;
      } else if (payload !== undefined) {
        init.method = "POST";
        headers.set("Content-Type", "application/json");
        init.body = JSON.stringify(payload);
      }
      let response: Response;
      try { response = await fetchRequest(path, init); }
      catch { throw new UiError(() => t("network")); }
      let data: Endpoints[K] & ErrorPayload;
      try { data = await response.json() as Endpoints[K] & ErrorPayload; }
      catch { throw new UiError(() => t("unknownResponse")); }
      if (!response.ok || data.ok === false) {
        throw new UiError(data.error || (() => t("failed")), data.field, response.status, data.details);
      }
      return data;
    },
    // 下载本机生成的热词模板。
    async template(): Promise<Blob> {
      try {
        const response = await fetchRequest("/api/hotwords-template", options());
        if (!response.ok) throw new UiError(() => t("templateFailed"));
        return await response.blob();
      } catch { throw new UiError(() => t("templateFailed")); }
    },
    // 读取会话结束事件，结束或断开后关闭连接。
    listen(ended, disconnected): () => void {
      const source = eventSource("/api/events");
      source.addEventListener("ended", event => {
        source.close();
        try { ended(JSON.parse((event as MessageEvent<string>).data) as SessionEnd); }
        catch { disconnected(); }
      });
      source.onerror = () => { source.close(); disconnected(); };
      return () => source.close();
    },
  };
}
