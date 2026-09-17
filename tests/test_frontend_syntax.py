from html.parser import HTMLParser
from pathlib import Path
import os
import shutil
import subprocess
import pytest


class Sources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.handlers = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "script" and "src" in data:
            self.scripts.append(data["src"])
        self.handlers.extend(key for key in data if key.startswith("on"))


def test_frontend_javascript_syntax():
    root = Path("frontend")
    parsed = Sources()
    parsed.feed((root / "index.html").read_text(encoding="utf-8"))
    assert parsed.scripts
    node = os.environ.get("NODE_BINARY") or shutil.which("node")
    if not node:
        pytest.skip("Node.js syntax validation runs in the dedicated CI job")
    sources = [root / source for source in parsed.scripts]
    sources.append(root / "assets/local.js")
    for path in sources:
        assert path.is_file(), f"Missing local asset: {path}"
        result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_frontend_uses_local_assets_without_inline_handlers():
    parsed = Sources()
    parsed.feed(Path("frontend/index.html").read_text(encoding="utf-8"))
    assert not parsed.handlers
    assert all(not source.startswith(("http:", "https:", "//")) for source in parsed.scripts)


def test_frontend_organizer_controls_are_preserved():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    for action in ("up", "down", "undo", "redo", "duplicate", "delete", "rotate"):
        assert f'data-org="{action}"' in html
    assert 'id="saveOrg"' in html
    assert 'id="orgFile"' in html
    assert 'id="visualDialog"' in html
