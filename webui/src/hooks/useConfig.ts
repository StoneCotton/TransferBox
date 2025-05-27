import { useState, useEffect, useCallback } from "react";
import { API_BASE_URL } from "../constants";

interface ConfigData {
  tutorial_mode?: boolean;
  [key: string]: string | number | boolean | string[] | undefined;
}

interface UseConfigReturn {
  config: ConfigData | null;
  loading: boolean;
  error: string | null;
  refetchConfig: () => Promise<void>;
}

/**
 * Custom hook for managing application configuration
 * Fetches config from the API and provides loading/error states
 */
export const useConfig = (): UseConfigReturn => {
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/config`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to load configuration");
      }

      if (data.success && data.config) {
        setConfig(data.config);
      } else {
        throw new Error("Invalid response format");
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to load configuration";
      setError(errorMessage);
      console.error("Config fetch error:", errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const refetchConfig = useCallback(async () => {
    await fetchConfig();
  }, [fetchConfig]);

  // Load config on mount
  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  return {
    config,
    loading,
    error,
    refetchConfig,
  };
};
