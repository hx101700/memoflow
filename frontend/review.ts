import { UiError } from "./api";
import type { Translate } from "./i18n";
import type { ErrorPayload, Language, LocalizedText, ReviewApi, ReviewEndpoints, ReviewSentence } from "./types";

export class ReviewRequestError extends UiError {
  // 保留冲突状态码，防止失败保存覆盖其他页面的修改。
  constructor(text: LocalizedText | (() => string), public status: number) { super(text); }
}

// 创建回听页的同源接口，错误保留双语说明与HTTP状态。
export function createReviewApi(fetchRequest: typeof fetch, language: () => Language, t: Translate, eventSource: (url: string) => EventSource = url => new EventSource(url)): ReviewApi {
  return {
    // 保持浏览器在场连接，断网沿用EventSource重连，离页由调用方显式关闭。
    presence(connected, disconnected): () => void {
      const source = eventSource("/api/review/presence");
      source.onopen = connected;
      source.onerror = disconnected;
      return () => { source.onopen = null; source.onerror = null; source.close(); };
    },
    // 按端点读取回听快照或提交本机修改。
    async request<K extends keyof ReviewEndpoints>(path: K, payload?: object): Promise<ReviewEndpoints[K]> {
      let response: Response;
      try {
        response = await fetchRequest(path, { method: payload === undefined ? "GET" : "POST",
          credentials: "same-origin", cache: "no-store",
          headers: { "Accept-Language": language(), ...(payload === undefined ? {} : { "Content-Type": "application/json" }) },
          body: payload === undefined ? undefined : JSON.stringify(payload) });
      } catch { throw new ReviewRequestError(() => t("reviewNetwork"), 0); }
      let data: ReviewEndpoints[K] & ErrorPayload;
      try { data = await response.json(); }
      catch { throw new ReviewRequestError(() => t("unknownResponse"), response.status); }
      if (!response.ok || data.ok === false) throw new ReviewRequestError(data.error ?? (() => t("failed")), response.status);
      return data;
    },
  };
}

// 比较原始识别结果，只标记本句正文或说话人归属的修改。
export function sentenceModified(sentence: ReviewSentence): boolean {
  return sentence.text !== sentence.original_text || sentence.speaker_id !== sentence.original_speaker_id;
}
