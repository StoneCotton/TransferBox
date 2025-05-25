"use client";

import React, { useState, useEffect, useCallback } from "react";
import Modal from "./Modal";
import Button from "./Button";

interface ConfigEditorProps {
  isOpen: boolean;
  onClose: () => void;
}

type ConfigValue = string | number | boolean | string[];

interface ConfigData {
  [key: string]: ConfigValue;
}

interface ConfigFieldInfo {
  displayName: string;
  description: string;
  section: string;
}

// Mapping of technical config keys to user-friendly names and descriptions
const CONFIG_FIELD_INFO: Record<string, ConfigFieldInfo> = {
  // File Handling
  rename_with_timestamp: {
    displayName: "Add Timestamp to Filename",
    description:
      "Automatically add a timestamp to file names to prevent duplicates and track when files were ingested",
    section: "File Handling",
  },
  preserve_original_filename: {
    displayName: "Keep Original Filename",
    description:
      "Preserve the original filename when adding timestamps (requires 'Add Timestamp to Filename' to be enabled)",
    section: "File Handling",
  },
  filename_template: {
    displayName: "Filename Template",
    description:
      "Template for renaming files. Use {original} for original name and {timestamp} for timestamp",
    section: "File Handling",
  },
  timestamp_format: {
    displayName: "Timestamp Format",
    description:
      "Format for timestamps in filenames (e.g., %Y%m%d_%H%M%S for YYYYMMDD_HHMMSS)",
    section: "File Handling",
  },
  create_mhl_files: {
    displayName: "Generate MHL Checksum Files",
    description:
      "Create Media Hash List (MHL) files for data integrity verification",
    section: "File Handling",
  },

  // Media Transfer
  media_only_transfer: {
    displayName: "Transfer Only Media Files",
    description:
      "Only transfer files with media extensions, ignoring other file types",
    section: "Media Transfer",
  },
  preserve_folder_structure: {
    displayName: "Keep Folder Structure",
    description: "Maintain the original folder structure from the source drive",
    section: "Media Transfer",
  },
  media_extensions: {
    displayName: "Media File Extensions",
    description:
      "List of file extensions considered as media files (e.g., .mp4, .mov, .wav)",
    section: "Media Transfer",
  },

  // Directory Structure
  create_date_folders: {
    displayName: "Create Date-Based Folders",
    description: "Organize files into folders based on their creation date",
    section: "Directory Structure",
  },
  date_folder_format: {
    displayName: "Date Folder Format",
    description:
      "Format for date-based folder names (e.g., %Y/%m/%d for YYYY/MM/DD)",
    section: "Directory Structure",
  },
  create_device_folders: {
    displayName: "Create Device-Based Folders",
    description: "Create separate folders for each source device or drive",
    section: "Directory Structure",
  },
  device_folder_template: {
    displayName: "Device Folder Template",
    description:
      "Template for device folder names. Use {device_name} for the device name",
    section: "Directory Structure",
  },

  // Proxy Generation
  generate_proxies: {
    displayName: "Generate Proxy Files",
    description:
      "Create lower-resolution proxy files for easier preview and editing",
    section: "Proxy Generation",
  },
  proxy_subfolder: {
    displayName: "Proxy Subfolder Name",
    description: "Name of the subfolder where proxy files will be stored",
    section: "Proxy Generation",
  },
  include_proxy_watermark: {
    displayName: "Add Watermark to Proxies",
    description:
      "Include a watermark on generated proxy files to identify them as proxies",
    section: "Proxy Generation",
  },
  proxy_watermark_path: {
    displayName: "Watermark Image Path",
    description: "Path to the watermark image file to use for proxy files",
    section: "Proxy Generation",
  },

  // Sound Settings
  enable_sounds: {
    displayName: "Enable Sound Notifications",
    description: "Play audio notifications for transfer completion and errors",
    section: "Sound Settings",
  },
  sound_volume: {
    displayName: "Sound Volume",
    description: "Volume level for sound notifications (0-100)",
    section: "Sound Settings",
  },

  // Advanced Settings
  buffer_size: {
    displayName: "Transfer Buffer Size",
    description:
      "Size of the memory buffer used for file transfers (in bytes). Higher values may improve performance",
    section: "Advanced Settings",
  },
  verify_transfers: {
    displayName: "Verify File Integrity",
    description:
      "Check file integrity after transfer using checksums to ensure data accuracy",
    section: "Advanced Settings",
  },
  max_transfer_threads: {
    displayName: "Maximum Transfer Threads",
    description:
      "Number of parallel file transfer threads. More threads may improve speed but use more resources",
    section: "Advanced Settings",
  },

  // Logging Settings
  log_level: {
    displayName: "Log Detail Level",
    description:
      "Amount of detail to include in log files (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    section: "Logging Settings",
  },
  log_file_rotation: {
    displayName: "Log File Rotation Count",
    description: "Number of old log files to keep before deleting them",
    section: "Logging Settings",
  },
  log_file_max_size: {
    displayName: "Maximum Log File Size (MB)",
    description:
      "Maximum size of each log file in megabytes before creating a new one",
    section: "Logging Settings",
  },

  // User Experience
  tutorial_mode: {
    displayName: "Enable Tutorial Mode",
    description: "Show helpful tips and guidance for first-time users",
    section: "User Experience",
  },
};

