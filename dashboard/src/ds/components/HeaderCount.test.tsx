import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HiddenSessionsCount } from "./HeaderCount";

afterEach(cleanup);

describe("the header's hidden sessions count", () => {
  it("says how many sessions are hidden and opens their list", () => {
    const onOpen = vi.fn();
    render(<HiddenSessionsCount count={3} onOpen={onOpen} />);

    fireEvent.click(screen.getByRole("button", { name: /3 hidden/ }));

    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("shows nothing while no session is hidden", () => {
    const { container } = render(<HiddenSessionsCount count={0} onOpen={() => {}} />);

    expect(container.textContent).toBe("");
  });
});
