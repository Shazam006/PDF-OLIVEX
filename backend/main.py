from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader, PdfWriter
import fitz
import img2pdf
import os, uuid, shutil, tempfile, subprocess, zipfile, glob, json, mimetypes

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORK = os.path.join(BASE, "work")
FRONT = os.path.join(BASE, "frontend")
os.makedirs(WORK, exist_ok=True)

def tool_path(names):
    for name in names:
        p = shutil.which(name)
        if p:
            return p
    return None

def system_capabilities():
    return {
        "libreoffice": bool(tool_path(["soffice", "libreoffice"])),
        "tesseract": bool(tool_path(["tesseract"])),
        "ocrmypdf": bool(tool_path(["ocrmypdf"])),
        "ghostscript": bool(tool_path(["gswin64c", "gs"])),
        "verapdf": bool(tool_path(["verapdf"])),
    }


app = FastAPI(title="PDF OLIVEX", version="4.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=os.path.join(FRONT, "assets")), name="assets")

@app.get("/", response_class=HTMLResponse)
def home():
    with open(os.path.join(FRONT, "index.html"), encoding="utf-8") as f:
        return f.read()

def save_upload(upload: UploadFile):
    ext = os.path.splitext(upload.filename or "")[1].lower()
    path = os.path.join(WORK, uuid.uuid4().hex + ext)
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path

def out(ext=".pdf"):
    return os.path.join(WORK, uuid.uuid4().hex + ext)

def download(path, filename, media):
    return FileResponse(path, filename=filename, media_type=media)

def parse_pages(expr, total):
    result = []
    for part in expr.split(","):
        part = part.strip()
        if not part: continue
        if "-" in part:
            a,b = map(int, part.split("-",1))
            if a > b: a,b = b,a
            result.extend(range(a,b+1))
        else:
            result.append(int(part))
    if any(n < 1 or n > total for n in result):
        raise ValueError
    return result

@app.get("/api/health")
def health():
    return {"status":"ok","version":"4.2","local":True}

@app.post("/api/system/cleanup")
def cleanup():
    removed=0
    for name in os.listdir(WORK):
        path=os.path.join(WORK,name)
        try:
            if os.path.isfile(path):
                os.remove(path); removed += 1
        except OSError:
            pass
    return {"removed":removed}

@app.get("/api/system/capabilities")
def capabilities():
    return system_capabilities()

@app.post("/api/merge")
async def merge(files: list[UploadFile] = File(...)):
    if len(files) < 2: raise HTTPException(400,"Envie pelo menos 2 PDFs.")
    writer=PdfWriter()
    for f in files:
        r=PdfReader(save_upload(f))
        for p in r.pages: writer.add_page(p)
    path=out()
    with open(path,"wb") as h: writer.write(h)
    return download(path,"pdf_unificado.pdf","application/pdf")

@app.post("/api/organize")
async def organize(file: UploadFile=File(...), order:str=Form(...), rotations:str=Form("")):
    r=PdfReader(save_upload(file))
    nums=[int(x) for x in order.split(",") if x.strip()]
    if sorted(nums)!=list(range(1,len(r.pages)+1)):
        raise HTTPException(400,"A ordem deve conter todas as páginas uma única vez.")
    rots={}
    if rotations:
        for pair in rotations.split(","):
            if ":" in pair:
                n,d=pair.split(":",1); rots[int(n)]=int(d)%360
    w=PdfWriter()
    for n in nums:
        p=r.pages[n-1]
        if rots.get(n,0): p.rotate(rots[n])
        w.add_page(p)
    path=out()
    with open(path,"wb") as h:w.write(h)
    return download(path,"pdf_organizado.pdf","application/pdf")

@app.post("/api/organize-multi")
async def organize_multi(files: list[UploadFile]=File(...), order: str=Form(...), rotations: str=Form("")):
    if not files:
        raise HTTPException(400, "Envie pelo menos um PDF.")
    try:
        import json
        order_data=json.loads(order)
    except Exception:
        raise HTTPException(400, "Ordem de páginas inválida.")
    if not isinstance(order_data,list) or not order_data:
        raise HTTPException(400, "A organização não contém páginas.")
    paths=[save_upload(f) for f in files]
    try:
        readers=[PdfReader(path) for path in paths]
        for item in order_data:
            fi=int(item["fileIndex"]); pg=int(item["page"])
            if fi<0 or fi>=len(readers) or pg<1 or pg>len(readers[fi].pages):
                raise ValueError
        rots={}
        if rotations:
            try:
                for item in json.loads(rotations):
                    rots[(int(item["fileIndex"]),int(item["page"]))]=int(item["rotation"])%360
            except Exception:
                raise HTTPException(400,"Rotações inválidas.")
        w=PdfWriter()
        for item in order_data:
            fi=int(item["fileIndex"]);pg=int(item["page"])
            page=readers[fi].pages[pg-1];rot=rots.get((fi,pg),0)
            if rot: page.rotate(rot)
            w.add_page(page)
        path=out()
        with open(path,"wb") as h:w.write(h)
        return download(path,"pdf_organizado.pdf","application/pdf")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400,"Não foi possível montar o PDF com a ordem informada.")
    finally:
        for path in paths:
            try: os.remove(path)
            except OSError: pass

