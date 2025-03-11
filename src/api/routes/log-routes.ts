import express from 'express';
import { getLogs, getLogsByAgentId } from '../services/logging-service';

export default function() {
  const router = express.Router();

  // Get all LLM API logs with pagination
  router.get('/', async (req: express.Request, res: express.Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;
      
      const logs = await getLogs(page, limit);
      res.json(logs);
    } catch (error) {
      console.error('Error fetching logs:', error);
      res.status(500).json({ error: 'Failed to fetch logs' });
    }
  });

  // Get logs for a specific agent
  router.get('/agent/:agentId', async (req: express.Request, res: express.Response) => {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;
      
      const logs = await getLogsByAgentId(req.params.agentId, page, limit);
      res.json(logs);
    } catch (error) {
      console.error(`Error fetching logs for agent ${req.params.agentId}:`, error);
      res.status(500).json({ error: 'Failed to fetch logs' });
    }
  });

  return router;
}