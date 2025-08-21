import React from "react";
import { render, screen } from "@testing-library/react";
import ProgressBar from "@/components/ProgressBar";

describe("ProgressBar Component", () => {
  it("renders with default props", () => {
    render(<ProgressBar progress={50} />);

    // Check that percentage is displayed by default
    expect(screen.getByText("50%")).toBeInTheDocument();

    // Check that the progress bar container exists
    const progressContainer = document.querySelector(".w-full");
    expect(progressContainer).toBeInTheDocument();
  });

  it("displays correct percentage", () => {
    render(<ProgressBar progress={75} />);

    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("hides percentage when showPercentage is false", () => {
    render(<ProgressBar progress={50} showPercentage={false} />);

    expect(screen.queryByText("50%")).not.toBeInTheDocument();
  });

  it("displays status text when provided", () => {
    const statusText = "Copying files...";
    render(<ProgressBar progress={30} status={statusText} />);

    expect(screen.getByText(statusText)).toBeInTheDocument();
  });

  it("normalizes progress values outside 0-100 range", () => {
    // Test progress > 100
    const { rerender } = render(<ProgressBar progress={150} />);
    expect(screen.getByText("100%")).toBeInTheDocument();

    // Test progress < 0
    rerender(<ProgressBar progress={-10} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("rounds decimal progress values", () => {
    render(<ProgressBar progress={33.7} />);

    expect(screen.getByText("34%")).toBeInTheDocument();
  });

  describe("variants", () => {
    const variants = ["primary", "success", "warning", "danger"] as const;

    variants.forEach((variant) => {
      it(`renders ${variant} variant correctly`, () => {
        render(<ProgressBar progress={50} variant={variant} />);

        const progressBar = document.querySelector('[style*="width: 50%"]');
        expect(progressBar).toBeInTheDocument();

        const variantClassMap = {
          primary: "bg-blue-600",
          success: "bg-green-600",
          warning: "bg-amber-500",
          danger: "bg-red-600",
        };

        expect(progressBar).toHaveClass(variantClassMap[variant]);
      });
    });
  });

  describe("heights", () => {
    const heights = ["sm", "md", "lg"] as const;

    heights.forEach((height) => {
      it(`renders ${height} height correctly`, () => {
        render(<ProgressBar progress={50} height={height} />);

        const heightClassMap = {
          sm: "h-2",
          md: "h-4",
          lg: "h-6",
        };

        const progressContainer = document.querySelector(".bg-slate-200");
        const progressBar = document.querySelector('[style*="width: 50%"]');

        expect(progressContainer).toHaveClass(heightClassMap[height]);
        expect(progressBar).toHaveClass(heightClassMap[height]);
      });
    });
  });

  it("applies animation classes when animated is true", () => {
    render(<ProgressBar progress={50} animated={true} />);

    const progressBar = document.querySelector('[style*="width: 50%"]');
    expect(progressBar).toHaveClass(
      "transition-all",
      "duration-300",
      "ease-out"
    );
  });

  it("does not apply animation classes when animated is false", () => {
    render(<ProgressBar progress={50} animated={false} />);

    const progressBar = document.querySelector('[style*="width: 50%"]');
    expect(progressBar).not.toHaveClass("transition-all");
    expect(progressBar).not.toHaveClass("duration-300");
    expect(progressBar).not.toHaveClass("ease-out");
  });

  it("applies custom className", () => {
    const customClass = "custom-progress-bar";
    render(<ProgressBar progress={50} className={customClass} />);

    const container = document.querySelector(".w-full");
    expect(container).toHaveClass(customClass);
  });

  it("sets correct width style based on progress", () => {
    render(<ProgressBar progress={75} />);

    const progressBar = document.querySelector('[style*="width: 75%"]');
    expect(progressBar).toBeInTheDocument();
    expect(progressBar).toHaveStyle("width: 75%");
  });

  it("handles zero progress", () => {
    render(<ProgressBar progress={0} />);

    expect(screen.getByText("0%")).toBeInTheDocument();

    const progressBar = document.querySelector('[style*="width: 0%"]');
    expect(progressBar).toBeInTheDocument();
    expect(progressBar).toHaveStyle("width: 0%");
  });

  it("handles full progress", () => {
    render(<ProgressBar progress={100} />);

    expect(screen.getByText("100%")).toBeInTheDocument();

    const progressBar = document.querySelector('[style*="width: 100%"]');
    expect(progressBar).toBeInTheDocument();
    expect(progressBar).toHaveStyle("width: 100%");
  });

  it("displays both status and percentage when both are provided", () => {
    const statusText = "Processing...";
    render(
      <ProgressBar progress={60} status={statusText} showPercentage={true} />
    );

    expect(screen.getByText(statusText)).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
  });

  it("has proper accessibility structure", () => {
    render(<ProgressBar progress={50} status="Loading..." />);

    // Check that the progress bar has proper structure
    const container = document.querySelector(".w-full");
    expect(container).toBeInTheDocument();

    // Check that the background container exists
    const background = document.querySelector(".bg-slate-200");
    expect(background).toBeInTheDocument();
    expect(background).toHaveClass("rounded-full");
  });
});
