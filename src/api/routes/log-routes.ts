import express from 'express';
import { 
  getLLMLogs, getSystemLogs, 
  getLLMLogsByAgentId, getSystemLogsByAgentId 
} from '../services/logging-service';

export default function() {
  const router = express.Router();

  // Get all LLM logs with pagination (default route for backward compatibility)
  router.get('/', async (req: express.Request, res: express.Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;
      
      const logs = await getLLMLogs(page, limit);
      res.json(logs);
    } catch (error) {
      console.error('Error fetching LLM logs:', error);
      res.status(500).json({ error: 'Failed to fetch LLM logs' });
    }
  });

  // Get LLM logs specifically 
  router.get('/llm', async (req: express.Request, res: express.Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;
      
      const logs = await getLLMLogs(page, limit);
      res.json(logs);
    } catch (error) {
      console.error('Error fetching LLM logs:', error);
      res.status(500).json({ error: 'Failed to fetch LLM logs' });
    }
  });

  // Get system logs
  router.get('/system', async (req: express.Request, res: express.Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;
      
      const logs = await getSystemLogs(page, limit);
      res.json(logs);
    } catch (error) {
      console.error('Error fetching system logs:', error);
      res.status(500).json({ error: 'Failed to fetch system logs' });
    }
  });

  // Get LLM logs for a specific agent
  router.get('/agent/:agentId', async (req: express.Request, res: express.Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;
      
      const logs = await getLLMLogsByAgentId(req.params.agentId, page, limit);
      res.json(logs);
    } catch (error) {
      console.error(`Error fetching LLM logs for agent ${req.params.agentId}:`, error);
      res.status(500).json({ error: 'Failed to fetch logs' });
    }
  });

  // Get LLM logs for a specific agent
  router.get('/llm/agent/:agentId', async (req: express.Request, res: express.Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;
      
      const logs = await getLLMLogsByAgentId(req.params.agentId, page, limit);
      res.json(logs);
    } catch (error) {
      console.error(`Error fetching LLM logs for agent ${req.params.agentId}:`, error);
      res.status(500).json({ error: 'Failed to fetch logs' });
    }
  });

  // Get system logs for a specific agent
  router.get('/system/agent/:agentId', async (req: express.Request, res: express.Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;
      
      const logs = await getSystemLogsByAgentId(req.params.agentId, page, limit);
      res.json(logs);
    } catch (error) {
      console.error(`Error fetching system logs for agent ${req.params.agentId}:`, error);
      res.status(500).json({ error: 'Failed to fetch logs' });
    }
  });

  return router;
}