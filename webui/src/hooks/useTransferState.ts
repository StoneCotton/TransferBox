import { useState, useCallback } from "react";
import type {
  BackendTransferProgress,
  TransferState,
  StatusType,
} from "../types";

interface UseTransferStateReturn {
  // Transfer state
  transferProgress: BackendTransferProgress | null;
  isTransferring: boolean;
  transferError: string | null;
  transferState: TransferState;

  // Card detection
  isCardDetected: boolean;
  deviceName: string;
  devicePath: string;

  // Status
  currentStatus: string;
  statusType: StatusType;

  // Actions
  setTransferProgress: (progress: BackendTransferProgress | null) => void;
  setTransferError: (error: string | null) => void;
  setCardDetected: (detected: boolean, name?: string, path?: string) => void;
  setStatus: (status: string, type?: StatusType) => void;
  resetTransfer: () => void;
  updateFromProgress: (progress: BackendTransferProgress) => void;
}

/**
 * Custom hook for managing transfer state and progress
 * Centralizes all transfer-related state management
 */
export const useTransferState = (): UseTransferStateReturn => {
  // Transfer state
  const [transferProgress, setTransferProgress] =
    useState<BackendTransferProgress | null>(null);
  const [isTransferring, setIsTransferring] = useState(false);
  const [transferError, setTransferError] = useState<string | null>(null);
  const [transferState, setTransferState] = useState<TransferState>("idle");

  // Card detection
  const [isCardDetected, setIsCardDetected] = useState(false);
  const [deviceName, setDeviceName] = useState("");
  const [devicePath, setDevicePath] = useState("");

  // Status
  const [currentStatus, setCurrentStatus] = useState("Connecting...");
  const [statusType, setStatusType] = useState<StatusType>("info");

  const setCardDetected = useCallback(
    (detected: boolean, name = "", path = "") => {
      setIsCardDetected(detected);
      setDeviceName(name);
      setDevicePath(path);
    },
    []
  );

  const setStatus = useCallback((status: string, type: StatusType = "info") => {
    setCurrentStatus(status);
    setStatusType(type);
  }, []);

  const resetTransfer = useCallback(() => {
    setTransferError(null);
    setTransferState("idle");
    setIsTransferring(false);
    setTransferProgress(null);
    setStatusType("info");
    setCurrentStatus("Ready for transfer");
    setCardDetected(false);
  }, [setCardDetected]);

  const updateFromProgress = useCallback(
    (progress: BackendTransferProgress) => {
      setTransferProgress(progress);

      const status = progress.status;

      if (
        status === "COPYING" ||
        status === "CHECKSUMMING" ||
        status === "GENERATING_PROXY" ||
        status === "VERIFYING"
      ) {
        setIsTransferring(true);
        setTransferState("transferring");

        // Use source drive info from the backend progress data
        if (progress.source_drive_name && progress.source_drive_path) {
          setCardDetected(
            true,
            progress.source_drive_name,
            progress.source_drive_path
          );
        }

        // Update status message based on current operation
        let statusMessage = "";
        switch (status) {
          case "COPYING":
            statusMessage = `Copying files... (${progress.file_number}/${progress.total_files})`;
            break;
          case "CHECKSUMMING":
            statusMessage = `Verifying files... (${progress.file_number}/${progress.total_files})`;
            break;
          case "GENERATING_PROXY":
            statusMessage = `Generating proxies... (${progress.proxy_file_number}/${progress.proxy_total_files})`;
            break;
          case "VERIFYING":
            statusMessage = "Verifying transfer...";
            break;
        }
        setStatus(statusMessage, "info");
      } else if (status === "SUCCESS") {
        setIsTransferring(false);
        setTransferState("completed");
        setStatus("Transfer completed successfully", "success");
        setCardDetected(false);
      } else if (status === "ERROR") {
        setIsTransferring(false);
        setTransferState("failed");
        setStatus("Transfer failed", "error");
        setTransferError("Transfer failed");
        setCardDetected(false);
      }
    },
    [setCardDetected, setStatus]
  );

  return {
    // State
    transferProgress,
    isTransferring,
    transferError,
    transferState,
    isCardDetected,
    deviceName,
    devicePath,
    currentStatus,
    statusType,

    // Actions
    setTransferProgress,
    setTransferError,
    setCardDetected,
    setStatus,
    resetTransfer,
    updateFromProgress,
  };
};
