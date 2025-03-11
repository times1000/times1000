import React, { useState } from 'react';
import LogViewer from './LogViewer';

const LogsDashboard: React.FC = () => {
  const [logType, setLogType] = useState<'llm' | 'system'>('llm');

  return (
    <div className="container">
      <div className="dashboard-header">
        <h1>Logs Dashboard</h1>
        <div className="log-type-tabs">
          <button 
            className={`tab-button ${logType === 'llm' ? 'active' : ''}`}
            onClick={() => setLogType('llm')}
          >
            LLM Logs
          </button>
          <button 
            className={`tab-button ${logType === 'system' ? 'active' : ''}`}
            onClick={() => setLogType('system')}
          >
            System Logs
          </button>
        </div>
      </div>
      
      <div className="dashboard-content">
        <LogViewer logType={logType} />
      </div>
    </div>
  );
};

export default LogsDashboard;