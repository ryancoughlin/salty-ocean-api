FROM node:20.11.1-alpine AS builder

# Create app directory
WORKDIR /usr/src/app

# Install app dependencies
# A wildcard is used to ensure both package.json AND package-lock.json are copied
COPY package*.json ./

# Install dependencies including 'devDependencies'
RUN npm ci

# Bundle app source
COPY . .

FROM node:20.11.1-alpine AS runtime

# Create app directory
WORKDIR /usr/src/app

# Create a non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 -G nodejs

# Copy built node modules and binaries
COPY --from=builder --chown=nodejs:nodejs /usr/src/app/node_modules ./node_modules
COPY --chown=nodejs:nodejs . .

# Set NODE_ENV
ENV NODE_ENV=production
ENV PORT=5010

# Switch to non-root user
USER nodejs

EXPOSE 5010

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --spider -q http://0.0.0.0:5010/health || exit 1

CMD ["node", "app.js"] 