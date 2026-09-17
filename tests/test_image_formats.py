import io
import base64
import json

import fitz
import pytest
from PIL import Image


@pytest.mark.parametrize("fmt,ext,mime",[("JPEG","jpg","image/jpeg"),("PNG","png","image/png"),("TIFF","tiff","image/tiff"),("WEBP","webp","image/webp")])
def test_preserved_image_formats(client,fmt,ext,mime):
    stream=io.BytesIO();Image.new("RGB",(100,150),"green").save(stream,fmt)
    response=client.post("/api/images-to-pdf",files={"files":("image."+ext,stream.getvalue(),mime)})
    assert response.status_code==200,response.text[:1000] if response.status_code!=200 else ""
    with fitz.open(stream=response.content,filetype="pdf") as doc:
        assert len(doc)==1


def test_image_magic_must_match_extension(client):
    stream=io.BytesIO();Image.new("RGB",(100,150),"green").save(stream,"JPEG")
    response=client.post("/api/images-to-pdf",files={"files":("image.png",stream.getvalue(),"image/png")})
    assert response.status_code==400


@pytest.mark.parametrize("tool", ["images-to-pdf", "edit"])
def test_image_pixel_limit_is_enforced_before_processing(client, pdf, monkeypatch, tool):
    stream = io.BytesIO()
    Image.new("RGB", (11, 10), "green").save(stream, "PNG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    if tool == "images-to-pdf":
        response = client.post("/api/images-to-pdf", files={"files": ("image.png", stream.getvalue(), "image/png")})
    else:
        operation = {"type": "image", "page": 1, "x": .1, "y": .1, "w": .5, "h": .5,
                     "image": base64.b64encode(stream.getvalue()).decode()}
        response = client.post("/api/edit", files={"file": ("a.pdf", pdf, "application/pdf")},
                               data={"operations": json.dumps([operation])})
    assert response.status_code == 400
