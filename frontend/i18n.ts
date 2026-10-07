import type { Language, LocalizedText } from "./types";

const en = {
  title: "Audio transcription",
  intro: "Turn meeting, interview, and lecture recordings into text.",
  region: "China (Beijing)", language: "Interface language", theme: "Appearance",
  system: "System", light: "Light", dark: "Dark", skip: "Skip to transcription settings",
  stepConfigure: "Configure", stepReview: "Preview",
  beforeStart: "Add your recording and choose the settings. Review them before handing the task to Codex.",
  audioHeading: "Add audio", oneFile: "One file at a time", chooseAudio: "Choose an audio file",
  replaceAudio: "Replace audio", audioLocation: "Original file location",
  audioLimits: "Audio can be up to {hours} hours. The file sent to Alibaba Cloud must be no larger than {upload} GB. If channels are merged, the converted file must meet this limit.",
  audioFormats: "Supported formats: {formats}.",
  audioWaiting: "Choose an audio file in the system dialog. You can cancel if the dialog is not visible.",
  settings: "Transcription settings", audioLanguage: "Audio language", automatic: "Auto-detect",
  diarization: "Speaker diarization", diarizationHelp: "Label speech from different speakers in the transcript.",
  monoHelp: "Multi-channel audio is merged into a mono copy. Your original file is preserved.",
  speakers: "Number of speakers", optional: "Optional", speakerHint: "Enter {min}–{max} as a hint, or leave blank for automatic detection.",
  enhancement: "Improve recognition accuracy",
  hotwords: "Add hotwords", hotwordsHelp: "Improve recognition of names, product names, and technical terms.",
  hotwordFile: "Hotword list",
  template: "Download template", hotwordLimit: ".xlsx · Up to {size} MB",
  hotwordHelp: "Import Excel or add rows below. Keep one row per hotword. Up to {count} hotwords; weights: 1–5 or 50.",
  importHotwords: "Import Excel", addHotword: "Add hotword",
  importedHotwords: "Imported: {name}",
  hotwordIssues: "The hotword table contains errors. Correct the rows marked in red.", hotwordRules: "Alibaba Cloud hotword requirements",
  hotwordEmpty: "Add a row to enter a hotword, or import an Excel file.",
  hotwordRows: "{count} rows",
  rowNumber: "Row", actions: "Action", hotwordCell: "Row {row}, hotword", weightCell: "Row {row}, weight",
  removeHotword: "Delete row {row}",
  context: "Add context", contextHelp: "Provide relevant terms, dialogue, or reference material.",
  reference: "Reference text", contextHint: "Include specific terms that may occur in the recording. Up to {count} characters.", contextRules: "Alibaba Cloud context requirements",
  contextPlaceholder: "For example: This technical review covers Kubernetes, container orchestration, canary releases, and service rollback.",
  savingLocations: "Save locations", rawResult: "Original result (JSON)", documents: "Transcripts",
  chooseFolder: "Choose folder", resetFolder: "Reset", choosingFolder: "Choose in the dialog…",
  folderWaiting: "Choose a folder in the system dialog. You can cancel if the dialog is not visible.",
  cancelWaiting: "Cancel selection", cancelling: "Cancelling…",
  useKey: "Use API key", consoleDefault: "Otherwise, use Console login.",
  keyModeHelp: "Use your API key to transcribe directly. Console login is not required.",
  enterKey: "Enter your Model Studio API key (Beijing)",
  saveKey: "Save API key", keySaved: "API key saved to this working folder.",
  keySaveHelp: "Save the key separately to .asr-transcription/.env in your working folder. Confirm and preview also saves any changes automatically.",
  loadingKey: "Reading…",
  review: "Transcription details",
  currentSettings: "Current settings", noAudio: "Not selected", contextCount: "{count} characters",
  audioFile: "Audio file", duration: "Duration", fileSize: "File size", formatChannels: "Format / channels",
  channel: "{count} channel", channels: "{count} channels", sampleRate: "Sample rate", connection: "Authentication",
  consoleLogin: "Console login", enabled: "On", disabled: "Off",
  speakerValue: "{count} speakers (hint)", hotwordsLabel: "Hotwords", contextLabel: "Context",
  modelRegion: "Model and region", jsonLocation: "JSON folder", documentLocation: "Transcript folder",
  next: "Next: review transcription settings", nextHelp: "Check the audio, recognition options, and save locations.",
  reviewTitle: "Ready for your confirmation", reviewHelp: "Click “Copy for Codex” and send the confirmation message in your chat to start transcription.",
  uploadDisclosure: "Sending the confirmation message allows this recording, the enabled hotwords, and reference text to be sent to Alibaba Cloud Model Studio in the Beijing region. Usage charges may apply. Settings cannot be changed after the task is handed over to Codex.",
  expiryHelp: "This page is available for two hours after opening. Tasks already handed over to Codex can continue.",
  check: "Confirm and preview", edit: "Back to editing", copyToCodex: "Copy for Codex",
  confirmationLabel: "Confirmation message", confirmationMessage: "Confirm transcription. Session ID: {id}",
  copied: "Copied. Paste and send the message in Codex.", copyFailed: "Copy failed. Select and copy the confirmation message above.",
  handedOffTitle: "Handed over to Codex", handedOffHelp: "Continue in Codex for authentication, transcription, and your files. You can close this page.",
  expiredTitle: "This session has expired", expiredHelp: "The two-hour editing period has ended. Ask Codex to open a new page. You can close this tab.",
  cancelledTitle: "This session was cancelled", cancelledHelp: "No transcription task was created. You can close this page.",
  endedLocal: "Follow the next steps and progress in Codex.", job: "Task ID",
  network: "The page connection was lost. Return to Codex to check that the local transcription service is running. This operation will not retry automatically.",
  unknownResponse: "The operation result is unavailable. Return to Codex for details.",
  failed: "The operation could not be completed. Check your input and try again manually.",
  templateFailed: "The template could not be downloaded. Return to Codex to check the local transcription service.",
  keyNotReady: "Enter a Model Studio API key for the Beijing region.",
  missingAudio: "Choose an audio file.",
  invalidSpeaker: "Enter an integer from {min} to {max}, or leave blank for automatic detection.",
  singleFile: "Select one file at a time.", wrongHotwords: "Select a hotword list in .xlsx format.",
  tooLarge: "The file exceeds {size} MB. Select another file.",
  textColumn: "Hotword", weightColumn: "Weight",
  loading: "Loading settings…", unavailable: "Page unavailable", unavailableHelp: "Return to Codex to reopen the transcription page.",
  footer: "Powered by MemoFlow", provider: "Speech recognition by Alibaba Cloud Model Studio", selectedBadge: "Selected",
};
const zh: Record<keyof typeof en, string> = {
  title: "录音转写",
  intro: "将会议、访谈或课程录音转换为文字。",
  region: "华北 2（北京）", language: "界面语言", theme: "外观",
  system: "跟随系统", light: "浅色", dark: "深色", skip: "跳到转写设置",
  stepConfigure: "填写", stepReview: "预览",
  beforeStart: "添加录音并填写设置，预览确认后交给 Codex 转写。",
  audioHeading: "添加音频", oneFile: "每次 1 个文件", chooseAudio: "选择音频文件",
  replaceAudio: "更换音频", audioLocation: "原文件位置",
  audioLimits: "音频最长 {hours} 小时。发送至阿里云的文件须不超过 {upload} GB；合并声道后，以转换后的文件大小为准。",
  audioFormats: "支持 {formats}。",
  audioWaiting: "请在系统窗口中选择音频文件。未看到窗口时可取消等待。",
  settings: "转写设置", audioLanguage: "音频语言", automatic: "自动识别",
  diarization: "区分发言人", diarizationHelp: "在转写内容中标记不同发言人。",
  monoHelp: "多声道音频将自动合并为单声道副本，保留原文件。",
  speakers: "发言人数", optional: "选填", speakerHint: "可填写 {min}–{max} 人供识别参考，留空自动判断。",
  enhancement: "精度增强",
  hotwords: "添加热词", hotwordsHelp: "提高人名、产品名称和专业术语的识别准确率。",
  hotwordFile: "热词表",
  template: "下载模板", hotwordLimit: ".xlsx · 最大 {size} MB",
  hotwordHelp: "导入 Excel 或直接添加行填写。同一热词只保留一行，最多 {count} 个热词；权重可填 1–5 或 50。",
  importHotwords: "导入 Excel", addHotword: "添加热词",
  importedHotwords: "已导入：{name}",
  hotwordIssues: "热词表输入存在错误，请处理标红行数据。", hotwordRules: "阿里云热词表要求",
  hotwordEmpty: "添加行直接填写热词，也可以导入 Excel。",
  hotwordRows: "{count} 行",
  rowNumber: "行号", actions: "操作", hotwordCell: "第 {row} 行热词", weightCell: "第 {row} 行权重",
  removeHotword: "删除第 {row} 行",
  context: "添加上下文", contextHelp: "提供与录音相关的术语、对话或参考资料。",
  reference: "参考文本", contextHint: "包含录音中可能出现的具体词语，最多 {count} 个字符。", contextRules: "阿里云上下文要求",
  contextPlaceholder: "例如：本次技术评审讨论 Kubernetes、容器编排、灰度发布和服务回滚方案。",
  savingLocations: "保存位置", rawResult: "原始结果（JSON）", documents: "转写文档",
  chooseFolder: "选择文件夹", resetFolder: "恢复默认", choosingFolder: "请在弹窗中选择…",
  folderWaiting: "请在系统窗口中选择文件夹。未看到窗口时可取消等待。",
  cancelWaiting: "取消等待", cancelling: "正在取消…",
  useKey: "使用指定 API Key", consoleDefault: "未开启时使用百炼控制台登录。",
  keyModeHelp: "使用指定 Key 直接转写，无需登录百炼控制台。",
  enterKey: "填写北京地域的百炼 API Key",
  saveKey: "保存 API Key", keySaved: "API Key 已保存到当前工作目录。",
  keySaveHelp: "可单独保存 Key 到当前工作目录的 .asr-transcription/.env；“确认并预览”也会自动保存修改。",
  loadingKey: "正在读取…",
  review: "转写信息",
  currentSettings: "当前设置", noAudio: "未选择", contextCount: "{count} 个字符",
  audioFile: "音频文件", duration: "音频时长", fileSize: "文件大小", formatChannels: "格式 / 声道",
  channel: "{count} 声道", channels: "{count} 声道", sampleRate: "采样率", connection: "认证方式",
  consoleLogin: "百炼控制台登录", enabled: "开启", disabled: "关闭",
  speakerValue: "{count} 人（参考）", hotwordsLabel: "热词", contextLabel: "上下文",
  modelRegion: "模型与地域", jsonLocation: "JSON 保存位置", documentLocation: "文档保存位置",
  next: "下一步：核对转写信息", nextHelp: "检查音频、识别选项和保存位置。",
  reviewTitle: "确认后交给 Codex", reviewHelp: "点击“复制给 Codex”，将确认消息发送到对话后开始转写。",
  uploadDisclosure: "发送确认消息即同意将本次录音、已启用的热词和参考文本发送至阿里云百炼北京地域，可能产生调用费用。交给 Codex 后，本次设置不能修改。",
  expiryHelp: "此页面从打开起有效 2 小时，不影响已交给 Codex 的任务。",
  check: "确认并预览", edit: "返回修改", copyToCodex: "复制给 Codex",
  confirmationLabel: "确认消息", confirmationMessage: "确认转写，会话编号：{id}",
  copied: "已复制，请粘贴到 Codex 对话并发送。", copyFailed: "复制失败，请选中并复制上方确认消息。",
  handedOffTitle: "已交给 Codex", handedOffHelp: "认证、转写和文件交付将在 Codex 中继续，此页面可以关闭。",
  expiredTitle: "会话已失效", expiredHelp: "已超过 2 小时填写时限，请让 Codex 重新打开页面。此标签页可以关闭。",
  cancelledTitle: "会话已取消", cancelledHelp: "没有创建转写任务，此页面可以关闭。",
  endedLocal: "后续操作与进度请在 Codex 中查看。", job: "任务编号",
  network: "页面连接已断开，请返回 Codex 检查转写页面服务是否仍在运行。本次操作不会自动重试。",
  unknownResponse: "暂时无法获取操作结果，请返回 Codex 查看详情。",
  failed: "本次操作未完成，请检查输入后手动再试。",
  templateFailed: "模板下载失败，请返回 Codex 检查转写页面服务。",
  keyNotReady: "请填写北京地域的百炼 API Key。",
  missingAudio: "请选择音频文件。",
  invalidSpeaker: "请输入 {min}–{max} 的整数，或留空自动判断。",
  singleFile: "一次只能添加 1 个文件。", wrongHotwords: "请选择 .xlsx 格式的热词文件。",
  tooLarge: "文件超过 {size} MB，请重新选择。",
  textColumn: "热词", weightColumn: "权重",
  loading: "正在加载设置…", unavailable: "页面暂不可用", unavailableHelp: "请返回 Codex 重新打开转写页面。",
  footer: "Powered by MemoFlow", provider: "语音识别由阿里云百炼提供", selectedBadge: "已选择",
};
export type MessageKey = keyof typeof en;
export type Translate = (key: MessageKey, values?: Record<string, string | number>) => string;

