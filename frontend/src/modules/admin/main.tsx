import React from 'react';
import ReactDOM from 'react-dom/client';
import { AdminRoutes } from './routes';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AdminRoutes />
  </React.StrictMode>
);

export default AdminRoutes;
