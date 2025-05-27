# Testing Guide for TransferBox WebUI

This document provides comprehensive information about the testing setup and practices for the TransferBox frontend application.

## Overview

The TransferBox WebUI uses Jest as the primary testing framework along with React Testing Library for component testing. The testing setup is configured to work seamlessly with Next.js and TypeScript.

## Testing Stack

- **Jest**: JavaScript testing framework
- **React Testing Library**: Testing utilities for React components
- **Jest DOM**: Custom Jest matchers for DOM elements
- **User Event**: Library for simulating user interactions

## Project Structure

```
src/
├── __tests__/
│   ├── components/          # Component tests
│   ├── hooks/              # Custom hook tests
│   ├── services/           # API service tests
│   └── setup.d.ts          # TypeScript declarations for Jest matchers
├── components/             # React components
├── hooks/                  # Custom React hooks
├── services/              # API services
└── types/                 # TypeScript type definitions
```

## Running Tests

### Basic Commands

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage report
npm run test:coverage
```

### Test Coverage

The project is configured with coverage thresholds:

- **Statements**: 70%
- **Branches**: 70%
- **Functions**: 70%
- **Lines**: 70%

## Configuration

### Jest Configuration (`jest.config.js`)

The Jest configuration includes:

- Next.js integration via `next/jest`
- TypeScript support
- Module path mapping (`@/` → `src/`)
- Coverage collection and thresholds
- Custom setup files

### Setup Files

- `jest.setup.js`: Global test setup including mocks for Next.js router and WebSocket
- `src/__tests__/setup.d.ts`: TypeScript declarations for Jest DOM matchers

## Testing Patterns

### Component Testing

Components are tested for:

- Rendering with default and custom props
- User interactions (clicks, form submissions)
- Conditional rendering
- Accessibility features
- CSS classes and styling

Example:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Button from "@/components/Button";

describe("Button Component", () => {
  it("handles click events", async () => {
    const user = userEvent.setup();
    const handleClick = jest.fn();

    render(<Button label="Test" onClick={handleClick} />);

    await user.click(screen.getByRole("button"));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### Hook Testing

Custom hooks are tested using `renderHook` from React Testing Library:

```typescript
import { renderHook, act } from "@testing-library/react";
import { useTransferState } from "@/hooks/useTransferState";

describe("useTransferState", () => {
  it("initializes with default state", () => {
    const { result } = renderHook(() => useTransferState());

    expect(result.current.isTransferring).toBe(false);
  });
});
```

### Service Testing

API services are tested with mocked fetch calls:

```typescript
import { apiService } from "@/services/api";

// Mock fetch globally
beforeEach(() => {
  (global.fetch as jest.Mock).mockClear();
});

describe("apiService", () => {
  it("loads app metadata", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ appName: "TransferBox" }),
    });

    const result = await apiService.loadAppMetadata();

    expect(result).toEqual({ appName: "TransferBox" });
  });
});
```

## Mocking

### Global Mocks

The following are mocked globally in `jest.setup.js`:

- Next.js router (`next/navigation`)
- WebSocket API
- Fetch API

### Module Mocking

Use Jest's module mocking for external dependencies:

```typescript
jest.mock("@/constants", () => ({
  API_BASE_URL: "http://localhost:8000",
}));
```

## Best Practices

### Test Organization

1. **Group related tests** using `describe` blocks
2. **Use descriptive test names** that explain the expected behavior
3. **Follow the AAA pattern**: Arrange, Act, Assert
4. **Test one thing at a time** in each test case

### Component Testing

1. **Test user interactions** rather than implementation details
2. **Use semantic queries** (getByRole, getByLabelText) over CSS selectors
3. **Test accessibility** features and ARIA attributes
4. **Mock external dependencies** to isolate component behavior

### Hook Testing

1. **Test state changes** and side effects
2. **Use act()** for state updates
3. **Test error conditions** and edge cases
4. **Mock dependencies** that hooks rely on

### Service Testing

1. **Mock HTTP requests** using Jest mocks
2. **Test both success and error scenarios**
3. **Verify request parameters** and headers
4. **Test error handling** and fallback behavior

## Debugging Tests

### Common Issues

1. **Act warnings**: Wrap state updates in `act()`
2. **Async operations**: Use `await` and proper async/await patterns
3. **Module resolution**: Check path mappings in Jest config
4. **Mock issues**: Ensure mocks are properly reset between tests

### Debugging Tools

```bash
# Run specific test file
npm test Button.test.tsx

# Run tests matching pattern
npm test -- --testNamePattern="renders correctly"

# Debug mode
npm test -- --detectOpenHandles --forceExit
```

## Coverage Reports

Coverage reports are generated in the `coverage/` directory and include:

- HTML report (`coverage/lcov-report/index.html`)
- LCOV format for CI/CD integration
- Console summary

## Continuous Integration

Tests run automatically on:

- Pull requests
- Main branch commits
- Release builds

The CI pipeline includes:

- Unit tests
- Coverage reporting
- Linting and type checking

## Contributing

When adding new features:

1. **Write tests first** (TDD approach recommended)
2. **Maintain coverage thresholds**
3. **Follow existing patterns** and conventions
4. **Update documentation** for new testing utilities

## Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Jest DOM Matchers](https://github.com/testing-library/jest-dom)
- [User Event](https://testing-library.com/docs/user-event/intro/)