@app.post("/api/split")
async def split(file:UploadFile=File(...), pages:str=Form(...)):
    r=PdfReader(save_upload(file)); nums=parse_pages(pages,len(r.pages))
    w=PdfWriter()
    for n in nums:w.add_page(r.pages[n-1])
    path=out()
    with open(path,"wb") as h:w.write(h)
    return download(path,"paginas_extraidas.pdf","application/pdf")

@app.post("/api/remove-pages")
async def remove_pages(file:UploadFile=File(...), pages:str=Form(...)):
    r=PdfReader(save_upload(file)); rem=set(parse_pages(pages,len(r.pages)))
    if len(rem)>=len(r.pages): raise HTTPException(400,"Não é possível remover todas as páginas.")
    w=PdfWriter()
    for i,p in enumerate(r.pages,1):
        if i not in rem:w.add_page(p)
    path=out()
    with open(path,"wb") as h:w.write(h)
    return download(path,"pdf_sem_paginas.pdf","application/pdf")

@app.post("/api/rotate")
async def rotate(file:UploadFile=File(...), degrees:int=Form(90)):
    if degrees%90: raise HTTPException(400,"Use múltiplos de 90 graus.")
    r=PdfReader(save_upload(file)); w=PdfWriter()
    for p in r.pages:p.rotate(degrees%360);w.add_page(p)
    path=out()
    with open(path,"wb") as h:w.write(h)
    return download(path,"pdf_rotacionado.pdf","application/pdf")

@app.post("/api/images-to-pdf")
async def images_to_pdf(files:list[UploadFile]=File(...)):
    paths=[save_upload(f) for f in files]
    try:
        path=out()
        with open(path,"wb") as h:h.write(img2pdf.convert(paths))
        return download(path,"imagens.pdf","application/pdf")
    except Exception as e: raise HTTPException(400,f"Falha na conversão: {e}")

@app.post("/api/pdf-to-images")
async def pdf_to_images(file:UploadFile=File(...), fmt:str=Form("png"), dpi:int=150):
    doc=fitz.open(save_upload(file)); td=tempfile.mkdtemp(dir=WORK)
    ext="jpg" if fmt.lower()=="jpg" else "png"
    for i,p in enumerate(doc,1):
        pix=p.get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),alpha=False)
        pix.save(os.path.join(td,f"pagina_{i:03d}.{ext}"))
    archive=out(".zip")[:-4]
    shutil.make_archive(archive,"zip",td)
    return download(archive+".zip","pdf_para_imagens.zip","application/zip")

