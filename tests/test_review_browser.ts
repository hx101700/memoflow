import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { createInterface } from "node:readline";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import test, { type TestContext } from "node:test";
import { chromium, type Browser } from "playwright";
import type { ReviewDocument } from "../frontend/types";

const repository = path.resolve(".");

// 启动独立的合成千句回听服务，测试退出时只结束自身进程树。
async function startReviewFixture(t: TestContext, closeBrowser: () => Promise<void>, existing?: { workspace: string; job_id: string }) {
  const parent = path.join(repository, ".runtime/review-browser-tests");
  await fs.mkdir(parent, { recursive: true });
  const workspace = existing?.workspace ?? await fs.mkdtemp(path.join(parent, "run-"));
  const server = spawn(path.join(repository, ".venv/Scripts/python.exe"),
    existing ? ["-B", "-X", "utf8", "skills/asr-transcription/scripts/asr.py", "--workspace", workspace, "review", "--job", existing.job_id, "--no-browser"] :
      ["-B", "-X", "utf8", "-m", "tests.review_browser_server", "--workspace", workspace],
    { cwd: repository, windowsHide: true, stdio: "pipe", env: { ...process.env, TEMP: workspace, TMP: workspace } });
  let errors = "";
  server.stderr.on("data", value => { errors += String(value); });
  const exited = new Promise<void>(resolve => server.once("exit", () => resolve()));
  // 有界等待真实退出事件，避免结束回执与Windows进程退出之间的清理竞态。
  async function waitForExit(milliseconds: number): Promise<boolean> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([exited.then(() => true), new Promise<boolean>(resolve => {
        timer = setTimeout(() => resolve(false), milliseconds);
      })]);
    } finally { clearTimeout(timer); }
  }
  t.after(async () => {
    // 先释放浏览器，之后服务清理即使失败也不会遗漏Edge的连接句柄。
    try { await closeBrowser(); }
    finally {
      if (!await waitForExit(2000)) {
        assert.ok(server.pid, "测试服务没有可确认的进程编号。");
        try {
          if (process.platform === "win32") execFileSync(path.join(process.env.SystemRoot!, "System32/taskkill.exe"),
            ["/PID", String(server.pid), "/T", "/F"], { windowsHide: true, stdio: "pipe", timeout: 5000 });
          else server.kill();
        } catch (error) {
          // 进程可能在等待截止与taskkill之间自行退出；只有实际退出才接受该竞争。
          if (!await waitForExit(2000)) throw error;
        }
        assert.equal(await waitForExit(5000), true, "测试服务没有退出，请检查本次夹具进程。");
      }
    }
  });
  const lines = createInterface({ input: server.stdout });
  const connection = await new Promise<{ url: string; job_id: string }>((resolve, reject) => {
    lines.once("line", line => { try { resolve(JSON.parse(line)); } catch { reject(new Error("无效测试启动回执")); } lines.close(); });
    server.once("error", reject);
    server.once("exit", () => reject(new Error(`回听测试服务启动失败：${errors}`)));
  });
  return { workspace, connection, waitForExit };
}

