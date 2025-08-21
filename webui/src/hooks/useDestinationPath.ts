import { useState, useCallback } from "react";
import { apiService } from "../services/api";

interface UseDestinationPathReturn {
  destinationPath: string;
  isPathValid: boolean | undefined;
  pathError: string;
  destinationSet: boolean;
  setDestinationPath: (path: string) => void;
  validateAndSetDestination: () => Promise<void>;
  resetDestination: () => void;
}

/**
 * Custom hook for managing destination path validation and setting
 * Handles path input, validation, and backend communication
 */
export const useDestinationPath = (
  onLog: (
    message: string,
    level?: "info" | "warning" | "error" | "success"
  ) => void,
  onStatusUpdate: (
    status: string,
    type?: "info" | "warning" | "error" | "success"
  ) => void
): UseDestinationPathReturn => {
  const [destinationPath, setDestinationPath] = useState("");
  const [isPathValid, setIsPathValid] = useState<boolean | undefined>(
    undefined
  );
  const [pathError, setPathError] = useState("");
  const [destinationSet, setDestinationSet] = useState(false);

  const validateAndSetDestination = useCallback(async () => {
    if (!destinationPath.trim()) {
      setPathError("Please enter a destination path");
      setIsPathValid(false);
      return;
    }

    onStatusUpdate("Validating path...");
    onLog("Validating destination path...", "info");

    const validation = await apiService.validatePath(destinationPath);

    if (validation.is_valid) {
      setIsPathValid(true);
      setPathError("");

      // Set the destination in the backend
      const result = await apiService.setDestinationPath(
        validation.sanitized_path!
      );

      if (result.success) {
        onStatusUpdate("Destination path set successfully", "success");
        setDestinationSet(true);
        onLog(`Destination set to: ${result.path}`, "success");
      } else {
        setPathError(result.message || "Failed to set destination");
        setIsPathValid(false);
        onStatusUpdate("Failed to set destination", "error");
        onLog(`Failed to set destination: ${result.message}`, "error");
      }
    } else {
      setIsPathValid(false);
      setPathError(validation.error_message || "Invalid path");
      onStatusUpdate("Path validation failed", "error");
      onLog(`Path validation failed: ${validation.error_message}`, "error");
    }
  }, [destinationPath, onLog, onStatusUpdate]);

  const resetDestination = useCallback(() => {
    setDestinationSet(false);
    setIsPathValid(undefined);
    setPathError("");
    onLog("Destination reset", "info");
  }, [onLog]);

  return {
    destinationPath,
    isPathValid,
    pathError,
    destinationSet,
    setDestinationPath,
    validateAndSetDestination,
    resetDestination,
  };
};
