# TransferBox Frontend Architecture

## Overview

The TransferBox frontend has been refactored from a single large component (799 lines) into a modular, maintainable architecture following DRY and KISS principles.

## Directory Structure

```
src/
├── components/          # React components
│   ├── TransferBox.tsx  # Main application component (now ~300 lines)
│   └── ...              # Other UI components
├── hooks/               # Custom React hooks
│   ├── useWebSocket.ts  # WebSocket connection management
│   ├── useLogs.ts       # Log management
│   ├── useTutorial.ts   # Tutorial state management
│   ├── useTransferState.ts # Transfer progress and state
│   ├── useDestinationPath.ts # Path validation and setting
│   ├── useAppMetadata.ts # App metadata loading
│   └── index.ts         # Barrel export for all hooks
├── services/            # API and external service functions
│   └── api.ts           # Centralized API calls
├── handlers/            # Business logic handlers
│   └── websocketHandlers.ts # WebSocket message processing
├── types/               # TypeScript type definitions
│   └── index.ts         # Shared interfaces and types
└── constants/           # Application constants
    └── index.ts         # Configuration and static data
```

## Key Principles Applied

### Single Responsibility Principle

- Each hook manages one specific concern
- Components focus only on UI rendering
- Services handle external communication
- Handlers process business logic

### DRY (Don't Repeat Yourself)

- Centralized type definitions in `types/index.ts`
- Reusable API functions in `services/api.ts`
- Shared constants in `constants/index.ts`
- Custom hooks eliminate duplicate state management

### KISS (Keep It Simple, Stupid)

- Clear separation of concerns
- Descriptive naming conventions
- Minimal dependencies between modules
- Easy-to-follow data flow

## Custom Hooks

### `useWebSocket`

Manages WebSocket connection lifecycle, including:

- Connection establishment and reconnection
- Message routing to handlers
- Connection state management
- Error handling

### `useTransferState`

Handles all transfer-related state:

- Transfer progress tracking
- Card detection status
- Transfer error handling
- Status updates based on backend messages

### `useDestinationPath`

Manages destination path operations:

- Path validation
- Backend communication for path setting
- Path state management

### `useLogs`

Centralized logging system:

- Log entry creation and management
- Different log levels (info, warning, error, success)
- Log clearing and filtering

### `useTutorial`

Tutorial flow management:

- LocalStorage persistence
- Step navigation
- Modal state management

### `useAppMetadata`

Application metadata handling:

- Backend metadata loading
- Fallback to defaults
- Loading state management

## Services

### `apiService`

Centralized API communication:

- Path validation
- Destination setting
- App metadata loading
- Consistent error handling

## Handlers

### `websocketHandlers`

Processes WebSocket messages:

- Message type routing
- State updates based on messages
- Business logic for different message types

## Benefits of This Architecture

1. **Maintainability**: Each module has a clear purpose and can be modified independently
2. **Testability**: Hooks and services can be unit tested in isolation
3. **Reusability**: Hooks can be reused across different components
4. **Readability**: Code is organized logically and easy to navigate
5. **Scalability**: New features can be added as new hooks or services
6. **Type Safety**: Centralized types ensure consistency across the application
7. **Better UX**: Transfer state is used to disable inputs during active transfers

## UX Improvements

### Transfer State Management

The application provides clear visual feedback during transfers:

- **Destination path input** becomes disabled during active transfers
- **Set/Reset buttons** are disabled to prevent conflicts
- **Visual indicators** show transfer progress and status
- **Inputs re-enable** automatically when transfer completes or fails

## Migration Summary

The original 799-line `TransferBox.tsx` component was reduced to ~300 lines by extracting:

- **~200 lines** to custom hooks
- **~150 lines** to services and handlers
- **~100 lines** to types and constants
- **~50 lines** eliminated through DRY refactoring

This results in a 62% reduction in the main component size while improving overall code organization and maintainability.
