import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './core/App';
import './index.css';
// Telemetry beacons to /collect/events. The module self-invokes on import.
// Requires TELEMETRY_ENABLED=true in the backend .env, otherwise the
// collector answers 503 and every monitoring panel stays empty.
import './telemetry';
import { bootstrapTheme } from './shared/features/settings/useTheme';

// Apply the stored theme before the first paint. Doing it in a component would
// render one frame in the wrong theme, which a dark-mode user sees as a white
// flash on every reload.
bootstrapTheme();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
