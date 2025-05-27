import { renderHook, act } from "@testing-library/react";
import { useTransferState } from "@/hooks/useTransferState";
import type { BackendTransferProgress } from "@/types";

describe("useTransferState", () => {
  it("initializes with default state", () => {
    const { result } = renderHook(() => useTransferState());

    expect(result.current.transferProgress).toBeNull();
    expect(result.current.isTransferring).toBe(false);
    expect(result.current.transferError).toBeNull();
    expect(result.current.transferState).toBe("idle");
    expect(result.current.isCardDetected).toBe(false);
    expect(result.current.deviceName).toBe("");
    expect(result.current.devicePath).toBe("");
    expect(result.current.currentStatus).toBe("Connecting...");
    expect(result.current.statusType).toBe("info");
  });

  it("sets transfer progress", () => {
    const { result } = renderHook(() => useTransferState());

    const mockProgress: BackendTransferProgress = {
      current_file: "test.jpg",
      file_number: 1,
      total_files: 10,
      bytes_transferred: 1024,
      total_bytes: 10240,
      total_transferred: 1024,
      total_size: 10240,
      current_file_progress: 10,
      overall_progress: 10,
      status: "COPYING",
      proxy_progress: 0,
      proxy_file_number: 0,
      proxy_total_files: 0,
      speed_bytes_per_sec: 1024,
      eta_seconds: 9,
      total_elapsed: 1,
      file_elapsed: 1,
      checksum_elapsed: 0,
      source_drive_name: "Test Drive",
      source_drive_path: "/test/path",
    };

    act(() => {
      result.current.setTransferProgress(mockProgress);
    });

    expect(result.current.transferProgress).toEqual(mockProgress);
  });

  it("sets transfer error", () => {
    const { result } = renderHook(() => useTransferState());
    const errorMessage = "Transfer failed due to network error";

    act(() => {
      result.current.setTransferError(errorMessage);
    });

    expect(result.current.transferError).toBe(errorMessage);
  });

  it("sets card detection state", () => {
    const { result } = renderHook(() => useTransferState());

    act(() => {
      result.current.setCardDetected(true, "SD Card", "/dev/disk2");
    });

    expect(result.current.isCardDetected).toBe(true);
    expect(result.current.deviceName).toBe("SD Card");
    expect(result.current.devicePath).toBe("/dev/disk2");
  });

  it("sets status with type", () => {
    const { result } = renderHook(() => useTransferState());

    act(() => {
      result.current.setStatus("Transfer in progress", "info");
    });

    expect(result.current.currentStatus).toBe("Transfer in progress");
    expect(result.current.statusType).toBe("info");
  });

  it("resets transfer state", () => {
    const { result } = renderHook(() => useTransferState());

    // Set some state first
    act(() => {
      result.current.setTransferError("Some error");
      result.current.setCardDetected(true, "Test Card", "/test/path");
      result.current.setStatus("Error occurred", "error");
    });

    // Reset
    act(() => {
      result.current.resetTransfer();
    });

    expect(result.current.transferError).toBeNull();
    expect(result.current.transferState).toBe("idle");
    expect(result.current.isTransferring).toBe(false);
    expect(result.current.transferProgress).toBeNull();
    expect(result.current.statusType).toBe("info");
    expect(result.current.currentStatus).toBe("Ready for transfer");
    expect(result.current.isCardDetected).toBe(false);
  });

  describe("updateFromProgress", () => {
    it("handles COPYING status", () => {
      const { result } = renderHook(() => useTransferState());

      const mockProgress: BackendTransferProgress = {
        current_file: "test.jpg",
        file_number: 5,
        total_files: 10,
        bytes_transferred: 5120,
        total_bytes: 10240,
        total_transferred: 5120,
        total_size: 10240,
        current_file_progress: 50,
        overall_progress: 50,
        status: "COPYING",
        proxy_progress: 0,
        proxy_file_number: 0,
        proxy_total_files: 0,
        speed_bytes_per_sec: 1024,
        eta_seconds: 5,
        total_elapsed: 5,
        file_elapsed: 1,
        checksum_elapsed: 0,
        source_drive_name: "Test Drive",
        source_drive_path: "/test/path",
      };

      act(() => {
        result.current.updateFromProgress(mockProgress);
      });

      expect(result.current.transferProgress).toEqual(mockProgress);
      expect(result.current.isTransferring).toBe(true);
      expect(result.current.transferState).toBe("transferring");
      expect(result.current.isCardDetected).toBe(true);
      expect(result.current.deviceName).toBe("Test Drive");
      expect(result.current.devicePath).toBe("/test/path");
      expect(result.current.currentStatus).toBe("Copying files... (5/10)");
      expect(result.current.statusType).toBe("info");
    });

    it("handles CHECKSUMMING status", () => {
      const { result } = renderHook(() => useTransferState());

      const mockProgress: BackendTransferProgress = {
        current_file: "test.jpg",
        file_number: 3,
        total_files: 10,
        bytes_transferred: 3072,
        total_bytes: 10240,
        total_transferred: 3072,
        total_size: 10240,
        current_file_progress: 30,
        overall_progress: 30,
        status: "CHECKSUMMING",
        proxy_progress: 0,
        proxy_file_number: 0,
        proxy_total_files: 0,
        speed_bytes_per_sec: 1024,
        eta_seconds: 7,
        total_elapsed: 3,
        file_elapsed: 1,
        checksum_elapsed: 2,
        source_drive_name: "Test Drive",
        source_drive_path: "/test/path",
      };

      act(() => {
        result.current.updateFromProgress(mockProgress);
      });

      expect(result.current.currentStatus).toBe("Verifying files... (3/10)");
      expect(result.current.isTransferring).toBe(true);
      expect(result.current.transferState).toBe("transferring");
    });

    it("handles GENERATING_PROXY status", () => {
      const { result } = renderHook(() => useTransferState());

      const mockProgress: BackendTransferProgress = {
        current_file: "test.jpg",
        file_number: 10,
        total_files: 10,
        bytes_transferred: 10240,
        total_bytes: 10240,
        total_transferred: 10240,
        total_size: 10240,
        current_file_progress: 100,
        overall_progress: 100,
        status: "GENERATING_PROXY",
        proxy_progress: 50,
        proxy_file_number: 2,
        proxy_total_files: 4,
        speed_bytes_per_sec: 1024,
        eta_seconds: 2,
        total_elapsed: 10,
        file_elapsed: 1,
        checksum_elapsed: 0,
        source_drive_name: "Test Drive",
        source_drive_path: "/test/path",
      };

      act(() => {
        result.current.updateFromProgress(mockProgress);
      });

      expect(result.current.currentStatus).toBe("Generating proxies... (2/4)");
      expect(result.current.isTransferring).toBe(true);
      expect(result.current.transferState).toBe("transferring");
    });

    it("handles SUCCESS status", () => {
      const { result } = renderHook(() => useTransferState());

      const mockProgress: BackendTransferProgress = {
        current_file: "",
        file_number: 10,
        total_files: 10,
        bytes_transferred: 10240,
        total_bytes: 10240,
        total_transferred: 10240,
        total_size: 10240,
        current_file_progress: 100,
        overall_progress: 100,
        status: "SUCCESS",
        proxy_progress: 100,
        proxy_file_number: 4,
        proxy_total_files: 4,
        speed_bytes_per_sec: 0,
        eta_seconds: 0,
        total_elapsed: 10,
        file_elapsed: 0,
        checksum_elapsed: 0,
        source_drive_name: "",
        source_drive_path: "",
      };

      act(() => {
        result.current.updateFromProgress(mockProgress);
      });

      expect(result.current.isTransferring).toBe(false);
      expect(result.current.transferState).toBe("completed");
      expect(result.current.currentStatus).toBe(
        "Transfer completed successfully"
      );
      expect(result.current.statusType).toBe("success");
      expect(result.current.isCardDetected).toBe(false);
    });

    it("handles ERROR status", () => {
      const { result } = renderHook(() => useTransferState());

      const mockProgress: BackendTransferProgress = {
        current_file: "failed.jpg",
        file_number: 5,
        total_files: 10,
        bytes_transferred: 5120,
        total_bytes: 10240,
        total_transferred: 5120,
        total_size: 10240,
        current_file_progress: 50,
        overall_progress: 50,
        status: "ERROR",
        proxy_progress: 0,
        proxy_file_number: 0,
        proxy_total_files: 0,
        speed_bytes_per_sec: 0,
        eta_seconds: 0,
        total_elapsed: 5,
        file_elapsed: 1,
        checksum_elapsed: 0,
        source_drive_name: "",
        source_drive_path: "",
      };

      act(() => {
        result.current.updateFromProgress(mockProgress);
      });

      expect(result.current.isTransferring).toBe(false);
      expect(result.current.transferState).toBe("failed");
      expect(result.current.currentStatus).toBe("Transfer failed");
      expect(result.current.statusType).toBe("error");
      expect(result.current.transferError).toBe("Transfer failed");
      expect(result.current.isCardDetected).toBe(false);
    });
  });
});
