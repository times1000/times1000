import React, { useState, useEffect } from 'react';

interface Log {
  id: string;
  agentId: string;
  planId: string;
  operation: string;
  model: string;
  prompt: string;
  response: string;
  tokensPrompt: number;
  tokensCompletion: number;
  costUsd: number;
  durationMs: number;
  status: string;
  createdAt: string;
  errorMessage?: string;
}

interface Pagination {
  page: number;
  limit: number;
  totalItems: number;
  totalPages: number;
}

interface LogViewerProps {
  agentId?: string;
}

const LogViewer: React.FC<LogViewerProps> = ({ agentId }) => {
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
  
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        setLoading(true);
        const url = agentId 
          ? `/api/logs/agent/${agentId}?page=${pagination.page}&limit=${pagination.limit}`
          : `/api/logs?page=${pagination.page}&limit=${pagination.limit}`;
        
        const response = await fetch(url);
        
        if (!response.ok) {
          throw new Error('Failed to fetch logs');
        }
        
        const data = await response.json();
        setLogs(data.logs);
        setPagination(data.pagination);
      } catch (err) {
        console.error('Error fetching logs:', err);
        setError(err instanceof Error ? err.message : 'Failed to load logs');
      } finally {
        setLoading(false);
      }
    };
    
    fetchLogs();
  }, [agentId, pagination.page, pagination.limit]);
  
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
      <h2>{agentId ? 'Agent LLM API Logs' : 'All LLM API Logs'}</h2>
      
      {logs.length === 0 ? (
        <p className="no-logs">No logs found.</p>
      ) : (
        <>
          <div className="logs-table-container">
            <table className="logs-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Operation</th>
                  <th>Model</th>
                  <th>Status</th>
                  <th>Tokens</th>
                  <th>Duration</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id} className={`log-row status-${log.status}`}>
                    <td>{formatDate(log.createdAt)}</td>
                    <td>{log.operation}</td>
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
                        onClick={() => handleViewDetails(log)}
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
              
              <div className="log-details-row">
                <span className="label">Operation:</span>
                <span className="value">{selectedLog.operation}</span>
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LogViewer;