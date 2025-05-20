import sys
import types
import pytest
from unittest import mock
from pathlib import Path
import build

def test_extract_metadata_success(tmp_path, monkeypatch):
    # Create a fake __init__.py
    init_path = tmp_path / 'src' / '__init__.py'
    init_path.parent.mkdir(parents=True)
    init_path.write_text("""
__version__ = '1.2.3'
__author__ = 'Test Author'
__license__ = 'MIT'
__description__ = 'desc'
__project_name__ = 'TestProject'
__copyright__ = '2024'
""")
    monkeypatch.setattr(build, 'ROOT_DIR', tmp_path)
    monkeypatch.setattr(build.os.path, 'join', lambda *a: str(init_path))
    meta = build.extract_metadata()
    assert meta['version'] == '1.2.3'
    assert meta['author'] == 'Test Author'
    assert meta['project_name'] == 'TestProject'

def test_extract_metadata_missing_version(tmp_path, monkeypatch):
    init_path = tmp_path / 'src' / '__init__.py'
    init_path.parent.mkdir(parents=True)
    init_path.write_text("__author__ = 'Test Author'\n")
    monkeypatch.setattr(build, 'ROOT_DIR', tmp_path)
    monkeypatch.setattr(build.os.path, 'join', lambda *a: str(init_path))
    with pytest.raises(RuntimeError):
        build.extract_metadata()

def test_ensure_pyinstaller_installed(monkeypatch):
    # Already installed path
    called_run = {}
    monkeypatch.setattr(build.shutil, 'which', lambda x: True)
    monkeypatch.setattr(build.subprocess, 'run', lambda *a, **k: called_run.setdefault('ran', True))
    build.ensure_pyinstaller_installed()
    assert called_run['ran']
    # Install path
    class CalledInstall(Exception): pass
    monkeypatch.setattr(build.shutil, 'which', lambda x: None)
    monkeypatch.setattr(build.subprocess, 'check_call', lambda *a, **k: (_ for _ in ()).throw(CalledInstall()))
    with pytest.raises(CalledInstall):
        build.ensure_pyinstaller_installed()

def test_get_platform_icon(monkeypatch, tmp_path):
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'icon.icns').write_text('x')
    (assets / 'icon.ico').write_text('x')
    (assets / 'icon.png').write_text('x')
    (assets / 'TransferBox_Icon.png').write_text('x')
    monkeypatch.setattr(build, 'ASSETS_DIR', assets)
    monkeypatch.setattr(build.platform, 'system', lambda: 'Darwin')
    assert build.get_platform_icon().endswith('icon.icns')
    monkeypatch.setattr(build.platform, 'system', lambda: 'Windows')
    assert build.get_platform_icon().endswith('icon.ico')
    monkeypatch.setattr(build.platform, 'system', lambda: 'Linux')
    assert build.get_platform_icon().endswith('icon.png')
    # Fallback
    (assets / 'icon.png').unlink()
    assert build.get_platform_icon().endswith('TransferBox_Icon.png')

def test_clean_build_directories(monkeypatch, tmp_path):
    dist = tmp_path / 'dist'
    buildd = tmp_path / 'build'
    dist.mkdir()
    buildd.mkdir()
    monkeypatch.setattr(build, 'DIST_DIR', dist)
    monkeypatch.setattr(build, 'BUILD_DIR', buildd)
    build.clean_build_directories()
    assert not dist.exists()
    assert not buildd.exists()

def test_main_platforms(monkeypatch):
    monkeypatch.setattr(build, 'extract_metadata', lambda: {'project_name': 'Test', 'version': '1.0', 'author': 'A'})
    monkeypatch.setattr(build, 'ensure_pyinstaller_installed', lambda: None)
    monkeypatch.setattr(build, 'get_platform_icon', lambda: 'icon')
    monkeypatch.setattr(build, 'build_macos', lambda meta: True)
    monkeypatch.setattr(build, 'build_windows', lambda meta: True)
    monkeypatch.setattr(build, 'build_linux', lambda meta: True)
    monkeypatch.setattr(build.platform, 'system', lambda: 'Darwin')
    assert build.main() == 0
    monkeypatch.setattr(build.platform, 'system', lambda: 'Windows')
    assert build.main() == 0
    monkeypatch.setattr(build.platform, 'system', lambda: 'Linux')
    assert build.main() == 0
    monkeypatch.setattr(build.platform, 'system', lambda: 'Other')
    assert build.main() == 1

def test_main_error(monkeypatch):
    monkeypatch.setattr(build, 'extract_metadata', mock.Mock(side_effect=RuntimeError('fail')))
    assert build.main() == 1 