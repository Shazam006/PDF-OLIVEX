import { chromium } from 'playwright';
import { PDFDocument } from 'pdf-lib';
import fs from 'node:fs/promises';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ acceptDownloads: true });
await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
await page.waitForFunction(() => window.PDFLib && window.pdfjsLib);

const source = await PDFDocument.create();
for (const [w, h] of [[300, 400], [400, 500], [500, 600]]) source.addPage([w, h]);
const sourceBytes = await source.save();

await page.locator('#orgFile').setInputFiles({
  name: 'teste.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from(sourceBytes),
});
await page.getByRole('button', { name: 'Adicionar PDFs' }).click();
await page.locator('.page').nth(2).waitFor();
if (await page.locator('.page').count() !== 3) throw new Error('Organizador não carregou 3 páginas.');

await page.locator('.page').nth(2).dragTo(page.locator('.page').nth(0));
const downloadPromise = page.waitForEvent('download');
await page.getByRole('button', { name: 'Salvar PDF organizado' }).click();
const download = await downloadPromise;
const outputPath = '/tmp/pdf_organizado.pdf';
await download.saveAs(outputPath);
const result = await PDFDocument.load(await fs.readFile(outputPath));
if (result.getPageCount() !== 3) throw new Error('PDF organizado não preservou as 3 páginas.');
const sizes = result.getPages().map(p => [Math.round(p.getWidth()), Math.round(p.getHeight())]);
const expected = [[500, 600], [300, 400], [400, 500]];
if (JSON.stringify(sizes) !== JSON.stringify(expected)) throw new Error(`Ordem incorreta: ${JSON.stringify(sizes)}`);

await page.getByRole('button', { name: 'Otimizar PDF' }).click();
await page.locator('#compress').setInputFiles({
  name: 'teste-compress.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from(sourceBytes),
});
await page.locator('#targetMB').fill('0.1');
const compressDownloadPromise = page.waitForEvent('download');
await page.getByRole('button', { name: 'Comprimir até a meta' }).click();
const compressDownload = await compressDownloadPromise;
const compressedPath = '/tmp/pdf_comprimido.pdf';
await compressDownload.saveAs(compressedPath);
const compressed = await PDFDocument.load(await fs.readFile(compressedPath));
if (compressed.getPageCount() !== 3) throw new Error('Compressão não gerou um PDF válido de 3 páginas.');

await browser.close();
console.log('Browser smoke tests passed.');
