"use client";

import React from "react";
import ProgressBar from "./ProgressBar";

interface FileTransferProgressProps {
  title: string;
  progress: number;
  currentItem?: string;
  itemCount?: { current: number; total: number };
  size?: { transferred: number; total: number };
  speed?: number;
  time?: { elapsed: number; remaining: number };
  className?: string;
}

const FileTransferProgress: React.FC<FileTransferProgressProps> = ({
  title,
  progress,
  currentItem,
  itemCount,
  size,
  speed,
  time,
  className = "",
}) => {
  // Format bytes to human-readable format (KB, MB, GB)
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
  };

  // Format seconds to human-readable time (hh:mm:ss)
  const formatTime = (seconds: number): string => {
    if (seconds < 0) seconds = 0;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    return [
      hours > 0 ? hours.toString().padStart(2, "0") : undefined,
      minutes.toString().padStart(2, "0"),
      secs.toString().padStart(2, "0"),
    ]
      .filter(Boolean)
      .join(":");
  };

  // Format speed in bytes/second to human-readable format
  const formatSpeed = (bytesPerSecond: number): string => {
    return `${formatBytes(bytesPerSecond)}/s`;
  };

  return (
    <div
      className={`bg-white p-4 rounded-md border border-slate-200 ${className}`}
    >
      <div className="flex justify-between items-center mb-2">
        <h3 className="font-medium text-slate-800">{title}</h3>
        {itemCount && (
          <div className="text-sm text-slate-600">
            {itemCount.current} of {itemCount.total}{" "}
            {itemCount.total === 1 ? "file" : "files"}
          </div>
        )}
      </div>

      {currentItem && (
        <div className="text-sm font-mono bg-slate-50 p-2 rounded mb-2 truncate">
          {currentItem}
        </div>
      )}

      <ProgressBar
        progress={progress}
        showPercentage={true}
        variant={progress === 100 ? "success" : "primary"}
        height="md"
      />

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-3 text-xs text-slate-600">
        {size && (
          <>
            <div>Transferred:</div>
            <div className="text-right font-medium">
              {formatBytes(size.transferred)} / {formatBytes(size.total)}
            </div>
          </>
        )}

        {speed && (
          <>
            <div>Speed:</div>
            <div className="text-right font-medium">{formatSpeed(speed)}</div>
          </>
        )}

        {time && (
          <>
            <div>Time elapsed:</div>
            <div className="text-right font-medium">
              {formatTime(time.elapsed)}
            </div>

            <div>Time remaining:</div>
            <div className="text-right font-medium">
              {formatTime(time.remaining)}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default FileTransferProgress;
