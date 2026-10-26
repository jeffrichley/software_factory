import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./ds";
import { Gallery } from "./gallery/Gallery";

// The dashboard proper arrives with the tracer bullet (#19); until then the root shows the design-system gallery.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Gallery />
  </StrictMode>,
);
