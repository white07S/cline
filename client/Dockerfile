# Multi-stage: build the SPA with bun + vite, serve static files with nginx.

FROM oven/bun:1.1-debian AS build
WORKDIR /app

COPY package.json bun.lockb* ./
RUN bun install --frozen-lockfile

COPY . .
RUN bun run build

FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
# nginx config is provided by configs/infra/nginx/ in compose — no need to bake one in here.
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
