import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './core/App';
import './index.css';
import { bootstrapTheme } from './shared/features/settings/useTheme';

// Apply the stored theme before the first paint. Doing it in a component would
// render one frame in the wrong theme, which a dark-mode user sees as a white
// flash on every reload.
bootstrapTheme();

// Register the PWA service worker (auto-updates on new version).
if (import.meta.env.PROD) {
  void import('./registerSW').then(({ registerSW }) => registerSW());
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
