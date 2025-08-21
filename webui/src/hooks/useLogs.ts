import { useState, useCallback } from "react";
import type { LogEntry } from "../types";

interface UseLogsReturn {
  logs: LogEntry[];
  addLog: (message: string, level?: LogEntry["level"]) => void;
  clearLogs: (preserveErrors?: boolean) => void;
  clearErrorLogs: () => void;
}

/**
 * Custom hook for managing application logs
 * Provides centralized log management with different log levels
 */
export const useLogs = (): UseLogsReturn => {
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const addLog = useCallback(
    (message: string, level: LogEntry["level"] = "info") => {
      const newLog: LogEntry = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        message,
        timestamp: new Date().toLocaleString(),
        level,
      };
      setLogs((prev) => [...prev, newLog]);
    },
    []
  );

  const clearLogs = useCallback((preserveErrors = false) => {
    if (preserveErrors) {
      setLogs((prev) => prev.filter((log) => log.level === "error"));
    } else {
      setLogs([]);
    }
  }, []);

  const clearErrorLogs = useCallback(() => {
    setLogs((prev) => prev.filter((log) => log.level !== "error"));
  }, []);

  return {
    logs,
    addLog,
    clearLogs,
    clearErrorLogs,
  };
};
