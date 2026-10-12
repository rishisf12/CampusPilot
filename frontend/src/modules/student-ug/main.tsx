import React from 'react';
import ReactDOM from 'react-dom/client';
import { StudentUGRoutes } from './routes';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <StudentUGRoutes />
  </React.StrictMode>
);

export default StudentUGRoutes;
