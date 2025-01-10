#!/bin/sh

echo "Starting Salty Server..."
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la
echo "Node version: $(node --version)"
echo "Environment variables:"
env
echo "Starting application..."
node app.js 