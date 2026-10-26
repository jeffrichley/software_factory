import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./ds";
import { Dashboard } from "./app/Dashboard";
import { Gallery } from "./gallery/Gallery";

// `?gallery` shows the design-system gallery instead of the dashboard.
const gallery = new URLSearchParams(location.search).has("gallery");

createRoot(document.getElementById("root")!).render(<StrictMode>{gallery ? <Gallery /> : <Dashboard />}</StrictMode>);
