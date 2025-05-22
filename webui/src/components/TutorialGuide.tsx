"use client";

import React from "react";
import Button from "./Button";

interface TutorialStep {
  id: string;
  title: string;
  description: string;
  image?: string;
}

interface TutorialGuideProps {
  steps: TutorialStep[];
  currentStep: number;
  onNext: () => void;
  onPrevious: () => void;
  onSkip: () => void;
  onComplete: () => void;
  className?: string;
  inModal?: boolean;
}

const TutorialGuide: React.FC<TutorialGuideProps> = ({
  steps,
  currentStep,
  onNext,
  onPrevious,
  onSkip,
  onComplete,
  className = "",
  inModal = false,
}) => {
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;
  const currentStepData = steps[currentStep];

  return (
    <div
      className={`
        ${inModal ? "" : "border border-blue-200 rounded-md bg-blue-50"}
        ${className}
      `}
    >
      {!inModal && (
        <div className="border-b border-blue-200 bg-blue-100 px-4 py-3">
          <div className="flex justify-between items-center">
            <h3 className="font-medium text-blue-800">Tutorial Guide</h3>
            <Button
              label="Skip Tutorial"
              variant="secondary"
              size="sm"
              onClick={onSkip}
            />
          </div>
        </div>
      )}

      <div className="p-5">
        <div className="mb-2 flex items-center">
          <div className="bg-blue-600 text-white rounded-full h-6 w-6 flex items-center justify-center text-sm mr-2">
            {currentStep + 1}
          </div>
          <h4 className="font-medium text-lg">{currentStepData.title}</h4>
        </div>

        <div className="mb-6 text-slate-700">{currentStepData.description}</div>

        {currentStepData.image && (
          <div className="mb-6">
            <img
              src={currentStepData.image}
              alt={`Tutorial step ${currentStep + 1}`}
              className="max-w-full rounded-md border border-slate-200"
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
          />
        </div>
      </div>

      <div
        className={`${
          inModal
            ? "border-t border-slate-200"
            : "bg-blue-100 border-t border-blue-200"
        } px-4 py-3`}
      >
        <div className="flex justify-center">
          {steps.map((_, index) => (
            <div
              key={`step-${index}`}
              className={`
                h-2 w-2 rounded-full mx-1
                ${index === currentStep ? "bg-blue-600" : "bg-blue-300"}
              `}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default TutorialGuide;
