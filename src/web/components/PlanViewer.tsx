import React, { useState } from 'react';

interface PlanStep {
  id: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  estimatedDuration?: number;
  result?: any;
}

interface Plan {
  planId: string;
  command: string;
  description: string;
  reasoning: string;
  status: 'draft' | 'awaiting_approval' | 'approved' | 'executing' | 'completed' | 'failed' | 'rejected';
  steps: PlanStep[];
  hasFollowUp: boolean;
  followUpSuggestions?: string[];
}

interface PlanViewerProps {
  plan: Plan;
}

const PlanViewer: React.FC<PlanViewerProps> = ({ plan }) => {
  const [showReasoning, setShowReasoning] = useState(false);
  
  const getStepStatusIcon = (status: string): string => {
    switch (status) {
      case 'pending':
        return '⏳'; // Hourglass
      case 'in_progress':
        return '🔄'; // Refresh
      case 'completed':
        return '✅'; // Check mark
      case 'failed':
        return '❌'; // Cross mark
      default:
        return '•'; // Bullet
    }
  };
  
  const formatDuration = (seconds?: number): string => {
    if (!seconds) return 'N/A';
    
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    if (minutes === 0) {
      return `${seconds}s`;
    } else {
      return `${minutes}m ${remainingSeconds}s`;
    }
  };
  
  const getPlanStatusClass = (status: string): string => {
    switch (status) {
      case 'draft':
        return 'status-draft';
      case 'awaiting_approval':
        return 'status-draft'; // Use the same styling as draft
      case 'approved':
        return 'status-approved';
      case 'executing':
        return 'status-executing';
      case 'completed':
        return 'status-completed';
      case 'failed':
        return 'status-failed';
      case 'rejected':
        return 'status-rejected';
      default:
        return '';
    }
  };
  
  const getResultDisplay = (result: any): JSX.Element => {
    if (!result) return <span>No result yet</span>;
    
    if (typeof result === 'string') {
      return <p className="step-result">{result}</p>;
    } else {
      return (
        <pre className="step-result-json">
          {JSON.stringify(result, null, 2)}
        </pre>
      );
    }
  };
  
  return (
    <div className="plan-viewer">
      <div className="plan-header">
        <div className="plan-status-container">
          <span className="plan-id">Plan #{plan.planId ? plan.planId.substring(0, 8) : 'Unknown'}</span>
          <span className={`plan-status ${getPlanStatusClass(plan.status)}`}>
            {plan.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </span>
        </div>
        
        <div className="plan-command">
          <strong>Command:</strong> {plan.command}
        </div>
      </div>
      
      <div className="plan-body">
        <h3>Description</h3>
        <p>{plan.description}</p>
        
        <div className="plan-reasoning">
          <h3 onClick={() => setShowReasoning(!showReasoning)} className="toggle-section">
            Reasoning {showReasoning ? '▼' : '▶'}
          </h3>
          
          {showReasoning && (
            <p>{plan.reasoning}</p>
          )}
        </div>
        
        <h3>Steps</h3>
        <div className="plan-steps">
          {plan.steps.map((step) => (
            <div key={step.id} className={`plan-step step-${step.status}`}>
              <div className="step-header">
                <span className="step-icon">{getStepStatusIcon(step.status)}</span>
                <span className="step-description">{step.description}</span>
                <span className="step-status">{step.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                <span className="step-time">Est: {formatDuration(step.estimatedDuration)}</span>
              </div>
              
              {(step.status === 'completed' || step.status === 'failed') && step.result && (
                <div className="step-result-container">
                  {getResultDisplay(step.result)}
                </div>
              )}
            </div>
          ))}
        </div>
        
        {plan.hasFollowUp && plan.followUpSuggestions && plan.followUpSuggestions.length > 0 && (
          <div className="follow-up-section">
            <h3>Suggested Follow-Up Actions</h3>
            <ul>
              {plan.followUpSuggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default PlanViewer;