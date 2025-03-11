import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface NewAgentFormProps {
  onCreateAgent: (agentData: {
    command: string;
  }) => Promise<any>;
}

const NewAgentForm: React.FC<NewAgentFormProps> = ({ onCreateAgent }) => {
  const navigate = useNavigate();
  const [command, setCommand] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!command) {
      setError('Please enter a command for the agent');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const requestData = {
        command
      };
      
      const newAgent = await onCreateAgent(requestData);
      
      // Navigate to the new agent's detail page
      navigate(`/agents/${newAgent.id}`);
    } catch (err) {
      console.error('Error creating agent:', err);
      setError('Failed to create agent. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="create-agent-form">
      <h1>Create New Agent</h1>
      
      {error && <div className="error-message">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="agent-command">Initial Command (required)</label>
          <textarea
            id="agent-command"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder="Enter a command for the agent (e.g., 'Monitor my Twitter account and suggest responses')"
            rows={3}
            required
          />
          <p className="help-text">
            The agent will be created with a name and description based on this command.
          </p>
        </div>
        
        <div className="form-actions">
          <button
            type="button"
            className="cancel-button"
            onClick={() => navigate('/')}
          >
            Cancel
          </button>
          
          <button
            type="submit"
            className="create-button"
            disabled={loading}
          >
            {loading ? 'Creating...' : 'Create Agent'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default NewAgentForm;