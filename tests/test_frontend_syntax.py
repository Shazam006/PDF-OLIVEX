from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def test_frontend_javascript_syntax():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, flags=re.I | re.S)
    assert scripts, "Nenhum bloco JavaScript encontrado no frontend"
    node = shutil.which("node")
    assert node, "Node.js é necessário para validar o JavaScript do frontend"
    with tempfile.TemporaryDirectory() as tmp:
        for index, script in enumerate(scripts):
            if not script.strip():
                continue
            path = Path(tmp) / f"frontend_{index}.js"
            path.write_text(script, encoding="utf-8")
            result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
            assert result.returncode == 0, f"Erro de sintaxe em {path.name}:\n{result.stderr}"


def test_frontend_buttons_have_callable_handlers():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    handlers = set(re.findall(r"onclick=[\"'](?:await\s+)?([A-Za-z_$][\w$]*)\s*\(", html, re.I))
    js_functions = set(re.findall(r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", html))
    missing = sorted(h for h in handlers if h not in js_functions and h not in {"switchTab"})
    assert not missing, f"Handlers onclick sem função correspondente: {missing}"


def test_frontend_organizer_and_compression_controls_exist():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    required = [
        "moveSelected(-1)", "moveSelected(1)", "undoOrg()", "redoOrg()",
        "duplicateSel()", "deleteSel()", "rotateSel()", "saveOrg()",
        "targetMB", "compressPdf()"
    ]
    for marker in required:
        assert marker in html, f"Controle ausente: {marker}"
    assert "draggable" in html, "Organizador sem suporte declarado a arraste"
