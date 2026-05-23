import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { PlatformThemeProvider } from "./theme/PlatformThemeProvider";
import "./App.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PlatformThemeProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </PlatformThemeProvider>
  </React.StrictMode>,
);
