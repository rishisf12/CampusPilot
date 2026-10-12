import React from 'react';
import ReactDOM from 'react-dom/client';
import { StudentPGRoutes } from './routes';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <StudentPGRoutes />
  </React.StrictMode>
);

export default StudentPGRoutes;
