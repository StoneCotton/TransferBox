"use client";

import React, { useState, useCallback, useMemo } from "react";
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

// Import custom hooks and utilities
import {
  useWebSocket,
  useLogs,
  useTutorial,
  useTransferState,
  useDestinationPath,
  useAppMetadata,
  useTransferControls,
} from "../hooks";

// Import constants and handlers
import { getTutorialSteps, API_BASE_URL } from "../constants";
import { createWebSocketHandlers } from "../handlers/websocketHandlers";

const TransferBox: React.FC = () => {
  // Config modal state
  const [showConfigModal, setShowConfigModal] = useState(false);

  // Custom hooks for state management
  const { logs, addLog, clearLogs } = useLogs();

  const transferState = useTransferState();
  const {
    transferProgress,
    isTransferring,
    transferError,
    isCardDetected,
    deviceName,
    devicePath,
    currentStatus,
    statusType,
    setStatus,
    resetTransfer,
  } = transferState;

  const destinationHook = useDestinationPath(addLog, setStatus);
  const {
    destinationPath,
    isPathValid,
    pathError,
    destinationSet,
    setDestinationPath,
    validateAndSetDestination,
    resetDestination,
  } = destinationHook;

  const { appMetadata } = useAppMetadata();

  // Get platform-specific tutorial steps
  const tutorialSteps = getTutorialSteps(appMetadata.platform);
  const tutorial = useTutorial(tutorialSteps.length);
  const {
    showTutorialModal,
    tutorialStep,
    nextStep,
    previousStep,
    completeTutorial,
    showTutorial,
    skipTutorial,
    resetTutorialState,
  } = tutorial;

  // Transfer controls for stop and shutdown
  const { isStopping, isShuttingDown, stopTransfer, shutdownApplication } =
    useTransferControls(addLog, setStatus);

  // WebSocket message handlers - memoized to prevent reconnection loops
  const wsHandlers = useMemo(
    () =>
      createWebSocketHandlers({
        addLog,
        setStatus: transferState.setStatus,
        updateFromProgress: transferState.updateFromProgress,
        setTransferError: transferState.setTransferError,
        setTransferProgress: transferState.setTransferProgress,
        setCardDetected: transferState.setCardDetected,
        resetDestination,
        clearLogs,
      }),
    [
      addLog,
      transferState.setStatus,
      transferState.updateFromProgress,
      transferState.setTransferError,
      transferState.setTransferProgress,
      transferState.setCardDetected,
      resetDestination,
      clearLogs,
    ]
  );

  // WebSocket connection callbacks - memoized to prevent reconnection loops
  const handleWebSocketConnect = useCallback(() => {
    setStatus("Connected to TransferBox", "info");
    addLog("Connected to TransferBox", "info");
  }, [setStatus, addLog]);

  const handleWebSocketDisconnect = useCallback(() => {
    setStatus("Disconnected from TransferBox", "warning");
  }, [setStatus]);

  const handleWebSocketError = useCallback(() => {
    setStatus("Connection error", "error");
  }, [setStatus]);

  // WebSocket connection
  const { isConnected } = useWebSocket({
    onMessage: wsHandlers.handleMessage,
    onConnect: handleWebSocketConnect,
    onDisconnect: handleWebSocketDisconnect,
    onError: handleWebSocketError,
  });

  // Event handlers
  const handleResetTransfer = useCallback(() => {
    resetTransfer();
    resetDestination();
    addLog("Transfer reset", "info");
  }, [resetTransfer, resetDestination, addLog]);

  const handleResetDestination = useCallback(() => {
    resetDestination();
  }, [resetDestination]);

  const handleShowConfig = useCallback(() => {
    setShowConfigModal(true);
  }, []);

  const handleCloseConfig = useCallback(() => {
    setShowConfigModal(false);
  }, []);

  const handleResetTutorialWithLog = useCallback(() => {
    const success = resetTutorialState();
    if (success) {
      addLog("Tutorial state reset - refresh to see tutorial", "info");
    } else {
      addLog("Failed to reset tutorial state", "error");
    }
  }, [resetTutorialState, addLog]);

  return (
    <div className="min-h-screen bg-slate-50">
      <Header
        appName={appMetadata.appName}
        version={appMetadata.version}
        author={appMetadata.author}
        onShowTutorial={showTutorial}
        onShowConfig={handleShowConfig}
        onShutdown={shutdownApplication}
        isShuttingDown={isShuttingDown}
      />

      <main className="container mx-auto p-4 md:p-6">
        {/* Dev button for testing - remove in production */}
        {process.env.NODE_ENV === "development" && (
          <div className="mb-4 flex gap-2">
            <Button
              label="Reset Tutorial State"
              onClick={handleResetTutorialWithLog}
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
                      onSubmit={validateAndSetDestination}
                      disabled={isTransferring}
                    />
                  </div>
                  <div className="ml-2 flex-shrink-0 self-start flex gap-2">
                    <Button
                      label={destinationSet ? "Set ✓" : "Set"}
                      onClick={validateAndSetDestination}
                      size="md"
                      disabled={
                        !isConnected || destinationSet || isTransferring
                      }
                      variant={destinationSet ? "success" : "primary"}
                    />
                    {destinationSet && !isTransferring && (
                      <Button
                        label="Reset"
                        onClick={handleResetDestination}
                        size="md"
                        variant="secondary"
                        disabled={isTransferring}
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
                devicePath={devicePath}
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
                  {transferError.includes("No valid media files found") ? (
                    <div className="text-sm mb-3">
                      <p className="mb-2">
                        This usually means one of the following:
                      </p>
                      <ul className="list-disc list-inside space-y-1 ml-2">
                        <li>The card/drive is empty</li>
                        <li>
                          The files don&apos;t match the configured media
                          extensions
                        </li>
                        <li>
                          The files are in a format not recognized by
                          TransferBox
                        </li>
                      </ul>
                      <p className="mt-2">
                        Check your files in Explorer/Finder and verify the
                        configuration if needed.
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm mb-3">
                      The transfer was interrupted and file data may be
                      incomplete or corrupted. Please reconnect the card and try
                      again.
                    </p>
                  )}
                  <Button
                    label="Dismiss & Reset"
                    onClick={handleResetTransfer}
                    variant="danger"
                    size="sm"
                  />
                </div>
              )}

              {/* Transfer Controls - Show during active transfer */}
              {isTransferring && (
                <div className="bg-blue-50 border border-blue-200 p-4 mb-6 rounded-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-blue-800 mb-2">
                        Transfer Controls
                      </h3>
                      <p className="text-blue-700 text-sm">
                        Stop the current transfer or shutdown the application
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        label={isStopping ? "Stopping..." : "Stop Transfer"}
                        onClick={stopTransfer}
                        variant="secondary"
                        size="sm"
                        disabled={isStopping || isShuttingDown}
                      />
                      <Button
                        label={isShuttingDown ? "Shutting Down..." : "Shutdown"}
                        onClick={shutdownApplication}
                        variant="danger"
                        size="sm"
                        disabled={isStopping || isShuttingDown}
                      />
                    </div>
                  </div>
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
            <LogContainer logs={logs} />
            <AvailableDrives apiBaseUrl={API_BASE_URL} />
          </div>
        </div>

        {/* Tutorial Modal */}
        {showTutorialModal && (
          <Modal
            isOpen={showTutorialModal}
            onClose={skipTutorial}
            title="Tutorial"
            disableClickOutside={true}
          >
            <TutorialGuide
              steps={tutorialSteps}
              currentStep={tutorialStep}
              onNext={nextStep}
              onPrevious={previousStep}
              onComplete={completeTutorial}
              inModal={true}
              // Destination path props
              destinationPath={destinationPath}
              setDestinationPath={setDestinationPath}
              isPathValid={isPathValid}
              pathError={pathError}
              destinationSet={destinationSet}
              validateAndSetDestination={validateAndSetDestination}
              resetDestination={resetDestination}
              isConnected={isConnected}
              // Card detection props
              isCardDetected={isCardDetected}
              deviceName={deviceName}
              devicePath={devicePath}
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
