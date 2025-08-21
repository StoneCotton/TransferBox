import { apiService } from "@/services/api";
import type { AppMetadata, PathValidationResult, ApiResponse } from "@/types";

// Mock the constants
jest.mock("@/constants", () => ({
  API_BASE_URL: "http://localhost:8000",
}));

describe("apiService", () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();

    // Reset fetch mock
    (global.fetch as jest.Mock).mockClear();
  });

  describe("loadAppMetadata", () => {
    it("successfully loads app metadata", async () => {
      const mockMetadata: AppMetadata = {
        appName: "TransferBox",
        version: "1.0.0",
        author: "Test Author",
        description: "Test Description",
        license: "MIT",
        platform: "darwin",
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockMetadata,
      });

      const result = await apiService.loadAppMetadata();

      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/app-metadata"
      );
      expect(result).toEqual(mockMetadata);
    });

    it("returns null when response is not ok", async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      const consoleSpy = jest.spyOn(console, "warn").mockImplementation();

      const result = await apiService.loadAppMetadata();

      expect(result).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to load app metadata, using defaults"
      );

      consoleSpy.mockRestore();
    });

    it("returns null when fetch throws an error", async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error("Network error")
      );

      const consoleSpy = jest.spyOn(console, "warn").mockImplementation();

      const result = await apiService.loadAppMetadata();

      expect(result).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        "Error loading app metadata:",
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe("validatePath", () => {
    it("successfully validates a path", async () => {
      const mockResult: PathValidationResult = {
        is_valid: true,
        sanitized_path: "/valid/path",
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResult,
      });

      const result = await apiService.validatePath("/test/path");

      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/validate-path",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ path: "/test/path" }),
        }
      );
      expect(result).toEqual(mockResult);
    });

    it("returns invalid result when path validation fails", async () => {
      const mockResult: PathValidationResult = {
        is_valid: false,
        error_message: "Path does not exist",
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResult,
      });

      const result = await apiService.validatePath("/invalid/path");

      expect(result).toEqual(mockResult);
    });

    it("handles network errors gracefully", async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error("Network error")
      );

      const consoleSpy = jest.spyOn(console, "error").mockImplementation();

      const result = await apiService.validatePath("/test/path");

      expect(result).toEqual({
        is_valid: false,
        error_message: "Network error",
      });
      expect(consoleSpy).toHaveBeenCalledWith(
        "Error validating path:",
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe("setDestinationPath", () => {
    it("successfully sets destination path", async () => {
      const mockResponse: ApiResponse = {
        success: true,
        message: "Destination path set successfully",
        path: "/destination/path",
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await apiService.setDestinationPath("/destination/path");

      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/set-destination",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ path: "/destination/path" }),
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it("handles network errors gracefully", async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error("Network error")
      );

      const consoleSpy = jest.spyOn(console, "error").mockImplementation();

      const result = await apiService.setDestinationPath("/test/path");

      expect(result).toEqual({
        success: false,
        message: "Network error",
      });
      expect(consoleSpy).toHaveBeenCalledWith(
        "Error setting destination path:",
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe("stopTransfer", () => {
    it("successfully stops transfer", async () => {
      const mockResponse: ApiResponse = {
        success: true,
        message: "Transfer stopped successfully",
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await apiService.stopTransfer();

      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/stop-transfer",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it("handles network errors gracefully", async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error("Network error")
      );

      const consoleSpy = jest.spyOn(console, "error").mockImplementation();

      const result = await apiService.stopTransfer();

      expect(result).toEqual({
        success: false,
        message: "Network error",
      });
      expect(consoleSpy).toHaveBeenCalledWith(
        "Error stopping transfer:",
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe("shutdown", () => {
    it("successfully initiates shutdown", async () => {
      const mockResponse: ApiResponse = {
        success: true,
        message: "Shutdown initiated",
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await apiService.shutdown();

      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/shutdown",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it("handles non-ok response", async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      const result = await apiService.shutdown();

      expect(result).toEqual({
        success: false,
        message: "Shutdown request failed",
      });
    });

    it("handles network errors (expected during shutdown)", async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error("Network error")
      );

      const consoleSpy = jest.spyOn(console, "log").mockImplementation();

      const result = await apiService.shutdown();

      expect(result).toEqual({
        success: true,
        message: "Shutdown initiated",
      });
      expect(consoleSpy).toHaveBeenCalledWith(
        "Shutdown request sent, server may have shut down:",
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });
});
