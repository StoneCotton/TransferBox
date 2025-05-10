import pytest
from unittest import mock
from pathlib import Path
from src.platform.macos.storage_macos import MacOSStorage
from src.core.exceptions import StorageError

@pytest.fixture
def storage():
    return MacOSStorage()

def test_get_available_drives_success(monkeypatch, tmp_path):
    vol_dir = tmp_path / "Volumes"
    vol_dir.mkdir()
    drive = vol_dir / "Drive1"
    drive.mkdir()
    # Patch Path('/Volumes') to our temp dir
    monkeypatch.setattr('pathlib.Path.iterdir', lambda self: [drive] if str(self) == str(vol_dir) else [])
    monkeypatch.setattr('pathlib.Path.is_mount', lambda self: str(self) == str(drive))
    # Patch Path('/Volumes') to our temp dir in the test
    monkeypatch.setattr('pathlib.Path.__new__', staticmethod(lambda cls, *a, **kw: vol_dir if a and a[0] == '/Volumes' else Path.__new__(cls, *a, **kw)))
    s = MacOSStorage()
    drives = s.get_available_drives()
    assert drives == [drive]

def test_get_available_drives_permission_error(monkeypatch):
    monkeypatch.setattr('pathlib.Path.iterdir', mock.Mock(side_effect=PermissionError("denied")))
    s = MacOSStorage()
    with pytest.raises(StorageError):
        s.get_available_drives()

def test_get_drive_info_success(monkeypatch, tmp_path):
    s = MacOSStorage()
    fake_df = mock.Mock()
    fake_df.stdout = "Filesystem 1K-blocks Used Available Capacity Mounted on\n/dev/disk1s1 1000 200 800 20% /"
    monkeypatch.setattr('subprocess.run', mock.Mock(return_value=fake_df))
    info = s.get_drive_info(tmp_path)
    assert info['total'] == 1000 * 1024
    assert info['used'] == 200 * 1024
    assert info['free'] == 800 * 1024

def test_get_drive_info_df_error(monkeypatch, tmp_path):
    s = MacOSStorage()
    monkeypatch.setattr('subprocess.run', mock.Mock(side_effect=mock.Mock(side_effect=Exception('fail'))))
    with pytest.raises(StorageError):
        s.get_drive_info(tmp_path)

def test_is_drive_mounted_success(monkeypatch, tmp_path):
    s = MacOSStorage()
    monkeypatch.setattr('pathlib.Path.is_mount', lambda self: True)
    assert s.is_drive_mounted(tmp_path)

def test_is_drive_mounted_error(monkeypatch, tmp_path):
    s = MacOSStorage()
    monkeypatch.setattr('pathlib.Path.is_mount', mock.Mock(side_effect=Exception('fail')))
    with pytest.raises(StorageError):
        s.is_drive_mounted(tmp_path)

def test_unmount_drive_success(monkeypatch, tmp_path):
    s = MacOSStorage()
    monkeypatch.setattr('subprocess.run', mock.Mock())
    monkeypatch.setattr('time.sleep', lambda x: None)
    monkeypatch.setattr('pathlib.Path.exists', lambda self: False)
    monkeypatch.setattr('pathlib.Path.is_mount', lambda self: False)
    assert s.unmount_drive(tmp_path)

def test_unmount_drive_failure(monkeypatch, tmp_path):
    s = MacOSStorage()
    monkeypatch.setattr('subprocess.run', mock.Mock(side_effect=Exception('fail')))
    with pytest.raises(StorageError):
        s.unmount_drive(tmp_path)

def test_get_and_set_dump_drive(tmp_path):
    s = MacOSStorage()
    s.set_dump_drive(tmp_path)
    assert s.get_dump_drive() == tmp_path

def test_set_dump_drive_error(monkeypatch):
    s = MacOSStorage()
    monkeypatch.setattr('os.access', mock.Mock(return_value=False))
    with pytest.raises(StorageError):
        s.set_dump_drive('/no/perm')

def test_wait_for_new_drive(monkeypatch):
    s = MacOSStorage()
    initial = [Path('/Volumes/Drive1')]
    monkeypatch.setattr(s, 'get_available_drives', mock.Mock(side_effect=[[Path('/Volumes/Drive1')], [Path('/Volumes/Drive1'), Path('/Volumes/Drive2')]]))
    monkeypatch.setattr('time.sleep', lambda x: None)
    result = s.wait_for_new_drive(initial)
    assert result == Path('/Volumes/Drive2')

def test_wait_for_drive_removal(monkeypatch):
    s = MacOSStorage()
    path = Path('/Volumes/Drive1')
    states = [True, False]
    monkeypatch.setattr('pathlib.Path.exists', lambda self: states.pop(0))
    monkeypatch.setattr('pathlib.Path.is_mount', lambda self: states[0])
    monkeypatch.setattr('time.sleep', lambda x: None)
    s.wait_for_drive_removal(path)

def test_has_enough_space(monkeypatch, tmp_path):
    s = MacOSStorage()
    monkeypatch.setattr(s, 'get_drive_info', lambda path: {'free': 2000})
    assert s.has_enough_space(tmp_path, 1000)
    assert not s.has_enough_space(tmp_path, 3000)

def test_get_file_metadata(monkeypatch, tmp_path):
    s = MacOSStorage()
    f = tmp_path / 'file.txt'
    f.write_text('x')
    monkeypatch.setattr('os.stat', mock.Mock(return_value=mock.Mock(st_mode=0o644, st_uid=1000, st_gid=1000, st_atime=1, st_mtime=2, st_ctime=3, st_flags=None)))
    # Patch sys.modules['xattr'] to a mock
    import sys
    fake_xattr = mock.Mock()
    fake_xattr.xattr.return_value = {'foo': b'bar'}
    sys.modules['xattr'] = fake_xattr
    meta = s.get_file_metadata(f)
    assert 'st_mode' in meta
    assert 'xattrs' in meta
    assert meta['xattrs'] == {'foo': b'bar'}

def test_set_file_metadata(monkeypatch, tmp_path):
    s = MacOSStorage()
    f = tmp_path / 'file.txt'
    f.write_text('x')
    meta = {'st_mode': 0o644, 'st_uid': 1000, 'st_gid': 1000, 'st_atime': 1, 'st_mtime': 2, 'st_flags': None, 'xattrs': {}}
    monkeypatch.setattr('os.chmod', mock.Mock())
    monkeypatch.setattr('os.chown', mock.Mock())
    monkeypatch.setattr('os.utime', mock.Mock())
    assert s.set_file_metadata(f, meta)
    # Test error
    monkeypatch.setattr('os.chmod', mock.Mock(side_effect=Exception('fail')))
    with pytest.raises(StorageError):
        s.set_file_metadata(f, meta) 