"use client";

import React from "react";

interface ButtonProps {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "success" | "danger" | "warning";
  size?: "sm" | "md" | "lg";
  fullWidth?: boolean;
  className?: string;
  icon?: React.ReactNode;
  type?: "button" | "submit" | "reset";
}

const Button: React.FC<ButtonProps> = ({
  label,
  onClick,
  disabled = false,
  variant = "primary",
  size = "md",
  fullWidth = false,
  className = "",
  icon,
  type = "button",
}) => {
  const baseClasses =
    "inline-flex items-center justify-center rounded-md font-medium transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1";

  const variantClasses = {
    primary:
      "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 focus:ring-blue-500 disabled:bg-blue-300 border border-transparent",
    secondary:
      "bg-white text-slate-700 hover:bg-slate-50 active:bg-slate-100 focus:ring-slate-500 disabled:text-slate-400 border border-slate-300 hover:border-slate-400",
    success:
      "bg-green-600 text-white hover:bg-green-700 active:bg-green-800 focus:ring-green-500 disabled:bg-green-300 border border-transparent",
    danger:
      "bg-red-600 text-white hover:bg-red-700 active:bg-red-800 focus:ring-red-500 disabled:bg-red-300 border border-transparent",
    warning:
      "bg-amber-500 text-white hover:bg-amber-600 active:bg-amber-700 focus:ring-amber-400 disabled:bg-amber-200 border border-transparent",
  };

  const sizeClasses = {
    sm: "px-2 py-1 text-xs",
    md: "px-3 py-1.5 text-sm",
    lg: "px-4 py-2 text-base",
  };

  const widthClass = fullWidth ? "w-full" : "";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`
        ${baseClasses}
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${widthClass}
        ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}
        ${className}
      `}
    >
      {icon && <span className="mr-1.5">{icon}</span>}
      {label}
    </button>
  );
};

export default Button;
