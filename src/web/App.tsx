import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import io from 'socket.io-client';
import Dashboard from './components/Dashboard';
import AgentDetails from './components/AgentDetails';
import NavBar from './components/NavBar';
import NewAgentForm from './components/NewAgentForm';
import LogsDashboard from './components/LogsDashboard';
import PendingApprovals from './components/PendingApprovals';
import { AgentData } from '../types/agent';

// Initialize Socket.io connection
const socket = io();

function App() {
  const [agents, setAgents] = useState<AgentData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  // Fetch agents on component mount
  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await fetch('/api/agents');
        if (!response.ok) {
          throw new Error('Failed to fetch agents');
        }
        
        const data = await response.json();
        setAgents(data.agents || []);
      } catch (err) {
        setError('Error loading agents. Please refresh the page.');
        console.error('Error fetching agents:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchAgents();
    
    // Set up socket event listeners
    socket.on('agent:created', (newAgent) => {
      setAgents(prev => [...prev, newAgent]);
    });
    
    socket.on('agent:updated', (updatedAgent) => {
      setAgents(prev => 
        prev.map(agent => 
          agent.id === updatedAgent.id ? updatedAgent : agent
        )
      );
    });
    
    socket.on('agent:deleted', (agentId) => {
      setAgents(prev => prev.filter(agent => agent.id !== agentId));
    });
    
    return () => {
      // Clean up socket listeners
      socket.off('agent:created');
      socket.off('agent:updated');
      socket.off('agent:deleted');
    };
  }, []);
  
  const createAgent = async (agentData: { command: string }) => {
    try {
      const response = await fetch('/api/agents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(agentData),
      });
      
      if (!response.ok) {
        throw new Error('Failed to create agent');
      }
      
      const data = await response.json();
      // Return the agent part of the response (not the whole response which includes the plan)
      return data.agent;
    } catch (err) {
      console.error('Error creating agent:', err);
      throw err;
    }
  };
  
  const deleteAgent = async (agentId: string) => {
    try {
      const response = await fetch(`/api/agents/${agentId}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete agent');
      }
      
      setAgents(prev => prev.filter(agent => agent.id !== agentId));
    } catch (err) {
      console.error('Error deleting agent:', err);
      throw err;
    }
  };
  
  if (loading) {
    return <div className="loading">Loading agents...</div>;
  }
  
  return (
    <Router>
      <div className="app">
        <NavBar />
        
        {error && (
          <div className="error-banner">
            {error}
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}
        
        <div className="container">
          <Routes>
            <Route 
              path="/" 
              element={<Dashboard agents={agents} onDeleteAgent={deleteAgent} />} 
            />
            <Route 
              path="/agents/new" 
              element={<NewAgentForm onCreateAgent={createAgent} />} 
            />
            <Route 
              path="/agents/:agentId" 
              element={<AgentDetails socket={socket} />} 
            />
            <Route
              path="/logs"
              element={<LogsDashboard />}
            />
            <Route
              path="/pending-approvals"
              element={<PendingApprovals socket={socket} />}
            />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;