// 按当前语言显示服务端已返回的双语提示。
export function localize(message: LocalizedText, language: Language): string {
  return language === "en" ? message.en : message.zh;
}

// 按界面语言读取文案，仅替换开发者定义的命名占位符。
export function translate(language: Language, key: MessageKey, values: Record<string, string | number> = {}): string {
  const template = (language === "en" ? en : zh)[key];
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(values[name] ?? `{${name}}`));
}

// 使用标准语言代码显示本地化名称，保留百炼使用的菲律宾语名称。
export function languageName(code: string, language: Language): string {
  if (code === "tl") return language === "en" ? "Filipino" : "菲律宾语";
  return new Intl.DisplayNames([language], { type: "language" }).of(code) ?? code;
}

// 将文件大小显示为与服务端限制一致的十进制单位。
export function fileSize(bytes: number): string {
  return bytes < 1_000_000 ? `${(bytes / 1000).toFixed(1)} KB` : `${(bytes / 1_000_000).toFixed(2)} MB`;
}

// 将秒数显示为跨语言一致的时分秒。
export function durationText(seconds: number): string {
  const total = Math.round(seconds);
  return [Math.floor(total / 3600), Math.floor(total / 60) % 60, total % 60].map(value => String(value).padStart(2, "0")).join(":");
}
