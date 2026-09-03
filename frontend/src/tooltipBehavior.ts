export const tooltipPopperModifiers = [
  {
    name: "offset",
    options: { offset: [0, 10] }
  },
  {
    name: "flip",
    options: {
      fallbackPlacements: ["bottom", "right", "left"],
      padding: 8
    }
  },
  {
    name: "preventOverflow",
    options: {
      altAxis: true,
      boundary: "viewport",
      padding: 8,
      tether: true
    }
  }
];

function referencesTooltip(element: Element, tooltipId: string) {
  return (element.getAttribute("aria-describedby") ?? "")
    .split(/\s+/)
    .includes(tooltipId);
}

export function dismissVisibleTooltips(documentRoot: Document = document) {
  const tooltips = documentRoot.querySelectorAll<HTMLElement>(
    '[role="tooltip"][id]'
  );
  const anchors = documentRoot.querySelectorAll<HTMLElement>(
    "[aria-describedby]"
  );

  tooltips.forEach((tooltip) => {
    anchors.forEach((anchor) => {
      if (!referencesTooltip(anchor, tooltip.id)) {
        return;
      }
      anchor.dispatchEvent(new Event("mouseout", { bubbles: true }));
      anchor.dispatchEvent(new Event("mouseleave"));
      anchor.dispatchEvent(new Event("touchend", { bubbles: true }));
    });
  });
}

export function installGlobalTooltipDismissal(
  documentRoot: Document = document
) {
  const dismiss = () => dismissVisibleTooltips(documentRoot);
  documentRoot.addEventListener("pointerdown", dismiss, true);

  return () => {
    documentRoot.removeEventListener("pointerdown", dismiss, true);
  };
}
