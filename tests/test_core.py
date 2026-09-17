import os
from pathlib import Path
import fitz
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.main import app

client=TestClient(app)

def make_pdf(path, pages=2):
    doc=fitz.open()
    for i in range(pages):
        p=doc.new_page()
        p.insert_text((72,72), f"Página {i+1}")
    doc.save(path)
    doc.close()

def test_health():
    r=client.get("/api/health")
    assert r.status_code==200
    assert r.json()["local"] is True

def test_capabilities():
    r=client.get("/api/system/capabilities")
    assert r.status_code==200
    assert "libreoffice" in r.json()

def test_merge(tmp_path):
    a=tmp_path/"a.pdf"; b=tmp_path/"b.pdf"
    make_pdf(a,2); make_pdf(b,1)
    with open(a,"rb") as fa, open(b,"rb") as fb:
        r=client.post("/api/merge",files=[
            ("files",("a.pdf",fa,"application/pdf")),
            ("files",("b.pdf",fb,"application/pdf")),
        ])
    assert r.status_code==200
    doc=fitz.open(stream=r.content,filetype="pdf")
    assert doc.page_count==3
    doc.close()
