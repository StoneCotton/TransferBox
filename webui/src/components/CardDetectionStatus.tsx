"use client";

import React from "react";

interface CardDetectionStatusProps {
  isDetected: boolean;
  deviceName?: string;
  waitingMessage?: string;
  detectedMessage?: string;
  className?: string;
}

const CardDetectionStatus: React.FC<CardDetectionStatusProps> = ({
  isDetected,
  deviceName,
  waitingMessage = "Waiting for source drive...",
  detectedMessage = "Source drive detected:",
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

        <div>
          {isDetected ? (
            <div>
              <span className="font-medium text-green-700">
                {detectedMessage}
              </span>
              {deviceName && (
                <span className="ml-2 font-mono bg-slate-100 px-2 py-1 rounded text-sm">
                  {deviceName}
                </span>
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
