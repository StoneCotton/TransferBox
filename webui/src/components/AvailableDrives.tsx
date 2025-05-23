import React, { useState, useEffect, useCallback } from "react";

interface DriveInfo {
  path: string;
  name: string;
  total_space: number;
  free_space: number;
  used_space: number;
  total_space_gb: number;
  free_space_gb: number;
  used_space_gb: number;
  drive_type?: string;
  is_mounted: boolean;
  is_removable?: boolean;
}

interface AvailableDrivesResponse {
  success: boolean;
  drives: DriveInfo[];
  message?: string;
}

interface AvailableDrivesProps {
  apiBaseUrl?: string;
  onDriveSelect?: (drive: DriveInfo) => void;
}

const AvailableDrives: React.FC<AvailableDrivesProps> = ({
  apiBaseUrl = "http://127.0.0.1:8000",
  onDriveSelect,
}) => {
  const [drives, setDrives] = useState<DriveInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchDrives = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${apiBaseUrl}/api/drives`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: AvailableDrivesResponse = await response.json();

      if (data.success) {
        setDrives(data.drives);
        setLastUpdated(new Date());
      } else {
        throw new Error(data.message || "Failed to fetch drives");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      console.error("Error fetching drives:", err);
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchDrives();

    // Set up polling to refresh drives every 5 seconds
    const interval = setInterval(fetchDrives, 5000);

    return () => clearInterval(interval);
  }, [fetchDrives]);

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 GB";
    const gb = bytes / 1024 ** 3;
    return `${gb.toFixed(2)} GB`;
  };

  const getDriveIcon = (drive: DriveInfo): string => {
    if (drive.is_removable) return "💾";
    if (drive.drive_type === "NETWORK") return "🌐";
    if (drive.drive_type === "CDROM") return "💿";
    return "💽";
  };

  const getDriveTypeLabel = (drive: DriveInfo): string => {
    if (drive.is_removable) return "Removable";
    return drive.drive_type || "Fixed";
  };

  const getUsageColor = (usedPercent: number): string => {
    if (usedPercent < 70) return "bg-green-500";
    if (usedPercent < 90) return "bg-yellow-500";
    return "bg-red-500";
  };

  if (isLoading && drives.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center space-x-2 mb-4">
          <h3 className="text-lg font-semibold text-gray-800">
            Available Drives
          </h3>
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
        </div>
        <p className="text-gray-600">Loading drives...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-800">
          Available Drives
        </h3>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchDrives}
            disabled={isLoading}
            className="p-2 text-gray-600 hover:text-blue-600 disabled:opacity-50"
            title="Refresh drives"
          >
            <svg
              className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
          {lastUpdated && (
            <span className="text-xs text-gray-500">
              Updated: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-red-600 text-sm">Error: {error}</p>
        </div>
      )}

      {drives.length === 0 && !isLoading ? (
        <p className="text-gray-600">No drives detected</p>
      ) : (
        <div className="space-y-3">
          {drives.map((drive, index) => {
            const usedPercent =
              drive.total_space > 0
                ? (drive.used_space / drive.total_space) * 100
                : 0;

            return (
              <div
                key={index}
                className={`border rounded-lg p-4 transition-all ${
                  onDriveSelect
                    ? "cursor-pointer hover:border-blue-300 hover:shadow-sm"
                    : ""
                } ${
                  drive.is_mounted
                    ? "border-gray-200"
                    : "border-red-200 bg-red-50"
                }`}
                onClick={() => onDriveSelect && onDriveSelect(drive)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-lg">{getDriveIcon(drive)}</span>
                    <div>
                      <h4 className="font-medium text-gray-800">
                        {drive.name}
                      </h4>
                      <p className="text-xs text-gray-500">{drive.path}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                        drive.is_mounted
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {drive.is_mounted ? "Mounted" : "Unmounted"}
                    </span>
                    <p className="text-xs text-gray-500 mt-1">
                      {getDriveTypeLabel(drive)}
                    </p>
                  </div>
                </div>

                {drive.total_space > 0 && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm text-gray-600">
                      <span>Used: {formatBytes(drive.used_space)}</span>
                      <span>Free: {formatBytes(drive.free_space)}</span>
                      <span>Total: {formatBytes(drive.total_space)}</span>
                    </div>

                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-300 ${getUsageColor(
                          usedPercent
                        )}`}
                        style={{ width: `${Math.min(usedPercent, 100)}%` }}
                      ></div>
                    </div>

                    <p className="text-xs text-center text-gray-500">
                      {usedPercent.toFixed(1)}% used
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AvailableDrives;
