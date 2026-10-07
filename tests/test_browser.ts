import { chromium, type Browser, type Locator } from "playwright";
import { execFileSync, spawn } from "node:child_process";
import { createInterface } from "node:readline";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import assert from "node:assert/strict";
import test, { type TestContext } from "node:test";
import type { Receipt, SessionDescription, SessionEnd } from "../frontend/types";

const repository = path.resolve(".");
const python = path.join(repository, ".venv/Scripts/python.exe");
const entry = path.join(repository, "skills/asr-transcription/scripts/asr.py");
const screenshots = path.join(repository, ".runtime/ui-previews");

// 调用实际代码入口，将复制的会话编号交接为任务并解析回执。
function confirmSession(workspace: string, sessionId: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const command = spawn(python, ["-B", "-X", "utf8", entry, "--workspace", workspace, "confirm", "--session", sessionId],
      { cwd: repository, windowsHide: true });
    let output = "", errors = "";
    command.stdout.on("data", value => { output += String(value); });
    command.stderr.on("data", value => { errors += String(value); });
    command.once("error", reject);
    command.once("exit", code => {
      if (code !== 0) { reject(new Error(errors || output)); return; }
      try { resolve(JSON.parse(output) as Record<string, unknown>); }
      catch (error) { reject(error); }
    });
  });
}

// 核对提示与输入卡片使用相同的水平位置和宽度。
async function assertMatchingHorizontalBounds(first: Locator, second: Locator): Promise<void> {
  await Promise.all([first, second].map(locator => locator.evaluate(element =>
    Promise.all(element.getAnimations().map(animation => animation.finished)))));
  const [firstBox, secondBox] = await Promise.all([first.boundingBox(), second.boundingBox()]);
  assert.ok(firstBox && secondBox);
  assert.ok(Math.abs(firstBox.x - secondBox.x) <= 1);
  assert.ok(Math.abs(firstBox.width - secondBox.width) <= 1);
}

// 核对热词表头与数据行有颜色层级，并突出列名和居中数值列。
async function assertHotwordHeader(table: Locator): Promise<void> {
  const headers = table.locator(".el-table__header-wrapper th");
  const headerBackground = await headers.first().evaluate(element => getComputedStyle(element).backgroundColor);
  const rowBackground = await table.locator(".el-table__body tbody tr").first().evaluate(element => getComputedStyle(element).backgroundColor);
  assert.notEqual(headerBackground, rowBackground);
  const primary = await table.evaluate(() => getComputedStyle(document.documentElement).color);
  for (const index of [0, 1, 2]) {
    assert.equal(await headers.nth(index).evaluate(element => getComputedStyle(element).fontWeight), "600");
    assert.equal(await headers.nth(index).evaluate(element => getComputedStyle(element).color), primary);
  }
  for (const index of [0, 1, 2]) assert.equal(await headers.nth(index).evaluate(element => getComputedStyle(element).textAlign), "center");
}

// 在独立页面中核对终态、加载失败和填写中断连的双语主题展示。
async function assertSessionViews(browser: Browser, url: string, description: SessionDescription): Promise<void> {
  const receipt: Receipt = { session_id: description.session_id, job_id: "visual-check-job", config_path: "D:/example/config.json",
    json_directory: "D:/example/json", document_directory: "D:/example/documents", auth_mode: "console", execution_started: false };
  for (const language of ["zh-CN", "en"] as const) {
    for (const theme of ["light", "dark"] as const) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: language, colorScheme: theme });
      let releaseEvents!: () => void;
      const eventsGate = new Promise<void>(resolve => { releaseEvents = resolve; });
      try {
        const page = await context.newPage();
        const failures: string[] = [];
        page.on("pageerror", error => failures.push(error.message));
        let scenario: SessionEnd["state"] | "unavailable" | "disconnected" = "cancelled";
        let eventRequests = 0;
        await page.route(new URL("/api/events", url).href, async route => {
          eventRequests += 1;
          await eventsGate;
          await route.abort("failed");
        });
        await page.route(new URL("/api/session", url).href, route => {
          if (scenario === "unavailable") return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({
            ok: false, error: { zh: "无法加载测试会话。", en: "The test session could not be loaded." },
          }) });
          if (scenario === "disconnected") return route.fulfill({ contentType: "application/json", body: JSON.stringify({
            ...description, phase: "editing", preview: null, terminal: null,
          } satisfies SessionDescription) });
          const session: SessionDescription = { ...description, phase: scenario, preview: null,
            terminal: { state: scenario, receipt: scenario === "handed_off" ? receipt : null } };
          return route.fulfill({ contentType: "application/json", body: JSON.stringify(session) });
        });
        for (const state of ["cancelled", "expired", "handed_off", "unavailable", "disconnected"] as const) {
          scenario = state;
          await page.goto(url);
          const unavailable = state === "unavailable" || state === "disconnected";
          if (state === "disconnected") {
            await page.locator("#config-fields").waitFor();
            await page.locator('label[for="context-enabled"]').click();
            await page.locator("#context-text").fill("In-progress text");
            releaseEvents();
          }
          await page.locator(unavailable ? "#session-unavailable" : "#session-ended").waitFor();
          assert.equal(await page.locator("#config-fields").count(), 0);
          assert.equal(await page.locator(".settings-summary").count(), 0);
          assert.equal(await page.locator(".action-bar").count(), 0);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
          assert.equal(await page.locator(".intro-note").count(), 0);
          assert.equal(await page.locator(".steps").count(), 0);
          assert.equal(await page.locator(".el-alert").count(), 0);
          assert.equal(await page.locator(".el-result").count(), 1);
          assert.equal(await page.locator("#error-panel").count(), 0);
          if (!unavailable) {
            assert.equal(await page.locator("#session-ended").getByText("visual-check-job", { exact: true }).count(), state === "handed_off" ? 1 : 0);
          } else {
            assert.equal(await page.locator("#session-unavailable .el-result__title").innerText(), language === "en" ? "Page unavailable" : "页面暂不可用");
            assert.equal(await page.locator("#session-ended").count(), 0);
          }
          await page.screenshot({ path: path.join(screenshots, `state-${state}-${language}-${theme}.png`), animations: "disabled" });
          if (language === "en" && theme === "dark") {
            await page.setViewportSize({ width: 390, height: 844 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            await page.screenshot({ path: path.join(screenshots, `state-${state}-mobile.png`), animations: "disabled" });
            await page.setViewportSize({ width: 1280, height: 900 });
          }
        }
        assert.equal(eventRequests, 1);
        assert.deepEqual(failures, []);
      } finally { releaseEvents(); await context.close(); }
    }
  }
}

