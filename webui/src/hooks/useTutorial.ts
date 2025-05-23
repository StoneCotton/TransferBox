import { useState, useEffect, useCallback } from "react";
import { TUTORIAL_SHOWN_KEY } from "../constants";

interface UseTutorialReturn {
  showTutorialModal: boolean;
  tutorialStep: number;
  hasSeenTutorial: boolean;
  setShowTutorialModal: (show: boolean) => void;
  nextStep: () => void;
  previousStep: () => void;
  completeTutorial: () => void;
  showTutorial: () => void;
  skipTutorial: () => void;
  resetTutorialState: () => boolean;
}

/**
 * Custom hook for managing tutorial state and localStorage persistence
 * Handles tutorial navigation and user preference storage
 */
export const useTutorial = (totalSteps: number): UseTutorialReturn => {
  const [showTutorialModal, setShowTutorialModal] = useState(false);
  const [tutorialStep, setTutorialStep] = useState(0);
  const [hasSeenTutorial, setHasSeenTutorial] = useState(true);

  // Check local storage for tutorial preference on mount
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
  }, []);

  const nextStep = useCallback(() => {
    setTutorialStep((prev) => Math.min(prev + 1, totalSteps - 1));
  }, [totalSteps]);

  const previousStep = useCallback(() => {
    setTutorialStep((prev) => Math.max(prev - 1, 0));
  }, []);

  const completeTutorial = useCallback(() => {
    setShowTutorialModal(false);
    setTutorialStep(0);
    try {
      localStorage.setItem(TUTORIAL_SHOWN_KEY, "true");
      setHasSeenTutorial(true);
    } catch (error) {
      console.error("Error saving tutorial state:", error);
    }
  }, []);

  const showTutorial = useCallback(() => {
    setTutorialStep(0);
    setShowTutorialModal(true);
  }, []);

  const skipTutorial = useCallback(() => {
    completeTutorial();
  }, [completeTutorial]);

  const resetTutorialState = useCallback(() => {
    try {
      localStorage.removeItem(TUTORIAL_SHOWN_KEY);
      setHasSeenTutorial(false);
      return true;
    } catch (error) {
      console.error("Error resetting tutorial state:", error);
      return false;
    }
  }, []);

  return {
    showTutorialModal,
    tutorialStep,
    hasSeenTutorial,
    setShowTutorialModal,
    nextStep,
    previousStep,
    completeTutorial,
    showTutorial,
    skipTutorial,
    resetTutorialState,
  };
};
