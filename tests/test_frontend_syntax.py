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
