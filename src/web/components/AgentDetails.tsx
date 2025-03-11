import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Socket } from 'socket.io-client';
import { AgentStatus, AgentData } from '../../types/agent';
import { Plan } from '../../types/db';
import PlanViewer from './PlanViewer';
import LogViewer from './LogViewer';

interface AgentDetailsProps {
  socket: Socket;
}

const AgentDetails: React.FC<AgentDetailsProps> = ({ socket }) => {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  
  const [agent, setAgent] = useState<AgentData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [command, setCommand] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'plan' | 'logs'>('plan');
  
  // Fetch agent details on component mount
  useEffect(() => {
    const fetchAgentDetails = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/agents/${agentId}`);
        
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Agent not found');
          }
          throw new Error('Failed to fetch agent details');
        }
        
        const data = await response.json();
        setAgent(data);
      } catch (err) {
        console.error('Error fetching agent details:', err);
        setError(err instanceof Error ? err.message : 'Failed to load agent details');
      } finally {
        setLoading(false);
      }
    };
    
    fetchAgentDetails();
    
    // Set up socket event listeners with optimized updates
    socket.on('agent:updated', (updatedAgent) => {
      if (updatedAgent.id === agentId) {
        setAgent((prevAgent) => prevAgent ? {
          ...prevAgent,
          ...updatedAgent
        } : updatedAgent);
      }
    });
    
    socket.on('plan:created', (plan) => {
      if (plan.agentId === agentId) {
        // Update current plan directly instead of full refresh
        setCurrentPlan(plan);
        // Update agent status if needed
        setAgent(prev => prev ? { ...prev, status: AgentStatus.AWAITING_APPROVAL } : prev);
      }
    });
    
    socket.on('plan:approved', (data) => {
      if (data.agentId === agentId) {
        // Update plan status directly
        setCurrentPlan(prev => prev ? { ...prev, status: 'approved' } : null);
        // Update agent status
        setAgent(prev => prev ? { ...prev, status: AgentStatus.EXECUTING } : prev);
      }
    });
    
    socket.on('plan:rejected', (data) => {
      if (data.agentId === agentId) {
        // Just clear the current plan
        setCurrentPlan(null);
        // Update agent status
        setAgent(prev => prev ? { ...prev, status: AgentStatus.IDLE } : prev);
      }
    });
    
    return () => {
      // Clean up socket listeners
      socket.off('agent:updated');
      socket.off('plan:created');
      socket.off('plan:approved');
      socket.off('plan:rejected');
    };
  }, [agentId, socket]);
  
  // Fetch current plan
  const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
  const [planLoading, setPlanLoading] = useState<boolean>(false);
  
  useEffect(() => {
    const abortController = new AbortController();
    
    const fetchCurrentPlan = async () => {
      if (!agentId) return;
      
      try {
        setPlanLoading(true);
        // Use AbortController signal for fetch requests
        const response = await fetch(`/api/agents/${agentId}/current-plan`, {
          signal: abortController.signal
        });
        
        if (!response.ok) {
          throw new Error('Failed to fetch plan');
        }
        
        const data = await response.json();
        setCurrentPlan(data.hasPlan ? data : null);
      } catch (err) {
        // Avoid logging aborted requests
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error('Error fetching current plan:', err);
        }
      } finally {
        // Only set loading to false if component is still mounted
        if (!abortController.signal.aborted) {
          setPlanLoading(false);
        }
      }
    };
    
    fetchCurrentPlan();
    
    // Join agent-specific room for targeted updates
    socket.emit('agent:subscribe', agentId);
    
    // Listen for specific plan events
    socket.on('step:status', (data) => {
      if (data.agentId === agentId) {
        setCurrentPlan(prevPlan => {
          if (!prevPlan) return null;
          
          // Update the specific step's status
          const updatedSteps = prevPlan.steps.map(step => 
            step.id === data.stepId ? { ...step, status: data.status } : step
          );
          
          return { ...prevPlan, steps: updatedSteps };
        });
      }
    });
    
    socket.on('step:completed', (data) => {
      if (data.agentId === agentId) {
        setCurrentPlan(prevPlan => {
          if (!prevPlan) return null;
          
          // Update completed step with result
          const updatedSteps = prevPlan.steps.map(step => 
            step.id === data.stepId ? { 
              ...step, 
              status: 'completed',
              result: data.result 
            } : step
          );
          
          return { ...prevPlan, steps: updatedSteps };
        });
      }
    });
    
    socket.on('plan:completed', (data) => {
      if (data.agentId === agentId) {
        setCurrentPlan(prevPlan => {
          if (!prevPlan) return null;
          return { 
            ...prevPlan, 
            status: 'completed',
            hasFollowUp: data.hasFollowUp,
            followUpSuggestions: data.followUpSuggestions
          };
        });
      }
    });
    
    socket.on('plan:failed', (data) => {
      if (data.agentId === agentId) {
        setCurrentPlan(prevPlan => {
          if (!prevPlan) return null;
          return { ...prevPlan, status: 'failed' };
        });
      }
    });
    
    socket.on('plan:followup', (data) => {
      if (data.agentId === agentId) {
        setCurrentPlan(prevPlan => {
          if (!prevPlan) return null;
          return { 
            ...prevPlan, 
            hasFollowUp: data.hasFollowUp,
            followUpSuggestions: data.followUpSuggestions
          };
        });
      }
    });
    
    // Cleanup function
    return () => {
      // Unsubscribe from agent room
      socket.emit('agent:unsubscribe', agentId);
      
      // Remove all listeners
      socket.off('step:status');
      socket.off('step:completed');
      socket.off('plan:completed');
      socket.off('plan:failed');
      socket.off('plan:followup');
      
      abortController.abort();
    };
  }, [agentId, socket]);
  
  const handleSubmitCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!command.trim()) {
      return;
    }
    
    setSubmitting(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/agents/${agentId}/command`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ command: command.trim() }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to send command');
      }
      
      await response.json();
      
      // Clear command input
      setCommand('');
      
      // Switch to plan tab (rest of updates will come via socket)
      setActiveTab('plan');
      
      // Optimistic status update (the real status will come via socket)
      setAgent(prev => prev ? { ...prev, status: AgentStatus.PLANNING } : prev);
    } catch (err) {
      console.error('Error sending command:', err);
      setError(err instanceof Error ? err.message : 'Failed to send command');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleApprovePlan = async () => {
    if (!currentPlan) return;
    
    try {
      // Use the correct API endpoint
      const response = await fetch(`/api/plans/${currentPlan.planId}/approve`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to approve plan');
      }
      
      // Optimistic update - the socket will provide real data if needed
      setCurrentPlan(prev => prev ? { ...prev, status: 'approved' } : null);
      setAgent(prev => prev ? { ...prev, status: AgentStatus.EXECUTING } : prev);
    } catch (err) {
      console.error('Error approving plan:', err);
      setError(err instanceof Error ? err.message : 'Failed to approve plan');
    }
  };
  
  const handleRejectPlan = async () => {
    if (!currentPlan) return;
    
    try {
      // Use the correct API endpoint
      const response = await fetch(`/api/plans/${currentPlan.planId}/reject`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to reject plan');
      }
      
      // Optimistic update
      setCurrentPlan(null);
      setAgent(prev => prev ? { ...prev, status: AgentStatus.IDLE } : prev);
    } catch (err) {
      console.error('Error rejecting plan:', err);
      setError(err instanceof Error ? err.message : 'Failed to reject plan');
    }
  };
  
  if (loading) {
    return <div className="loading">Loading agent details...</div>;
  }
  
  if (error) {
    return (
      <div className="error-container">
        <h2>Error</h2>
        <p>{error}</p>
        <button onClick={() => navigate('/')}>Back to Dashboard</button>
      </div>
    );
  }
  
  if (!agent) {
    return (
      <div className="not-found">
        <h2>Agent Not Found</h2>
        <p>The requested agent could not be found.</p>
        <button onClick={() => navigate('/')}>Back to Dashboard</button>
      </div>
    );
  }
  
  const canSendCommand = agent.status === AgentStatus.IDLE || agent.status === AgentStatus.ERROR;
  
  return (
    <div className="agent-details">
      <div className="agent-header">
        <h1>{agent.name}</h1>
        <div className={`agent-status status-${agent.status}`}>
          {agent.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
        </div>
      </div>
      
      <div className="agent-info">
        <div className="info-section">
          <h2>Details</h2>
          <p><strong>Description:</strong> {agent.description}</p>
        </div>
        
        {agent.personalityProfile && (
          <div className="info-section">
            <h2>Personality Profile</h2>
            <p>{agent.personalityProfile}</p>
          </div>
        )}
      </div>
      
      <div className="command-section">
        <h2>Send Command</h2>
        <form onSubmit={handleSubmitCommand}>
          <div className="form-group">
            <textarea
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="Enter command for the agent..."
              rows={4}
              disabled={!canSendCommand || submitting}
            />
          </div>
          
          <button
            type="submit"
            className="send-button"
            disabled={!canSendCommand || submitting || !command.trim()}
          >
            {submitting ? 'Sending...' : 'Send Command'}
          </button>
          
          {!canSendCommand && (
            <p className="note">
              Cannot send command while agent is {agent.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}. Wait for the current operation to complete.
            </p>
          )}
        </form>
      </div>
      
      <div className="agent-details-tabs">
        <div className="tabs-header">
          <button 
            className={`tab-button ${activeTab === 'plan' ? 'active' : ''}`}
            onClick={() => setActiveTab('plan')}
          >
            Current Plan
          </button>
          <button 
            className={`tab-button ${activeTab === 'logs' ? 'active' : ''}`}
            onClick={() => setActiveTab('logs')}
          >
            LLM API Logs
          </button>
        </div>
        
        <div className="tab-content">
          {activeTab === 'plan' ? (
            <div className="plan-section">
              {planLoading ? (
                <div className="loading">Loading plan...</div>
              ) : currentPlan ? (
                <>
                  <PlanViewer plan={{
                    ...currentPlan,
                    planId: currentPlan.planId || currentPlan.id // Ensure planId is always set
                  }} />
                  
                  {(currentPlan.status === 'draft' || currentPlan.status === 'awaiting_approval') && (
                    <div className="plan-actions">
                      <button
                        className="approve-button"
                        onClick={handleApprovePlan}
                      >
                        Approve Plan
                      </button>
                      
                      <button
                        className="reject-button"
                        onClick={handleRejectPlan}
                      >
                        Reject Plan
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <p className="no-plan">No active plan. Send a command to create one.</p>
              )}
            </div>
          ) : (
            <div className="logs-section">
              <LogViewer agentId={agentId} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentDetails;