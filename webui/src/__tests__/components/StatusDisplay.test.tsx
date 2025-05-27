import React from "react";
import { render, screen } from "@testing-library/react";
import StatusDisplay from "@/components/StatusDisplay";

describe("StatusDisplay Component", () => {
  const defaultProps = {
    status: "Test status message",
  };

  it("renders with default props", () => {
    render(<StatusDisplay {...defaultProps} />);

    expect(screen.getByText("Test status message")).toBeInTheDocument();

    // Check default type is 'info'
    const container = screen.getByText("Test status message").parentElement;
    expect(container).toHaveClass(
      "bg-blue-50",
      "border-blue-200",
      "text-blue-800"
    );
  });

  it("renders with custom status text", () => {
    render(<StatusDisplay status="Custom status" />);

    expect(screen.getByText("Custom status")).toBeInTheDocument();
  });

  describe("status types", () => {
    const types = ["info", "warning", "error", "success"] as const;

    types.forEach((type) => {
      it(`renders ${type} type correctly`, () => {
        render(<StatusDisplay {...defaultProps} type={type} />);

        const container = screen.getByText("Test status message").parentElement;

        const typeClassMap = {
          info: ["bg-blue-50", "border-blue-200", "text-blue-800"],
          warning: ["bg-amber-50", "border-amber-200", "text-amber-800"],
          error: ["bg-red-50", "border-red-200", "text-red-800"],
          success: ["bg-green-50", "border-green-200", "text-green-800"],
        };

        typeClassMap[type].forEach((className) => {
          expect(container).toHaveClass(className);
        });
      });
    });
  });

  it("renders with icon", () => {
    const TestIcon = () => <span data-testid="test-icon">🔔</span>;

    render(<StatusDisplay {...defaultProps} icon={<TestIcon />} />);

    expect(screen.getByTestId("test-icon")).toBeInTheDocument();
    expect(screen.getByText("Test status message")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const customClass = "custom-status-class";
    render(<StatusDisplay {...defaultProps} className={customClass} />);

    const container = screen.getByText("Test status message").parentElement;
    expect(container).toHaveClass(customClass);
  });

  it("has proper structure and styling", () => {
    render(<StatusDisplay {...defaultProps} />);

    const container = screen.getByText("Test status message").parentElement;

    // Check base classes
    expect(container).toHaveClass(
      "border",
      "rounded-md",
      "p-4",
      "flex",
      "items-center"
    );

    // Check text styling
    const textElement = screen.getByText("Test status message");
    expect(textElement).toHaveClass("font-medium");
  });

  it("renders icon with proper spacing", () => {
    const TestIcon = () => <span data-testid="test-icon">⚠️</span>;

    render(<StatusDisplay {...defaultProps} icon={<TestIcon />} />);

    const iconContainer = screen.getByTestId("test-icon").parentElement;
    expect(iconContainer).toHaveClass("mr-3");
  });

  it("renders without icon when not provided", () => {
    render(<StatusDisplay {...defaultProps} />);

    // Should not have any icon container
    const container = screen.getByText("Test status message").parentElement;
    const iconContainer = container?.querySelector(".mr-3");
    expect(iconContainer).not.toBeInTheDocument();
  });

  describe("accessibility", () => {
    it("has proper text content", () => {
      render(<StatusDisplay status="Important message" type="warning" />);

      expect(screen.getByText("Important message")).toBeInTheDocument();
    });

    it("maintains readability with different types", () => {
      const { rerender } = render(<StatusDisplay status="Test" type="info" />);

      let container = screen.getByText("Test").parentElement;
      expect(container).toHaveClass("text-blue-800");

      rerender(<StatusDisplay status="Test" type="error" />);
      container = screen.getByText("Test").parentElement;
      expect(container).toHaveClass("text-red-800");
    });
  });

  describe("edge cases", () => {
    it("handles empty status", () => {
      render(<StatusDisplay status="" />);

      const container = document.querySelector(".font-medium");
      expect(container).toBeInTheDocument();
      expect(container).toHaveTextContent("");
    });

    it("handles long status text", () => {
      const longStatus =
        "This is a very long status message that should still render correctly and maintain proper styling";
      render(<StatusDisplay status={longStatus} />);

      expect(screen.getByText(longStatus)).toBeInTheDocument();
    });

    it("handles special characters in status", () => {
      const specialStatus = "Status with special chars: @#$%^&*()_+";
      render(<StatusDisplay status={specialStatus} />);

      expect(screen.getByText(specialStatus)).toBeInTheDocument();
    });
  });
});
