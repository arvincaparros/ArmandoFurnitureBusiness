# --- Build stage ---
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines import.meta.env.* at build time, not at container
# runtime - so this must be a build ARG, not a runtime environment
# variable, or the deployed frontend would keep whatever URL was
# baked in the last time the image was built regardless of any
# `environment:` value set in docker-compose.client.yml.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# --- Runtime stage ---
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
