"use client";

import React from "react";

interface ProgressBarProps {
  progress: number; // 0-100
  showPercentage?: boolean;
  status?: string;
  variant?: "primary" | "success" | "warning" | "danger";
  height?: "sm" | "md" | "lg";
  animated?: boolean;
  className?: string;
}

const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  showPercentage = true,
  status,
  variant = "primary",
  height = "md",
  animated = true,
  className = "",
}) => {
  // Ensure progress is between 0-100
  const normalizedProgress = Math.max(0, Math.min(100, progress));

  const variantClasses = {
    primary: "bg-blue-600",
    success: "bg-green-600",
    warning: "bg-amber-500",
    danger: "bg-red-600",
  };

  const heightClasses = {
    sm: "h-2",
    md: "h-4",
    lg: "h-6",
  };

  const animationClass = animated ? "transition-all duration-300 ease-out" : "";

  return (
    <div className={`w-full ${className}`}>
      <div className="mb-1 flex justify-between items-center">
        {status && (
          <div className="text-sm font-medium text-slate-700">{status}</div>
        )}
        {showPercentage && (
          <div className="text-sm font-medium text-slate-700">
            {Math.round(normalizedProgress)}%
          </div>
        )}
      </div>
      <div
        className={`w-full bg-slate-200 rounded-full overflow-hidden ${heightClasses[height]}`}
      >
        <div
          className={`${variantClasses[variant]} ${heightClasses[height]} ${animationClass} rounded-full`}
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>
    </div>
  );
};

export default ProgressBar;
