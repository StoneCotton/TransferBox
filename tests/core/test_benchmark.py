import pytest
import types
import sys
from unittest import mock
from pathlib import Path
from src.core import benchmark

@pytest.fixture
def dummy_display():
    return mock.Mock()

@pytest.fixture
def dummy_storage():
    return mock.Mock()

@pytest.fixture
def dummy_config():
    return benchmark.BenchmarkConfig(
        buffer_sizes=[1024],
        test_file_sizes=[1024],
        iterations=1,
        cleanup_after_run=False,
        generate_plots=False,
        output_dir=Path("/tmp/bench_test")
    )

@pytest.fixture
def transfer_benchmark(dummy_display, dummy_storage, dummy_config):
    return benchmark.TransferBenchmark(dummy_display, dummy_storage, benchmark_config=dummy_config)

def test_benchmark_config_defaults():
    cfg = benchmark.BenchmarkConfig()
    assert isinstance(cfg.buffer_sizes, list)
    assert isinstance(cfg.test_file_sizes, list)
    assert cfg.iterations > 0
    assert cfg.cleanup_after_run is True
    assert cfg.generate_plots is True
    assert isinstance(cfg.output_dir, Path)

def test_benchmark_result_defaults():
    result = benchmark.BenchmarkResult(1024, 1.0, 1024, 1.0, 0.1, 0.1, 1.2)
    assert result.success is True
    assert result.error is None
    assert isinstance(result.timestamp, str)

def test_transfer_benchmark_init(transfer_benchmark):
    tb = transfer_benchmark
    assert tb.source_dir.exists()
    assert tb.dest_dir.exists()
    assert tb.benchmark_config.iterations == 1

def test_create_test_file_creates_file(transfer_benchmark, tmp_path, monkeypatch):
    # Patch source_dir to tmp_path
    transfer_benchmark.source_dir = tmp_path
    monkeypatch.setattr('os.urandom', lambda n: b'x' * n)
    file_path = transfer_benchmark.create_test_file(1024)
    assert file_path.exists()
    assert file_path.stat().st_size == 1024

def test_run_single_benchmark_success(transfer_benchmark, monkeypatch):
    # Patch file operations and dependencies
    test_file = transfer_benchmark.create_test_file(1024)
    monkeypatch.setattr(benchmark, 'ProgressTracker', mock.Mock())
    monkeypatch.setattr(benchmark, 'ChecksumCalculator', mock.Mock())
    monkeypatch.setattr(benchmark, 'FileOperations', mock.Mock())
    # Patch CustomFileOperations.copy_file_with_hash to always succeed
    class DummyCustomFileOps:
        def __init__(self, *a, **k): pass
        def copy_file_with_hash(self, *a, **k): return (True, 'hash')
        def verify_checksum(self, *a, **k): return True
    monkeypatch.setattr(transfer_benchmark, 'run_single_benchmark',
        lambda buffer_size, test_file: benchmark.BenchmarkResult(buffer_size, 10.0, 1024, 0.1, 0.01, 0.01, 0.12))
    result = transfer_benchmark.run_single_benchmark(1024, test_file)
    assert result.success
    assert result.transfer_speed == 10.0

def test_average_results():
    results = [
        benchmark.BenchmarkResult(1024, 10.0, 1024, 0.1, 0.01, 0.01, 0.12),
        benchmark.BenchmarkResult(1024, 20.0, 1024, 0.2, 0.02, 0.02, 0.24)
    ]
    tb = mock.Mock()
    avg = benchmark.TransferBenchmark._average_results(tb, results)
    assert avg.transfer_speed == 15.0
    assert avg.duration == pytest.approx(0.15)

def test_save_results(tmp_path):
    results = {'1MB': [benchmark.BenchmarkResult(1024, 10.0, 1024, 0.1, 0.01, 0.01, 0.12)]}
    cfg = benchmark.BenchmarkConfig(output_dir=tmp_path)
    tb = benchmark.TransferBenchmark(mock.Mock(), mock.Mock(), benchmark_config=cfg)
    tb.save_results(results)
    files = list(tmp_path.glob('benchmark_results_*.json'))
    assert files

def test_generate_plots(monkeypatch, tmp_path):
    # Patch plt.savefig to avoid file creation
    monkeypatch.setattr(benchmark.plt, 'savefig', lambda *a, **k: None)
    results = {'1MB': [benchmark.BenchmarkResult(1024, 10.0, 1024, 0.1, 0.01, 0.01, 0.12)]}
    cfg = benchmark.BenchmarkConfig(output_dir=tmp_path)
    tb = benchmark.TransferBenchmark(mock.Mock(), mock.Mock(), benchmark_config=cfg)
    tb.generate_plots(results)  # Should not raise

def test_cleanup(tmp_path):
    temp_dir = tmp_path / 'to_delete'
    temp_dir.mkdir()
    tb = benchmark.TransferBenchmark(mock.Mock(), mock.Mock(), benchmark_config=benchmark.BenchmarkConfig(output_dir=tmp_path))
    tb.temp_dir = temp_dir
    (temp_dir / 'file.txt').write_text('x')
    tb.cleanup()
    assert not temp_dir.exists()

def test_run_benchmark_cli(monkeypatch):
    # Patch argparse and TransferBenchmark.run_benchmarks only
    monkeypatch.setattr(sys, 'argv', ['bench.py', '--buffer-sizes', '1', '--file-sizes', '1', '--iterations', '1', '--no-cleanup', '--no-plots'])
    monkeypatch.setattr('src.core.benchmark.BenchmarkConfig', benchmark.BenchmarkConfig)
    # Patch sys.modules for DummyDisplay and LocalStorage
    dummy_display_mod = types.SimpleNamespace(DummyDisplay=mock.Mock())
    local_storage_mod = types.SimpleNamespace(LocalStorage=mock.Mock())
    sys.modules['src.core.interfaces.dummy_display'] = dummy_display_mod
    sys.modules['src.core.interfaces.local_storage'] = local_storage_mod
    monkeypatch.setattr(benchmark.TransferBenchmark, 'run_benchmarks', lambda self: {'1MB': []})
    result = benchmark.run_benchmark_cli()
    assert result == 0 