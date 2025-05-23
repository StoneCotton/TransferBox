"use client";

import React, { useRef, useEffect } from "react";
import type { LogEntry } from "../types";

interface LogContainerProps {
  logs: LogEntry[];
  title?: string;
  maxHeight?: string;
  autoScroll?: boolean;
  className?: string;
}

const LogContainer: React.FC<LogContainerProps> = ({
  logs,
  title = "Logs",
  maxHeight = "300px",
  autoScroll = true,
  className = "",
}) => {
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const getLevelStyles = (level: string = "info") => {
    switch (level) {
      case "error":
        return "text-red-600";
      case "warning":
        return "text-amber-600";
      case "success":
        return "text-green-600";
      default:
        return "text-slate-600";
    }
  };

  return (
    <div className={`border border-slate-200 rounded-md bg-white ${className}`}>
      <div className="border-b border-slate-200 px-4 py-2 bg-slate-50 font-medium">
        {title}
      </div>
      <div
        className="p-4 font-mono text-sm overflow-y-auto"
        style={{ maxHeight }}
      >
        {logs.length === 0 ? (
          <div className="text-slate-400 italic">No logs to display</div>
        ) : (
          <>
            {logs.map((log) => (
              <div key={log.id} className="mb-1 leading-relaxed">
                <span className="text-slate-400 mr-2">[{log.timestamp}]</span>
                <span className={getLevelStyles(log.level)}>{log.message}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </>
        )}
      </div>
    </div>
  );
};

export default LogContainer;
