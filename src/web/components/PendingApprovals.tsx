import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Socket } from 'socket.io-client';
import { AgentData, AgentStatus } from '../../types/agent';

interface PlanStep {
  id: string;
  description: string;
  status: string;
  position: number;
  estimatedDuration?: number;
}

interface PlanData {
  id: string;
  agentId: string;
  command: string;
  description: string;
  reasoning: string;
  status: string;
  steps: PlanStep[];
}

interface PendingApprovalItem {
  agent: AgentData;
  plan: PlanData;
}

interface PendingApprovalsProps {
  socket: Socket;
}

const PendingApprovals = ({ socket }: PendingApprovalsProps) => {
  const [pendingItems, setPendingItems] = useState<PendingApprovalItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Function to fetch all agents with awaiting_approval status
  const fetchPendingApprovals = async () => {
    try {
      const response = await fetch('/api/agents');
      if (!response.ok) {
        throw new Error('Failed to fetch agents');
      }

      const data = await response.json();
      const agents = data.agents || [];

      // Filter agents with awaiting_approval status
      const awaitingApprovalAgents = agents.filter((agent: AgentData) => 
        agent.status === AgentStatus.AWAITING_APPROVAL
      );

      // For each agent, fetch their current plan
      const pendingItemsData = await Promise.all(
        awaitingApprovalAgents.map(async (agent: AgentData) => {
          const planResponse = await fetch(`/api/agents/${agent.id}/current-plan`);
          if (!planResponse.ok) {
            return null;
          }

          const planData = await planResponse.json();
          if (!planData.hasPlan) {
            return null;
          }

          return {
            agent,
            plan: planData
          };
        })
      );

      // Filter out null values and set state
      setPendingItems(pendingItemsData.filter(Boolean));
      setLoading(false);
    } catch (err) {
      setError('Error loading pending approvals');
      console.error('Error fetching pending approvals:', err);
      setLoading(false);
    }
  };

  // Approve a plan
  const approvePlan = async (planId: string) => {
    try {
      const response = await fetch(`/api/plans/${planId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Failed to approve plan');
      }

      // Remove the approved item from the list
      setPendingItems(prev => prev.filter(item => item.plan.id !== planId));
    } catch (err) {
      setError('Error approving plan');
      console.error('Error approving plan:', err);
    }
  };

  // Reject a plan
  const rejectPlan = async (planId: string) => {
    try {
      const response = await fetch(`/api/plans/${planId}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Failed to reject plan');
      }

      // Remove the rejected item from the list
      setPendingItems(prev => prev.filter(item => item.plan.id !== planId));
    } catch (err) {
      setError('Error rejecting plan');
      console.error('Error rejecting plan:', err);
    }
  };

  // Send a new command to modify the plan
  const sendCommand = async (agentId: string, command: string) => {
    try {
      const response = await fetch(`/api/agents/${agentId}/command`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ command })
      });

      if (!response.ok) {
        throw new Error('Failed to send command');
      }

      // Refresh pending approvals after sending command
      fetchPendingApprovals();
    } catch (err) {
      setError('Error sending command');
      console.error('Error sending command:', err);
    }
  };

  useEffect(() => {
    // Fetch pending approvals on component mount
    fetchPendingApprovals();

    // Listen for socket events
    socket.on('agents:awaiting_approval', (data: PendingApprovalItem[]) => {
      setPendingItems(data);
    });

    socket.on('plan:approved', ({ planId }) => {
      setPendingItems(prev => prev.filter(item => item.plan.id !== planId));
    });

    socket.on('plan:rejected', ({ planId }) => {
      setPendingItems(prev => prev.filter(item => item.plan.id !== planId));
    });

    socket.on('plan:created', () => {
      fetchPendingApprovals();
    });

    // Clean up socket listeners
    return () => {
      socket.off('agents:awaiting_approval');
      socket.off('plan:approved');
      socket.off('plan:rejected');
      socket.off('plan:created');
    };
  }, [socket]);

  if (loading) {
    return <div className="loading">Loading pending approvals...</div>;
  }

  if (error) {
    return (
      <div className="error-container">
        <p className="error-message">{error}</p>
        <button onClick={() => {
          setError(null);
          fetchPendingApprovals();
        }}>
          Try Again
        </button>
      </div>
    );
  }

  if (pendingItems.length === 0) {
    return (
      <div className="pending-approvals empty-state">
        <h2>Pending Approvals</h2>
        <p>No plans awaiting approval</p>
      </div>
    );
  }

  return (
    <div className="pending-approvals">
      <h2>Pending Approvals</h2>
      <div className="approval-items">
        {pendingItems.map(({ agent, plan }) => (
          <div key={plan.id} className="approval-item">
            <div className="approval-header">
              <h3>{agent.name}</h3>
              <span className="status-badge awaiting">Awaiting Approval</span>
              {agent.type && <span className="agent-type">{agent.type}</span>}
            </div>
            
            <div className="plan-details">
              <p><strong>Command:</strong> {plan.command}</p>
              <p><strong>Description:</strong> {plan.description}</p>
              {plan.reasoning && (
                <div className="plan-reasoning">
                  <p><strong>Reasoning:</strong></p>
                  <p>{plan.reasoning}</p>
                </div>
              )}
              {agent.personalityProfile && (
                <div className="agent-personality">
                  <p><strong>Personality:</strong> {agent.personalityProfile}</p>
                </div>
              )}
            </div>
            
            <div className="plan-steps">
              <h4>Steps:</h4>
              <ol>
                {plan.steps.map((step) => (
                  <li key={step.id}>
                    {step.description}
                    {step.estimatedDuration && (
                      <span className="step-duration">
                        ({Math.round(step.estimatedDuration / 60)} min)
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
            
            <div className="approval-actions">
              <div className="action-buttons">
                <button 
                  className="btn approve-btn"
                  onClick={() => approvePlan(plan.id)}
                >
                  Approve
                </button>
                <button 
                  className="btn reject-btn"
                  onClick={() => rejectPlan(plan.id)}
                >
                  Reject
                </button>
              </div>
              
              <div className="command-form">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const formData = new FormData(e.target as HTMLFormElement);
                    const command = formData.get('command') as string;
                    if (command.trim()) {
                      sendCommand(agent.id, command);
                      (e.target as HTMLFormElement).reset();
                    }
                  }}
                >
                  <input
                    type="text"
                    name="command"
                    placeholder="Enter new command to modify plan..."
                    required
                  />
                  <button type="submit" className="btn cmd-btn">Send</button>
                </form>
              </div>
              
              <div className="view-details">
                <Link to={`/agents/${agent.id}`} className="btn details-btn">
                  View Agent Details
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PendingApprovals;