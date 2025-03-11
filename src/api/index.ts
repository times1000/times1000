import express from 'express';
import { Server } from 'socket.io';
import OpenAI from 'openai';
import agentRoutes from './routes/agent-routes';
import planRoutes from './routes/plan-routes';
import logRoutes from './routes/log-routes';
import { startBackgroundProcessor } from '../background-processor';

// Export a function to configure the API
export function setupAPI(app: express.Application, io: Server, openai: OpenAI) {
  // Add middleware
  app.use(express.json());
  
  // Register API routes
  app.use('/api/agents', agentRoutes(io, openai));
  app.use('/api/plans', planRoutes(io, openai));
  app.use('/api/logs', logRoutes());
  
  // Start the background processor
  const processor = startBackgroundProcessor(io, openai);
  
  // Store the processor reference in the app for cleanup
  (app as any).backgroundProcessor = processor;
  
  // Error handling middleware
  app.use((err: any, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    console.error('API Error:', err);
    
    // Send back a proper error response
    const statusCode = err.statusCode || 500;
    res.status(statusCode).json({
      error: err.message || 'Internal Server Error',
      status: statusCode
    });
  });
  
  return app;
}