const ConfigEditor: React.FC<ConfigEditorProps> = ({ isOpen, onClose }) => {
  const [config, setConfig] = useState<ConfigData>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const loadConfig = useCallback(async () => {
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
      setError(
        err instanceof Error ? err.message : "Failed to load configuration"
      );
    } finally {
      setLoading(false);
    }
  }, [API_BASE_URL]);

  // Load config when modal opens
  useEffect(() => {
    if (isOpen) {
      loadConfig();
    }
  }, [isOpen, loadConfig]);

  const saveConfig = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/config`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ config }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to save configuration");
      }

      if (data.success) {
        setSuccess("Configuration saved successfully!");
        // Update local config with the response
        if (data.config) {
          setConfig(data.config);
        }
      } else {
        throw new Error("Invalid response format");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save configuration"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleInputChange = (key: string, value: ConfigValue) => {
    setConfig((prev) => ({
      ...prev,
      [key]: value,
    }));
    // Clear success message when making changes
    setSuccess(null);
  };

  const handleArrayChange = (key: string, index: number, value: string) => {
    setConfig((prev) => {
      const currentArray = prev[key];
      if (Array.isArray(currentArray)) {
        const newArray = [...currentArray];
        newArray[index] = value;
        return {
          ...prev,
          [key]: newArray,
        };
      }
      return prev;
    });
    setSuccess(null);
  };

  const addArrayItem = (key: string) => {
    setConfig((prev) => {
      const currentArray = prev[key];
      if (Array.isArray(currentArray)) {
        return {
          ...prev,
          [key]: [...currentArray, ""],
        };
      }
      return {
        ...prev,
        [key]: [""],
      };
    });
  };

  const removeArrayItem = (key: string, index: number) => {
    setConfig((prev) => {
      const currentArray = prev[key];
      if (Array.isArray(currentArray)) {
        const newArray = [...currentArray];
        newArray.splice(index, 1);
        return {
          ...prev,
          [key]: newArray,
        };
      }
      return prev;
    });
  };

  const renderConfigField = (key: string, value: ConfigValue) => {
    const fieldInfo = CONFIG_FIELD_INFO[key];
    const displayName = fieldInfo?.displayName || key;
    const description = fieldInfo?.description;

    const isBoolean = typeof value === "boolean";
    const isNumber = typeof value === "number";
    const isArray = Array.isArray(value);
    const isString = typeof value === "string";

    if (isBoolean) {
      return (
        <div key={key} className="mb-4">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={value}
              onChange={(e) => handleInputChange(key, e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-medium text-slate-700">
              {displayName}
            </span>
          </label>
          {description && (
            <p className="text-xs text-slate-500 mt-1 ml-6">{description}</p>
          )}
        </div>
      );
    }

    if (isNumber) {
      return (
        <div key={key} className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            {displayName}
          </label>
          <input
            type="number"
            value={value}
            onChange={(e) =>
              handleInputChange(key, parseInt(e.target.value) || 0)
            }
            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          {description && (
            <p className="text-xs text-slate-500 mt-1">{description}</p>
          )}
        </div>
      );
    }

    if (isArray) {
      return (
        <div key={key} className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            {displayName}
          </label>
          {description && (
            <p className="text-xs text-slate-500 mb-2">{description}</p>
          )}
          <div className="space-y-2">
            {value.map((item: string, index: number) => (
              <div key={index} className="flex items-center space-x-2">
                <input
                  type="text"
                  value={item}
                  onChange={(e) =>
                    handleArrayChange(key, index, e.target.value)
                  }
                  className="flex-1 px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <Button
                  label="Remove"
                  onClick={() => removeArrayItem(key, index)}
                  size="sm"
                  variant="danger"
                />
              </div>
            ))}
            <Button
              label="Add Item"
              onClick={() => addArrayItem(key)}
              size="sm"
              variant="secondary"
            />
          </div>
        </div>
      );
    }

    if (isString) {
      // Special handling for log_level to show dropdown
      if (key === "log_level") {
        const logLevels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
        return (
          <div key={key} className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {displayName}
            </label>
            <select
              value={value}
              onChange={(e) => handleInputChange(key, e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {logLevels.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
            {description && (
              <p className="text-xs text-slate-500 mt-1">{description}</p>
            )}
          </div>
        );
      }

      return (
        <div key={key} className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            {displayName}
          </label>
          <input
            type="text"
            value={value}
            onChange={(e) => handleInputChange(key, e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          {description && (
            <p className="text-xs text-slate-500 mt-1">{description}</p>
          )}
        </div>
      );
    }

    return null;
  };

  // Group config fields by section based on CONFIG_FIELD_INFO
  const configSections = Object.keys(config).reduce((sections, key) => {
    if (key === "version") return sections; // Skip version field in UI

    const fieldInfo = CONFIG_FIELD_INFO[key];
    const sectionName = fieldInfo?.section || "Other Settings";

    if (!sections[sectionName]) {
      sections[sectionName] = [];
    }
    sections[sectionName].push(key);
    return sections;
  }, {} as Record<string, string[]>);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Configuration Editor">
      <div className="max-h-96 overflow-y-auto">
        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-slate-600">Loading configuration...</p>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            <p>{error}</p>
            <Button
              label="Retry"
              onClick={loadConfig}
              size="sm"
              variant="primary"
              className="mt-2"
            />
          </div>
        ) : (
          <div className="space-y-6">
            {Object.entries(configSections).map(([sectionName, keys]) => (
              <div
                key={sectionName}
                className="border border-slate-200 rounded-lg p-4"
              >
                <h3 className="text-lg font-semibold text-slate-800 mb-4">
                  {sectionName}
                </h3>
                <div className="space-y-2">
                  {keys.map((key) => {
                    if (config.hasOwnProperty(key)) {
                      return renderConfigField(key, config[key]);
                    }
                    return null;
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-6 pt-4 border-t">
        {/* Show success/error messages in the footer area where they're always visible */}
        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4">
            {success}
          </div>
        )}
        {error && !loading && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            <p>{error}</p>
            <Button
              label="Retry"
              onClick={loadConfig}
              size="sm"
              variant="primary"
              className="mt-2"
            />
          </div>
        )}

        <div className="flex justify-end space-x-3">
          <Button
            label="Cancel"
            onClick={onClose}
            variant="secondary"
            disabled={saving}
          />
          <Button
            label={saving ? "Saving..." : "Save Changes"}
            onClick={saveConfig}
            variant="primary"
            disabled={saving || loading}
          />
        </div>
      </div>
    </Modal>
  );
};

export default ConfigEditor;
