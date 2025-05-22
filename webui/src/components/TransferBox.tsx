"use client";

import React, { useState, useEffect } from "react";
import Header from "./Header";
import Button from "./Button";
import PathInput from "./PathInput";
import StatusDisplay from "./StatusDisplay";
import LogContainer from "./LogContainer";
import CardDetectionStatus from "./CardDetectionStatus";
import TutorialGuide from "./TutorialGuide";
import Modal from "./Modal";
import FileTransferProgress from "./FileTransferProgress";

// Import the LogEntry type from LogContainer to ensure consistency
import type { LogEntry } from "./LogContainer";

// Mock data for initial UI development
const APP_DATA = {
  appName: "TransferBox",
  version: "1.4.0",
  author: "Tyler Saari",
};

const EXAMPLE_LOGS: LogEntry[] = [
  {
    id: "1",
    message: "TransferBox started",
    timestamp: "2023-08-15 10:30:22",
    level: "info",
  },
  {
    id: "2",
    message: "Waiting for source drive",
    timestamp: "2023-08-15 10:30:23",
    level: "info",
  },
];

// Mock file data for simulation
const MOCK_FILES = [
  {
    name: "DCIM/100GOPRO/GH010047.MP4",
    size: 1073741,
  },
  {
    name: "DCIM/100GOPRO/GH010042.MP4",
    size: 3865470566, // ~3.6GB
  },
  {
    name: "DCIM/100GOPRO/GH010043.MP4",
    size: 4294967296, // 4GB
  },
  {
    name: "DCIM/100GOPRO/GH010044.MP4",
    size: 2147483648, // 2GB
  },
  {
    name: "DCIM/100GOPRO/GH010045.MP4",
    size: 1073741824, // 1GB
  },
  {
    name: "DCIM/100GOPRO/GH010046.MP4",
    size: 536870912, // 512MB
  },
];

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

