import React from "react";
import ReactDOM from "react-dom/client";
import { AppRoot } from "./app/AppRoot";
import "./styles/global.css";
import "./styles/tokens.css";
import "./styles/app.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppRoot />
  </React.StrictMode>,
);
