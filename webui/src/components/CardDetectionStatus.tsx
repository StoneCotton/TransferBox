"use client";

import React from "react";

interface CardDetectionStatusProps {
  isDetected: boolean;
  deviceName?: string;
  devicePath?: string;
  waitingMessage?: string;
  className?: string;
}

const CardDetectionStatus: React.FC<CardDetectionStatusProps> = ({
  isDetected,
  deviceName,
  devicePath,
  waitingMessage = "Waiting for source drive...",
  className = "",
}) => {
  return (
    <div className={`rounded-md p-4 ${className}`}>
      <div className="flex items-center">
        <div
          className={`
          h-3 w-3 rounded-full mr-3
          ${
            isDetected
              ? "bg-green-500 animate-pulse"
              : "bg-amber-500 animate-ping opacity-75"
          }
        `}
        />

        <div className="flex-1">
          {isDetected && deviceName ? (
            <div className="space-y-1">
              <div>
                <span className="font-semibold text-green-700 text-lg">
                  {deviceName}
                </span>
              </div>
              {devicePath && (
                <div>
                  <span className="text-sm text-gray-600 font-mono bg-slate-100 px-2 py-1 rounded">
                    {devicePath}
                  </span>
                </div>
              )}
            </div>
          ) : (
            <span className="font-medium text-amber-700">{waitingMessage}</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default CardDetectionStatus;
