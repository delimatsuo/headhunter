import React from 'react';
import { AllowedUsersPanel } from './AllowedUsersPanel';

export const AdminPage: React.FC = () => {
  return (
    <div className="admin-page">
      <div className="dashboard-header">
        <h1>Admin</h1>
        <p>Manage access control (allowed users and roles)</p>
      </div>

      <AllowedUsersPanel />
    </div>
  );
};


