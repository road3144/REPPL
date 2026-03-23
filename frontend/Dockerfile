# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app

ARG VITE_API_TARGET
ENV VITE_API_TARGET=${VITE_API_TARGET}

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80