FROM node:20.11.1-alpine AS builder

WORKDIR /usr/src/app

COPY package*.json ./
RUN npm ci

COPY . .

FROM node:20.11.1-alpine AS runtime

WORKDIR /usr/src/app

COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY . .

ENV NODE_ENV=production
ENV PORT=5010

EXPOSE 5010

# Install wget for healthcheck
RUN apk add --no-cache wget

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --spider -q http://0.0.0.0:5010/health || exit 1

CMD ["node", "app.js"] 