@app.post("/api/compress")
async def compress(file:UploadFile=File(...), level:str=Form("balanced")):
    src=save_upload(file)
    try:
        doc=fitz.open(src)
        path=out()
        # Conservative defaults preserve technical drawings and scans.
        # Higher compression profiles use controlled image re-encoding.
        if level == "maximum":
            # Rasterize pages at a moderate DPI only when necessary; this is
            # intentionally opt-in because it can degrade vector drawings.
            newdoc=fitz.open()
            for p in doc:
                pix=p.get_pixmap(matrix=fitz.Matrix(1.35,1.35), alpha=False)
                img=fitz.Pixmap(fitz.csRGB, pix)
                rect=p.rect
                np=newdoc.new_page(width=rect.width, height=rect.height)
                np.insert_image(rect, pixmap=img, keep_proportion=False)
            newdoc.save(path, garbage=4, deflate=True, clean=True)
            newdoc.close()
        else:
            doc.save(path, garbage=4, deflate=True, clean=True)
        doc.close()
        # Validate output.
        check=fitz.open(path); check.close()
        return download(path,"pdf_comprimido.pdf","application/pdf")
    except Exception as e:
        raise HTTPException(400,f"Não foi possível comprimir o PDF: {e}")

@app.post("/api/watermark")
async def watermark(file:UploadFile=File(...), text:str=Form(...)):
    doc=fitz.open(save_upload(file))
    for p in doc:
        r=p.rect
        p.insert_text((r.width/2-120,r.height/2),text,fontsize=28,rotate=45,
                      color=(0.5,0.5,0.5),fill_opacity=0.25)
    path=out();doc.save(path,garbage=4,deflate=True);doc.close()
    return download(path,"pdf_marca_dagua.pdf","application/pdf")

@app.post("/api/protect")
async def protect(file:UploadFile=File(...), password:str=Form(...)):
    r=PdfReader(save_upload(file));w=PdfWriter()
    for p in r.pages:w.add_page(p)
    w.encrypt(password);path=out()
    with open(path,"wb") as h:w.write(h)
    return download(path,"pdf_protegido.pdf","application/pdf")

@app.post("/api/unlock")
async def unlock(file:UploadFile=File(...), password:str=Form("")):
    path=save_upload(file);r=PdfReader(path)
    if r.is_encrypted:
        if not r.decrypt(password): raise HTTPException(400,"Senha incorreta.")
    w=PdfWriter()
    for p in r.pages:w.add_page(p)
    path2=out()
    with open(path2,"wb") as h:w.write(h)
    return download(path2,"pdf_desbloqueado.pdf","application/pdf")

@app.post("/api/add-page-numbers")
async def add_page_numbers(file:UploadFile=File(...), start:int=Form(1)):
    doc=fitz.open(save_upload(file))
    for i,p in enumerate(doc):
        r=p.rect
        p.insert_text((r.width/2-10,r.height-25),str(start+i),fontsize=10,color=(0,0,0))
    path=out();doc.save(path);doc.close()
    return download(path,"pdf_numerado.pdf","application/pdf")

@app.post("/api/crop")
async def crop(file:UploadFile=File(...), margin:float=Form(20)):
    doc=fitz.open(save_upload(file))
    for p in doc:
        r=p.rect
        p.set_cropbox(fitz.Rect(r.x0+margin,r.y0+margin,r.x1-margin,r.y1-margin))
    path=out();doc.save(path);doc.close()
    return download(path,"pdf_recortado.pdf","application/pdf")

@app.post("/api/repair")
async def repair(file:UploadFile=File(...)):
    path=save_upload(file)
    try:
        doc=fitz.open(path);new=out();doc.save(new,garbage=4,deflate=True,clean=True);doc.close()
        return download(new,"pdf_reparado.pdf","application/pdf")
    except Exception as e: raise HTTPException(400,f"Não foi possível reparar: {e}")

