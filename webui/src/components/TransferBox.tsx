"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Header from "./Header";
import Button from "./Button";
import PathInput from "./PathInput";
import StatusDisplay from "./StatusDisplay";
import LogContainer from "./LogContainer";
import CardDetectionStatus from "./CardDetectionStatus";
import TutorialGuide from "./TutorialGuide";
import Modal from "./Modal";
import FileTransferProgress from "./FileTransferProgress";
import ConfigEditor from "./ConfigEditor";
import AvailableDrives from "./AvailableDrives";

// Import the LogEntry type from LogContainer to ensure consistency
import type { LogEntry } from "./LogContainer";

// App metadata interface
interface AppMetadata {
  appName: string;
  version: string;
  author: string;
  description: string;
  license: string;
}

// Default app metadata as fallback
const DEFAULT_APP_DATA: AppMetadata = {
  appName: "TransferBox",
  version: "1.4.0",
  author: "Tyler Saari",
  description: "A utility for secure file transfers with verification",
  license: "MIT",
};

const TUTORIAL_STEPS = [
  {
    id: "step1",
    title: "Welcome to TransferBox",
    description:
      "This tutorial will guide you through the process of transferring files from your SD card to your computer.",
  },
  {
    id: "step2",
    title: "Choose Destination",
    description:
      "First, select where you want to save your files. Enter a valid path to a directory on your computer.",
  },
  {
    id: "step3",
    title: "Insert SD Card",
    description:
      "Insert your SD card into your computer. TransferBox will automatically detect it.",
  },
  {
    id: "step4",
    title: "Transfer Files",
    description:
      "Once your SD card is detected, the transfer will begin automatically. You can monitor the progress here.",
  },
];

// Store whether the tutorial has been shown
const TUTORIAL_SHOWN_KEY = "transferbox_tutorial_shown";

// WebSocket message types
interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

// Transfer progress data structure from backend
type BackendTransferProgress = {
  current_file: string;
  file_number: number;
  total_files: number;
  bytes_transferred: number;
  total_bytes: number;
  total_transferred: number;
  total_size: number;
  current_file_progress: number;
  overall_progress: number;
  status: string;
  proxy_progress: number;
  proxy_file_number: number;
  proxy_total_files: number;
  speed_bytes_per_sec: number;
  eta_seconds: number;
  total_elapsed: number;
  file_elapsed: number;
  checksum_elapsed: number;
};

