"use client";

import React from "react";

interface StatusDisplayProps {
  status: string;
  type?: "info" | "warning" | "error" | "success";
  icon?: React.ReactNode;
  className?: string;
}

const StatusDisplay: React.FC<StatusDisplayProps> = ({
  status,
  type = "info",
  icon,
  className = "",
}) => {
  const typeClasses = {
    info: "bg-blue-50 border-blue-200 text-blue-800",
    warning: "bg-amber-50 border-amber-200 text-amber-800",
    error: "bg-red-50 border-red-200 text-red-800",
    success: "bg-green-50 border-green-200 text-green-800",
  };

  return (
    <div
      className={`
        border rounded-md p-4 flex items-center 
        ${typeClasses[type]}
        ${className}
      `}
    >
      {icon && <div className="mr-3">{icon}</div>}
      <div className="font-medium">{status}</div>
    </div>
  );
};

export default StatusDisplay;
