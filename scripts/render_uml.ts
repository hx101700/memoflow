import { readFile, readdir } from "node:fs/promises";
import { createRequire } from "node:module";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, type Browser } from "playwright";
import type { Mermaid, MermaidConfig } from "mermaid";

declare const mermaid: Mermaid;

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const directory = path.join(root, "doc/uml");
const require = createRequire(import.meta.url);

// 渲染一份图稿，确认文字没有越过画布后保存同名PNG。
async function renderDiagram(browser: Browser, name: string, renderer: string, theme: MermaidConfig) {
  const source = await readFile(path.join(directory, `${name}.mmd`), "utf8");
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1.5 });
  try {
    await page.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:white"><main></main></body></html>');
    await page.addScriptTag({ path: renderer });
    await page.evaluate(async ({ source, name, theme }) => {
      mermaid.initialize(theme);
      const { svg } = await mermaid.render(`uml-${name}`, source);
      document.querySelector("main")!.innerHTML = svg;
      await document.fonts.ready;
      const element = document.querySelector<SVGSVGElement>("main > svg")!;
      const box = element.viewBox.baseVal;
      element.style.maxWidth = "none";
      element.style.width = `${Math.ceil(box.width)}px`;
      element.style.height = `${Math.ceil(box.height)}px`;
    }, { source, name, theme });
    const report = await page.evaluate(() => {
      const svg = document.querySelector<SVGSVGElement>("main > svg")!;
      const box = svg.getBoundingClientRect();
      const texts = [...svg.querySelectorAll("text, foreignObject")];
      // 浏览器的亚像素取整允许1px误差；实际越界文字阻止写入PNG。
      const outside = texts.filter(text => {
        const bounds = text.getBoundingClientRect();
        return bounds.left < box.left - 1 || bounds.top < box.top - 1
          || bounds.right > box.right + 1 || bounds.bottom > box.bottom + 1;
      }).map(text => text.textContent);
      return { textNodes: texts.length, outside };
    });
    if (report.outside.length) throw new Error(`${name}文字越界：${JSON.stringify(report.outside)}`);
    const png = await page.locator("main > svg").screenshot({ path: path.join(directory, `${name}.png`) });
    // PNG的IHDR头记录实际像素宽高，包含本次截图的像素密度。
    return { diagram: name, width: png.readUInt32BE(16), height: png.readUInt32BE(20), textNodes: report.textNodes };
  } finally {
    await page.close();
  }
}

// 读取唯一共享主题，使用锁定依赖与本机Edge渲染全部或指定图稿。
async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.length === 1 && args[0] === "--help") {
    console.log("npm run render:uml -- [图名 ...]；省略图名时渲染doc/uml中的全部.mmd。示例：02-install 07-state");
    return;
  }
  const available = (await readdir(directory)).filter(name => name.endsWith(".mmd")).map(name => name.slice(0, -4)).sort();
  const selected = args.length ? [...new Set(args.map(name => name.replace(/\.mmd$/, "")))] : available;
  for (const name of selected) {
    if (!available.includes(name)) throw new Error(`未知图名：${name}。可用图名：${available.join(", ")}`);
  }
  const theme = JSON.parse(await readFile(path.join(directory, "theme.json"), "utf8")) as MermaidConfig;
  if (!theme.theme || !theme.themeVariables || !theme.fontFamily) {
    throw new Error("doc/uml/theme.json缺少主题、配色或字体配置；停止渲染。");
  }
  const renderer = require.resolve("mermaid/dist/mermaid.min.js");
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  try {
    for (const name of selected) console.log(JSON.stringify(await renderDiagram(browser, name, renderer, theme)));
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error("UML渲染失败：", error);
  process.exitCode = 1;
});