const TransferBox: React.FC = () => {
  // State
  const [destinationPath, setDestinationPath] = useState("");
  const [isPathValid, setIsPathValid] = useState<boolean | undefined>(
    undefined
  );
  const [pathError, setPathError] = useState("");
  const [currentStatus, setCurrentStatus] = useState("Connecting...");
  const [statusType, setStatusType] = useState<
    "info" | "warning" | "error" | "success"
  >("info");
  const [isCardDetected, setIsCardDetected] = useState(false);
  const [deviceName, setDeviceName] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showTutorialModal, setShowTutorialModal] = useState(false);
  const [tutorialStep, setTutorialStep] = useState(0);
  const [, setHasSeenTutorial] = useState(true);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [appMetadata, setAppMetadata] = useState<AppMetadata>(DEFAULT_APP_DATA);

  // Transfer progress state - connected to backend
  const [transferProgress, setTransferProgress] =
    useState<BackendTransferProgress | null>(null);
  const [isTransferring, setIsTransferring] = useState(false);
  const [transferError, setTransferError] = useState<string | null>(null);
  const [, setTransferState] = useState<
    "idle" | "transferring" | "completed" | "failed"
  >("idle");
  const [destinationSet, setDestinationSet] = useState(false);

  // WebSocket connection
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // API base URL
  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  // Load app metadata from backend
  const loadAppMetadata = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/app-metadata`);
      if (response.ok) {
        const metadata = await response.json();
        setAppMetadata(metadata);
        console.log(
          `Loaded app metadata: ${metadata.appName} v${metadata.version}`
        );
      } else {
        console.warn("Failed to load app metadata, using defaults");
      }
    } catch (error) {
      console.warn("Error loading app metadata:", error);
      // Keep using default values
    }
  }, [API_BASE_URL]);

  // Check local storage for tutorial
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const tutorialShown = localStorage.getItem(TUTORIAL_SHOWN_KEY);
        if (tutorialShown === "true") {
          setHasSeenTutorial(true);
        } else {
          setHasSeenTutorial(false);
          setShowTutorialModal(true);
        }
      } catch (error) {
        console.error("Error accessing localStorage:", error);
        setShowTutorialModal(true);
      }
    }

    // Load app metadata
    loadAppMetadata();
  }, [loadAppMetadata]);

  // WebSocket connection and management
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const wsUrl = `ws://127.0.0.1:8000/ws`;
        console.log("Connecting to WebSocket:", wsUrl);

        wsRef.current = new WebSocket(wsUrl);

        wsRef.current.onopen = () => {
          console.log("WebSocket connected");
          setIsConnected(true);
          setCurrentStatus("Connected to TransferBox");
          setStatusType("info");
          addLog("Connected to TransferBox", "info");

          // Clear any reconnection timeout
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
          }
        };

        wsRef.current.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            handleWebSocketMessage(message);
          } catch (error) {
            console.error("Error parsing WebSocket message:", error);
          }
        };

        wsRef.current.onclose = () => {
          console.log("WebSocket disconnected");
          setIsConnected(false);
          setCurrentStatus("Disconnected from TransferBox");
          setStatusType("warning");

          // Attempt to reconnect after 3 seconds
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log("Attempting to reconnect...");
            connectWebSocket();
          }, 3000);
        };

        wsRef.current.onerror = (error) => {
          console.error("WebSocket error:", error);
          setCurrentStatus("Connection error");
          setStatusType("error");
        };
      } catch (error) {
        console.error("Error creating WebSocket:", error);
        setCurrentStatus("Failed to connect");
        setStatusType("error");
      }
    };

    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle WebSocket messages from backend
  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    console.log("Received WebSocket message:", message);

    switch (message.type) {
      case "initial_state":
        // Handle initial state from backend
        const initialData = message.data as {
          status?: string;
          errors?: string[];
          progress?: BackendTransferProgress;
        };
        if (initialData.status) {
          setCurrentStatus(initialData.status);
          setStatusType("info");
        }
        if (initialData.errors && initialData.errors.length > 0) {
          initialData.errors.forEach((error: string) => {
            addLog(error, "error");
          });
        }
        if (initialData.progress) {
          setTransferProgress(initialData.progress);
          setIsTransferring(initialData.progress.status !== "READY");
        }
        break;

      case "status":
        const statusData = message.data as { message: string };
        setCurrentStatus(statusData.message);

        // Update card detection based on status message
        if (statusData.message.toLowerCase().includes("card detected")) {
          setIsCardDetected(true);
          setDeviceName("SD Card");
        } else if (
          statusData.message.toLowerCase().includes("waiting for source") ||
          statusData.message.toLowerCase().includes("no source drive") ||
          statusData.message.toLowerCase().includes("source drive removed")
        ) {
          setIsCardDetected(false);
          setDeviceName("");
        }

        // Set appropriate status type
        if (
          statusData.message.toLowerCase().includes("error") ||
          statusData.message.toLowerCase().includes("failed")
        ) {
          setStatusType("error");
        } else if (
          statusData.message.toLowerCase().includes("complete") ||
          statusData.message.toLowerCase().includes("success")
        ) {
          setStatusType("success");
        } else if (statusData.message.toLowerCase().includes("warning")) {
          setStatusType("warning");
        } else {
          setStatusType("info");
        }

        addLog(statusData.message, "info");
        break;

      case "progress":
        const progressData = message.data as BackendTransferProgress;
        console.log("Progress data received:", progressData);
        setTransferProgress(progressData);

        // Update transfer state and UI based on progress status
        const status = progressData.status;
        console.log("Transfer status:", status);

        if (
          status === "COPYING" ||
          status === "CHECKSUMMING" ||
          status === "GENERATING_PROXY" ||
          status === "VERIFYING"
        ) {
          setIsTransferring(true);
          setTransferState("transferring");
          // Don't automatically set card as detected during transfer
          // Card detection should only be based on actual hardware detection events

          // Update status message based on current operation
          let statusMessage = "";
          switch (status) {
            case "COPYING":
              statusMessage = `Copying files... (${progressData.file_number}/${progressData.total_files})`;
              break;
            case "CHECKSUMMING":
              statusMessage = `Verifying files... (${progressData.file_number}/${progressData.total_files})`;
              break;
            case "GENERATING_PROXY":
              statusMessage = `Generating proxies... (${progressData.proxy_file_number}/${progressData.proxy_total_files})`;
              break;
            case "VERIFYING":
              statusMessage = "Verifying transfer...";
              break;
          }
          setCurrentStatus(statusMessage);
          setStatusType("info");
        } else if (status === "SUCCESS") {
          setIsTransferring(false);
          setTransferState("completed");
          setStatusType("success");
          setCurrentStatus("Transfer completed successfully");
          setIsCardDetected(false);
          setDeviceName("");
          // Reset destination after successful transfer
          setDestinationSet(false);
          setIsPathValid(undefined);
          addLog("Transfer completed successfully", "success");
        } else if (status === "ERROR") {
          setIsTransferring(false);
          setTransferState("failed");
          setStatusType("error");
          setCurrentStatus("Transfer failed");
          setTransferError("Transfer failed");
          setIsCardDetected(false);
          setDeviceName("");
          // Reset destination after failed transfer
          setDestinationSet(false);
          setIsPathValid(undefined);
          addLog("Transfer failed", "error");
        }
        break;

      case "error":
        const errorData = message.data as { message: string };
        setTransferError(errorData.message);
        setTransferState("failed");
        setStatusType("error");
        setIsTransferring(false);
        setIsCardDetected(false);
        setDeviceName("");
        // Reset destination after error
        setDestinationSet(false);
        setIsPathValid(undefined);
        addLog(errorData.message, "error");
        break;

      case "clear":
        const clearData = message.data as { preserve_errors?: boolean };
        if (!clearData.preserve_errors) {
          setTransferError(null);
          // Clear logs except errors if preserve_errors is false
          setLogs((prev) => prev.filter((log) => log.level !== "error"));
        }
        setCurrentStatus("");
        setTransferProgress(null);
        setIsTransferring(false);
        setIsCardDetected(false);
        setDeviceName("");
        break;

      case "pong":
        // Handle ping/pong for connection keepalive
        break;

      default:
        console.log("Unknown WebSocket message type:", message.type);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // API functions
  const validatePath = async (path: string) => {
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
  };

  const setDestinationPathAPI = async (
    path: string
  ): Promise<{ success: boolean; message?: string; path?: string }> => {
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
  };

  // Event handlers
  const handleDestinationSubmit = async () => {
    if (!destinationPath.trim()) {
      setPathError("Please enter a destination path");
      setIsPathValid(false);
      return;
    }

    setCurrentStatus("Validating path...");
    addLog("Validating destination path...", "info");

    const validation = await validatePath(destinationPath);

    if (validation.is_valid) {
      setIsPathValid(true);
      setPathError("");

      // Set the destination in the backend
      const result = await setDestinationPathAPI(validation.sanitized_path);

      if (result.success) {
        setCurrentStatus("Destination path set successfully");
        setStatusType("success");
        setDestinationSet(true);
        addLog(`Destination set to: ${result.path}`, "success");
      } else {
        setPathError(result.message || "Failed to set destination");
        setIsPathValid(false);
        setStatusType("error");
        addLog(`Failed to set destination: ${result.message}`, "error");
      }
    } else {
      setIsPathValid(false);
      setPathError(validation.error_message || "Invalid path");
      setStatusType("error");
      addLog(`Path validation failed: ${validation.error_message}`, "error");
    }
  };

  const resetTransfer = () => {
    setTransferError(null);
    setTransferState("idle");
    setIsTransferring(false);
    setTransferProgress(null);
    setStatusType("info");
    setCurrentStatus("Ready for transfer");
    setDestinationSet(false);
    setIsPathValid(undefined);
    setIsCardDetected(false);
    setDeviceName("");
    addLog("Transfer reset", "info");
  };

  const addLog = useCallback(
    (
      message: string,
      level: "info" | "warning" | "error" | "success" = "info"
    ) => {
      const newLog: LogEntry = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        message,
        timestamp: new Date().toLocaleString(),
        level,
      };
      setLogs((prev) => [...prev, newLog]);
    },
    []
  );

  // Tutorial handlers
  const handleTutorialNext = () => {
    setTutorialStep((prev) => Math.min(prev + 1, TUTORIAL_STEPS.length - 1));
  };

  const handleTutorialPrevious = () => {
    setTutorialStep((prev) => Math.max(prev - 1, 0));
  };

  const handleTutorialComplete = () => {
    setShowTutorialModal(false);
    setTutorialStep(0);
    try {
      localStorage.setItem(TUTORIAL_SHOWN_KEY, "true");
      setHasSeenTutorial(true);
    } catch (error) {
      console.error("Error saving tutorial state:", error);
    }
  };

  const handleShowTutorial = () => {
    setTutorialStep(0);
    setShowTutorialModal(true);
  };

  const handleSkipTutorial = () => {
    handleTutorialComplete();
  };

  const resetTutorialState = () => {
    try {
      localStorage.removeItem(TUTORIAL_SHOWN_KEY);
      setHasSeenTutorial(false);
      addLog("Tutorial state reset - refresh to see tutorial", "info");
    } catch (error) {
      console.error("Error resetting tutorial state:", error);
    }
  };

  const handleShowConfig = () => {
    setShowConfigModal(true);
  };

  const handleCloseConfig = () => {
    setShowConfigModal(false);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <Header
        appName={appMetadata.appName}
        version={appMetadata.version}
        author={appMetadata.author}
        onShowTutorial={handleShowTutorial}
        onShowConfig={handleShowConfig}
      />

      <main className="container mx-auto p-4 md:p-6">
        {/* Dev button for testing - remove in production */}
        {process.env.NODE_ENV === "development" && (
          <div className="mb-4 flex gap-2">
            <Button
              label="Reset Tutorial State"
              onClick={resetTutorialState}
              size="sm"
              variant="secondary"
            />
            <div
              className={`px-3 py-1 rounded text-sm ${
                isConnected
                  ? "bg-green-100 text-green-800"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {isConnected ? "Connected" : "Disconnected"}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Left Column - Input and Status */}
          <div className="md:col-span-2 space-y-6">
            <div className="bg-white p-6 rounded-lg shadow-sm">
              <h2 className="text-xl font-semibold mb-4">Transfer Setup</h2>

              <div className="mb-6">
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Destination Path
                </label>
                <div className="flex items-start">
                  <div className="flex-grow">
                    <PathInput
                      value={destinationPath}
                      onChange={setDestinationPath}
                      isValid={isPathValid}
                      errorMessage={pathError}
                      examplePath="/Volumes/External/Media"
                      onSubmit={handleDestinationSubmit}
                    />
                  </div>
                  <div className="ml-2 flex-shrink-0 self-start flex gap-2">
                    <Button
                      label={destinationSet ? "Set ✓" : "Set"}
                      onClick={handleDestinationSubmit}
                      size="md"
                      disabled={
                        !isConnected || destinationSet || isTransferring
                      }
                      variant={destinationSet ? "success" : "primary"}
                    />
                    {destinationSet && !isTransferring && (
                      <Button
                        label="Reset"
                        onClick={() => {
                          setDestinationSet(false);
                          setIsPathValid(undefined);
                          addLog("Destination reset", "info");
                        }}
                        size="md"
                        variant="secondary"
                      />
                    )}
                  </div>
                </div>
              </div>

              <StatusDisplay
                status={currentStatus}
                type={statusType}
                className="mb-6"
              />

              <CardDetectionStatus
                isDetected={isCardDetected}
                deviceName={deviceName}
                className="mb-6"
              />

              {/* Display error message if transfer failed */}
              {transferError && (
                <div className="bg-red-50 border-2 border-red-500 text-red-800 p-4 mb-6 rounded-md">
                  <div className="flex items-center mb-2">
                    <svg
                      className="h-6 w-6 text-red-600 mr-2"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                      />
                    </svg>
                    <h3 className="text-lg font-semibold">Transfer Error</h3>
                  </div>
                  <p className="mb-3">{transferError}</p>
                  <p className="text-sm mb-3">
                    The transfer was interrupted and file data may be incomplete
                    or corrupted. Please reconnect the card and try again.
                  </p>
                  <Button
                    label="Dismiss & Reset"
                    onClick={resetTransfer}
                    variant="danger"
                    size="sm"
                  />
                </div>
              )}

              {/* Transfer Progress Display */}
              {transferProgress && isTransferring && (
                <div className="space-y-5 mb-6">
                  {/* Overall Transfer Progress */}
                  <FileTransferProgress
                    title="Total Transfer Progress"
                    progress={transferProgress.overall_progress || 0}
                    itemCount={{
                      current: transferProgress.file_number || 0,
                      total: transferProgress.total_files || 0,
                    }}
                    size={{
                      transferred: transferProgress.total_transferred || 0,
                      total: transferProgress.total_size || 0,
                    }}
                    speed={transferProgress.speed_bytes_per_sec || 0}
                    time={{
                      elapsed: transferProgress.total_elapsed || 0,
                      remaining: transferProgress.eta_seconds || 0,
                    }}
                  />

                  {/* File Transfer Progress - Show when copying */}
                  {transferProgress.current_file &&
                    transferProgress.status === "COPYING" && (
                      <FileTransferProgress
                        title="File Transfer Progress"
                        progress={transferProgress.current_file_progress || 0}
                        currentItem={transferProgress.current_file}
                        size={{
                          transferred: transferProgress.bytes_transferred || 0,
                          total: transferProgress.total_bytes || 0,
                        }}
                        speed={transferProgress.speed_bytes_per_sec || 0}
                        time={{
                          elapsed: transferProgress.file_elapsed || 0,
                          remaining: transferProgress.eta_seconds || 0,
                        }}
                      />
                    )}

                  {/* Checksum Progress - Show when checksumming */}
                  {transferProgress.current_file &&
                    transferProgress.status === "CHECKSUMMING" && (
                      <FileTransferProgress
                        title="Checksum Verification Progress"
                        progress={transferProgress.current_file_progress || 0}
                        currentItem={transferProgress.current_file}
                        size={{
                          transferred: transferProgress.bytes_transferred || 0,
                          total: transferProgress.total_bytes || 0,
                        }}
                        speed={transferProgress.speed_bytes_per_sec || 0}
                        time={{
                          elapsed: transferProgress.checksum_elapsed || 0,
                          remaining: transferProgress.eta_seconds || 0,
                        }}
                      />
                    )}

                  {/* Proxy Generation Progress - Show when generating proxies */}
                  {transferProgress.status === "GENERATING_PROXY" &&
                    transferProgress.proxy_progress > 0 && (
                      <FileTransferProgress
                        title="Proxy Generation Progress"
                        progress={transferProgress.proxy_progress || 0}
                        itemCount={{
                          current: transferProgress.proxy_file_number || 0,
                          total: transferProgress.proxy_total_files || 0,
                        }}
                        time={{
                          elapsed: transferProgress.total_elapsed || 0,
                          remaining: transferProgress.eta_seconds || 0,
                        }}
                      />
                    )}
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Logs */}
          <div className="space-y-6">
            <AvailableDrives apiBaseUrl={API_BASE_URL} />
            <LogContainer logs={logs} />
          </div>
        </div>

        {/* Tutorial Modal */}
        {showTutorialModal && (
          <Modal
            isOpen={showTutorialModal}
            onClose={handleSkipTutorial}
            title="Tutorial"
            disableClickOutside={true}
          >
            <TutorialGuide
              steps={TUTORIAL_STEPS}
              currentStep={tutorialStep}
              onNext={handleTutorialNext}
              onPrevious={handleTutorialPrevious}
              onComplete={handleTutorialComplete}
              inModal={true}
            />
          </Modal>
        )}

        {/* Config Editor Modal */}
        <ConfigEditor isOpen={showConfigModal} onClose={handleCloseConfig} />
      </main>
    </div>
  );
};

export default TransferBox;
