import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Button from "@/components/Button";

describe("Button Component", () => {
  const defaultProps = {
    label: "Test Button",
  };

  it("renders with default props", () => {
    render(<Button {...defaultProps} />);

    const button = screen.getByRole("button", { name: /test button/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute("type", "button");
    expect(button).not.toBeDisabled();
  });

  it("renders with custom label", () => {
    render(<Button label="Custom Label" />);

    expect(
      screen.getByRole("button", { name: /custom label/i })
    ).toBeInTheDocument();
  });

  it("handles click events", async () => {
    const user = userEvent.setup();
    const handleClick = jest.fn();

    render(<Button {...defaultProps} onClick={handleClick} />);

    const button = screen.getByRole("button", { name: /test button/i });
    await user.click(button);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("does not call onClick when disabled", async () => {
    const user = userEvent.setup();
    const handleClick = jest.fn();

    render(<Button {...defaultProps} onClick={handleClick} disabled />);

    const button = screen.getByRole("button", { name: /test button/i });
    await user.click(button);

    expect(handleClick).not.toHaveBeenCalled();
    expect(button).toBeDisabled();
  });

  describe("variants", () => {
    const variants = [
      "primary",
      "secondary",
      "success",
      "danger",
      "warning",
    ] as const;

    variants.forEach((variant) => {
      it(`renders ${variant} variant correctly`, () => {
        render(<Button {...defaultProps} variant={variant} />);

        const button = screen.getByRole("button", { name: /test button/i });
        expect(button).toBeInTheDocument();

        // Check that the button has the appropriate variant classes
        const variantClassMap = {
          primary: "bg-blue-600",
          secondary: "bg-white",
          success: "bg-green-600",
          danger: "bg-red-600",
          warning: "bg-amber-500",
        };

        expect(button).toHaveClass(variantClassMap[variant]);
      });
    });
  });

  describe("sizes", () => {
    const sizes = ["sm", "md", "lg"] as const;

    sizes.forEach((size) => {
      it(`renders ${size} size correctly`, () => {
        render(<Button {...defaultProps} size={size} />);

        const button = screen.getByRole("button", { name: /test button/i });

        const sizeClassMap = {
          sm: "px-2 py-1 text-xs",
          md: "px-3 py-1.5 text-sm",
          lg: "px-4 py-2 text-base",
        };

        expect(button).toHaveClass(sizeClassMap[size]);
      });
    });
  });

  it("renders with full width when specified", () => {
    render(<Button {...defaultProps} fullWidth />);

    const button = screen.getByRole("button", { name: /test button/i });
    expect(button).toHaveClass("w-full");
  });

  it("applies custom className", () => {
    const customClass = "custom-test-class";
    render(<Button {...defaultProps} className={customClass} />);

    const button = screen.getByRole("button", { name: /test button/i });
    expect(button).toHaveClass(customClass);
  });

  it("renders with icon", () => {
    const TestIcon = () => <span data-testid="test-icon">🔥</span>;

    render(<Button {...defaultProps} icon={<TestIcon />} />);

    expect(screen.getByTestId("test-icon")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /test button/i })
    ).toBeInTheDocument();
  });

  it("sets correct button type", () => {
    render(<Button {...defaultProps} type="submit" />);

    const button = screen.getByRole("button", { name: /test button/i });
    expect(button).toHaveAttribute("type", "submit");
  });

  it("applies disabled styles when disabled", () => {
    render(<Button {...defaultProps} disabled />);

    const button = screen.getByRole("button", { name: /test button/i });
    expect(button).toHaveClass("cursor-not-allowed", "opacity-60");
    expect(button).toBeDisabled();
  });

  it("has proper accessibility attributes", () => {
    render(<Button {...defaultProps} />);

    const button = screen.getByRole("button", { name: /test button/i });
    expect(button).toHaveClass("focus:outline-none", "focus:ring-2");
  });

  it("handles keyboard interactions", () => {
    const handleClick = jest.fn();
    render(<Button {...defaultProps} onClick={handleClick} />);

    const button = screen.getByRole("button", { name: /test button/i });

    // Test Enter key
    fireEvent.keyDown(button, { key: "Enter", code: "Enter" });
    button.focus();
    fireEvent.keyDown(button, { key: "Enter" });

    // Test Space key
    fireEvent.keyDown(button, { key: " ", code: "Space" });
  });
});
