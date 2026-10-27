import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Clock } from "./TopBar";

afterEach(cleanup);

describe("the header clock", () => {
  it("shows the local time to the second, with the instant as its machine-readable time", () => {
    const at = new Date(2026, 9, 27, 9, 5, 7).getTime();
    render(<Clock now={at} />);

    const clock = screen.getByText("09:05:07");
    expect(clock.tagName).toBe("TIME");
    expect(clock.getAttribute("datetime")).toBe(new Date(at).toISOString());
  });
});
