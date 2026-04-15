import React from "react";
import ReactDOM from "react-dom/client";
import * as AppModule from "./App.jsx";
import "./styles.css";

const App = AppModule.default || AppModule.App || (() => null);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
