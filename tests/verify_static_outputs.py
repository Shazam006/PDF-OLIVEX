import io
from pathlib import Path
import sys
import zipfile

import fitz
from PIL import Image

folder = Path(sys.argv[1])
with fitz.open(folder / "organized.pdf") as document:
    assert len(document) == 6
    assert "B PAGE 2" in document[0].get_text()
    assert [page.rotation for page in document] == [0, 90, 90, 0, 0, 0]
with fitz.open(folder / "split.pdf") as document:
    assert "A PAGE 3" in document[0].get_text()
    assert "A PAGE 1" in document[1].get_text()
with fitz.open(folder / "compressed.pdf") as document:
    for number, page in enumerate(document, 1):
        assert f"A PAGE {number}" in page.get_text()
        assert page.get_drawings(), "Local compression must preserve vectors"
with fitz.open(folder / "watermark.pdf") as document:
    assert "LOCAL WATERMARK" in document[0].get_text()
with fitz.open(folder / "numbered.pdf") as document:
    assert "7" in document[0].get_text()
with zipfile.ZipFile(folder / "images.zip") as archive:
    assert len(archive.namelist()) == 3
    for name in archive.namelist():
        with Image.open(io.BytesIO(archive.read(name))) as image:
            assert image.convert("L").getextrema()[0] < 200, "Image export must contain visible page content"
print("Static PDF contents, drag order, rotations, live text, vectors and nonblank image exports verified")
