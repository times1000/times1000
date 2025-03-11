import React from 'react';
import LogViewer from './LogViewer';

const LogsDashboard: React.FC = () => {
  return (
    <div className="container">
      <div className="dashboard-header">
        <h1>LLM API Logs</h1>
      </div>
      
      <div className="dashboard-content">
        <LogViewer />
      </div>
    </div>
  );
};

export default LogsDashboard;