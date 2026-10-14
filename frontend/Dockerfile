# Frontend Dockerfile - Multi-stage build
# Use node:20 instead of node:20-alpine because @tailwindcss/postcss requires
# lightningcss native binary which is not available for Alpine (musl libc)
FROM node:20 AS builder

WORKDIR /app

# Install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend/ ./
RUN npm run build

# Production stage - serve with nginx
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]