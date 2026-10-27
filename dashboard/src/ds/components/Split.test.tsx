import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Split } from "./Panel";

afterEach(cleanup);

describe("the page split", () => {
  it("scrolls the centre back to the top when what it shows changes, and only then", () => {
    const scrollTo = vi.fn();
    Element.prototype.scrollTo = scrollTo as unknown as typeof Element.prototype.scrollTo;
    const { rerender } = render(<Split side={<nav />} view="session:1">one</Split>);
    scrollTo.mockClear();

    rerender(<Split side={<nav />} view="session:1">one, updated</Split>);
    expect(scrollTo).not.toHaveBeenCalled();

    rerender(<Split side={<nav />} view="session:2">two</Split>);
    expect(scrollTo).toHaveBeenCalledWith(0, 0);
    expect(scrollTo.mock.contexts[0]).toBe(screen.getByRole("region", { name: "Focus" }));
  });
});
