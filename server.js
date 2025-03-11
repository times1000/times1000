const express = require('express');
const http = require('http');
const path = require('path');
const { Server } = require('socket.io');
const { setupAPI } = require('./dist/api');
require('dotenv').config();
const { v4: uuidv4 } = require('uuid');
const db = require('./dist/db');

// Initialize Express app and server
const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Verify LLM API keys are configured
const hasOpenAIKey = !!process.env.OPENAI_API_KEY;
const hasAnthropicKey = !!process.env.ANTHROPIC_API_KEY;

if (!hasOpenAIKey && !hasAnthropicKey) {
  console.warn('WARNING: No LLM API keys (OPENAI_API_KEY or ANTHROPIC_API_KEY) are set. LLM features will not work correctly.');
} else {
  console.log(`Using LLM provider: ${process.env.DEFAULT_LLM_PROVIDER || 'openai'} (default)`);
  if (hasOpenAIKey) console.log('OpenAI API key is configured');
  if (hasAnthropicKey) console.log('Anthropic API key is configured');
}

// Test database connection on startup and force reload
console.log('Testing database connection and ensuring fresh connection...');

// Add a delay to allow MySQL to fully initialize
const waitForDatabase = () => {
  return new Promise((resolve) => {
    // Don't try to close the pool, just wait for the database to be available
    const maxAttempts = 30; // 60 seconds total wait time
    let attempts = 0;
    
    const attempt = () => {
      attempts++;
      try {
        console.log(`Attempting database connection (${attempts}/${maxAttempts})...`);
        db.default.testConnection()
          .then(() => {
            console.log('Database connection successful!');
            resolve();
          })
          .catch(err => {
            if (attempts >= maxAttempts) {
              console.log('Maximum database connection attempts reached, continuing anyway...');
              resolve(); // Continue server startup even without database
            } else {
              console.log('Database connection failed, retrying in 2 seconds...', err.message);
              setTimeout(attempt, 2000);
            }
          });
      } catch (err) {
        if (attempts >= maxAttempts) {
          console.log('Maximum database connection attempts reached, continuing anyway...');
          resolve(); // Continue server startup even without database
        } else {
          console.log('Database connection error, retrying in 2 seconds...', err.message);
          setTimeout(attempt, 2000);
        }
      }
    };
    
    attempt();
  });
};

// Wait for database before proceeding with server setup
waitForDatabase().catch(err => {
  console.error('Final database connection error:', err);
});

// Execute the newest migration for system logs
const fs = require('fs');

const runMigration = async (filename) => {
  // Make sure we have a database connection before running migrations
  if (!db.pool) {
    console.log('No database pool available, skipping migration');
    return;
  }
  
  try {
    console.log(`Executing migration: ${filename}`);
    const migrationPath = path.join(__dirname, 'init-sql', filename);
    const migrationSql = fs.readFileSync(migrationPath, 'utf8');
    
    // Split the SQL by semicolons to execute multiple statements
    const statements = migrationSql.split(';').filter(stmt => stmt.trim());
    
    for (const statement of statements) {
      if (statement.trim()) {
        try {
          await db.pool.query(statement);
        } catch (statementError) {
          // Log the error but continue with other statements
          console.log(`Error executing statement: ${statementError.message}`);
          // If it's a "table already exists" error, we can safely ignore it
          if (statementError.code !== 'ER_TABLE_EXISTS_ERROR') {
            throw statementError;
          }
        }
      }
    }
    
    console.log(`Migration ${filename} executed successfully`);
  } catch (error) {
    console.error(`Error executing migration ${filename}:`, error);
    // Don't fail the server startup for migrations that might have already been applied
  }
};

// Run our new separate logs migration after successful database connection
waitForDatabase().then(() => {
  try {
    console.log('Database connected, running migrations...');
    runMigration('04-separate-logs-migration.sql');
  } catch (error) {
    console.warn('Migration could not be run at startup, will try again later:', error.message);
  }
});

// Export db pool for shutdown handling
exports.pool = db.pool;

// Serve static files from the dist directory
app.use(express.static(path.join(__dirname, 'dist')));

// Set up API routes - IMPORTANT: API routes must be defined after static files but before the catch-all route
setupAPI(app, io);

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

// Start the server after database connection
const PORT = process.env.PORT || 3000;

// Wait for database before starting the server
waitForDatabase().then(() => {
  server.listen(PORT, () => {
    console.log(`*1000 API server running on port ${PORT}`);
    console.log(`Access the app via the Vite dev server at http://localhost:5173`);
  });
}).catch(err => {
  console.error('Failed to start server:', err);
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