import pytest
from src.core.platform_manager import PlatformManager
from src.core.exceptions import ConfigError, DisplayError, StorageError

# --- get_platform ---
def test_get_platform_supported(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert PlatformManager.get_platform() == "darwin"
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert PlatformManager.get_platform() == "windows"
    monkeypatch.setattr("platform.system", lambda: "Linux")
    # Simulate not a Raspberry Pi
    import builtins
    real_open = builtins.open
    class DummyFile:
        def read(self): return "not a pi"
        def __enter__(self): return self
        def __exit__(self, *a): pass
    def fake_open(path, *a, **k):
        if path == "/proc/cpuinfo":
            return DummyFile()
        return real_open(path, *a, **k)
    monkeypatch.setattr("builtins.open", fake_open)
    assert PlatformManager.get_platform() == "linux"

def test_get_platform_raspberry_pi(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    class FakeFile:
        def read(self): return "Raspberry Pi"
        def __enter__(self): return self
        def __exit__(self, *a): pass
    monkeypatch.setattr("builtins.open", lambda *a, **k: FakeFile())
    assert PlatformManager.get_platform() == "raspberry_pi"

def test_get_platform_unsupported(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Plan9")
    with pytest.raises(ConfigError):
        PlatformManager.get_platform()

def test_get_platform_cpuinfo_error(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    def raise_io(*a, **k): raise IOError("fail")
    monkeypatch.setattr("builtins.open", raise_io)
    assert PlatformManager.get_platform() == "linux"

# --- create_display ---
def test_create_display_raspberry_pi(monkeypatch):
    monkeypatch.setattr(PlatformManager, "get_platform", staticmethod(lambda: "raspberry_pi"))
    class DummyDisplay: pass
    import sys
    sys.modules["src.platform.raspberry_pi.display"] = type("m", (), {"RaspberryPiDisplay": DummyDisplay})
    result = PlatformManager.create_display()
    assert isinstance(result, DummyDisplay)
    del sys.modules["src.platform.raspberry_pi.display"]

def test_create_display_rich(monkeypatch):
    monkeypatch.setattr(PlatformManager, "get_platform", staticmethod(lambda: "darwin"))
    class DummyDisplay: pass
    import sys
    sys.modules["src.core.rich_display"] = type("m", (), {"RichDisplay": DummyDisplay})
    result = PlatformManager.create_display()
    assert isinstance(result, DummyDisplay)
    del sys.modules["src.core.rich_display"]

def test_create_display_import_error(monkeypatch):
    monkeypatch.setattr(PlatformManager, "get_platform", staticmethod(lambda: "raspberry_pi"))
    import importlib
    monkeypatch.setattr(importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("fail")))
    import sys
    if "src.platform.raspberry_pi.display" in sys.modules:
        del sys.modules["src.platform.raspberry_pi.display"]
    with pytest.raises(DisplayError):
        PlatformManager.create_display()

# --- create_storage ---
def test_create_storage_raspberry_pi(monkeypatch):
    monkeypatch.setattr(PlatformManager, "get_platform", staticmethod(lambda: "raspberry_pi"))
    class DummyStorage: pass
    import sys
    sys.modules["src.platform.raspberry_pi.storage_pi"] = type("m", (), {"RaspberryPiStorage": DummyStorage})
    result = PlatformManager.create_storage()
    assert isinstance(result, DummyStorage)
    del sys.modules["src.platform.raspberry_pi.storage_pi"]

def test_create_storage_macos(monkeypatch):
    monkeypatch.setattr(PlatformManager, "get_platform", staticmethod(lambda: "darwin"))
    class DummyStorage: pass
    import sys
    sys.modules["src.platform.macos.storage_macos"] = type("m", (), {"MacOSStorage": DummyStorage})
    result = PlatformManager.create_storage()
    assert isinstance(result, DummyStorage)
    del sys.modules["src.platform.macos.storage_macos"]

def test_create_storage_windows(monkeypatch):
    monkeypatch.setattr(PlatformManager, "get_platform", staticmethod(lambda: "windows"))
    class DummyStorage: pass
    import sys
    sys.modules["src.platform.windows.storage_win"] = type("m", (), {"WindowsStorage": DummyStorage})
    result = PlatformManager.create_storage()
    assert isinstance(result, DummyStorage)
    del sys.modules["src.platform.windows.storage_win"]

def test_create_storage_unsupported(monkeypatch):
    monkeypatch.setattr(PlatformManager, "get_platform", staticmethod(lambda: "plan9"))
    with pytest.raises(ConfigError):
        PlatformManager.create_storage()

def test_create_storage_import_error(monkeypatch):
    monkeypatch.setattr(PlatformManager, "get_platform", staticmethod(lambda: "darwin"))
    import sys
    sys.modules["src.platform.macos.storage_macos"] = None
    with pytest.raises(StorageError):
        PlatformManager.create_storage()
    del sys.modules["src.platform.macos.storage_macos"] 