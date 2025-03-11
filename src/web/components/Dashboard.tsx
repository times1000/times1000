import React from 'react';
import { Link } from 'react-router-dom';
import { AgentData, AgentStatus } from '../../types/agent';

interface DashboardProps {
  agents: AgentData[];
  onDeleteAgent: (agentId: string) => Promise<void>;
}

const Dashboard: React.FC<DashboardProps> = ({ agents, onDeleteAgent }) => {
  const handleDelete = async (agentId: string, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    
    if (window.confirm('Are you sure you want to delete this agent?')) {
      try {
        await onDeleteAgent(agentId);
      } catch (error) {
        console.error('Error deleting agent:', error);
        alert('Failed to delete agent');
      }
    }
  };
  
  const getStatusClass = (status: AgentStatus): string => {
    switch (status) {
      case AgentStatus.IDLE:
        return 'status-idle';
      case AgentStatus.PLANNING:
        return 'status-planning';
      case AgentStatus.AWAITING_APPROVAL:
        return 'status-awaiting';
      case AgentStatus.EXECUTING:
        return 'status-executing';
      case AgentStatus.ERROR:
        return 'status-error';
      default:
        return '';
    }
  };
  
  // Filter agents awaiting approval
  const awaitingApprovalAgents = agents.filter(agent => agent.status === AgentStatus.AWAITING_APPROVAL);
  
  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <Link to="/agents/new" className="button create-agent-button">
          Create New Agent
        </Link>
      </div>
      
      {awaitingApprovalAgents.length > 0 && (
        <div className="awaiting-approval-banner">
          <h2>Agents Awaiting Approval: {awaitingApprovalAgents.length}</h2>
          <p>
            You have agents with plans that need your approval.
            <Link to="/pending-approvals" className="view-approvals-link">
              View Pending Approvals
            </Link>
          </p>
        </div>
      )}
      
      {agents.length === 0 ? (
        <div className="no-agents">
          <p>No agents created yet. Click &quot;Create New Agent&quot; to get started.</p>
        </div>
      ) : (
        <div className="agent-grid">
          {agents.map(agent => (
            <Link to={`/agents/${agent.id}`} key={agent.id} className="agent-card">
              <div className="agent-card-header">
                <h2>{agent.name}</h2>
                <div className={`agent-status ${getStatusClass(agent.status)}`}>
                  {agent.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </div>
              </div>
              
              {/* agent.type no longer exists */}
              <p className="agent-description">{agent.description}</p>
              
              <div className="agent-capabilities">
                <h3>Capabilities:</h3>
                <ul>
                  {agent.capabilities?.map((capability, index) => (
                    <li key={index}>{capability}</li>
                  ))}
                </ul>
              </div>
              
              <button 
                className="delete-button"
                onClick={(e) => handleDelete(agent.id, e)}
              >
                Delete
              </button>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default Dashboard;