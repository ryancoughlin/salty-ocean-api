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
app.use(routes);

// Health check endpoint
app.get("/health", (req, res) => {
  res.status(200).json({ status: "ok", timestamp: new Date().toISOString() });
});

// Root endpoint
app.get("/", (req, res) => {
  res.send("Salty API - Marine Weather and Tide Data");
});

app.use(errorHandler);

// Start cache cleanup scheduler
scheduleCacheMonitoring();

const startApp = async () => {
  try {
    const server = app.listen(PORT, "0.0.0.0", () => {
      console.log(`🌊 Server running on port ${PORT}`);
    });

    // // Initialize data after server is running
    // try {
    //     await initializeData();
    //     console.log('Data initialization complete');
    // } catch (error) {
    //     console.error('Data initialization failed:', error);
    //     // Continue running even if initialization fails
    // }
  } catch (error) {
    console.error("Failed to start server:", error);
    process.exit(1);
  }
};

// Error handling
process.on("uncaughtException", (error) => {
  console.error("Uncaught Exception:", error);
  process.exit(1);
});

process.on("unhandledRejection", (error) => {
  console.error("Unhandled Rejection:", error);
  process.exit(1);
});

startApp();