// 在隔离目录启动真实本机服务，测试结束后回收自身进程和合成文件。
async function startFixture(t: TestContext, audioName?: string) {
  const testRoot = path.join(repository, ".runtime/browser-tests");
  await fs.mkdir(testRoot, { recursive: true });
  await fs.mkdir(screenshots, { recursive: true });
  const root = await fs.mkdtemp(path.join(testRoot, "run-"));
  const previousTemp = { TEMP: process.env.TEMP, TMP: process.env.TMP };
  process.env.TEMP = root;
  process.env.TMP = root;
  const serverArguments = ["-B", "-X", "utf8", "-m", "tests.browser_server", "--workspace", root];
  if (audioName) serverArguments.push("--audio", path.join(root, "fixtures", audioName));
  const server = spawn(python, serverArguments,
    { cwd: repository, windowsHide: true, stdio: "pipe" });
  const exited = new Promise<number | null>(resolve => server.once("exit", resolve));
  const diagnostics = { errors: "" };
  server.stderr.on("data", value => { diagnostics.errors += String(value); });
  t.after(async () => {
    try {
      if (server.exitCode === null && server.signalCode === null) {
        assert.ok(server.pid, "测试服务没有可确认的进程编号，保留测试目录。");
        if (process.platform === "win32") {
          // Windows venv启动器与服务worker共同退出后，才清理本测试的文件。
          execFileSync(path.join(process.env.SystemRoot!, "System32/taskkill.exe"),
            ["/PID", String(server.pid), "/T", "/F"], { windowsHide: true, stdio: "pipe" });
        } else server.kill();
      }
      await exited;
      const actual = await fs.realpath(root);
      assert.equal(path.dirname(actual), await fs.realpath(testRoot));
      await fs.rm(actual, { recursive: true });
    } finally {
      for (const name of ["TEMP", "TMP"] as const) {
        if (previousTemp[name] === undefined) delete process.env[name];
        else process.env[name] = previousTemp[name];
      }
    }
  });
  const lines = createInterface({ input: server.stdout });
  const connection = await new Promise<{ url: string; session_id: string }>((resolve, reject) => {
    lines.once("line", line => {
      try { resolve(JSON.parse(line) as { url: string; session_id: string }); }
      catch { reject(new Error("本机测试服务返回了无效的启动回执。")); }
      lines.close();
    });
    server.once("error", reject);
    server.once("exit", () => reject(new Error("本机测试服务在就绪前退出。")));
  });
  return { root, connection, exited, diagnostics };
}