@app.post("/api/ocr")
async def ocr(file:UploadFile=File(...), language:str=Form("por")):
    inp=save_upload(file); output=out()
    exe=tool_path(["ocrmypdf"])
    if not exe:
        raise HTTPException(501,"OCR não instalado. Instale OCRmyPDF e Tesseract no Windows para habilitar esta função.")
    p=subprocess.run([exe,"--deskew","--rotate-pages","-l",language,inp,output],capture_output=True,text=True)
    if p.returncode!=0: raise HTTPException(500,p.stderr[-1500:])
    return download(output,"pdf_ocr.pdf","application/pdf")

@app.post("/api/scan-to-pdf")
async def scan_to_pdf(files:list[UploadFile]=File(...), run_ocr:bool=Form(False), language:str=Form("por")):
    if not files:
        raise HTTPException(400,"Envie pelo menos uma imagem.")
    images=[save_upload(f) for f in files]
    pdf_path=out()
    try:
        with open(pdf_path,"wb") as h:
            h.write(img2pdf.convert(images))
    except Exception as e:
        raise HTTPException(400,f"Não foi possível criar o PDF: {e}")
    if not run_ocr:
        return download(pdf_path,"digitalizacao.pdf","application/pdf")
    exe=tool_path(["ocrmypdf"])
    if not exe or not tool_path(["tesseract"]):
        return download(pdf_path,"digitalizacao.pdf","application/pdf")
    ocr_path=out()
    p=subprocess.run([exe,"--deskew","--rotate-pages","-l",language,pdf_path,ocr_path],
                     capture_output=True,text=True)
    if p.returncode==0:
        return download(ocr_path,"digitalizacao_ocr.pdf","application/pdf")
    return download(pdf_path,"digitalizacao.pdf","application/pdf")

@app.post("/api/office-to-pdf")
async def office_to_pdf(file:UploadFile=File(...)):
    inp=save_upload(file); outdir=tempfile.mkdtemp(dir=WORK)
    exe=shutil.which("soffice") or shutil.which("libreoffice")
    if not exe: raise HTTPException(501,"LibreOffice não está instalado.")
    p=subprocess.run([exe,"--headless","--convert-to","pdf","--outdir",outdir,inp],capture_output=True,text=True)
    pdfs=glob.glob(os.path.join(outdir,"*.pdf"))
    if p.returncode!=0 or not pdfs: raise HTTPException(500,p.stderr[-1500:] or "Conversão falhou.")
    return download(pdfs[0],"convertido.pdf","application/pdf")

@app.post("/api/html-to-pdf")
async def html_to_pdf(file:UploadFile=File(...)):
    raise HTTPException(501,"HTML → PDF será habilitado com um motor Chromium local na próxima etapa.")

@app.post("/api/pdf-a")
async def pdf_a(file:UploadFile=File(...)):
    raise HTTPException(501,"PDF/A requer um conversor/validador PDF/A instalado. A interface já está preparada.")

@app.post("/api/sign")
async def sign(file:UploadFile=File(...)):
    raise HTTPException(501,"Assinatura digital ainda requer configuração de certificado e política de assinatura.")

@app.post("/api/redact")
async def redact(file:UploadFile=File(...)):
    raise HTTPException(501,"Ocultar informações exige seleção visual das áreas. O editor será implementado na etapa de edição visual.")

@app.post("/api/compare")
async def compare(file1:UploadFile=File(...), file2:UploadFile=File(...)):
    raise HTTPException(501,"Comparação visual será implementada no editor avançado.")

@app.post("/api/forms")
async def forms(file:UploadFile=File(...)):
    raise HTTPException(501,"Editor de formulários será implementado no módulo avançado.")

@app.post("/api/edit")
async def edit(file:UploadFile=File(...)):
    raise HTTPException(501,"Editor visual será implementado no próximo módulo.")

@app.post("/api/pdf-to-office")
async def pdf_to_office(file:UploadFile=File(...), target:str=Form("docx")):
    raise HTTPException(501,"PDF → Word/Excel/PowerPoint exige conversor específico. O módulo será implementado separadamente.")
