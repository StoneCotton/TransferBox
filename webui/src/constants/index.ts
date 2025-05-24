import type { TutorialStep } from "../types";

// API Configuration
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export const WS_URL = "ws://127.0.0.1:8000/ws";

// Local Storage Keys
export const TUTORIAL_SHOWN_KEY = "transferbox_tutorial_shown";

// WebSocket Configuration
export const WS_RECONNECT_DELAY = 3000; // 3 seconds

// OS-specific path copy instructions
export const getPathCopyInstructions = (platform: string): string => {
  switch (platform.toLowerCase()) {
    case "darwin":
      return '💡 Tip: Right-click any folder in Finder and hold down the ⌥Option key. While holding down the Option key, select "Copy as Pathname" to get the full path quickly.';
    case "windows":
      return "💡 Tip: Navigate to your desired folder in File Explorer, click in the address bar, and copy the path (Ctrl+C).";
    case "linux":
      return "💡 Tip: Right-click any folder in your file manager and select \"Copy Location\" or use the terminal to navigate and run 'pwd'.";
    default:
      return "💡 Tip: Use your file manager to navigate to the desired folder and copy its full path.";
  }
};

// Function to get tutorial steps with platform-specific instructions
export const getTutorialSteps = (
  platform: string = "unknown"
): TutorialStep[] => [
  {
    id: "step1",
    title: "Welcome to TransferBox",
    description:
      "This tutorial will guide you through the process of transferring files from your SD card to your computer.",
    stepType: "info",
  },
  {
    id: "step2",
    title: "Choose Destination",
    description: `First, select where you want to save your files. Enter a valid path to a directory on your computer and click Set.\n\n${getPathCopyInstructions(
      platform
    )}`,
    stepType: "destination",
    requiresCompletion: true,
  },
  {
    id: "step3",
    title: "Insert SD Card",
    description:
      "Insert your SD card into your computer. TransferBox will automatically detect it when it's ready.",
    stepType: "card_detection",
    requiresCompletion: true,
  },
  {
    id: "step4",
    title: "Ready to Transfer",
    description:
      "Great! Your destination is set and SD card is detected. You can now monitor transfers as they happen. The tutorial will complete automatically.",
    stepType: "monitoring",
  },
];

// Default tutorial steps (for backwards compatibility)
export const TUTORIAL_STEPS: TutorialStep[] = getTutorialSteps();