// 验证表格修改、语言切换、两步编辑和代码交接的真实浏览器链路。
test("Edge页面以显式会话编号交接一个任务", { timeout: 120_000 }, async t => {
  const { root, connection, exited, diagnostics } = await startFixture(t);
  assert.equal(new URL(connection.url).hash, "");
  const origin = new URL(connection.url).origin;
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, locale: "zh-CN", colorScheme: "light" });
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin });
    const page = await context.newPage();
    const errors: string[] = [], requests: { origin: string; path: string }[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("request", request => { const url = new URL(request.url()); requests.push({ origin: url.origin, path: url.pathname }); });
    await page.goto(connection.url);
    await page.getByText("选择音频文件", { exact: true }).waitFor();
    const summary = page.locator("aside.settings-summary");
    assert.equal(await summary.isVisible(), true);
    const initialSummary = (await summary.boundingBox())!;
    assert.ok(initialSummary.y + initialSummary.height <= (await page.locator(".action-bar").boundingBox())!.y);
    const sessionDescription = await (await context.request.get(origin + "/api/session")).json() as SessionDescription;
    await assertSessionViews(browser, connection.url, sessionDescription);
    await assertMatchingHorizontalBounds(page.locator(".intro-note"), page.locator("#audio_id"));
    assert.equal(await page.locator(".region").count(), 0);
    const lightPage = await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor);
    const lightCard = await page.locator("#audio_id").evaluate(element => getComputedStyle(element).backgroundColor);
    assert.notEqual(lightPage, lightCard);
    await page.screenshot({ path: path.join(screenshots, "zh-light.png"), animations: "disabled" });
    await page.emulateMedia({ colorScheme: "dark" });
    await page.waitForFunction(() => document.documentElement.classList.contains("dark"));
    await page.screenshot({ path: path.join(screenshots, "zh-dark.png"), animations: "disabled" });
    const darkPage = await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor);
    const darkCard = await page.locator("#audio_id").evaluate(element => getComputedStyle(element).backgroundColor);
    assert.notEqual(darkPage, darkCard);
    assert.notEqual(darkPage, lightPage);
    assert.notEqual(darkCard, lightCard);
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "English", exact: true }).click();
    await page.screenshot({ path: path.join(screenshots, "en-dark.png"), animations: "disabled" });
    await page.locator(".theme-select").click();
    await page.getByRole("option", { name: "Light", exact: true }).click();
    await page.locator("#page-title").click();
    await page.screenshot({ path: path.join(screenshots, "en-light.png"), animations: "disabled" });
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    await page.locator("#audio_id .field-error").getByText("Choose an audio file.", { exact: true }).waitFor();
    assert.equal(await page.locator("#audio_id").evaluate(element => element.contains(document.activeElement)), true);
    assert.equal(await page.locator("#error-panel").count(), 0);
    await page.setViewportSize({ width: 390, height: 844 });
    await assertMatchingHorizontalBounds(page.locator(".intro-note"), page.locator("#audio_id"));
    assert.equal(await summary.isVisible(), false);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(screenshots, "missing-audio-en-mobile.png"), animations: "disabled" });
    await page.setViewportSize({ width: 1440, height: 1050 });
    assert.equal(await summary.isVisible(), true);
    await assert.rejects(confirmSession(root, connection.session_id), /预览/);
    await assert.rejects(fs.access(path.join(root, ".asr-transcription/.state/jobs")), { code: "ENOENT" });

    await page.locator('label[for="use-api-key"]').click();
    await page.locator("#api-key-value").fill("fixture-ui-key-not-real");
    await page.route(origin + "/api/save-api-key", route => route.fulfill({ status: 422, contentType: "application/json",
      body: JSON.stringify({ ok: false, field: "auth_mode", error: { zh: "无法保存合成凭据。", en: "Cannot save fixture key." } }) }), { times: 1 });
    const saveKey = page.getByRole("button", { name: "Save API key", exact: true });
    await saveKey.click();
    await page.locator("#error-panel").getByText("Cannot save fixture key.", { exact: true }).waitFor();
    assert.equal(await page.locator("#api-key-value").inputValue(), "fixture-ui-key-not-real");
    await saveKey.click();
    await page.getByText("API key saved to this working folder.", { exact: true }).waitFor();
    let releaseAudio!: () => void;
    const audioGate = new Promise<void>(resolve => { releaseAudio = resolve; });
    await page.route(origin + "/api/select-audio", async route => { await audioGate; await route.continue(); }, { times: 1 });
    const chooseAudio = page.locator("#audio_id").getByRole("button", { name: "Choose an audio file", exact: true });
    try {
      await chooseAudio.click();
      await page.locator("#audio_id .el-loading-mask").waitFor();
      assert.equal(await chooseAudio.isDisabled(), true);
      const buttonBox = (await chooseAudio.boundingBox())!;
      const spinnerBox = (await page.locator("#audio_id .el-loading-spinner .circular").boundingBox())!;
      assert.ok(Math.abs(spinnerBox.x + spinnerBox.width / 2 - buttonBox.x - buttonBox.width / 2) <= 4);
      assert.ok(Math.abs(spinnerBox.y + spinnerBox.height / 2 - buttonBox.y - buttonBox.height / 2) <= 4);
      await page.locator("#audio_id").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
      await page.locator("#audio_id").screenshot({ path: path.join(screenshots, "audio-loading-centered.png"), animations: "disabled" });
    } finally { releaseAudio(); }
    await page.locator("#audio_id").getByText("Selected", { exact: true }).waitFor();
    assert.equal(await page.locator("#audio_id input[type=file]").count(), 0);
    assert.match(await page.locator(".audio-path").innerText(), /sample\.wav/);
    assert.match(await summary.locator(".el-descriptions__content").nth(0).innerText(), /^sample\.wav · 64.0 KB$/);
    assert.equal(await summary.locator(".el-descriptions__content").nth(5).innerText(), "API Key");
    assert.equal((await summary.innerText()).includes("fixture-ui-key-not-real"), false);
    const selectedAudio = page.locator("#audio_id").getByRole("button", { name: "Replace audio", exact: true });
    assert.equal(await selectedAudio.locator(".audio-name").innerText(), "sample.wav");
    assert.equal(await selectedAudio.evaluate(element => element.classList.contains("el-button--success")), false);
    assert.equal(await selectedAudio.getByText("Selected", { exact: true }).count(), 1);
    assert.equal(await selectedAudio.locator(".el-tag--success").innerText(), "Selected");
    assert.equal(await selectedAudio.locator(".el-icon").evaluate(element => getComputedStyle(element).color),
      await selectedAudio.locator(".el-tag--success").evaluate(element => getComputedStyle(element).color));
    assert.match(await selectedAudio.locator(".helper").innerText(), /Supported formats:/);
    assert.equal(await selectedAudio.locator(".helper br").count(), 1);
    assert.equal(await page.locator("#audio_id .el-collapse").count(), 0);
    await page.locator("#audio_id").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
    await page.locator("#audio_id").screenshot({ path: path.join(screenshots, "audio-selected-en.png"), animations: "disabled" });
    const audioRequests = requests.filter(request => request.path === "/api/select-audio").length;
    await page.locator(".theme-select").click();
    await page.getByRole("option", { name: "Dark", exact: true }).click();
    await page.locator("#audio_id").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
    await page.locator("#audio_id").screenshot({ path: path.join(screenshots, "audio-selected-en-dark.png"), animations: "disabled" });
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "简体中文", exact: true }).click();
    await summary.getByRole("heading", { name: "当前设置", exact: true }).waitFor();
    assert.match(await summary.locator(".el-descriptions__content").nth(0).innerText(), /^sample\.wav · 64.0 KB$/);
    const selectedChineseAudio = page.locator("#audio_id").getByRole("button", { name: "更换音频", exact: true });
    assert.equal(await selectedChineseAudio.locator(".audio-name").innerText(), "sample.wav");
    assert.equal(await selectedChineseAudio.getByText("已选择", { exact: true }).count(), 1);
    assert.equal(await selectedChineseAudio.locator(".el-tag--success").innerText(), "已选择");
    await page.locator("#audio_id").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
    await page.locator("#audio_id").screenshot({ path: path.join(screenshots, "audio-selected-zh-dark.png"), animations: "disabled" });
    await page.locator(".theme-select").click();
    await page.getByRole("option", { name: "浅色", exact: true }).click();
    await page.locator("#audio_id").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
    await page.locator("#audio_id").screenshot({ path: path.join(screenshots, "audio-selected-zh.png"), animations: "disabled" });
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "English", exact: true }).click();
    assert.equal(requests.filter(request => request.path === "/api/select-audio").length, audioRequests);
    await summary.getByRole("heading", { name: "Current settings", exact: true }).waitFor();
    const summaryRequests = requests.filter(request => request.path === "/api/validate").length;
    await page.locator("#audio-language").click();
    const audioOptions = await page.locator("#audio-language").getAttribute("aria-controls");
    assert.ok(audioOptions);
    await page.locator(`[id="${audioOptions}"]`).getByRole("option", { name: "English", exact: true }).click();
    assert.equal(await summary.locator(".el-descriptions__content").nth(1).innerText(), "English");
    await page.locator('label[for="diarization"]').click();
    assert.equal(await summary.locator(".el-descriptions__content").nth(2).innerText(), "Off");
    await page.locator('label[for="diarization"]').click();
    assert.equal(await summary.locator(".el-descriptions__content").nth(2).innerText(), "On");
    assert.equal(requests.filter(request => request.path === "/api/validate").length, summaryRequests);
    assert.equal(await page.locator("#enhancement .el-card__header h2 + .section-caption").count(), 0);
    assert.match(await page.locator('.toggle-row').filter({ has: page.locator('label[for="diarization"]') }).locator("p").innerText(), /mono copy/);
    const hotwordRules = page.locator("#enhancement").getByRole("link", { name: "Alibaba Cloud hotword requirements", exact: true });
    const contextRules = page.locator("#enhancement").getByRole("link", { name: "Alibaba Cloud context requirements", exact: true });
    for (const rules of [hotwordRules, contextRules]) {
      assert.equal(await rules.isVisible(), true);
      assert.equal(await rules.evaluate(element => element.classList.contains("el-link--primary")), true);
      assert.equal(await rules.evaluate(element => getComputedStyle(element).fontSize === getComputedStyle(element.parentElement!).fontSize), true);
    }
    assert.equal(await hotwordRules.getAttribute("href"), "https://www.alibabacloud.com/help/en/model-studio/improve-asr-accuracy#hotword-format-2");
    assert.equal(await contextRules.getAttribute("href"), "https://www.alibabacloud.com/help/en/model-studio/improve-asr-accuracy#context-enhancement");
    await page.locator('label[for="hotwords-enabled"]').click();
    await page.locator('label[for="context-enabled"]').click();
    assert.equal(await page.getByRole("textbox", { name: "Reference text", exact: true }).count(), 1);
    assert.equal(await page.locator("#context .el-form-item__label").count(), 0);
    assert.equal(await page.locator("#hotword_rows").getByRole("heading", { name: "Hotword list", exact: true }).count(), 0);
    assert.equal(await page.locator(".hotword-toolbar button.is-text").count(), 2);
    assert.match(await page.locator("footer").innerText(), /^Powered by MemoFlow · Speech recognition by Alibaba Cloud Model Studio$/);
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download template", exact: true }).click();
    assert.equal((await download).suggestedFilename(), "hotwords-template.xlsx");
    const input = '--terms "Kubernetes"\nC:\\voice\\😀 context';
    await page.locator("#context-text").fill(input);
    assert.equal(await summary.locator(".el-descriptions__content").nth(4).innerText(), `${Array.from(input).length} characters`);
    await page.locator("#hotword_rows input[type=file]").setInputFiles(path.join(root, "fixtures/invalid.xlsx"));
    await page.locator("#hotword-issues").getByText(/This Excel file does not match the template/).waitFor();
    assert.equal(await page.locator("#hotword-issues .error-details").count(), 0);
    await page.locator("#hotword_rows button").filter({ hasText: /^Import Excel$/ }).click({ trial: true });
    const largeStart = performance.now();
    await page.locator("#hotword_rows input[type=file]").setInputFiles(path.join(root, "fixtures/limit.xlsx"));
    await page.getByText("Imported: limit.xlsx", { exact: true }).waitFor();
    await page.locator("#hotword-2000-text").waitFor({ state: "attached" });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    t.diagnostic(`2,000 hotwords imported and rendered in ${Math.round(performance.now() - largeStart)} ms`);
    assert.equal(await page.locator('.hotword-table input[id$="-text"]').count(), 2000);
    const table = page.locator(".hotword-table");
    assert.ok(Math.ceil((await table.boundingBox())!.height) <= 420);
    const scroll = table.locator(".el-table__body-wrapper .el-scrollbar__wrap");
    const largeEditStart = performance.now();
    await page.locator("#hotword-2000-text").fill("EditedLastTerm");
    assert.equal(await page.locator("#hotword-2000-text").inputValue(), "EditedLastTerm");
    t.diagnostic(`Last-row edit completed in ${Math.round(performance.now() - largeEditStart)} ms`);
    assert.ok(await scroll.evaluate(element => element.scrollTop) > 0);
    await page.locator("#hotword_rows input[type=file]").setInputFiles(path.join(root, "fixtures/scroll.xlsx"));
    await page.getByText("Imported: scroll.xlsx", { exact: true }).waitFor();
    assert.equal(await page.locator(".hotword-error-row").count(), 0);
    await assertHotwordHeader(table);
    assert.equal(await page.locator("#hotword-1-weight").evaluate(element => getComputedStyle(element).textAlign), "center");
    assert.equal(await summary.locator(".el-descriptions__content").nth(3).innerText(), "61 rows");
    await page.evaluate(() => window.scrollTo(0, 600));
    const firstStickyTop = (await summary.boundingBox())!.y;
    await page.evaluate(() => window.scrollTo(0, 800));
    const secondSticky = (await summary.boundingBox())!;
    assert.ok(Math.abs(firstStickyTop - 96) <= 1);
    assert.ok(Math.abs(secondSticky.y - firstStickyTop) <= 1);
    assert.ok(secondSticky.y + secondSticky.height <= (await page.locator(".action-bar").boundingBox())!.y);
    await page.screenshot({ path: path.join(screenshots, "settings-summary-sticky-en.png"), animations: "disabled" });
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    const bottomSummary = (await summary.boundingBox())!;
    assert.ok(bottomSummary.y + bottomSummary.height <= (await page.locator(".action-bar").boundingBox())!.y);
    const beforePreview = requests.filter(request => request.path === "/api/validate").length;
    await page.locator("#hotword-1-text").click();
    await page.locator("#context-text").click();
    assert.equal(requests.filter(request => request.path === "/api/validate").length, beforePreview);
    let releaseValidation!: () => void;
    let validationStarted!: () => void;
    const validationGate = new Promise<void>(resolve => { releaseValidation = resolve; });
    const validationRequest = new Promise<void>(resolve => { validationStarted = resolve; });
    await page.route(origin + "/api/validate", async route => {
      validationStarted();
      await validationGate;
      await route.continue();
    }, { times: 1 });
    const formElement = await page.locator("#config-fields").elementHandle();
    const summaryElement = await summary.elementHandle();
    const rowInput = await page.locator("#hotword-61-weight").elementHandle();
    const editRequests = requests.filter(request => request.path === "/api/edit").length;
    assert.ok(formElement && summaryElement && rowInput);
    try {
      await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
      await validationRequest;
      assert.equal(await formElement.evaluate(element => element.isConnected), true);
      assert.equal(await summaryElement.evaluate(element => element.isConnected), true);
      assert.equal(await rowInput.evaluate(element => element.isConnected), true);
      assert.equal(await page.locator("#config-fields").isVisible(), true);
      assert.equal(await summary.isVisible(), true);
      assert.equal(await page.locator('.hotword-table input[id$="-text"]').count(), 61);
      assert.equal(await page.locator("#hotword-61-weight").inputValue(), "8");
      assert.equal(await page.locator("#context-text").inputValue(), input);
      assert.equal(await page.locator("#api-key-value").inputValue(), "fixture-ui-key-not-real");
      for (const id of ["hotword-1-text", "hotword-61-weight", "context-text", "speaker-count", "api-key-value"]) {
        assert.equal(await page.locator(`#${id}`).isDisabled(), true, id);
      }
      for (const name of ["Add hotword", "Import Excel", "Download template", "Replace audio", "Confirm and preview"]) {
        assert.equal(await page.getByRole("button", { name, exact: true }).and(page.locator("button")).isDisabled(), true, name);
      }
      assert.equal(requests.filter(request => request.path === "/api/validate").length, beforePreview + 1);
      assert.equal(requests.filter(request => request.path === "/api/edit").length, editRequests);
    } finally { releaseValidation(); }
    await page.locator('#hotword-61-weight[aria-invalid="true"]').waitFor();
    assert.equal(await formElement.evaluate(element => element.isConnected), true);
    assert.equal(await rowInput.evaluate(element => element.isConnected), true);
    assert.equal(await page.locator("#hotword-61-weight").isDisabled(), false);
    assert.equal(await page.locator("#context-text").inputValue(), input);
    assert.equal(requests.filter(request => request.path === "/api/edit").length, editRequests);
    assert.equal(await page.locator('.hotword-table input[id$="-text"]').count(), 61);
    assert.ok(Math.ceil((await table.boundingBox())!.height) <= 420);
    await page.waitForFunction(() => (document.querySelector(".hotword-table .el-table__body-wrapper .el-scrollbar__wrap")?.scrollTop ?? 0) > 0);
    assert.equal(await page.locator("#hotword-61-weight").evaluate(element => element === document.activeElement), true);
    const weightMessage = await page.locator("#hotword-61-weight-errors").innerText();
    assert.match(weightMessage, /integer from 1 to 5/);
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "简体中文", exact: true }).click();
    await page.locator("#hotword-61-weight-errors").getByText(/权重必须/).waitFor();
    assert.ok(await scroll.evaluate(element => element.scrollTop) > 0);
    assert.equal(await page.locator("#hotword-61-weight").inputValue(), "8");
    await assertHotwordHeader(table);
    await page.locator("#hotword_rows").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
    await page.locator("#hotword_rows").screenshot({ path: path.join(screenshots, "hotwords-zh-header.png"), animations: "disabled" });
    await page.locator(".theme-select").click();
    await page.getByRole("option", { name: "深色", exact: true }).click();
    await page.locator("#hotword_rows").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
    await page.locator("#hotword_rows").screenshot({ path: path.join(screenshots, "hotwords-zh-header-dark.png"), animations: "disabled" });
    await assertHotwordHeader(table);
    await page.locator(".theme-select").click();
    await page.getByRole("option", { name: "浅色", exact: true }).click();
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "English", exact: true }).click();
    assert.equal(await page.locator("#hotword-61-weight-errors").innerText(), weightMessage);
    assert.equal(await page.locator('.hotword-table input[id$="-text"]').count(), 61);
    assert.ok(await scroll.evaluate(element => element.scrollTop) > 0);
    assert.equal(requests.filter(request => request.path === "/api/validate").length, beforePreview + 1);
    await page.locator("#hotword_rows").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
    await page.locator("#hotword_rows").screenshot({ path: path.join(screenshots, "hotwords-en-scroll.png"), animations: "disabled" });
    await page.locator("#hotword-61-weight").fill("4");
    await page.locator("#context-text").click();
    assert.equal(requests.filter(request => request.path === "/api/validate").length, beforePreview + 1);
    await page.getByRole("button", { name: "Delete row 61", exact: true }).click();
    await page.locator("#hotword-51-text").waitFor();
    await page.locator("#hotword_rows input[type=file]").setInputFiles(path.join(root, "fixtures/invalid-rows.xlsx"));
    await page.getByText("Imported: invalid-rows.xlsx", { exact: true }).waitFor();
    assert.equal(await page.locator(".hotword-error-row").count(), 0);
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    for (const row of [1, 3]) await page.locator(`#hotword-${row}-text[aria-invalid="true"]`).waitFor();
    await page.locator('#hotword-2-weight[aria-invalid="true"]').waitFor();
    await page.locator("#context-text").fill(input + " edited");
    assert.equal(await page.locator(".hotword-error-row").count(), 3);
    await page.locator("#hotword_rows input[type=file]").setInputFiles(path.join(root, "fixtures/invalid.xlsx"));
    await page.locator("#hotword-issues").getByText(/This Excel file does not match the template/).waitFor();
    assert.equal(await page.locator("#hotword-1-text").inputValue(), "Kubernetes");
    assert.equal(await page.locator("#hotword-2-weight").inputValue(), "9");
    assert.equal(await page.locator(".hotword-error-row").count(), 3);
    assert.match(await page.locator("#hotword-3-text-errors").innerText(), /Duplicate entries/);
    assert.equal(await hotwordRules.isVisible(), true);
    await page.locator("#hotword_rows").evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 96 }));
    await page.locator("#hotword_rows").screenshot({ path: path.join(screenshots, "hotwords-en-errors.png"), animations: "disabled" });
    await page.locator("#hotword-3-weight").fill("4");
    assert.equal(await page.locator(".hotword-error-row").count(), 3);
    await page.getByRole("button", { name: "Delete row 1", exact: true }).click();
    assert.equal(await page.locator("#hotword-1-text").inputValue(), "MemoFlow");
    assert.equal(await page.locator("#hotword-2-text").inputValue(), "Kubernetes");
    assert.equal(await page.locator("#hotword-3-text").count(), 0);
    await page.locator('#hotword-1-weight[aria-invalid="true"]').waitFor();
    assert.equal(await page.locator("#hotword-2-text").getAttribute("aria-invalid"), "false");
    assert.equal(await page.locator(".hotword-error-row").count(), 1);
    await page.locator("#hotword-1-weight").fill("4");
    assert.equal(await page.locator(".hotword-error-row").count(), 0);
    await page.locator("#context-text").click();
    assert.equal(requests.filter(request => request.path === "/api/validate").length, beforePreview + 2);
    await page.locator("#context-text").fill("😀".repeat(401));
    assert.equal(await page.locator("#context .el-form-item__error").count(), 0);
    assert.equal(await page.locator("#context .textarea-footer .field-error").count(), 0);
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    await page.locator("#context .el-form-item__error").waitFor();
    assert.match(await page.locator("#context .el-form-item__error").innerText(), /401 characters/);
    assert.equal(await page.locator("#context-text").inputValue(), "😀".repeat(401));
    const contextChecks = requests.filter(request => request.path === "/api/validate").length;
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "简体中文", exact: true }).click();
    assert.match(await page.locator("#context .el-form-item__error").innerText(), /401 个字符/);
    assert.equal(await page.locator("#context-text").inputValue(), "😀".repeat(401));
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "English", exact: true }).click();
    assert.match(await page.locator("#context .el-form-item__error").innerText(), /401 characters/);
    assert.equal(requests.filter(request => request.path === "/api/validate").length, contextChecks);
    await page.locator("#context-text").fill(input);
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    const copy = page.getByRole("button", { name: "Copy for Codex", exact: true });
    await copy.waitFor();
    await page.waitForFunction(() => !Array.from(document.querySelectorAll("button")).find(button => button.textContent?.includes("Copy for Codex"))?.disabled);
    assert.equal(await page.locator("#config-fields").count(), 0);
    assert.equal(await summary.count(), 0);
    assert.equal(await page.locator("#api-key-value").count(), 0);
    assert.ok(await page.locator("#page-title").evaluate(element => element.getBoundingClientRect().top >= 76));
    assert.equal(await page.locator(".preview-context").textContent(), input);
    assert.match(await page.locator("#review").innerText(), /MemoFlow/);
    assert.match(await page.locator("#review").innerText(), /Kubernetes/);
    await assertHotwordHeader(page.locator("#review .hotword-table"));
    assert.equal(await page.locator("#review .el-table__body tbody tr").first().locator("td").nth(2).evaluate(element => getComputedStyle(element).textAlign), "center");
    const previewBeforeLanguage = await (await context.request.get(origin + "/api/session")).json();
    const previewChecks = requests.filter(request => request.path === "/api/validate").length;
    assert.match(await page.locator(".review-warning").innerText(), /mono FLAC copy/);
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "简体中文", exact: true }).click();
    assert.match(await page.locator(".review-warning").innerText(), /单声道 FLAC 副本/);
    assert.equal(await page.locator(".preview-context").textContent(), input);
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "English", exact: true }).click();
    assert.match(await page.locator(".review-warning").innerText(), /mono FLAC copy/);
    const previewAfterLanguage = await (await context.request.get(origin + "/api/session")).json();
    assert.equal(previewAfterLanguage.preview.validation_id, previewBeforeLanguage.preview.validation_id);
    assert.equal(requests.filter(request => request.path === "/api/validate").length, previewChecks);
    await assert.rejects(fs.access(path.join(root, ".asr-transcription/.state/jobs")), { code: "ENOENT" });
    await page.screenshot({ path: path.join(screenshots, "preview-en-light.png"), animations: "disabled" });
    await page.getByRole("button", { name: "Back to editing", exact: true }).click();
    await page.locator("#context-text").waitFor();
    assert.equal(await page.locator("#context-text").inputValue(), input);
    assert.equal(await summary.isVisible(), true);
    await assert.rejects(confirmSession(root, connection.session_id), /预览/);
    await page.locator('label[for="hotwords-enabled"]').click();
    await page.locator('label[for="context-enabled"]').click();
    assert.equal(await page.locator("#hotword_rows").count(), 0);
    assert.equal(await page.locator("#context-text").count(), 0);
    assert.equal(await page.locator("#api-key-value").inputValue(), "fixture-ui-key-not-real");
    assert.match(await fs.readFile(path.join(root, ".asr-transcription/.env"), "utf8"), /fixture-ui-key-not-real/);
    await page.locator('label[for="hotwords-enabled"]').click();
    await page.locator('label[for="context-enabled"]').click();
    assert.equal(await page.locator("#hotword-1-text").inputValue(), "");
    assert.equal(await page.locator("#hotword-1-weight").inputValue(), "4");
    assert.equal(await page.locator("#context-text").inputValue(), "");
    await page.locator("#context-text").fill(input);
    await page.locator("#hotword-1-text").fill("IPO");
    for (const number of [2, 3, 4]) {
      await page.getByRole("button", { name: "Add hotword", exact: true }).click();
      await page.locator(`#hotword-${number}-text`).fill(number === 4 ? "IndependentTerm" : "IPO");
    }
    await page.locator("#hotword-4-weight").fill("9");
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    for (const number of [1, 2, 3]) await page.locator(`#hotword-${number}-text[aria-invalid="true"]`).waitFor();
    await page.locator('#hotword-4-weight[aria-invalid="true"]').waitFor();
    const duplicateChecks = requests.filter(request => request.path === "/api/validate").length;
    await page.locator("#hotword-1-weight").fill("5");
    assert.equal(await page.locator(".hotword-error-row").count(), 4);
    await page.getByRole("button", { name: "Delete row 1", exact: true }).click();
    for (const number of [1, 2]) {
      assert.equal(await page.locator(`#hotword-${number}-text`).inputValue(), "IPO");
      assert.equal(await page.locator(`#hotword-${number}-text`).getAttribute("aria-invalid"), "true");
    }
    assert.equal(await page.locator(".hotword-error-row").count(), 3);
    assert.equal(await page.locator("#hotword-3-text").inputValue(), "IndependentTerm");
    assert.equal(await page.locator("#hotword-3-weight").getAttribute("aria-invalid"), "true");
    await page.getByRole("button", { name: "Delete row 1", exact: true }).click();
    assert.equal(await page.locator("#hotword-1-text").inputValue(), "IPO");
    assert.equal(await page.locator("#hotword-1-text").getAttribute("aria-invalid"), "false");
    assert.equal(await page.locator("#hotword-2-weight").getAttribute("aria-invalid"), "true");
    assert.equal(await page.locator(".hotword-error-row").count(), 1);
    assert.equal(requests.filter(request => request.path === "/api/validate").length, duplicateChecks);
    const deleteRow = page.getByRole("button", { name: /^Delete row \d+$/ });
    while (await deleteRow.count()) await deleteRow.first().click();
    await page.getByRole("button", { name: "Add hotword", exact: true }).click();
    await page.locator("#hotword-1-text").fill("TypedTerm");
    await page.locator("#hotword-1-weight").fill("5");
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    await copy.waitFor();
    await page.reload();
    await copy.waitFor();
    assert.equal(await page.locator(".preview-context").textContent(), input);
    assert.match(await page.locator("#review").innerText(), /TypedTerm/);
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "简体中文", exact: true }).click();
    await page.locator(".theme-select").click();
    await page.getByRole("option", { name: "深色", exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(screenshots, "preview-zh-mobile.png"), animations: "disabled" });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.getByRole("button", { name: "复制给 Codex", exact: true }).click();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    assert.equal(copied, `确认转写，会话编号：${connection.session_id}`);
    const copiedId = copied.split("：").at(-1)!;
    const receipt = await confirmSession(root, copiedId);
    await page.locator("#session-ended").waitFor();
    await page.getByText("已交给 Codex", { exact: true }).waitFor();
    assert.equal(await page.locator("#config-fields").count(), 0);
    assert.equal(await page.locator("#review").count(), 0);
    assert.ok((await page.locator("#session-ended").innerText()).includes(String(receipt.job_id)));
    assert.equal(await exited, 0, diagnostics.errors);
    assert.equal(diagnostics.errors, "");
    assert.deepEqual(await confirmSession(root, copiedId), receipt);
    const files = await fs.readdir(path.join(root, ".asr-transcription/.state/jobs"));
    assert.equal(files.length, 1);
    const configuration = await fs.readFile(path.join(root, ".asr-transcription/.state/jobs", files[0], "config.json"), "utf8");
    assert.equal(configuration.includes("fixture-ui-key-not-real"), false);
    const config = JSON.parse(configuration);
    assert.equal(config.execution_authorized, true);
    assert.equal(config.enhancement.context, input);
    assert.deepEqual(config.enhancement.hotwords.vocabulary, { TypedTerm: 5 });
    await assert.rejects(fs.access(path.join(root, ".asr-transcription/.state/sessions", copiedId, "connection.json")), { code: "ENOENT" });
    assert.equal(config.audio.path, path.join(root, "fixtures/sample.wav"));
    assert.ok(await fs.stat(config.audio.path));
    await assert.rejects(fs.access(path.join(root, ".asr-transcription/.state/web-uploads")), { code: "ENOENT" });
    const storage = await page.evaluate(() => ({ ...localStorage }));
    assert.deepEqual(Object.keys(storage), ["asr-ui-preferences"]);
    assert.ok(requests.every(request => request.origin === origin));
    assert.equal(requests.filter(request => ["/api/confirm", "/api/reopen", "/api/cancel", "/api/validate-hotwords"].includes(request.path)).length, 0);
    assert.deepEqual(errors.filter(message => !message.includes("status of 422")), []);
    await page.screenshot({ path: path.join(screenshots, "handed-off-zh-mobile.png"), animations: "disabled" });
    await context.close();
  } finally { await browser.close(); }
});

