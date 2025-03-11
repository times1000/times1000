import React, { useState, useEffect } from 'react';

// LLM Log type
interface LLMLog {
  id: string;
  agentId: string;
  planId: string;
  operation: string;
  model: string;
  provider: string;
  prompt: string;
  response: string;
  tokensPrompt: number;
  tokensCompletion: number;
  costUsd: number;
  durationMs: number;
  status: string;
  createdAt: string;
  errorMessage?: string;
  logType: string;
}

// System Log type
interface SystemLog {
  id: string;
  agentId: string;
  planId: string;
  source: string;
  operation: string;
  message: string;
  details: string;
  level: string;
  durationMs: number;
  createdAt: string;
}

// Union type for logs
type Log = LLMLog | SystemLog;

// Type guard functions
function isLLMLog(log: Log): log is LLMLog {
  return (log as LLMLog).model !== undefined;
}

function isSystemLog(log: Log): log is SystemLog {
  return (log as SystemLog).source !== undefined;
}

interface Pagination {
  page: number;
  limit: number;
  totalItems: number;
  totalPages: number;
}

interface LogViewerProps {
  agentId?: string;
  logType?: 'llm' | 'system';
}

const LogViewer: React.FC<LogViewerProps> = ({ agentId, logType }) => {
  // Determine log type from URL hash if not provided via props
  const [activeLogType, setActiveLogType] = useState<'llm' | 'system'>('llm');
  
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState<Pagination>({
    page: 1,
    limit: 10,
    totalItems: 0,
    totalPages: 0
  });
  
  // Selected log for detailed view
  const [selectedLog, setSelectedLog] = useState<Log | null>(null);
  
  // Handle hash changes
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash;
      if (hash === '#/system-logs') {
        setActiveLogType('system');
      } else {
        setActiveLogType('llm');
      }
    };
    
    // Set initial state based on hash
    handleHashChange();
    
    // Listen for hash changes
    window.addEventListener('hashchange', handleHashChange);
    
    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);
  
  // Use the prop if provided, otherwise use the state from hash
  const currentLogType = logType || activeLogType;
  
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        setLoading(true);
        let url = '';
        
        if (agentId) {
          url = `/api/logs/${currentLogType}/agent/${agentId}?page=${pagination.page}&limit=${pagination.limit}`;
        } else {
          url = `/api/logs/${currentLogType}?page=${pagination.page}&limit=${pagination.limit}`;
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch ${currentLogType} logs`);
        }
        
        const data = await response.json();
        setLogs(data.logs);
        setPagination(data.pagination);
      } catch (err) {
        console.error(`Error fetching ${currentLogType} logs:`, err);
        setError(err instanceof Error ? err.message : 'Failed to load logs');
      } finally {
        setLoading(false);
      }
    };
    
    fetchLogs();
  }, [agentId, pagination.page, pagination.limit, currentLogType]);
  
  const handlePageChange = (newPage: number) => {
    if (newPage > 0 && newPage <= pagination.totalPages) {
      setPagination(prev => ({
        ...prev,
        page: newPage
      }));
    }
  };
  
  const handleViewDetails = (log: Log) => {
    setSelectedLog(log);
  };
  
  const handleCloseDetails = () => {
    setSelectedLog(null);
  };
  
  const handleToggleLogType = () => {
    // Reset pagination when switching log types
    setPagination(prev => ({
      ...prev,
      page: 1
    }));
  };
  
  // Format date for display
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };
  
  // Format duration for display
  const formatDuration = (ms: number) => {
    if (ms < 1000) {
      return `${ms}ms`;
    }
    return `${(ms / 1000).toFixed(2)}s`;
  };
  
  if (loading && logs.length === 0) {
    return <div className="loading">Loading logs...</div>;
  }
  
  if (error) {
    return (
      <div className="error-container">
        <h2>Error</h2>
        <p>{error}</p>
      </div>
    );
  }
  
  return (
    <div className="log-viewer">
      <div className="log-header">
        <h2>
          {agentId ? `Agent ${currentLogType.toUpperCase()} Logs` : `All ${currentLogType.toUpperCase()} Logs`}
        </h2>
        
        <div className="log-type-toggle">
          <a 
            href="#/llm-logs" 
            onClick={handleToggleLogType}
            className={`toggle-button ${currentLogType === 'llm' ? 'active' : ''}`}
          >
            LLM Logs
          </a>
          <a 
            href="#/system-logs" 
            onClick={handleToggleLogType}
            className={`toggle-button ${currentLogType === 'system' ? 'active' : ''}`}
          >
            System Logs
          </a>
        </div>
      </div>
      
      {logs.length === 0 ? (
        <p className="no-logs">No logs found.</p>
      ) : (
        <>
          <div className="logs-table-container">
            {logType === 'llm' ? (
              <table className="logs-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Operation</th>
                    <th>Provider</th>
                    <th>Model</th>
                    <th>Status</th>
                    <th>Tokens</th>
                    <th>Duration</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => {
                    if (!isLLMLog(log)) return null;
                    
                    return (
                      <tr 
                        key={log.id} 
                        className={`log-row status-${log.status} clickable-row`}
                        onClick={() => handleViewDetails(log)}
                      >
                        <td>{formatDate(log.createdAt)}</td>
                        <td>{log.operation}</td>
                        <td>{log.provider || 'unknown'}</td>
                        <td>{log.model}</td>
                        <td>
                          <span className={`status-badge ${log.status}`}>
                            {log.status}
                          </span>
                        </td>
                        <td>{log.tokensPrompt + log.tokensCompletion} (${typeof log.costUsd === 'number' ? log.costUsd.toFixed(6) : '0.000000'})</td>
                        <td>{formatDuration(log.durationMs)}</td>
                        <td>
                          <button 
                            className="view-details-button"
                            onClick={(e) => {
                              e.stopPropagation(); // Prevent row click from triggering
                              handleViewDetails(log);
                            }}
                          >
                            View Details
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <table className="logs-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Source</th>
                    <th>Operation</th> 
                    <th>Level</th>
                    <th>Message</th>
                    <th>Duration</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => {
                    if (!isSystemLog(log)) return null;
                    
                    return (
                      <tr 
                        key={log.id} 
                        className={`log-row level-${log.level} clickable-row`}
                        onClick={() => handleViewDetails(log)}
                      >
                        <td>{formatDate(log.createdAt)}</td>
                        <td>{log.source}</td>
                        <td>{log.operation}</td>
                        <td>
                          <span className={`level-badge ${log.level}`}>
                            {log.level}
                          </span>
                        </td>
                        <td>{log.message.length > 50 ? log.message.substring(0, 50) + '...' : log.message}</td>
                        <td>{log.durationMs ? formatDuration(log.durationMs) : 'N/A'}</td>
                        <td>
                          <button 
                            className="view-details-button"
                            onClick={(e) => {
                              e.stopPropagation(); // Prevent row click from triggering
                              handleViewDetails(log);
                            }}
                          >
                            View Details
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          
          <div className="pagination">
            <button 
              onClick={() => handlePageChange(pagination.page - 1)}
              disabled={pagination.page === 1}
            >
              Previous
            </button>
            
            <span className="page-info">
              Page {pagination.page} of {pagination.totalPages}
            </span>
            
            <button 
              onClick={() => handlePageChange(pagination.page + 1)}
              disabled={pagination.page === pagination.totalPages}
            >
              Next
            </button>
          </div>
        </>
      )}
      
      {selectedLog && (
        <div className="log-details-modal">
          <div className="log-details-content">
            <div className="modal-header">
              <h3>Log Details</h3>
              <button 
                className="close-button"
                onClick={handleCloseDetails}
              >
                &times;
              </button>
            </div>
            
            <div className="log-details">
              <div className="log-details-row">
                <span className="label">ID:</span>
                <span className="value">{selectedLog.id}</span>
              </div>
              
              <div className="log-details-row">
                <span className="label">Time:</span>
                <span className="value">{formatDate(selectedLog.createdAt)}</span>
              </div>
              
              {isLLMLog(selectedLog) ? (
                // LLM log specific details
                <>
                  <div className="log-details-row">
                    <span className="label">Operation:</span>
                    <span className="value">{selectedLog.operation}</span>
                  </div>
                  
                  <div className="log-details-row">
                    <span className="label">Provider:</span>
                    <span className="value">{selectedLog.provider || 'unknown'}</span>
                  </div>
                  
                  <div className="log-details-row">
                    <span className="label">Model:</span>
                    <span className="value">{selectedLog.model}</span>
                  </div>
                  
                  <div className="log-details-row">
                    <span className="label">Status:</span>
                    <span className={`value status-badge ${selectedLog.status}`}>
                      {selectedLog.status}
                    </span>
                  </div>
                  
                  <div className="log-details-row">
                    <span className="label">Duration:</span>
                    <span className="value">{formatDuration(selectedLog.durationMs)}</span>
                  </div>
                  
                  <div className="log-details-row">
                    <span className="label">Tokens:</span>
                    <span className="value">
                      Prompt: {selectedLog.tokensPrompt}, Completion: {selectedLog.tokensCompletion}
                    </span>
                  </div>
                  
                  <div className="log-details-row">
                    <span className="label">Estimated Cost:</span>
                    <span className="value">
                      ${typeof selectedLog.costUsd === 'number' ? selectedLog.costUsd.toFixed(6) : '0.000000'}
                    </span>
                  </div>
                  
                  {selectedLog.agentId && (
                    <div className="log-details-row">
                      <span className="label">Agent ID:</span>
                      <span className="value">{selectedLog.agentId}</span>
                    </div>
                  )}
                  
                  {selectedLog.planId && (
                    <div className="log-details-row">
                      <span className="label">Plan ID:</span>
                      <span className="value">{selectedLog.planId}</span>
                    </div>
                  )}
                  
                  {selectedLog.errorMessage && (
                    <div className="log-details-row error">
                      <span className="label">Error:</span>
                      <span className="value error-message">{selectedLog.errorMessage}</span>
                    </div>
                  )}
                  
                  <div className="log-details-section">
                    <h4>Prompt</h4>
                    <pre className="code-block">{
                      typeof selectedLog.prompt === 'string' ? selectedLog.prompt : JSON.stringify(selectedLog.prompt, null, 2)
                    }</pre>
                  </div>
                  
                  {selectedLog.response && (
                    <div className="log-details-section">
                      <h4>Response</h4>
                      <pre className="code-block">{
                        typeof selectedLog.response === 'string' ? selectedLog.response : JSON.stringify(selectedLog.response, null, 2)
                      }</pre>
                    </div>
                  )}
                </>
              ) : (
                // System log specific details
                <>
                  <div className="log-details-row">
                    <span className="label">Source:</span>
                    <span className="value">{selectedLog.source}</span>
                  </div>
                  
                  <div className="log-details-row">
                    <span className="label">Operation:</span>
                    <span className="value">{selectedLog.operation}</span>
                  </div>
                  
                  <div className="log-details-row">
                    <span className="label">Level:</span>
                    <span className={`value level-badge ${selectedLog.level}`}>
                      {selectedLog.level}
                    </span>
                  </div>
                  
                  {selectedLog.durationMs && (
                    <div className="log-details-row">
                      <span className="label">Duration:</span>
                      <span className="value">{formatDuration(selectedLog.durationMs)}</span>
                    </div>
                  )}
                  
                  {selectedLog.agentId && (
                    <div className="log-details-row">
                      <span className="label">Agent ID:</span>
                      <span className="value">{selectedLog.agentId}</span>
                    </div>
                  )}
                  
                  {selectedLog.planId && (
                    <div className="log-details-row">
                      <span className="label">Plan ID:</span>
                      <span className="value">{selectedLog.planId}</span>
                    </div>
                  )}
                  
                  <div className="log-details-section">
                    <h4>Message</h4>
                    <p className="message-content">{selectedLog.message}</p>
                  </div>
                  
                  {selectedLog.details && (
                    <div className="log-details-section">
                      <h4>Details</h4>
                      <pre className="code-block">{
                        typeof selectedLog.details === 'string' && selectedLog.details.startsWith('{') 
                          ? JSON.stringify(JSON.parse(selectedLog.details), null, 2) 
                          : selectedLog.details
                      }</pre>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LogViewer;