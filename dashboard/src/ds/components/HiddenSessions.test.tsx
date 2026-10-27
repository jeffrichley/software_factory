import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HiddenSessions } from "./InboxCards";

afterEach(cleanup);

const hidden = [
  { id: "4", kind: "ad hoc", repo: "jeff/worlds", machine: "mac-mini" },
  { id: "7", kind: "Ticket Job", repo: "jeff/factory", machine: "mbp" },
];

describe("the inbox's hidden sessions", () => {
  it("offers to list how many sessions are hidden", () => {
    const onToggle = vi.fn();
    render(<HiddenSessions sessions={hidden} open={false} onToggle={onToggle} onOpen={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "List 2 hidden sessions" }));

    expect(onToggle).toHaveBeenCalledOnce();
    expect(screen.queryByRole("list", { name: "Hidden sessions" })).toBeNull();
  });

  it("lists them, each opening its detail", () => {
    const onOpen = vi.fn();
    render(<HiddenSessions sessions={hidden} open onToggle={() => {}} onOpen={onOpen} />);

    fireEvent.click(screen.getByRole("button", { name: /Ticket Job · factory · mbp/ }));

    expect(onOpen).toHaveBeenCalledWith("7");
  });

  it("scrolls the list into view when it opens, e.g. from the header's count", () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    const { rerender } = render(<HiddenSessions sessions={hidden} open={false} onToggle={() => {}} onOpen={() => {}} />);
    expect(scroll).not.toHaveBeenCalled();

    rerender(<HiddenSessions sessions={hidden} open onToggle={() => {}} onOpen={() => {}} />);

    expect(scroll).toHaveBeenCalledOnce();
  });

  it("shows nothing while no session is hidden", () => {
    const { container } = render(<HiddenSessions sessions={[]} open onToggle={() => {}} onOpen={() => {}} />);

    expect(container.textContent).toBe("");
  });
});