for (const audioName of ["附件 recording.wav", "missing.wav"]) {
  test(`${audioName}附件仍通过网页预览，刷新和语言切换保留音频状态`, { timeout: 60_000 }, async t => {
    const { root, connection, exited, diagnostics } = await startFixture(t, audioName);
    const browser = await chromium.launch({ channel: "msedge", headless: true });
    try {
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "zh-CN" });
      const page = await context.newPage();
      const errors: string[] = [], paths: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("request", request => { paths.push(new URL(request.url()).pathname); });
      await page.goto(connection.url);
      await page.locator("#config-fields").waitFor();
      const initial = await (await context.request.get(new URL("/api/session", connection.url).href)).json() as SessionDescription;
      if (audioName === "missing.wav") {
        assert.equal(initial.audio, null);
        assert.ok(initial.audio_error);
        await page.locator("#audio_id .field-error").waitFor();
        assert.equal(await page.locator("#audio_id .field-error").innerText(), initial.audio_error.zh);
      } else {
        assert.ok(initial.audio);
        assert.equal(initial.audio_error, null);
        await page.locator("#audio_id .el-tag--success").waitFor();
        assert.equal(await page.locator(".audio-name").innerText(), audioName);
        assert.equal(await page.locator(".audio-path").innerText(), initial.audio.path);
      }
      assert.equal(await page.locator("#error-panel").count(), 0);
      assert.equal(await page.locator("#review").count(), 0);
      assert.equal(paths.filter(route => route === "/api/select-audio").length, 0);
      await assert.rejects(fs.access(path.join(root, ".asr-transcription/.state/jobs")), { code: "ENOENT" });
      await page.locator(".language-select").click();
      await page.getByRole("option", { name: "English", exact: true }).click();
      if (initial.audio_error) assert.equal(await page.locator("#audio_id .field-error").innerText(), initial.audio_error.en);
      else assert.equal(await page.locator("#audio_id .el-tag--success").innerText(), "Selected");
      await page.reload();
      await page.locator("#config-fields").waitFor();
      const restored = await (await context.request.get(new URL("/api/session", connection.url).href)).json() as SessionDescription;
      assert.deepEqual(restored.audio, initial.audio);
      assert.deepEqual(restored.audio_error, initial.audio_error);
      if (initial.audio_error) assert.equal(await page.locator("#audio_id .field-error").innerText(), initial.audio_error.en);
      else assert.equal(await page.locator(".audio-name").innerText(), audioName);
      const select = page.locator("#audio_id").getByRole("button", { name: initial.audio ? "Replace audio" : "Choose an audio file", exact: true });
      await select.click();
      await page.locator("#audio_id .el-tag--success").waitFor();
      assert.equal(await page.locator(".audio-name").innerText(), "sample.wav");
      assert.equal(await page.locator("#audio_id .field-error").count(), 0);
      assert.equal(paths.filter(route => route === "/api/select-audio").length, 1);
      const replacement = await (await context.request.get(new URL("/api/session", connection.url).href)).json() as SessionDescription;
      assert.ok(replacement.audio);
      assert.equal(replacement.audio_error, null);
      assert.notEqual(replacement.audio.audio_id, initial.audio?.audio_id);
      await page.reload();
      await page.locator("#audio_id .el-tag--success").waitFor();
      assert.equal(await page.locator(".audio-name").innerText(), "sample.wav");
      assert.equal(await page.locator("#audio_id .field-error").count(), 0);
      const afterRefresh = await (await context.request.get(new URL("/api/session", connection.url).href)).json() as SessionDescription;
      assert.deepEqual(afterRefresh.audio, replacement.audio);
      await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
      await page.getByRole("button", { name: "Copy for Codex", exact: true }).waitFor();
      assert.equal(await page.locator("#config-fields").count(), 0);
      await assert.rejects(fs.access(path.join(root, ".asr-transcription/.state/jobs")), { code: "ENOENT" });
      const receipt = await confirmSession(root, connection.session_id);
      await page.locator("#session-ended").waitFor();
      assert.equal(await exited, 0, diagnostics.errors);
      const config = JSON.parse(await fs.readFile(path.join(root, ".asr-transcription/.state/jobs", String(receipt.job_id), "config.json"), "utf8"));
      assert.equal(config.audio.path, path.join(root, "fixtures/sample.wav"));
      assert.deepEqual(errors, []);
      assert.equal(diagnostics.errors, "");
    } finally { await browser.close(); }
  });
}