// This is a placeholder component until we connect to the real backend
const TransferBox: React.FC = () => {
  // State
  const [destinationPath, setDestinationPath] = useState("");
  const [isPathValid, setIsPathValid] = useState<boolean | undefined>(
    undefined
  );
  const [pathError, setPathError] = useState("");
  const [currentStatus, setCurrentStatus] = useState("TransferBox Ready");
  const [statusType, setStatusType] = useState<
    "info" | "warning" | "error" | "success"
  >("info");
  const [isCardDetected, setIsCardDetected] = useState(false);
  const [deviceName, setDeviceName] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>(EXAMPLE_LOGS);
  const [showTutorialModal, setShowTutorialModal] = useState(false);
  const [tutorialStep, setTutorialStep] = useState(0);
  const [hasSeenTutorial, setHasSeenTutorial] = useState(true); // Default to true, will be updated in useEffect
  const [logIdCounter, setLogIdCounter] = useState(0);

  // Transfer simulation state
  const [isTransferring, setIsTransferring] = useState(false);
  const [totalProgress, setTotalProgress] = useState(0);
  const [fileProgress, setFileProgress] = useState(0);
  const [checksumProgress, setChecksumProgress] = useState(0);
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [transferSpeed, setTransferSpeed] = useState(0);
  const [totalTransferred, setTotalTransferred] = useState(0);

  // Add these states for error handling
  const [transferError, setTransferError] = useState<string | null>(null);
  const [transferState, setTransferState] = useState<
    "idle" | "transferring" | "completed" | "failed"
  >("idle");

  // Calculate total size of all files
  const totalSize = MOCK_FILES.reduce((acc, file) => acc + file.size, 0);

  // Check local storage on component mount to see if the tutorial has been shown before
  useEffect(() => {
    // Check if we're in a browser environment
    if (typeof window !== "undefined") {
      try {
        // For testing, you can clear localStorage to simulate first visit
        // localStorage.removeItem(TUTORIAL_SHOWN_KEY);

        const tutorialShown = localStorage.getItem(TUTORIAL_SHOWN_KEY);
        console.log("Tutorial shown status:", tutorialShown);

        // Only if explicitly set to 'true', consider it as shown
        if (tutorialShown === "true") {
          setHasSeenTutorial(true);
        } else {
          // Either null, undefined, or any other value means not seen
          setHasSeenTutorial(false);
          setShowTutorialModal(true);
          console.log("Opening tutorial modal on first visit");
        }
      } catch (error) {
        console.error("Error accessing localStorage:", error);
        // If there's an error, show the tutorial anyway
        setShowTutorialModal(true);
      }
    }
  }, []);

  // Simulation timer effect
  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;

    if (isTransferring) {
      timer = setInterval(() => {
        setElapsedTime((prev) => prev + 1);

        // Update elapsed time every second
        if (currentFileIndex < MOCK_FILES.length) {
          simulateProgress();
        } else {
          // Transfer complete
          if (timer) clearInterval(timer);
          setIsTransferring(false);
          setCurrentStatus("Transfer complete");
          setStatusType("success");
          addLog("Transfer complete", "success");
        }
      }, 1000);
    }

    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isTransferring, currentFileIndex, fileProgress, checksumProgress]);

  // Simulate progress for current file
  const simulateProgress = () => {
    const currentFile = MOCK_FILES[currentFileIndex];

    // File transfer progress
    if (fileProgress < 100) {
      // Simulate realistic transfer speed (between 20MB/s and 120MB/s)
      const speed = Math.random() * 100000000 + 20000000;
      setTransferSpeed(speed);

      // How much would be transferred in 1 second at this speed
      const bytesPerInterval = speed;
      const fileSizeBytes = currentFile.size;
      const increment = (bytesPerInterval / fileSizeBytes) * 100;

      // Cap the increment to ensure we don't exceed 100%
      const newProgress = Math.min(fileProgress + increment, 100);
      setFileProgress(newProgress);

      // Update total transferred
      const percentComplete = newProgress / 100;
      const bytesTransferred = fileSizeBytes * percentComplete;
      setTotalTransferred(
        (prev) => prev + bytesTransferred - fileSizeBytes * (fileProgress / 100)
      );

      // Log significant progress
      if (Math.floor(newProgress / 20) > Math.floor(fileProgress / 20)) {
        addLog(
          `Transferring ${currentFile.name}: ${Math.floor(newProgress)}%`,
          "info"
        );
      }

      // Update total progress continuously - based on completed files plus current file progress
      const completedFilesSize = MOCK_FILES.slice(0, currentFileIndex).reduce(
        (acc, file) => acc + file.size,
        0
      );
      const currentFileContribution = currentFile.size * (newProgress / 100);
      const newTotalTransferred = completedFilesSize + currentFileContribution;
      const newTotalProgress = (newTotalTransferred / totalSize) * 100;
      setTotalProgress(newTotalProgress);
    }
    // Start checksum after file transfer completes
    else if (checksumProgress < 100) {
      // Checksum is typically faster - simulate checksum speed
      const checksumSpeed = Math.random() * 150000000 + 50000000; // 50-200 MB/s
      setTransferSpeed(checksumSpeed);

      // Increment for checksum progress
      const increment = 5 + Math.random() * 10; // 5-15% per second
      const newProgress = Math.min(checksumProgress + increment, 100);
      setChecksumProgress(newProgress);

      // Log significant checksum progress
      if (Math.floor(newProgress / 25) > Math.floor(checksumProgress / 25)) {
        addLog(
          `Checksumming ${currentFile.name}: ${Math.floor(newProgress)}%`,
          "info"
        );
      }
    }
    // Move to next file when both transfer and checksum are complete
    else {
      addLog(
        `Successfully transferred and verified: ${currentFile.name}`,
        "success"
      );
      setCurrentFileIndex((prev) => prev + 1);
      setFileProgress(0);
      setChecksumProgress(0);
    }
  };

  // Mock handlers for UI interaction
  const handleDestinationSubmit = () => {
    if (destinationPath.trim() === "") {
      setIsPathValid(false);
      setPathError("Destination path cannot be empty");
      return;
    }

    // This would be validated by the backend in the real implementation
    const mockValidation =
      destinationPath.startsWith("/") || /^[A-Z]:\\/.test(destinationPath);
    setIsPathValid(mockValidation);

    if (mockValidation) {
      setCurrentStatus(`Destination set to: ${destinationPath}`);
      setStatusType("success");
      addLog(`Destination set to: ${destinationPath}`, "success");
    } else {
      setPathError("Invalid path format");
      addLog(`Invalid destination path: ${destinationPath}`, "error");
    }
  };

  const handleCardInserted = () => {
    setIsCardDetected(true);
    setDeviceName("SD CARD (F:)");
    setCurrentStatus("SD Card detected. Starting transfer...");
    setStatusType("info");
    setTransferError(null);
    setTransferState("transferring");
    addLog("SD Card detected: SD CARD (F:)", "info");

    // Reset transfer simulation stats
    setIsTransferring(true);
    setTotalProgress(0);
    setFileProgress(0);
    setChecksumProgress(0);
    setCurrentFileIndex(0);
    setElapsedTime(0);
    setTransferSpeed(0);
    setTotalTransferred(0);

    // Log the start of the transfer
    addLog(
      `Starting transfer of ${MOCK_FILES.length} files (${(
        totalSize / 1073741824
      ).toFixed(2)} GB)`,
      "info"
    );

    // Force a test error after a short delay
    console.log("Setting up error simulation...");
    setTimeout(() => {
      console.log("Triggering simulated failure now");
      simulateRandomFailure();
    }, 3000); // Fail after 3 seconds - more predictable for testing
  };

  const simulateCardRemoval = () => {
    // Only show error if we were actively transferring
    if (isTransferring) {
      setTransferError(
        "Transfer Failed: SD Card was unexpectedly disconnected"
      );
      setTransferState("failed");
      addLog(
        "ERROR: Card removed during active transfer. Data may be incomplete or corrupted.",
        "error"
      );
    } else {
      addLog("Card removed", "info");
    }

    setIsCardDetected(false);
    setDeviceName("");
    setIsTransferring(false);
    setCurrentStatus("Card removed. Transfer stopped.");
    setStatusType("error"); // Changed from warning to error
  };

  const resetTransfer = () => {
    setDestinationPath("");
    setIsPathValid(undefined);
    setPathError("");
    setCurrentStatus("TransferBox Ready");
    setStatusType("info");
    setIsCardDetected(false);
    setDeviceName("");
    setIsTransferring(false);
    setTotalProgress(0);
    setFileProgress(0);
    setChecksumProgress(0);
    setCurrentFileIndex(0);
    setElapsedTime(0);
    setTransferSpeed(0);
    setTotalTransferred(0);
    setTransferError(null);
    setTransferState("idle");
    // Keep logs for history
  };

  const addLog = (
    message: string,
    level: "info" | "warning" | "error" | "success" = "info"
  ) => {
    // Create a unique ID by combining timestamp with a counter
    const uniqueId = `${Date.now()}-${logIdCounter}`;
    setLogIdCounter((prev) => prev + 1);

    const newLog: LogEntry = {
      id: uniqueId,
      message,
      timestamp: new Date().toISOString().replace("T", " ").substring(0, 19),
      level,
    };
    setLogs((prevLogs) => [...prevLogs, newLog]);
  };

  // Tutorial handlers
  const handleTutorialNext = () => {
    setTutorialStep((prev) => Math.min(prev + 1, TUTORIAL_STEPS.length - 1));
  };

  const handleTutorialPrevious = () => {
    setTutorialStep((prev) => Math.max(prev - 1, 0));
  };

  const handleTutorialComplete = () => {
    // Mark the tutorial as seen
    if (typeof window !== "undefined") {
      localStorage.setItem(TUTORIAL_SHOWN_KEY, "true");
      setHasSeenTutorial(true);
    }
    setShowTutorialModal(false);
    setTutorialStep(0);
    addLog("Tutorial completed", "success");
  };

  const handleShowTutorial = () => {
    setTutorialStep(0);
    setShowTutorialModal(true);
  };

  const handleSkipTutorial = () => {
    // Mark the tutorial as seen even if skipped
    if (typeof window !== "undefined") {
      localStorage.setItem(TUTORIAL_SHOWN_KEY, "true");
      setHasSeenTutorial(true);
    }
    setShowTutorialModal(false);
    setTutorialStep(0);
    addLog("Tutorial skipped", "info");
  };

  // For development - reset tutorial state
  const resetTutorialState = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TUTORIAL_SHOWN_KEY);
      window.location.reload();
    }
  };

  // Calculate remaining time for total transfer
  const calculateRemainingTime = () => {
    if (transferSpeed === 0 || totalProgress === 100) return 0;

    const remainingBytes = totalSize - totalTransferred;
    return remainingBytes / transferSpeed;
  };

  // Calculate remaining time for current file
  const calculateFileRemainingTime = () => {
    if (transferSpeed === 0 || fileProgress === 100) return 0;

    const currentFile =
      currentFileIndex < MOCK_FILES.length
        ? MOCK_FILES[currentFileIndex]
        : null;
    if (!currentFile) return 0;

    const remainingBytes = currentFile.size * (1 - fileProgress / 100);
    return remainingBytes / transferSpeed;
  };

  // Simulate a random failure
  const simulateRandomFailure = () => {
    console.log("simulateRandomFailure called", { isTransferring });

    // Remove the isTransferring check - always show the error
    const errorTypes = [
      "Transfer Failed: Unexpected I/O error while reading from source",
      "Transfer Failed: File system error on destination drive",
      "Transfer Failed: Corrupted file detected during verification",
      "Transfer Failed: Write permission denied on destination",
    ];

    const randomError =
      errorTypes[Math.floor(Math.random() * errorTypes.length)];
    console.log("Setting error:", randomError);

    // Force display of error with timeout to ensure state updates properly
    setTimeout(() => {
      setTransferError(randomError);
      setTransferState("failed");
      setIsTransferring(false);
      setStatusType("error");
      setCurrentStatus("Transfer failed");
      addLog(`ERROR: ${randomError}`, "error");

      // Force a re-render by updating some state
      setTotalProgress((prev) => (prev > 0 ? prev - 0.1 : 0.1));
    }, 100);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <Header
        appName={APP_DATA.appName}
        version={APP_DATA.version}
        author={APP_DATA.author}
        onShowTutorial={handleShowTutorial}
      />

      <main className="container mx-auto p-4 md:p-6">
        {/* Dev button for testing - remove in production */}
        {process.env.NODE_ENV === "development" && (
          <div className="mb-4">
            <Button
              label="Reset Tutorial State"
              onClick={resetTutorialState}
              size="sm"
              variant="secondary"
            />
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
                  <div className="ml-2 flex-shrink-0 self-start">
                    <Button
                      label="Set"
                      onClick={handleDestinationSubmit}
                      size="md"
                    />
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

              {isTransferring && (
                <div className="space-y-5 mb-6">
                  {/* Overall Transfer Progress */}
                  <FileTransferProgress
                    title="Total Transfer Progress"
                    progress={totalProgress}
                    itemCount={{
                      current: currentFileIndex + (fileProgress < 100 ? 1 : 0),
                      total: MOCK_FILES.length,
                    }}
                    size={{
                      transferred: totalTransferred,
                      total: totalSize,
                    }}
                    speed={transferSpeed}
                    time={{
                      elapsed: elapsedTime,
                      remaining: calculateRemainingTime(),
                    }}
                  />

                  {/* Current File Transfer Progress */}
                  {currentFileIndex < MOCK_FILES.length && (
                    <FileTransferProgress
                      title="File Transfer Progress"
                      progress={fileProgress}
                      currentItem={MOCK_FILES[currentFileIndex]?.name}
                      size={{
                        transferred:
                          (fileProgress / 100) *
                          MOCK_FILES[currentFileIndex]?.size,
                        total: MOCK_FILES[currentFileIndex]?.size,
                      }}
                      speed={transferSpeed}
                      time={{
                        elapsed: elapsedTime,
                        remaining: calculateFileRemainingTime(),
                      }}
                    />
                  )}

                  {/* Checksum Progress (only show when file transfer is complete) */}
                  {fileProgress === 100 &&
                    checksumProgress < 100 &&
                    currentFileIndex < MOCK_FILES.length && (
                      <FileTransferProgress
                        title="Checksumming Progress"
                        progress={checksumProgress}
                        currentItem={MOCK_FILES[currentFileIndex]?.name}
                        size={{
                          transferred:
                            (checksumProgress / 100) *
                            MOCK_FILES[currentFileIndex]?.size,
                          total: MOCK_FILES[currentFileIndex]?.size,
                        }}
                        speed={transferSpeed}
                        time={{
                          elapsed: elapsedTime,
                          remaining: (100 - checksumProgress) / 10, // Rough estimate
                        }}
                      />
                    )}
                </div>
              )}

              <div className="mt-6 flex flex-wrap gap-2">
                {!isCardDetected ? (
                  <Button
                    label="Simulate Card Insert"
                    onClick={handleCardInserted}
                    disabled={!isPathValid}
                    variant="primary"
                    size="md"
                  />
                ) : (
                  <Button
                    label="Simulate Card Removal"
                    onClick={simulateCardRemoval}
                    variant="secondary"
                    size="md"
                  />
                )}

                <Button
                  label="Reset"
                  onClick={resetTransfer}
                  variant="danger"
                  size="md"
                />
              </div>
            </div>
          </div>

          {/* Right Column - Logs */}
          <div className="md:col-span-1">
            <LogContainer logs={logs} title="Transfer Logs" maxHeight="600px" />
          </div>
        </div>
      </main>

      {/* Tutorial Modal */}
      <Modal
        isOpen={showTutorialModal}
        onClose={handleSkipTutorial}
        title="TransferBox Tutorial"
        maxWidth="xl"
        disableClickOutside={!hasSeenTutorial}
        hideCloseButton={false}
      >
        <TutorialGuide
          steps={TUTORIAL_STEPS}
          currentStep={tutorialStep}
          onNext={handleTutorialNext}
          onPrevious={handleTutorialPrevious}
          onSkip={handleSkipTutorial}
          onComplete={handleTutorialComplete}
          inModal={true}
        />
      </Modal>
    </div>
  );
};

export default TransferBox;
