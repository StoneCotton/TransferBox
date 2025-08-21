import { useState, useCallback } from "react";
import { apiService } from "../services/api";

interface UseTransferControlsReturn {
  isStopping: boolean;
  isShuttingDown: boolean;
  stopTransfer: () => Promise<void>;
  shutdownApplication: () => Promise<void>;
}

/**
 * Custom hook for transfer control operations
 * Handles stopping transfers and shutting down the application
 */
export const useTransferControls = (
  onLog: (
    message: string,
    level?: "info" | "warning" | "error" | "success"
  ) => void,
  onStatusUpdate: (
    status: string,
    type?: "info" | "warning" | "error" | "success"
  ) => void,
  setStoppingState?: (stopping: boolean) => void
): UseTransferControlsReturn => {
  const [isStopping, setIsStopping] = useState(false);
  const [isShuttingDown, setIsShuttingDown] = useState(false);

  const stopTransfer = useCallback(async () => {
    if (isStopping) return; // Prevent multiple clicks

    setIsStopping(true);

    // Set the stopping state in the transfer state
    if (setStoppingState) {
      setStoppingState(true);
    }

    onStatusUpdate("Stop requested - finishing current file...", "warning");
    onLog(
      "Transfer stop requested - will finish current file before stopping",
      "warning"
    );

    try {
      const result = await apiService.stopTransfer();

      if (result.success) {
        onLog("Stop transfer request sent successfully", "info");
        // Keep the stopping state until transfer actually stops via WebSocket
      } else {
        onLog(`Failed to stop transfer: ${result.message}`, "error");
        onStatusUpdate("Failed to stop transfer", "error");
        // Reset stopping state on failure
        if (setStoppingState) {
          setStoppingState(false);
        }
      }
    } catch (error) {
      console.error("Error stopping transfer:", error);
      onLog("Error communicating with server to stop transfer", "error");
      onStatusUpdate("Error stopping transfer", "error");
      // Reset stopping state on error
      if (setStoppingState) {
        setStoppingState(false);
      }
    } finally {
      setIsStopping(false);
    }
  }, [isStopping, onLog, onStatusUpdate, setStoppingState]);

  const shutdownApplication = useCallback(async () => {
    if (isShuttingDown) return; // Prevent multiple clicks

    // Confirm with user
    const confirmed = window.confirm(
      "Are you sure you want to shutdown the TransferBox application? " +
        "Any ongoing transfers will be stopped and the application will close."
    );

    if (!confirmed) return;

    setIsShuttingDown(true);
    onStatusUpdate("Shutting down application...", "warning");
    onLog("Shutdown request sent to server...", "warning");

    try {
      const result = await apiService.shutdown();

      if (result.success) {
        onLog("Shutdown initiated successfully", "warning");
        // Server might disconnect before we get here
      } else {
        onLog(`Failed to shutdown: ${result.message}`, "error");
      }
    } catch (error) {
      // This is expected if the server shuts down quickly
      console.log("Server appears to have shut down:", error);
      onLog("Server connection lost - shutdown may have succeeded", "info");
    } finally {
      setIsShuttingDown(false);
    }
  }, [isShuttingDown, onLog, onStatusUpdate]);

  return {
    isStopping,
    isShuttingDown,
    stopTransfer,
    shutdownApplication,
  };
};
