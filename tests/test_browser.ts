import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import assert from "node:assert/strict";
import test from "node:test";

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

// 验证两步编辑、按区域校验、代码交接和终态通知的真实浏览器链路。
test("Edge页面以显式会话编号交接一个任务", { timeout: 120_000 }, async t => {
  const testRoot = path.join(repository, ".runtime/browser-tests");
  await fs.mkdir(testRoot, { recursive: true });
  await fs.mkdir(screenshots, { recursive: true });
  const root = await fs.mkdtemp(path.join(testRoot, "run-"));
  const previousTemp = { TEMP: process.env.TEMP, TMP: process.env.TMP };
  process.env.TEMP = root;
  process.env.TMP = root;
  const server = spawn(python, ["-B", "-X", "utf8", "-m", "tests.browser_server", "--workspace", root],
    { cwd: repository, windowsHide: true, stdio: "pipe" });
  const exited = new Promise<number | null>(resolve => server.once("exit", resolve));
  let serverErrors = "";
  server.stderr.on("data", value => { serverErrors += String(value); });
  t.after(async () => {
    if (server.exitCode === null && server.signalCode === null) server.kill();
    await exited;
    const actual = await fs.realpath(root);
    assert.equal(path.dirname(actual), await fs.realpath(testRoot));
    await fs.rm(actual, { recursive: true });
    for (const name of ["TEMP", "TMP"] as const) {
      if (previousTemp[name] === undefined) delete process.env[name];
      else process.env[name] = previousTemp[name];
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
    await page.screenshot({ path: path.join(screenshots, "zh-light.png"), animations: "disabled" });
    await page.emulateMedia({ colorScheme: "dark" });
    await page.waitForFunction(() => document.documentElement.classList.contains("dark"));
    await page.screenshot({ path: path.join(screenshots, "zh-dark.png"), animations: "disabled" });
    await page.locator(".language-select").click();
    await page.getByRole("option", { name: "English", exact: true }).click();
    await page.locator(".theme-select").click();
    await page.getByRole("option", { name: "Light", exact: true }).click();
    await page.locator("#page-title").click();
    await page.screenshot({ path: path.join(screenshots, "en-light.png"), animations: "disabled" });
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    await page.locator("#error-panel").getByText("Choose an audio file.", { exact: true }).waitFor();
    assert.equal(await page.locator("#audio_id").evaluate(element => element.contains(document.activeElement)), true);
    await assert.rejects(confirmSession(root, connection.session_id), /预览/);
    await assert.rejects(fs.access(path.join(root, ".asr-transcription/.state/jobs")), { code: "ENOENT" });

    await page.locator('label[for="use-api-key"]').click();
    await page.locator("#api-key-value").fill("fixture-ui-key-not-real");
    await page.route(origin + "/api/save-api-key", route => route.fulfill({ status: 422, contentType: "application/json",
      body: JSON.stringify({ ok: false, field: "auth_mode", error: "Cannot save fixture key." }) }), { times: 1 });
    const saveKey = page.getByRole("button", { name: "Save API key", exact: true });
    await saveKey.click();
    await page.locator("#error-panel").getByText("Cannot save fixture key.", { exact: true }).waitFor();
    assert.equal(await page.locator("#api-key-value").inputValue(), "fixture-ui-key-not-real");
    await saveKey.click();
    await page.getByText("API key saved to this working folder.", { exact: true }).waitFor();
    await page.locator("#audio_id").getByRole("button", { name: "Choose an audio file", exact: true }).click();
    await page.locator("#audio_id").getByText("Selected", { exact: true }).waitFor();
    assert.equal(await page.locator("#audio_id input[type=file]").count(), 0);
    assert.match(await page.locator(".audio-path").innerText(), /sample\.wav/);
    await page.locator('label[for="hotwords-enabled"]').click();
    await page.locator('label[for="context-enabled"]').click();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download template", exact: true }).click();
    assert.equal((await download).suggestedFilename(), "hotwords-template.xlsx");
    const input = '--terms "Kubernetes"\nC:\\voice\\😀 context';
    await page.locator("#context-text").fill(input);
    await page.locator("#hotword_rows input[type=file]").setInputFiles(path.join(root, "fixtures/invalid.xlsx"));
    await page.locator("#hotword-issues").getByText(/The first row must contain text and weight/).waitFor();
    assert.match(await page.locator("#hotword-issues").innerText(), /Row 1/);
    await page.locator("#hotword_rows button").filter({ hasText: /^Import Excel$/ }).click({ trial: true });
    await page.locator("#hotword_rows input[type=file]").setInputFiles(path.join(root, "fixtures/paged.xlsx"));
    await page.getByText("Imported: paged.xlsx", { exact: true }).waitFor();
    assert.equal(await page.locator(".hotword-error-row").count(), 0);
    const beforePreview = requests.filter(request => request.path === "/api/validate").length;
    await page.locator("#hotword-1-text").click();
    await page.locator("#context-text").click();
    assert.equal(requests.filter(request => request.path === "/api/validate").length, beforePreview);
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    await page.locator('#hotword-61-weight[aria-invalid="true"]').waitFor();
    assert.equal(await page.locator("#hotword-1-text").count(), 0);
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
    await page.locator("#hotword_rows").screenshot({ path: path.join(screenshots, "hotwords-en-errors.png"), animations: "disabled" });
    await page.locator("#hotword-2-weight").fill("4");
    await page.getByRole("button", { name: "Delete row 1", exact: true }).click();
    assert.equal(await page.locator("#hotword-1-text").inputValue(), "MemoFlow");
    assert.equal(await page.locator("#hotword-2-text").inputValue(), "Kubernetes");
    assert.equal(await page.locator("#hotword-3-text").count(), 0);
    await page.locator("#context-text").click();
    assert.equal(requests.filter(request => request.path === "/api/validate").length, beforePreview + 2);
    await page.locator("#context-text").fill("😀".repeat(401));
    assert.equal(await page.locator("#context .el-form-item__error").count(), 0);
    assert.equal(await page.locator("#context .textarea-footer .field-error").count(), 0);
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    await page.locator("#context .el-form-item__error").waitFor();
    assert.match(await page.locator("#context .el-form-item__error").innerText(), /401 characters/);
    assert.equal(await page.locator("#context-text").inputValue(), "😀".repeat(401));
    await page.locator("#context-text").fill(input);
    await page.getByRole("button", { name: "Confirm and preview", exact: true }).click();
    const copy = page.getByRole("button", { name: "Copy for Codex", exact: true });
    await copy.waitFor();
    await page.waitForFunction(() => !Array.from(document.querySelectorAll("button")).find(button => button.textContent?.includes("Copy for Codex"))?.disabled);
    assert.equal(await page.locator("#config-fields").count(), 0);
    assert.equal(await page.locator("#api-key-value").count(), 0);
    assert.ok(await page.locator("#page-title").evaluate(element => element.getBoundingClientRect().top >= 76));
    assert.equal(await page.locator(".preview-context").textContent(), input);
    assert.match(await page.locator("#review").innerText(), /MemoFlow/);
    assert.match(await page.locator("#review").innerText(), /Kubernetes/);
    await assert.rejects(fs.access(path.join(root, ".asr-transcription/.state/jobs")), { code: "ENOENT" });
    await page.screenshot({ path: path.join(screenshots, "preview-en-light.png"), animations: "disabled" });
    await page.getByRole("button", { name: "Back to editing", exact: true }).click();
    await page.locator("#context-text").waitFor();
    assert.equal(await page.locator("#context-text").inputValue(), input);
    await assert.rejects(confirmSession(root, connection.session_id), /预览/);
    const deleteRow = page.getByRole("button", { name: /^Delete row \d+$/ });
    while (await deleteRow.count()) await deleteRow.first().click();
    await page.getByRole("button", { name: "Add row", exact: true }).click();
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
    assert.equal(await exited, 0, serverErrors);
    assert.equal(serverErrors, "");
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
