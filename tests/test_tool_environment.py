import os
from pathlib import Path
import sys

from backend import runtime


def test_venv_console_script_is_detected_without_activation(tmp_path, monkeypatch):
    executable = tmp_path / ("ocrmypdf.exe" if os.name == "nt" else "ocrmypdf")
    executable.touch()
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    assert runtime.tool_path(["ocrmypdf"]) == str(executable)


def test_native_dependencies_are_visible_to_engine_subprocess(tmp_path, monkeypatch):
    native = tmp_path / "native"
    native.mkdir()
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(runtime, "tool_path", lambda names: str(native / names[0]))
    token = runtime.job.set({"directory": str(tmp_path), "id": "test-environment"})
    try:
        result = runtime.run_tool([sys.executable, "-c", "import os; print(os.environ['PATH'])"])
    finally:
        runtime.job.reset(token)
    directories = result.stdout.decode().strip().split(os.pathsep)
    assert str(Path(sys.executable).parent) in directories
    assert str(native) in directories
    assert os.environ["PATH"] == ""
