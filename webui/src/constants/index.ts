import type { TutorialStep } from "../types";

// API Configuration
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export const WS_URL = "ws://127.0.0.1:8000/ws";

// Local Storage Keys
export const TUTORIAL_SHOWN_KEY = "transferbox_tutorial_shown";

// WebSocket Configuration
export const WS_RECONNECT_DELAY = 3000; // 3 seconds

// Tutorial Steps
export const TUTORIAL_STEPS: TutorialStep[] = [
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
