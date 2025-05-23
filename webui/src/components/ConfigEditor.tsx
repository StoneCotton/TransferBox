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
            <span className="text-sm font-medium text-slate-700">{key}</span>
          </label>
        </div>
      );
    }

    if (isNumber) {
      return (
        <div key={key} className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            {key}
          </label>
          <input
            type="number"
            value={value}
            onChange={(e) =>
              handleInputChange(key, parseInt(e.target.value) || 0)
            }
            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      );
    }

    if (isArray) {
      return (
        <div key={key} className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            {key}
          </label>
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
      return (
        <div key={key} className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            {key}
          </label>
          <input
            type="text"
            value={value}
            onChange={(e) => handleInputChange(key, e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      );
    }

    return null;
  };

  const configSections = {
    "File Handling": [
      "rename_with_timestamp",
      "preserve_original_filename",
      "filename_template",
      "timestamp_format",
      "create_mhl_files",
    ],
    "Media Transfer": [
      "media_only_transfer",
      "preserve_folder_structure",
      "media_extensions",
    ],
    "Directory Structure": [
      "create_date_folders",
      "date_folder_format",
      "create_device_folders",
      "device_folder_template",
    ],
    "Proxy Generation": [
      "generate_proxies",
      "proxy_subfolder",
      "include_proxy_watermark",
      "proxy_watermark_path",
    ],
    "Sound Settings": ["enable_sounds", "sound_volume"],
    "Advanced Settings": [
      "buffer_size",
      "verify_transfers",
      "max_transfer_threads",
    ],
    "Logging Settings": ["log_level", "log_file_rotation", "log_file_max_size"],
    "User Experience": ["tutorial_mode"],
  };

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
            {success && (
              <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
                {success}
              </div>
            )}

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

      <div className="flex justify-end space-x-3 mt-6 pt-4 border-t">
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
    </Modal>
  );
};

export default ConfigEditor;
