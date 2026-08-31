import { describe, expect, it, vi } from "vitest";
import {
  dismissVisibleTooltips,
  installGlobalTooltipDismissal
} from "./tooltipBehavior";

describe("globalno ponašanje tooltip-a", () => {
  it("zatvara vidljiv tooltip bez presretanja klika", () => {
    const dispatched: string[] = [];
    const tooltip = { id: "help-tooltip" };
    const anchor = {
      getAttribute: () => "other-tooltip help-tooltip",
      dispatchEvent: (event: Event) => {
        dispatched.push(event.type);
        return true;
      }
    };
    const documentRoot = {
      querySelectorAll: (selector: string) =>
        selector.includes('[role="tooltip"') ? [tooltip] : [anchor]
    } as unknown as Document;

    dismissVisibleTooltips(documentRoot);

    expect(dispatched).toEqual(["mouseout", "mouseleave", "touchend"]);
  });

  it("zatvara tooltip na pointerdown i uklanja listener pri cleanup-u", () => {
    let listener: EventListener | undefined;
    const addEventListener = vi.fn(
      (_type: string, callback: EventListenerOrEventListenerObject) => {
        listener = callback as EventListener;
      }
    );
    const removeEventListener = vi.fn();
    const documentRoot = {
      addEventListener,
      removeEventListener,
      querySelectorAll: () => []
    } as unknown as Document;

    const cleanup = installGlobalTooltipDismissal(documentRoot);
    listener?.(new Event("pointerdown"));
    cleanup();

    expect(addEventListener).toHaveBeenCalledWith(
      "pointerdown",
      expect.any(Function),
      true
    );
    expect(removeEventListener).toHaveBeenCalledWith(
      "pointerdown",
      expect.any(Function),
      true
    );
  });
});
