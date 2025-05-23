import type { AppMetadata, PathValidationResult, ApiResponse } from "../types";
import { API_BASE_URL } from "../constants";

/**
 * API service for TransferBox application
 * Centralizes all HTTP API calls to the backend
 */

export const apiService = {
  /**
   * Load application metadata from the backend
   */
  async loadAppMetadata(): Promise<AppMetadata | null> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/app-metadata`);
      if (response.ok) {
        const metadata = await response.json();
        console.log(
          `Loaded app metadata: ${metadata.appName} v${metadata.version}`
        );
        return metadata;
      } else {
        console.warn("Failed to load app metadata, using defaults");
        return null;
      }
    } catch (error) {
      console.warn("Error loading app metadata:", error);
      return null;
    }
  },

  /**
   * Validate a file system path
   */
  async validatePath(path: string): Promise<PathValidationResult> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/validate-path`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ path }),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error("Error validating path:", error);
      return { is_valid: false, error_message: "Network error" };
    }
  },

  /**
   * Set the destination path for file transfers
   */
  async setDestinationPath(path: string): Promise<ApiResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/set-destination`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ path }),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error("Error setting destination path:", error);
      return { success: false, message: "Network error" };
    }
  },
};
