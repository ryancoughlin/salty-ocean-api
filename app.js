
const express = require('express')
const dotenv = require('dotenv')
const routes = require('./routes')
const helmet = require('helmet')
const compression = require('compression')
const rateLimit = require('express-rate-limit')
const morgan = require('morgan')
const { errorHandler } = require('./middlewares/errorHandler')
const { logger } = require('./utils/logger')
const { scheduleCacheMonitoring } = require('./services/scheduler')docker-compose up --build
const restrictOrigin = require('./middlewares/restrictOrigin')
const { initializeData } = require('./services/startupService')

dotenv.config()

const app = express()
const PORT = process.env.PORT || 3000

app.set('trust proxy', 1)

app.use(helmet({
    crossOriginResourcePolicy: false,
    crossOriginOpenerPolicy: false,
    crossOriginEmbedderPolicy: false,
    contentSecurityPolicy: false,
    originAgentCluster: false
}));
app.use(compression());

app.use(restrictOrigin)

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false
})
app.use(limiter)

app.use(morgan('combined', { stream: { write: message => logger.info(message.trim()) } }))

app.use(express.json())
app.use(express.urlencoded({ extended: true }))

app.use('/api', routes)

app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', timestamp: new Date().toISOString() })
})

app.get('/', (req, res) => {
  res.send('Salty API - Marine Weather and Tide Data')
})

app.use(errorHandler)

scheduleCacheMonitoring()

const startApp = async () => {
    try {
      
        const server = app.listen(PORT, '0.0.0.0', () => {
            console.log(`🌊 Server running on port ${PORT}`);
        }).on('error', (error) => {
            console.error('Server startup error:', error);
            process.exit(1);
        });

        server.on('error', (error) => {
            console.error('Server error:', error);
            process.exit(1);
        });

        server.on('listening', () => {
            console.log(`Server bound to port ${PORT}`);
            console.log(`Health check URL: http://0.0.0.0:${PORT}/health`);

            initializeData()
                .then(() => {
                    console.log('Data initialization complete');
                })
                .catch((error) => {
                    console.error('Data initialization failed:', error);
                });
        });

    } catch (error) {
        console.error('Failed to start server:', error);
        process.exit(1);
    }
};

process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    process.exit(1);
});

process.on('unhandledRejection', (error) => {
    console.error('Unhandled Rejection:', error);
  
    setTimeout(() => {
        process.exit(1);
    }, 1000);
});

startApp();

process.on('SIGTERM', () => {
    console.log('SIGTERM received. Starting graceful shutdown')
    app.close(() => {
        console.log('Server closed')
        process.exit(0)
    })
});
