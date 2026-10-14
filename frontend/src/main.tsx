import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './core/App';
import './index.css';
// import './telemetry'; // Disabled - backend TELEMETRY_ENABLED=false

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
