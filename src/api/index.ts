import express from 'express';
import { Server } from 'socket.io';
import agentRoutes from './routes/agent-routes';
import planRoutes from './routes/plan-routes';
import logRoutes from './routes/log-routes';
import { startBackgroundProcessor } from '../background-processor';
import { errorMiddleware } from './middleware/error-middleware';
import { eventService } from '../services/event-service';

// Export a function to configure the API
export function setupAPI(app: express.Application, io: Server) {
  // Add middleware
  app.use(express.json());
  
  // Initialize event service with socket.io
  eventService.initialize(io);
  
  // Start the background processor
  const processor = startBackgroundProcessor(io);
  
  // Register API routes
  app.use('/api/agents', agentRoutes(processor));
  app.use('/api/plans', planRoutes());
  app.use('/api/logs', logRoutes());
  
  // Store the processor reference in the app for cleanup
  (app as any).backgroundProcessor = processor;
  
  // Global error handling middleware
  app.use(errorMiddleware);
  
  return app;
}