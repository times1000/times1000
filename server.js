const express = require('express');
const http = require('http');
const path = require('path');
const { Server } = require('socket.io');
const { setupAPI } = require('./dist/api');
require('dotenv').config();
const { v4: uuidv4 } = require('uuid');
const db = require('./dist/db');
const OpenAI = require('openai');

// Initialize Express app and server
const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || '',
});

// Verify API key is configured
if (!process.env.OPENAI_API_KEY) {
  console.warn('WARNING: OPENAI_API_KEY environment variable not set. LLM features will not work correctly.');
}

// Test database connection on startup and force reload
console.log('Testing database connection and ensuring fresh connection...');
db.default.testConnection();

// Export db pool for shutdown handling
exports.pool = db.pool;

// Set up API routes
setupAPI(app, io, openai);

// Serve static files from the dist directory
app.use(express.static(path.join(__dirname, 'dist')));

// All other routes should redirect to index.html for SPA
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

// Socket.io event handling
io.on('connection', (socket) => {
  console.log('A client connected');
  
  // Socket events for real-time updates
  socket.on('agent:subscribe', (agentId) => {
    socket.join(`agent:${agentId}`);
  });
  
  socket.on('agent:unsubscribe', (agentId) => {
    socket.leave(`agent:${agentId}`);
  });
  
  socket.on('disconnect', () => {
    console.log('A client disconnected');
  });
  
  // Handle socket errors
  socket.on('error', (err) => {
    console.error('Socket error:', err);
  });
});

// Handle io server errors
io.engine.on('connection_error', (err) => {
  console.error('Socket.io connection error:', err);
});

// Start the server
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`*1000 API server running on port ${PORT}`);
  console.log(`Access the app via the Vite dev server at http://localhost:5173`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM signal received: closing HTTP server and database connections');
  
  // Stop the background processor if it exists
  if (app.backgroundProcessor) {
    console.log('Stopping background processor');
    app.backgroundProcessor.stop();
  }
  
  server.close(() => {
    console.log('HTTP server closed');
    
    // Close database pool connections
    if (db.pool && typeof db.pool.end === 'function') {
      db.pool.end().then(() => {
        console.log('Database connections closed');
        process.exit(0);
      });
    } else {
      console.log('No database pool to close');
      process.exit(0);
    }
  });
});