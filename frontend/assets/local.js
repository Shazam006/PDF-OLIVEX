export const LOCAL_TOOLS = new Set(['merge', 'split', 'remove', 'rotate', 'compress', 'repair', 'scan', 'images', 'pimg', 'nums', 'watermark', 'crop']);

function pages(expression, total, limit) {
  const result = [];
  for (const part of expression.split(',')) {
    const match = part.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);
    if (!match) throw new Error('Páginas inválidas. Confira os números e intervalos.');
    const start = Number(match[1]), end = Number(match[2] || match[1]);
    if (Math.min(start, end) < 1 || Math.max(start, end) > total) throw new Error('Página fora do documento.');
    if (result.length + Math.abs(end - start) + 1 > limit) throw new Error(`Limite de ${limit} páginas.`);
    for (let page = Math.min(start, end); page <= Math.max(start, end); page++) result.push(page - 1);
  }
  return result;
}

function response(bytes, name, headers = {}) {
  return new Response(bytes, {headers: {'Content-Type': name.endsWith('.zip') ? 'application/zip' : 'application/pdf',
    'Content-Disposition': `attachment; filename="${name}"`, ...headers}});
}

export async function runLocal(id, files, values, {maxPages, loadPdf, order = null}) {
  const {PDFDocument, StandardFonts, degrees, rgb} = window.PDFLib;
  const read = async file => {
    let document;
    try {document = await PDFDocument.load(await file.arrayBuffer());}
    catch {throw new Error('PDF inválido ou protegido. Desbloqueie-o no servidor antes de continuar.');}
    if (!document.getPageCount() || document.getPageCount() > maxPages) throw new Error(`Limite de ${maxPages} páginas.`);
    return document;
  };
  const output = await PDFDocument.create();
  if (id === 'organize' || id === 'merge') {
    const documents = await Promise.all(files.map(read));
    const sequence = order || documents.flatMap((doc, fileIndex) => doc.getPageIndices().map(index => ({fileIndex, page: index + 1, rotation: 0})));
    if (!sequence.length || sequence.length > maxPages) throw new Error(`Limite de ${maxPages} páginas.`);
    for (const item of sequence) {
      const [page] = await output.copyPages(documents[item.fileIndex], [item.page - 1]);
      page.setRotation(degrees((page.getRotation().angle + item.rotation) % 360));
      output.addPage(page);
    }
    if (id === 'merge' && files.length < 2) throw new Error('Selecione pelo menos dois PDFs.');
    return response(await output.save(), id === 'merge' ? 'pdf_unificado.pdf' : 'pdf_organizado.pdf');
  }
  if (id === 'images' || id === 'scan') {
    if (values.run_ocr === 'true') throw new Error('OCR exige conexão com o servidor.');
    if (files.length > maxPages) throw new Error(`Limite de ${maxPages} imagens.`);
    for (const file of files) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const png = bytes[0] === 137 && bytes[1] === 80 && bytes[2] === 78 && bytes[3] === 71;
      const jpeg = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
      if (!png && !jpeg) throw new Error('No modo local, selecione imagens PNG ou JPG.');
      const image = await (png ? output.embedPng(bytes) : output.embedJpg(bytes));
      if (image.width * image.height > 25_000_000) throw new Error('Imagem acima do limite de resolução.');
      output.addPage([image.width, image.height]).drawImage(image, {x: 0, y: 0, width: image.width, height: image.height});
    }
    return response(await output.save(), id === 'scan' ? 'digitalizacao.pdf' : 'imagens.pdf');
  }
  if (id === 'pimg') {
    const document = await loadPdf(files[0]), zip = new window.JSZip();
    try {
      if (document.numPages > maxPages) throw new Error(`Limite de ${maxPages} páginas.`);
      for (let index = 1; index <= document.numPages; index++) {
        const page = await document.getPage(index), viewport = page.getViewport({scale: Number(values.dpi || 150) / 72});
        if (viewport.width * viewport.height > 25_000_000) throw new Error('Página acima do limite de resolução. Reduza o DPI.');
        const canvas = window.document.createElement('canvas');
        canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
        await page.render({canvasContext: canvas.getContext('2d'), viewport}).promise;
        const format = values.fmt === 'jpg' ? 'jpg' : 'png';
        const blob = await new Promise(resolve => canvas.toBlob(resolve, format === 'jpg' ? 'image/jpeg' : 'image/png', .9));
        if (!blob) throw new Error('Não foi possível renderizar a página.');
        zip.file(`pagina_${String(index).padStart(3, '0')}.${format}`, await blob.arrayBuffer());
        canvas.width = canvas.height = 0;
      }
      return response(await zip.generateAsync({type: 'uint8array'}), 'pdf_para_imagens.zip');
    } finally {await document.loadingTask.destroy();}
  }
  const document = await read(files[0]);
  if (id === 'split' || id === 'remove') {
    const selected = pages(values.pages, document.getPageCount(), maxPages);
    const sequence = id === 'remove' ? document.getPageIndices().filter(index => !selected.includes(index)) : selected;
    if (!sequence.length) throw new Error('Não é possível remover todas as páginas.');
    if (id === 'split' && values.mode === 'individual') {
      const zip = new window.JSZip();
      for (const [position, index] of sequence.entries()) {
        const single = await PDFDocument.create();
        const [page] = await single.copyPages(document, [index]); single.addPage(page);
        zip.file(`pagina_${index + 1}_${position + 1}.pdf`, await single.save());
      }
      return response(await zip.generateAsync({type: 'uint8array'}), 'paginas_separadas.zip');
    }
    for (const page of await output.copyPages(document, sequence)) output.addPage(page);
    return response(await output.save(), id === 'remove' ? 'pdf_sem_paginas.pdf' : 'paginas_extraidas.pdf');
  }
  if (id === 'rotate') for (const page of document.getPages()) page.setRotation(degrees((page.getRotation().angle + Number(values.degrees || 90)) % 360));
  if (id === 'nums' || id === 'watermark') {
    const font = await document.embedFont(StandardFonts.Helvetica);
    for (const [index, page] of document.getPages().entries()) {
      const {width, height} = page.getSize();
      const text = id === 'nums' ? String(Number(values.start || 0) + index) : values.text.trim();
      if (!text) throw new Error('Informe o texto.');
      const size = id === 'nums' ? 10 : 28;
      page.drawText(text, {font, size, x: id === 'nums' ? (width - font.widthOfTextAtSize(text, size)) / 2 : width * .2,
        y: id === 'nums' ? 18 : height * .35, color: rgb(.4, .4, .4), opacity: id === 'nums' ? 1 : .25,
        rotate: degrees(id === 'nums' ? 0 : 35)});
    }
  }
  if (id === 'crop') for (const page of document.getPages()) {
    const margin = Number(values.margin), box = page.getCropBox();
    if (margin < 0 || margin * 2 >= Math.min(box.width, box.height)) throw new Error('A margem deve deixar uma área visível na página.');
    page.setCropBox(box.x + margin, box.y + margin, box.width - margin * 2, box.height - margin * 2);
  }
  let bytes = await document.save({useObjectStreams: true}), headers = {};
  if (id === 'compress') {
    if (bytes.length > files[0].size) bytes = new Uint8Array(await files[0].arrayBuffer());
    const target = Number(values.target_mb || 0);
    headers = {'X-Original-Bytes': String(files[0].size), 'X-Final-Bytes': String(bytes.length),
      'X-Reduction-Percent': ((1 - bytes.length / files[0].size) * 100).toFixed(1),
      'X-Target-Met': target ? String(bytes.length <= target * 1024 ** 2) : 'not-set'};
  }
  const names = {rotate: 'pdf_girado.pdf', nums: 'pdf_numerado.pdf', watermark: 'pdf_marca_dagua.pdf', crop: 'pdf_recortado.pdf', compress: 'pdf_comprimido.pdf', repair: 'pdf_reparado.pdf'};
  return response(bytes, names[id] || 'resultado.pdf', headers);
}
