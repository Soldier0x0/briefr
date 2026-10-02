# BRIEFR UI image. Build context is the repo root.
# Stage 1 builds the Vite app. The final image is nginx only — no Node.

FROM node:22-bookworm-slim AS build

WORKDIR /src/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/frontend/dist /usr/share/nginx/html

EXPOSE 80
