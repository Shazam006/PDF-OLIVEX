import base64
import io
import json

import fitz
import pytest
from PIL import Image, ImageDraw


def rotated_pdf(rotation):
    with fitz.open() as doc:
        page=doc.new_page(width=300,height=500)
        page.set_rotation(rotation)
        return doc.tobytes()


@pytest.mark.parametrize("rotation",[90,180,270])
def test_added_text_is_horizontal_in_displayed_page(client,rotation):
    operations=[{"type":"text","page":1,"x":.1,"y":.2,"w":.8,"h":.3,"text":"ADDED TEXT"}]
    response=client.post("/api/edit",files={"file":("rotated.pdf",rotated_pdf(rotation),"application/pdf")},data={"operations":json.dumps(operations)})
    assert response.status_code==200
    with fitz.open(stream=response.content,filetype="pdf") as doc:
        page=doc[0]
        line=page.get_text("dict")["blocks"][0]["lines"][0]
        displayed_direction=fitz.Point(line["dir"])*page.rotation_matrix-fitz.Point(0,0)*page.rotation_matrix
        assert displayed_direction.x==pytest.approx(1)
        assert displayed_direction.y==pytest.approx(0)


@pytest.mark.parametrize("rotation",[90,180,270])
def test_added_image_keeps_its_top_edge_on_rotated_page(client,rotation):
    image=Image.new("RGB",(100,100),"red")
    ImageDraw.Draw(image).rectangle((0,50,99,99),fill="green")
    encoded=io.BytesIO();image.save(encoded,"PNG")
    operations=[{"type":"image","page":1,"x":.1,"y":.1,"w":.6,"h":.6,"image":base64.b64encode(encoded.getvalue()).decode()}]
    response=client.post("/api/edit",files={"file":("rotated.pdf",rotated_pdf(rotation),"application/pdf")},data={"operations":json.dumps(operations)})
    assert response.status_code==200
    with fitz.open(stream=response.content,filetype="pdf") as doc:
        pix=doc[0].get_pixmap(alpha=False)
        # The square image is centered in the selection; sample its upper/lower halves.
        center_x=int(pix.width*.4)
        center_y=int(pix.height*.4)
        half_size=min(pix.width*.6,pix.height*.6)/2
        top=pix.pixel(center_x,int(center_y-half_size*.5))
        bottom=pix.pixel(center_x,int(center_y+half_size*.5))
        assert top[0]>200 and top[1]<30
        assert bottom[1]>80 and bottom[0]<30


def test_comparison_aligns_different_page_sizes(client):
    contents=[]
    for width in (1000,420):
        with fitz.open() as doc:
            page=doc.new_page(width=width,height=500)
            page.insert_text((40,60),"SAME CONTENT")
            if width==1000:
                page.insert_text((650,160),"ONLY IN ORIGINAL")
            contents.append(doc.tobytes())
    response=client.post("/api/compare",files={"file1":("first.pdf",contents[0],"application/pdf"),"file2":("second.pdf",contents[1],"application/pdf")})
    assert response.status_code==200
    assert response.headers["x-changed-pages"]=="1"
    with fitz.open(stream=response.content,filetype="pdf") as report:
        dimensions={(image[2],image[3]) for image in report[0].get_images(full=True)}
        assert dimensions=={(1000,500)}
