"use client";

import React, { useState } from "react";

interface PathInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  isValid?: boolean;
  errorMessage?: string;
  examplePath?: string;
  disabled?: boolean;
  onSubmit?: () => void;
}

const PathInput: React.FC<PathInputProps> = ({
  value,
  onChange,
  placeholder = "Enter destination path...",
  isValid,
  errorMessage,
  examplePath,
  disabled = false,
  onSubmit,
}) => {
  const [isFocused, setIsFocused] = useState(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && onSubmit) {
      onSubmit();
    }
  };

  return (
    <div className="w-full">
      <div
        className={`
          relative border rounded-md overflow-hidden transition-all shadow-sm
          ${disabled ? "bg-slate-100 opacity-70" : "bg-white"}
          ${
            isValid === false
              ? "border-red-500"
              : isFocused
              ? "border-blue-500 ring-1 ring-blue-500"
              : "border-slate-300 hover:border-slate-400"
          }
        `}
      >
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full px-3 py-1.5 text-sm focus:outline-none disabled:cursor-not-allowed"
        />
      </div>

      {isValid === false && errorMessage && (
        <div className="mt-1 text-red-500 text-xs">{errorMessage}</div>
      )}

      {examplePath && (
        <div className="mt-1 text-slate-500 text-xs">
          Example: <span className="font-mono">{examplePath}</span>
        </div>
      )}
    </div>
  );
};

export default PathInput;
