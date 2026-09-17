import io
import json

import fitz
from PIL import Image
from pypdf import PdfReader


def test_redaction_removes_selected_form_values(client,pdf):
    with fitz.open(stream=pdf,filetype="pdf") as doc:
        widget=fitz.Widget();widget.field_name="Secret";widget.field_type=fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect=fitz.Rect(40,180,300,210);widget.field_value="PRIVATE VALUE";widget.text_fontsize=12
        doc[0].add_widget(widget);content=doc.tobytes()
    operations=[{"type":"redact","page":1,"x":.05,"y":.25,"w":.9,"h":.15}]
    response=client.post("/api/redact",files={"file":("form.pdf",content,"application/pdf")},data={"operations":json.dumps(operations)})
    assert response.status_code==200
    assert "Secret" not in (PdfReader(io.BytesIO(response.content)).get_fields() or {})


def test_edit_image_and_rectangle(client,pdf):
    import base64
    stream=io.BytesIO();Image.new("RGB",(100,100),"red").save(stream,"PNG")
    operations=[{"type":"image","page":2,"x":.1,"y":.2,"w":.4,"h":.4,"image":base64.b64encode(stream.getvalue()).decode()},
                {"type":"rectangle","page":1,"x":.1,"y":.4,"w":.4,"h":.2,"color":"#ff0000"}]
    response=client.post("/api/edit",files={"file":("a.pdf",pdf,"application/pdf")},data={"operations":json.dumps(operations)})
    assert response.status_code==200
    with fitz.open(stream=response.content,filetype="pdf") as doc:
        assert len(doc[1].get_images())==1
        assert len(doc[0].get_drawings())>0


def test_protect_preserves_form_fields(client,pdf):
    with fitz.open(stream=pdf,filetype="pdf") as doc:
        widget=fitz.Widget();widget.field_name="Name";widget.field_type=fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect=fitz.Rect(40,180,300,210);widget.field_value="Pedro";widget.text_fontsize=12
        doc[0].add_widget(widget);content=doc.tobytes()
    protected=client.post("/api/protect",files={"file":("form.pdf",content,"application/pdf")},data={"password":"secret"})
    assert protected.status_code==200
    reader=PdfReader(io.BytesIO(protected.content));reader.decrypt("secret")
    assert reader.get_fields()["Name"]["/V"]=="Pedro"
