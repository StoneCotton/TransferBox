"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import Button from "./Button";
import PathInput from "./PathInput";
import CardDetectionStatus from "./CardDetectionStatus";
import type { TutorialStep } from "../types";

interface TutorialGuideProps {
  steps: TutorialStep[];
  currentStep: number;
  onNext: () => void;
  onPrevious: () => void;
  onComplete: () => void;
  className?: string;
  inModal?: boolean;

  // Props for interactive steps
  // Destination path step
  destinationPath?: string;
  setDestinationPath?: (path: string) => void;
  isPathValid?: boolean;
  pathError?: string;
  destinationSet?: boolean;
  validateAndSetDestination?: () => Promise<void>;
  resetDestination?: () => void;
  isConnected?: boolean;

  // Card detection step
  isCardDetected?: boolean;
  deviceName?: string;
  devicePath?: string;
}

const TutorialGuide: React.FC<TutorialGuideProps> = ({
  steps,
  currentStep,
  onNext,
  onPrevious,
  onComplete,
  className = "",
  inModal = false,
  // Destination props
  destinationPath = "",
  setDestinationPath,
  isPathValid,
  pathError = "",
  destinationSet = false,
  validateAndSetDestination,
  resetDestination,
  isConnected = true,
  // Card detection props
  isCardDetected = false,
  deviceName,
  devicePath,
}) => {
  const [autoCompleteTimer, setAutoCompleteTimer] = useState<number | null>(
    null
  );

  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;
  const currentStepData = steps[currentStep];

  // Check if current step requirements are met
  const isStepCompleted = () => {
    if (!currentStepData.requiresCompletion) return true;

    switch (currentStepData.stepType) {
      case "destination":
        return destinationSet;
      case "card_detection":
        return isCardDetected;
      default:
        return true;
    }
  };

  const canProceed = isStepCompleted();

  // Auto-advance for card detection step when card is detected
  useEffect(() => {
    if (
      currentStepData.stepType === "card_detection" &&
      isCardDetected &&
      !autoCompleteTimer
    ) {
      const timer = window.setTimeout(() => {
        if (isLastStep) {
          onComplete();
        } else {
          onNext();
        }
      }, 2000); // Wait 2 seconds after card detection

      setAutoCompleteTimer(timer);
    }

    return () => {
      if (autoCompleteTimer) {
        clearTimeout(autoCompleteTimer);
        setAutoCompleteTimer(null);
      }
    };
  }, [
    currentStepData.stepType,
    isCardDetected,
    isLastStep,
    onNext,
    onComplete,
    autoCompleteTimer,
  ]);

  // Auto-complete for monitoring step
  useEffect(() => {
    if (currentStepData.stepType === "monitoring" && !autoCompleteTimer) {
      const timer = window.setTimeout(() => {
        onComplete();
      }, 5000); // Auto-complete after 5 seconds

      setAutoCompleteTimer(timer);
    }

    return () => {
      if (autoCompleteTimer) {
        clearTimeout(autoCompleteTimer);
        setAutoCompleteTimer(null);
      }
    };
  }, [currentStepData.stepType, onComplete, autoCompleteTimer]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (autoCompleteTimer) {
        clearTimeout(autoCompleteTimer);
      }
    };
  }, [autoCompleteTimer]);

  const renderStepContent = () => {
    switch (currentStepData.stepType) {
      case "destination":
        return (
          <div className="mb-6">
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Destination Path
              </label>
              <div className="flex items-start">
                <div className="flex-grow">
                  <PathInput
                    value={destinationPath}
                    onChange={setDestinationPath || (() => {})}
                    isValid={isPathValid}
                    errorMessage={pathError}
                    examplePath="/Volumes/External/Media"
                    onSubmit={validateAndSetDestination}
                    disabled={false}
                  />
                </div>
                <div className="ml-2 flex-shrink-0 self-start flex gap-2">
                  <Button
                    label={destinationSet ? "Set ✓" : "Set"}
                    onClick={validateAndSetDestination || (() => {})}
                    size="md"
                    disabled={!isConnected || destinationSet}
                    variant={destinationSet ? "success" : "primary"}
                  />
                  {destinationSet && (
                    <Button
                      label="Reset"
                      onClick={resetDestination || (() => {})}
                      size="md"
                      variant="secondary"
                      disabled={false}
                    />
                  )}
                </div>
              </div>
            </div>
            {destinationSet && (
              <div className="bg-green-50 border border-green-200 text-green-800 p-3 rounded-md">
                <div className="flex items-center">
                  <svg
                    className="h-5 w-5 text-green-600 mr-2"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                  Destination path set successfully! You can now proceed to the
                  next step.
                </div>
              </div>
            )}
          </div>
        );

      case "card_detection":
        return (
          <div className="mb-6">
            <CardDetectionStatus
              isDetected={isCardDetected}
              deviceName={deviceName}
              devicePath={devicePath}
              waitingMessage="Waiting for SD card to be inserted..."
              className="bg-amber-50 border border-amber-200"
            />
            {isCardDetected && (
              <div className="mt-4 bg-green-50 border border-green-200 text-green-800 p-3 rounded-md">
                <div className="flex items-center">
                  <svg
                    className="h-5 w-5 text-green-600 mr-2"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                  SD card detected! Automatically proceeding to next step...
                </div>
              </div>
            )}
          </div>
        );

      case "monitoring":
        return (
          <div className="mb-6">
            <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-md">
              <div className="flex items-center mb-2">
                <svg
                  className="h-6 w-6 text-blue-600 mr-2"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <h4 className="font-medium">Tutorial Complete!</h4>
              </div>
              <p className="text-sm">
                You&apos;re all set! The main interface now shows your
                configured destination path and detected SD card. This tutorial
                will close automatically in a few seconds, or you can click
                Complete now.
              </p>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div
      className={`
        ${inModal ? "" : "border border-slate-200 rounded-md bg-slate-50"}
        ${className}
      `}
    >
      {!inModal && (
        <div className="border-b border-slate-200 bg-slate-100 px-4 py-3">
          <div className="flex justify-between items-center">
            <h3 className="font-medium text-slate-800">Tutorial Guide</h3>
          </div>
        </div>
      )}

      <div className="p-5">
        <div className="mb-2 flex items-center">
          <div className="bg-slate-600 text-white rounded-full h-6 w-6 flex items-center justify-center text-sm mr-2">
            {currentStep + 1}
          </div>
          <h4 className="font-medium text-lg">{currentStepData.title}</h4>
        </div>

        <div className="mb-6 text-slate-700 whitespace-pre-line">
          {currentStepData.description}
        </div>

        {renderStepContent()}

        {currentStepData.image && (
          <div className="mb-6">
            <Image
              src={currentStepData.image}
              alt={`Tutorial step ${currentStep + 1}`}
              width={800}
              height={600}
              className="max-w-full rounded-md border border-slate-200"
              style={{ height: "auto" }}
            />
          </div>
        )}

        <div className="flex justify-between">
          <Button
            label="Previous"
            variant="secondary"
            onClick={onPrevious}
            disabled={isFirstStep}
          />

          <Button
            label={isLastStep ? "Complete" : "Next"}
            variant={isLastStep ? "success" : "primary"}
            onClick={isLastStep ? onComplete : onNext}
            disabled={!canProceed}
          />
        </div>
      </div>

      <div
        className={`${
          inModal
            ? "border-t border-slate-200"
            : "bg-slate-100 border-t border-slate-200"
        } px-4 py-3`}
      >
        <div className="flex justify-center">
          {steps.map((step, index) => (
            <div
              key={`step-${index}`}
              className={`
                h-2 w-2 rounded-full mx-1
                ${
                  index === currentStep
                    ? "bg-slate-600"
                    : index < currentStep
                    ? "bg-green-500"
                    : "bg-slate-300"
                }
              `}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default TutorialGuide;
