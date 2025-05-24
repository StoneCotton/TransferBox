import type {
  WebSocketMessage,
  BackendTransferProgress,
  LogEntry,
} from "../types";

interface WebSocketHandlerContext {
  addLog: (message: string, level?: LogEntry["level"]) => void;
  setStatus: (
    status: string,
    type?: "info" | "warning" | "error" | "success"
  ) => void;
  updateFromProgress: (progress: BackendTransferProgress) => void;
  setTransferError: (error: string | null) => void;
  setTransferProgress: (progress: BackendTransferProgress | null) => void;
  setCardDetected: (detected: boolean, name?: string, path?: string) => void;
  resetDestination: () => void;
  clearLogs: (preserveErrors?: boolean) => void;
}

/**
 * WebSocket message handlers
 * Centralizes all WebSocket message processing logic
 */
export const createWebSocketHandlers = (context: WebSocketHandlerContext) => {
  const {
    addLog,
    setStatus,
    updateFromProgress,
    setTransferError,
    setTransferProgress,
    setCardDetected,
    resetDestination,
    clearLogs,
  } = context;

  const handleMessage = (message: WebSocketMessage): void => {
    switch (message.type) {
      case "initial_state":
        handleInitialState(message);
        break;
      case "status":
        handleStatus(message);
        break;
      case "progress":
        handleProgress(message);
        break;
      case "error":
        handleError(message);
        break;
      case "clear":
        handleClear(message);
        break;
      case "transfer_stopped":
        handleTransferStopped(message);
        break;
      case "shutdown_initiated":
        handleShutdownInitiated(message);
        break;
      case "pong":
        // Handle ping/pong for connection keepalive
        break;
      default:
        console.log("Unknown WebSocket message type:", message.type);
    }
  };

  const handleInitialState = (message: WebSocketMessage): void => {
    const initialData = message.data as {
      status?: string;
      errors?: string[];
      progress?: BackendTransferProgress;
    };

    if (initialData.status) {
      setStatus(initialData.status, "info");
    }

    if (initialData.errors && initialData.errors.length > 0) {
      initialData.errors.forEach((error: string) => {
        addLog(error, "error");
      });
    }

    if (initialData.progress) {
      setTransferProgress(initialData.progress);
      updateFromProgress(initialData.progress);
    }
  };

  const handleStatus = (message: WebSocketMessage): void => {
    const statusData = message.data as { message: string };

    // Determine status type based on message content
    let statusType: "info" | "warning" | "error" | "success" = "info";
    const msg = statusData.message.toLowerCase();

    if (msg.includes("error") || msg.includes("failed")) {
      statusType = "error";
    } else if (msg.includes("complete") || msg.includes("success")) {
      statusType = "success";
    } else if (msg.includes("warning")) {
      statusType = "warning";
    }

    setStatus(statusData.message, statusType);
    addLog(statusData.message, "info");
  };

  const handleProgress = (message: WebSocketMessage): void => {
    const progressData = message.data as unknown as BackendTransferProgress;
    updateFromProgress(progressData);

    // Reset destination after successful or failed transfer
    if (progressData.status === "SUCCESS" || progressData.status === "ERROR") {
      resetDestination();
    }
  };

  const handleError = (message: WebSocketMessage): void => {
    const errorData = message.data as { message: string };

    // Enhance error message for specific cases
    let displayError = errorData.message;
    if (errorData.message === "No valid media files found") {
      displayError =
        "No valid media files found on the source drive. Please check that the drive contains supported media files and try again.";
    }

    setTransferError(displayError);
    setStatus(errorData.message, "error");
    setCardDetected(false);
    resetDestination();
    addLog(errorData.message, "error");
  };

  const handleClear = (message: WebSocketMessage): void => {
    const clearData = message.data as { preserve_errors?: boolean };

    if (!clearData.preserve_errors) {
      setTransferError(null);
      clearLogs(false);
    } else {
      clearLogs(true);
    }

    setStatus("", "info");
    setTransferProgress(null);
    setCardDetected(false);
  };

  const handleTransferStopped = (message: WebSocketMessage): void => {
    const stopData = message.data as {
      message: string;
      files_transferred?: number;
      files_not_transferred?: number;
      cleanup_completed?: boolean;
    };

    setStatus(stopData.message, "warning");
    addLog(`Transfer stopped: ${stopData.message}`, "warning");

    if (stopData.files_transferred !== undefined) {
      addLog(`Files transferred: ${stopData.files_transferred}`, "info");
    }
    if (stopData.files_not_transferred !== undefined) {
      addLog(
        `Files not transferred: ${stopData.files_not_transferred}`,
        "warning"
      );
    }
    if (stopData.cleanup_completed) {
      addLog("Cleanup completed - temporary files removed", "info");
    }

    // Reset transfer state
    setTransferProgress(null);
    setCardDetected(false);
    resetDestination();
  };

  const handleShutdownInitiated = (message: WebSocketMessage): void => {
    const shutdownData = message.data as { message: string };
    setStatus(shutdownData.message, "warning");
    addLog("Application shutdown initiated", "warning");

    // The WebSocket connection will likely close after this message
  };

  return {
    handleMessage,
  };
};
