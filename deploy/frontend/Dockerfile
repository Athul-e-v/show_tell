FROM node:22-alpine AS builder

WORKDIR /app

RUN corepack enable

COPY web_app/package.json web_app/pnpm-lock.yaml web_app/pnpm-workspace.yaml ./

RUN pnpm install --frozen-lockfile

COPY web_app/ .

RUN pnpm build

FROM nginx:stable-alpine

COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

