// app.js
const express = require('express')
const dotenv = require('dotenv')
const routes = require('./routes')
const helmet = require('helmet')
const compression = require('compression')
const rateLimit = require('express-rate-limit')
const morgan = require('morgan')
const { errorHandler } = require('./middlewares/errorHandler')
const { logger } = require('./utils/logger')
const { scheduleCacheMonitoring } = require('./services/scheduler')
const restrictOrigin = require('./middlewares/restrictOrigin')
const { initializeData } = require('./services/startupService')

dotenv.config()

const app = express()
const PORT = process.env.PORT || 3000

// Security middleware
app.use(helmet({
    crossOriginResourcePolicy: false,
    crossOriginOpenerPolicy: false,
    crossOriginEmbedderPolicy: false,
    contentSecurityPolicy: false,
    originAgentCluster: false
}));
app.use(compression());

// CORS middleware
app.use(restrictOrigin)

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
})
app.use(limiter)

// Logging
app.use(morgan('combined', { stream: { write: message => logger.info(message.trim()) } }))

// Body parsing
app.use(express.json())
app.use(express.urlencoded({ extended: true }))

// API versioning
app.use('/api', routes)

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', timestamp: new Date().toISOString() })
})

// Root endpoint
app.get('/', (req, res) => {
  res.send('Salty API - Marine Weather and Tide Data')
})

// Error handling
app.use(errorHandler)

// Start cache cleanup scheduler
scheduleCacheMonitoring()

// Initialize data when app starts
const startApp = async () => {
    try {
        // Prefetch initial data
        await initializeData();
        
        // Start server
        app.listen(PORT, () => {
            logger.info(`🌊 Server running on port ${PORT}`);
        });
    } catch (error) {
        logger.error('Failed to start server:', error);
        process.exit(1);
    }
};

startApp();

// Graceful shutdown handling
process.on('SIGTERM', () => {
  logger.info('SIGTERM received. Starting graceful shutdown')
  app.close(() => {
    logger.info('Server closed')
    process.exit(0)
  })
})

// Improved error handling
process.on('unhandledRejection', (err) => {
  logger.error('Unhandled Promise Rejection:', err)
  // Give time for logging before exit
  setTimeout(() => {
    process.exit(1)
  }, 1000)
})
