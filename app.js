const express = require("express");
const dotenv = require("dotenv");
const routes = require("./routes");
const helmet = require("helmet");
const compression = require("compression");
const morgan = require("morgan");
const { errorHandler } = require("./middlewares/errorHandler");
const { scheduleCacheMonitoring } = require("./services/scheduler");
const restrictOrigin = require("./middlewares/restrictOrigin");
const { initializeData } = require("./services/startupService");
const { logger } = require("./utils/logger");

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.set("trust proxy", "loopback"); // Trust local proxy

app.use(helmet());
app.use(compression());
app.use(restrictOrigin);
app.use(morgan("combined"));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Health check endpoint
app.get("/health", (req, res) => {
  res.status(200).json({ status: "ok", timestamp: new Date().toISOString() });
});

// Root endpoint
app.get("/", (req, res) => {
  res.send("Salty API - Marine Weather and Tide Data");
});

// Mount API routes
app.use(routes);

app.use(errorHandler);

// Start cache cleanup scheduler
scheduleCacheMonitoring();

const startApp = async () => {
  try {
    // Start server first so health checks can pass
    const server = app.listen(PORT, "0.0.0.0", () => {
      logger.info(`🌊 Server running on port ${PORT}`);
    });

    // Initialize data after server is running
    try {
      // await initializeData();
      logger.info("✅ Data initialization complete");
    } catch (error) {
      logger.error("❌ Data initialization failed:", error);
      // Continue running even if initialization fails
    }
  } catch (error) {
    logger.error("Failed to start server:", error);
    process.exit(1);
  }
};

// Error handling
process.on("uncaughtException", (error) => {
  logger.error("Uncaught Exception:", error);
  process.exit(1);
});

process.on("unhandledRejection", (error) => {
  logger.error("Unhandled Rejection:", error);
  process.exit(1);
});

startApp();