test("Edge阅读回听支持完整正文、重置、单一提示、导出目录和关页恢复", { timeout: 180_000 }, async t => {
  let browser: Browser | undefined;
  const fixture = await startReviewFixture(t, async () => { await browser?.close(); });
  const { workspace, connection } = fixture;
  browser = await chromium.launch({ channel: "msedge", headless: true });
  const context = await browser.newContext({ locale: "zh-CN", viewport: { width: 1280, height: 1000 } });
  const page = await context.newPage();
  const failures: string[] = [];
  page.on("pageerror", error => failures.push(error.message));
  await page.goto(connection.url);
  const firstRow = page.locator("#review-sentence-1");
  const firstParagraph = firstRow.locator(".review-paragraph");
  await firstParagraph.waitFor();
  const original = await firstParagraph.innerText();
  assert.ok(original.length > 500 && original.includes("\n"));
  assert.equal(await firstParagraph.evaluate(element => element.scrollHeight <= element.clientHeight + 1), true);
  const alignment = await page.evaluate(() => [".brand", "#page-title", ".review-reading-list", ".review-toolbar"]
    .map(selector => document.querySelector(selector)!.getBoundingClientRect().left));
  assert.ok(Math.max(...alignment) - Math.min(...alignment) < 2, "品牌、标题、阅读区与播放器应共用左右基线");
  const headerButtons = await page.locator(".review-header-buttons .el-button").evaluateAll(buttons => buttons.map(button => {
    const box = button.getBoundingClientRect(); return { width: box.width, height: box.height };
  }));
  assert.deepEqual(headerButtons[0], headerButtons[1]);
  const titleBox = (await page.locator("#page-title").boundingBox())!;
  const actionsBox = (await page.locator(".review-header-buttons").boundingBox())!;
  assert.ok(Math.abs(titleBox.y + titleBox.height / 2 - actionsBox.y - actionsBox.height / 2) < 1.5,
    "标题和右侧操作应垂直居中对齐");
  const readingFrame = (await page.locator(".review-reading-frame").boundingBox())!;
  const scrollArea = (await page.locator(".review-reading-list").boundingBox())!;
  assert.ok(scrollArea.y - readingFrame.y >= 24 && readingFrame.y + readingFrame.height - scrollArea.y - scrollArea.height >= 24,
    "阅读区上下留白应位于滚动区域外，避免滚动后消失");
  const readingTextBox = (await firstParagraph.boundingBox())!;
  await firstParagraph.click({ position: { x: 110, y: 14 } });
  await page.waitForFunction(expected => {
    const editor = document.querySelector<HTMLTextAreaElement>("#review-sentence-1 textarea");
    if (!editor) return false;
    const box = editor.getBoundingClientRect();
    return Math.abs(box.x - expected.x) < 1 && Math.abs(box.y - expected.y) < 1
      && Math.abs(box.width - expected.width) < 1 && Math.abs(box.height - expected.height) < 1.5;
  }, readingTextBox);
  const caretPosition = await firstRow.getByRole("textbox").evaluate(input => (input as HTMLTextAreaElement).selectionStart);
  assert.ok(caretPosition > 0 && caretPosition < original.length, "点击正文应在点击文字附近进入编辑");
  await page.locator("#page-title").click();
  assert.equal(await page.locator(".el-alert").count(), 0);
  assert.equal(await page.getByRole("button", { name: "结束校验", exact: true }).count(), 0);
  const nextChange = page.getByRole("button", { name: "下一处修改", exact: true });
  assert.equal(await nextChange.isDisabled(), true);
  await page.screenshot({ path: path.join(workspace, "review-reading-light-1280.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth);
  const mobilePlayer = await page.locator(".review-toolbar").boundingBox();
  assert.ok(mobilePlayer && mobilePlayer.y >= 0 && mobilePlayer.y + mobilePlayer.height <= 845);
  assert.equal(await firstParagraph.evaluate(element => element.scrollHeight <= element.clientHeight + 1), true);
  await page.screenshot({ path: path.join(workspace, "review-reading-390.png"), animations: "disabled" });
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.waitForFunction(() => (document.querySelector("audio")?.readyState ?? 0) >= 1);
  assert.equal(await page.locator("audio").evaluate(audio => (audio as HTMLAudioElement).duration), 1000);
  await page.getByRole("button", { name: "回听第 1 句", exact: true }).click();
  await page.waitForFunction(() => { const audio = document.querySelector("audio"); return audio && audio.paused && audio.currentTime >= 0.99; });
  assert.ok(await page.locator("audio").evaluate(audio => (audio as HTMLAudioElement).currentTime <= 1.08));
  assert.equal(await firstRow.getAttribute("aria-current"), "true");
  const secondRow = page.locator("#review-sentence-2");
  await secondRow.locator(".review-paragraph").click();
  await secondRow.getByRole("textbox").fill("合成数据说明：这句已人工修改，保留独立的修改标记。");
  await page.locator("#page-title").click();
  await page.getByText("已保存", { exact: true }).waitFor();
  assert.equal(await page.locator("#review-notice").count(), 0);
  await page.getByRole("button", { name: "回听第 3 句", exact: true }).click();
  await page.waitForFunction(() => { const audio = document.querySelector("audio"); return audio && audio.paused && audio.currentTime >= 2.99; });
  assert.equal(await secondRow.getByText("已修改", { exact: true }).count(), 1);
  assert.equal(await page.locator("#review-sentence-3").getAttribute("aria-current"), "true");
  const currentTimecode = page.locator("#review-sentence-3 .review-timecode");
  assert.equal(await currentTimecode.evaluate(element => getComputedStyle(element).fontWeight), "700");
  assert.equal(await currentTimecode.evaluate(element => getComputedStyle(element).color),
    await firstRow.locator(".review-timecode").evaluate(element => getComputedStyle(element).color));
  assert.equal(await currentTimecode.evaluate(element => getComputedStyle(element).fontSize), "14px");
  await page.screenshot({ path: path.join(workspace, "review-modified-and-current.png"), animations: "disabled" });

  // 按顺序循环定位改动，重置的句子会退出导航，定位时暂停音频且不启动播放。
  const fourthRow = page.locator("#review-sentence-4");
  await fourthRow.locator(".review-paragraph").click();
  await fourthRow.getByRole("textbox").fill("另一处待核对修改。");
  await page.locator("#page-title").click();
  await page.getByText("已保存", { exact: true }).waitFor();
  await page.getByRole("button", { name: "播放", exact: true }).click();
  for (const index of [2, 4, 2]) {
    await nextChange.click();
    await page.waitForFunction(expected => document.activeElement?.closest(".review-sentence")?.id === `review-sentence-${expected}`, index);
    assert.equal(await page.locator("audio").evaluate(audio => (audio as HTMLAudioElement).paused), true);
  }
  await page.getByRole("button", { name: "重置第 4 句", exact: true }).click();
  await nextChange.click();
  assert.equal(await page.evaluate(() => document.activeElement?.closest(".review-sentence")?.id), "review-sentence-2");
  await page.getByRole("button", { name: "回听第 3 句", exact: true }).click();
  await page.waitForFunction(() => { const audio = document.querySelector("audio"); return audio && audio.paused && audio.currentTime >= 2.99; });

  // 暂停时自由拖动，释放后立即跳转、高亮并跟随到相应段落。
  const slider = page.getByRole("slider", { name: "播放进度", exact: true });
  const runway = (await page.locator(".review-progress .el-slider__runway").boundingBox())!;
  const thumb = (await slider.boundingBox())!;
  await page.mouse.move(thumb.x + thumb.width / 2, thumb.y + thumb.height / 2);
  await page.mouse.down();
  await page.mouse.move(runway.x + runway.width * 0.3, runway.y + runway.height / 2, { steps: 12 });
  assert.ok(Number(await slider.getAttribute("aria-valuenow")) > 290);
  assert.ok(await page.locator("audio").evaluate(audio => (audio as HTMLAudioElement).currentTime < 4));
  await page.mouse.up();
  await page.waitForFunction(() => {
    const audio = document.querySelector("audio");
    return audio && audio.paused && audio.currentTime > 290 && document.querySelector(".review-sentence.is-current")?.id === `review-sentence-${Math.floor(audio.currentTime) + 1}`;
  });
  await page.waitForFunction(() => {
    const row = document.querySelector(".review-sentence.is-current")!.getBoundingClientRect();
    const list = document.querySelector(".review-reading-list")!.getBoundingClientRect();
    return row.top >= list.top - 1 && row.bottom <= list.bottom + 1;
  });
  // 底部播放保持连续跨句，高亮随实际时钟移动；拖动预览不被播放进度拉回。
  await page.getByRole("button", { name: "播放", exact: true }).click();
  const startedAt = await page.locator("audio").evaluate(audio => (audio as HTMLAudioElement).currentTime);
  await page.waitForFunction(start => {
    const audio = document.querySelector("audio");
    return audio && !audio.paused && audio.currentTime > start + 1.3 && document.querySelector(".review-sentence.is-current")?.id === `review-sentence-${Math.floor(audio.currentTime) + 1}`;
  }, startedAt);
  const movingThumb = (await slider.boundingBox())!;
  await page.mouse.move(movingThumb.x + movingThumb.width / 2, movingThumb.y + movingThumb.height / 2);
  await page.mouse.down();
  await page.mouse.move(runway.x + runway.width * 0.7, runway.y + runway.height / 2, { steps: 12 });
  await page.waitForFunction(() => Number(document.querySelector('[role="slider"]')?.getAttribute("aria-valuenow")) > 690);
  assert.ok(await page.locator("audio").evaluate(audio => (audio as HTMLAudioElement).currentTime < 400));
  await page.mouse.up();
  await page.waitForFunction(() => document.querySelector("audio")!.currentTime > 690);
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await firstParagraph.scrollIntoViewIfNeeded();

  let releaseSave!: () => void;
  const pendingSave = new Promise<void>(resolve => { releaseSave = resolve; });
  t.after(() => releaseSave());
  await page.route("**/api/review/save", async route => { const response = await route.fetch(); await pendingSave; await route.fulfill({ response }); });
  await firstParagraph.click();
  const first = firstRow.getByRole("textbox");
  assert.equal(await first.inputValue(), original);
  assert.equal(await first.evaluate(element => element.scrollHeight <= element.clientHeight + 1), true, "编辑时长正文不能内部截断");
  await first.fill("浏览器保存期间仍保留的合成修改。");
  assert.equal(await firstRow.getByText("已修改", { exact: true }).count(), 1);
  await page.locator(".language-select").click();
  await page.getByRole("option", { name: "English", exact: true }).click();
  await page.locator(".theme-select").click();
  await page.getByRole("option", { name: "Dark", exact: true }).click();
  assert.equal(await firstParagraph.innerText(), "浏览器保存期间仍保留的合成修改。");
  releaseSave();
  await page.getByText("Saved", { exact: true }).waitFor();
  await page.unroute("**/api/review/save");
  await page.getByRole("button", { name: "Speaker names", exact: true }).click();
  await page.locator(".review-speaker-list input").first().fill("Synthetic host");
  await page.getByRole("button", { name: "Add speaker", exact: true }).click();
  await page.locator(".review-speaker-list input").last().fill("Synthetic guest");
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await firstRow.getByRole("button", { name: "Sentence 1 · Speaker", exact: true }).click();
  await page.getByRole("option", { name: "Synthetic guest", exact: true }).click();
  await page.getByText("Saved", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Reset sentence 1", exact: true }).click();
  await page.getByText("Saved", { exact: true }).waitFor();
  assert.equal(await firstParagraph.innerText(), original);
  assert.equal(await firstRow.getByText("Modified", { exact: true }).count(), 0);
  assert.equal(await firstRow.locator(".review-speaker-label").innerText(), "Synthetic host");
  await page.screenshot({ path: path.join(workspace, "review-reading-dark-1280.png"), animations: "disabled" });

  await firstParagraph.click();
  await first.fill("导出校验稿前的合成修改。");
  await fs.writeFile(path.join(workspace, "fixtures/cancel-next-directory"), "synthetic");
  let allowExport!: () => void;
  const exportGate = new Promise<void>(resolve => { allowExport = resolve; });
  t.after(() => allowExport());
  await page.route("**/api/review/export", async route => { await exportGate; await route.continue(); }, { times: 1 });
  await page.getByRole("button", { name: "Play", exact: true }).click();
  const cancelledExport = page.waitForResponse(response => new URL(response.url()).pathname === "/api/review/export");
  await page.getByRole("button", { name: "Export reviewed documents", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: "Pause", exact: true }).isEnabled(), true);
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: "Cancel selection", exact: true }).count(), 0);
  allowExport();
  assert.equal((await (await cancelledExport).json()).cancelled, true);
  await page.getByText("Saved", { exact: true }).waitFor();
  await firstParagraph.scrollIntoViewIfNeeded();
  await page.waitForFunction(() => document.querySelector<HTMLElement>("#review-sentence-1 .review-paragraph")?.innerText.includes("导出校验稿前"));
  assert.equal(await firstParagraph.innerText(), "导出校验稿前的合成修改。");
  await page.getByRole("button", { name: "Export reviewed documents", exact: true }).click();
  await page.getByText("Exported", { exact: true }).waitFor();
  const exported = await (await context.request.get(new URL("/api/review", connection.url).href)).json() as ReviewDocument;
  assert.equal(exported.sentences[0].text, "导出校验稿前的合成修改。");
  assert.equal(exported.delivery?.status, "COMPLETE");
  for (const file of Object.values(exported.delivery?.files ?? {})) {
    assert.equal(path.dirname(file.path!), path.join(workspace, "review_exports"));
    assert.ok((await fs.stat(file.path!)).size > 0);
    assert.equal((await page.locator("body").innerText()).includes(file.path!), false);
  }

  let allowSaveFailure!: () => void;
  const saveFailureGate = new Promise<void>(resolve => { allowSaveFailure = resolve; });
  t.after(() => allowSaveFailure());
  await page.route("**/api/review/save", async route => {
    await saveFailureGate;
    await route.fulfill({ status: 503, contentType: "application/json",
      body: JSON.stringify({ ok: false, error: { zh: "合成保存故障，输入保留。", en: "Synthetic save failure; input preserved." } }) });
  });
  await firstParagraph.click(); await first.fill("失败后保留且导出已过期。");
  await page.locator("#page-title").click();
  await page.getByText("Saving…", { exact: true }).waitFor();
  allowSaveFailure();
  await page.getByText("Synthetic save failure; input preserved.", { exact: true }).waitFor();
  assert.equal(await firstParagraph.innerText(), "失败后保留且导出已过期。");
  assert.equal(await page.locator(".el-alert").count(), 1);
  assert.equal(await page.getByText("Saved · not exported", { exact: true }).count(), 0);
  await page.unroute("**/api/review/save");
  const retried = page.waitForResponse(response => new URL(response.url()).pathname === "/api/review/save");
  await page.getByRole("button", { name: "Retry saving", exact: true }).click(); await retried;
  await page.reload();
  await firstParagraph.waitFor();
  assert.equal(await firstParagraph.innerText(), "失败后保留且导出已过期。");
  assert.equal(await firstRow.locator(".review-speaker-label").innerText(), "Synthetic host");
  await page.getByText("Saved · not exported", { exact: true }).waitFor();
  assert.equal(await page.locator(".el-alert").count(), 0);
  await page.locator("#review-sentence-1000").scrollIntoViewIfNeeded();
  // content-visibility在进入视口后才完成正文布局，等待实际可读文本而非仅检查DOM内容。
  await page.waitForFunction(() => document.querySelector<HTMLElement>("#review-sentence-1000 .review-paragraph")?.innerText.includes("第1000句"));
  const lastParagraph = (await page.locator("#review-sentence-1000 .review-paragraph").boundingBox())!;
  const readingViewport = (await page.locator(".review-reading-list").boundingBox())!;
  assert.ok(lastParagraph.y >= readingViewport.y && lastParagraph.y + lastParagraph.height <= readingViewport.y + readingViewport.height + 1);
  await page.screenshot({ path: path.join(workspace, "review-reading-long-list.png"), animations: "disabled" });

  await page.route("**/api/review", async route => {
    const response = await route.fetch(); const document = await response.json() as ReviewDocument;
    document.audio = { available: false, name: "missing.wav", kind: null, error: { zh: "合成录音缺失。", en: "Synthetic recording missing." } };
    await route.fulfill({ json: document });
  });
  await page.reload();
  await page.getByText("Synthetic recording missing.", { exact: true }).waitFor();
  assert.equal(await page.locator(".el-alert").count(), 1);
  assert.equal(await page.locator("audio").count(), 0);
  assert.equal(await page.getByRole("button", { name: "Select recording again", exact: true }).count(), 1);
  await page.route("**/api/review/select-audio", route => route.fulfill({ status: 422, contentType: "application/json",
    body: JSON.stringify({ ok: false, error: { zh: "合成录音不匹配。", en: "Synthetic recording does not match." } }) }));
  await page.getByRole("button", { name: "Select recording again", exact: true }).click();
  await page.getByText("Synthetic recording does not match.", { exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Select recording again", exact: true }).isEnabled(), true);
  await page.unroute("**/api/review/select-audio");
  await page.screenshot({ path: path.join(workspace, "review-audio-missing.png"), animations: "disabled" });
  await page.unroute("**/api/review");
  assert.deepEqual(failures, []);
  await page.close();
  assert.equal(await fixture.waitForExit(15_000), true, "最后页面关闭后服务应在10秒宽限期结束退出");

  const reopened = await startReviewFixture(t, async () => { await browser?.close(); }, { workspace, job_id: connection.job_id });
  const restored = await context.newPage();
  await restored.goto(reopened.connection.url);
  const restoredText = restored.locator("#review-sentence-1 .review-paragraph");
  await restoredText.waitFor();
  assert.equal(await restoredText.innerText(), "失败后保留且导出已过期。");
  assert.equal(await restored.locator("#review-sentence-1 .review-speaker-label").innerText(), "Synthetic host");
  await restored.close();
  assert.equal(await reopened.waitForExit(15_000), true);
});


test("Edge说话人名称弹窗限高滚动，新增定位且短窗口保留底部操作", { timeout: 90_000 }, async t => {
  let browser: Browser | undefined;
  const fixture = await startReviewFixture(t, async () => { await browser?.close(); });
  browser = await chromium.launch({ channel: "msedge", headless: true });
  const context = await browser.newContext({ locale: "zh-CN", viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const failures: string[] = [];
  page.on("pageerror", error => failures.push(error.message));
  await page.goto(fixture.connection.url);
  await page.getByRole("button", { name: "说话人名称", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const add = dialog.getByRole("button", { name: "新增说话人", exact: true });
  const done = dialog.getByRole("button", { name: "完成", exact: true });
  for (let index = 0; index < 18; index += 1) await add.click();
  await page.waitForFunction(() => document.querySelector(".review-speaker-list label:last-child input") === document.activeElement);
  assert.equal(await dialog.locator(".review-speaker-list input").count(), 21);
  const scroll = dialog.locator(".review-speaker-scroll .el-scrollbar__wrap");
  const dimensions = await scroll.evaluate(element => ({ height: element.clientHeight, content: element.scrollHeight, top: element.scrollTop }));
  assert.ok(dimensions.content > dimensions.height && dimensions.height <= 360 && dimensions.top > 0);
  const lastInput = dialog.locator(".review-speaker-list input").last();
  const lastBox = (await lastInput.boundingBox())!;
  const scrollBox = (await scroll.boundingBox())!;
  assert.ok(lastBox.y >= scrollBox.y && lastBox.y + lastBox.height <= scrollBox.y + scrollBox.height + 1);
  const footerBefore = (await dialog.locator(".el-dialog__footer").boundingBox())!;
  await scroll.evaluate(element => { element.scrollTop = 0; });
  const footerAfter = (await dialog.locator(".el-dialog__footer").boundingBox())!;
  assert.equal(footerAfter.y, footerBefore.y, "列表滚动不能移动底部操作");
  await page.screenshot({ path: path.join(fixture.workspace, "review-speakers-scroll-900.png"), animations: "disabled" });

  await page.setViewportSize({ width: 900, height: 500 });
  await page.waitForFunction(() => {
    const wrap = document.querySelector<HTMLElement>(".review-speaker-scroll .el-scrollbar__wrap");
    const footer = document.querySelector(".el-dialog__footer")?.getBoundingClientRect();
    return wrap && wrap.clientHeight <= 250 && footer && footer.bottom <= innerHeight;
  });
  await add.click();
  await page.waitForFunction(() => document.querySelector(".review-speaker-list label:last-child input") === document.activeElement);
  const shortLastBox = (await lastInput.boundingBox())!;
  const shortScrollBox = (await scroll.boundingBox())!;
  assert.ok(shortLastBox.y >= shortScrollBox.y && shortLastBox.y + shortLastBox.height <= shortScrollBox.y + shortScrollBox.height + 1);
  const addBox = (await add.boundingBox())!, doneBox = (await done.boundingBox())!;
  assert.ok(addBox.y >= 0 && addBox.y + addBox.height <= 500 && doneBox.y + doneBox.height <= 500);
  await lastInput.fill("合成说话人末行");
  await page.screenshot({ path: path.join(fixture.workspace, "review-speakers-scroll-500.png"), animations: "disabled" });
  await done.click();
  await dialog.waitFor({ state: "hidden" });
  await page.getByText("已保存", { exact: true }).waitFor();
  await page.reload();
  await page.getByRole("button", { name: "说话人名称", exact: true }).click();
  assert.equal(await dialog.locator(".review-speaker-list input").count(), 22);
  assert.equal(await dialog.locator(".review-speaker-list input").last().inputValue(), "合成说话人末行");
  assert.deepEqual(failures, []);
  await page.close();
  assert.equal(await fixture.waitForExit(15_000), true);
});
