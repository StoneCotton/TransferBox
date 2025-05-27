# Tutorial Logic Documentation

## Overview

The tutorial system in TransferBox WebUI uses a combination of localStorage and backend configuration to determine when to show tutorials to users.

## Key Components

### 1. Local Storage Key

- **Key**: `transferbox_tutorial_shown`
- **Values**: `"true"` (tutorial has been completed) or `null`/`"false"` (tutorial not completed)

### 2. Backend Configuration

- **Setting**: `tutorial_mode` (boolean)
- **Purpose**: When enabled, overrides localStorage and shows tutorial on first launch
- **Location**: Accessible via `/api/config` endpoint

## Logic Flow

### Before Fix (Issue)

```
if (localStorage.getItem("transferbox_tutorial_shown") === "true") {
  // Don't show tutorial
} else {
  // Show tutorial
}
```

**Problem**: Even when "Enable Tutorial Mode" was selected in config, if `transferbox_tutorial_shown` was `true`, the tutorial would never show.

### After Fix (Current Implementation)

```
const hasSeenBefore = localStorage.getItem("transferbox_tutorial_shown") === "true";
const shouldShowTutorial = config?.tutorial_mode === true || !hasSeenBefore;

if (shouldShowTutorial) {
  // Show tutorial
} else {
  // Don't show tutorial
}
```

## Key Behavior Changes

### 1. Config Override

- When `tutorial_mode` is `true` in config, tutorial will show regardless of localStorage
- This allows users to re-enable tutorials after they've been completed

### 2. First-Time Users

- Users who have never seen the tutorial (`transferbox_tutorial_shown` not set) will see it automatically
- This behavior remains unchanged

### 3. Config Changes

- When the config modal is closed, the config is refetched
- This ensures changes to `tutorial_mode` take effect immediately

## Use Cases

### Scenario 1: New User

- `transferbox_tutorial_shown`: not set
- `tutorial_mode`: default value (true)
- **Result**: Tutorial shows ✅

### Scenario 2: Returning User, Tutorial Mode Disabled

- `transferbox_tutorial_shown`: "true"
- `tutorial_mode`: false
- **Result**: Tutorial doesn't show ✅

### Scenario 3: Returning User, Tutorial Mode Enabled

- `transferbox_tutorial_shown`: "true"
- `tutorial_mode`: true
- **Result**: Tutorial shows ✅ (This was the bug we fixed)

### Scenario 4: First Launch After Enabling Tutorial Mode

- User enables "Enable Tutorial Mode" in config
- Config is refetched when modal closes
- Tutorial appears on next component render
- **Result**: Immediate tutorial display ✅

## Implementation Details

### Hooks Involved

1. **`useConfig`**: Fetches configuration from backend API
2. **`useTutorial`**: Manages tutorial state, now accepts config parameter
3. **`TransferBox`**: Combines both hooks and refetches config on modal close

### Files Modified

1. `webui/src/hooks/useConfig.ts` (new)
2. `webui/src/hooks/useTutorial.ts` (modified)
3. `webui/src/hooks/index.ts` (export added)
4. `webui/src/components/TransferBox.tsx` (integration)

## Testing the Fix

### Manual Test Steps

1. Complete the tutorial (sets `transferbox_tutorial_shown` to "true")
2. Open Config modal
3. Enable "Enable Tutorial Mode"
4. Close Config modal
5. **Expected**: Tutorial should appear immediately
6. **Before Fix**: Tutorial would not appear

### Verification Points

- Tutorial appears when `tutorial_mode` is true, regardless of localStorage
- Config changes take effect without page refresh
- Normal tutorial completion still works (sets localStorage flag)
- First-time user experience unchanged
