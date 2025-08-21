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

  /**
   * Stop the current transfer operation
   */
  async stopTransfer(): Promise<ApiResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/stop-transfer`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error("Error stopping transfer:", error);
      return { success: false, message: "Network error" };
    }
  },

  /**
   * Shutdown the TransferBox application
   */
  async shutdown(): Promise<ApiResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/shutdown`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      // Note: Response might not arrive if server shuts down immediately
      if (response.ok) {
        const result = await response.json();
        return result;
      } else {
        return { success: false, message: "Shutdown request failed" };
      }
    } catch (error) {
      // Network error is expected if server shuts down quickly
      console.log("Shutdown request sent, server may have shut down:", error);
      return { success: true, message: "Shutdown initiated" };
    }
  },
};
