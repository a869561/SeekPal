import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "react-hot-toast";
import "./index.css";
import App from "./App.jsx";
import { applyFontSize } from "./components/settings/FontSizeSelector.jsx";

applyFontSize(localStorage.getItem("seekpal_fontsize") || "md");

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
    <Toaster position="top-right" />
  </StrictMode>
);
