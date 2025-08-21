import { useState, useEffect, useCallback } from "react";
import type { AppMetadata } from "../types";
import { apiService } from "../services/api";

interface UseAppMetadataReturn {
  appMetadata: AppMetadata;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const DEFAULT_METADATA: AppMetadata = {
  appName: "TransferBox",
  version: "1.0.0",
  author: "Unknown",
  description: "File Transfer Application",
  license: "MIT",
  platform: "unknown",
};

/**
 * Custom hook for loading and managing application metadata
 * Handles loading from backend with fallback to defaults
 */
export const useAppMetadata = (): UseAppMetadataReturn => {
  const [appMetadata, setAppMetadata] = useState<AppMetadata>(DEFAULT_METADATA);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMetadata = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const metadata = await apiService.loadAppMetadata();
      if (metadata) {
        setAppMetadata(metadata);
      } else {
        setAppMetadata(DEFAULT_METADATA);
      }
    } catch (err) {
      console.error("Failed to load app metadata:", err);
      setError(err instanceof Error ? err.message : "Failed to load metadata");
      setAppMetadata(DEFAULT_METADATA);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetadata();
  }, [loadMetadata]);

  return {
    appMetadata,
    isLoading,
    error,
    refetch: loadMetadata,
  };
};
