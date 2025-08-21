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
  isStopping: boolean;
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
  setStoppingState: (stopping: boolean) => void;
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
  const [isStopping, setIsStopping] = useState(false);
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

  const setStoppingState = useCallback((stopping: boolean) => {
    setIsStopping(stopping);
  }, []);

  const resetTransfer = useCallback(() => {
    setTransferError(null);
    setTransferState("idle");
    setIsTransferring(false);
    setIsStopping(false);
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
            statusMessage = isStopping
              ? `Stopping after current file... (${progress.file_number}/${progress.total_files})`
              : `Copying files... (${progress.file_number}/${progress.total_files})`;
            break;
          case "CHECKSUMMING":
            statusMessage = isStopping
              ? `Stopping after current file verification... (${progress.file_number}/${progress.total_files})`
              : `Verifying files... (${progress.file_number}/${progress.total_files})`;
            break;
          case "GENERATING_PROXY":
            statusMessage = isStopping
              ? `Stopping after current proxy... (${progress.proxy_file_number}/${progress.proxy_total_files})`
              : `Generating proxies... (${progress.proxy_file_number}/${progress.proxy_total_files})`;
            break;
          case "VERIFYING":
            statusMessage = isStopping
              ? "Stopping after verification..."
              : "Verifying transfer...";
            break;
        }
        setStatus(statusMessage, isStopping ? "warning" : "info");
      } else if (status === "SUCCESS") {
        setIsTransferring(false);
        setIsStopping(false);
        setTransferState("completed");
        setStatus("Transfer completed successfully", "success");
        setCardDetected(false);
      } else if (status === "STOPPED") {
        setIsTransferring(false);
        setIsStopping(false);
        setTransferState("completed");
        setStatus("Transfer stopped successfully", "success");
        setCardDetected(false);
      } else if (status === "ERROR") {
        setIsTransferring(false);
        setIsStopping(false);
        setTransferState("failed");
        setStatus("Transfer failed", "error");
        setTransferError("Transfer failed");
        setCardDetected(false);
      }
    },
    [setCardDetected, setStatus, isStopping]
  );

  return {
    // State
    transferProgress,
    isTransferring,
    isStopping,
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
    setStoppingState,
    resetTransfer,
    updateFromProgress,
  };
};
