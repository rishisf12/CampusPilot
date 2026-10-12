import React from 'react';
import ReactDOM from 'react-dom/client';
import { FacultyRoutes } from './routes';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <FacultyRoutes />
  </React.StrictMode>
);

export default FacultyRoutes;
