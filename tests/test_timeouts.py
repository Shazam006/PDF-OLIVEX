def test_word_worker_timeout_cleans_job(client,pdf,monkeypatch):
    from backend import runtime
    monkeypatch.setattr(runtime,"TOOL_TIMEOUT",.001)
    response=client.post("/api/pdf-to-office",files={"file":("a.pdf",pdf,"application/pdf")},data={"target":"docx"})
    assert response.status_code==504
    assert "tempo" in response.json()["detail"]
