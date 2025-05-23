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
    setTransferError(errorData.message);
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

  return {
    handleMessage,
  };
};
