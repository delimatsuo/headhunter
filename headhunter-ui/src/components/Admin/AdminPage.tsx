import React, { useState } from 'react';
import { AllowedUsersPanel } from './AllowedUsersPanel';
import { BiasMetricsDashboard } from './BiasMetricsDashboard';
import './AdminPage.css';

type AdminTab = 'users' | 'bias';

/**
 * AdminPage provides administrative functions including:
 * - Access Control: Manage allowed users and roles
 * - Bias Metrics: Monitor selection rates and adverse impact
 */
export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdminTab>('users');

  return (
    <div className="admin-page">
      <div className="dashboard-header">
        <h1>Admin</h1>
        <p>Manage access control and monitor bias metrics</p>
      </div>

      <div className="admin-tabs">
        <button
          className={`tab-button ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          Access Control
        </button>
        <button
          className={`tab-button ${activeTab === 'bias' ? 'active' : ''}`}
          onClick={() => setActiveTab('bias')}
        >
          Bias Metrics
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'users' && <AllowedUsersPanel />}
        {activeTab === 'bias' && <BiasMetricsDashboard />}
      </div>
    </div>
  );
};

export default AdminPage;
