# Web dev server (Vite + HMR) for docker-compose so the app stays up with the
# stack. Source is bind-mounted at runtime; node_modules is kept in the image
# (an anonymous volume shadows the host's, which may be built for another OS).
FROM node:20-slim

WORKDIR /repo/apps/web

# Install deps first for layer caching; source arrives via bind mount at runtime.
COPY package.json package-lock.json* ./
RUN npm install

EXPOSE 5174

# host:true + port 5174 come from vite.config.ts.
CMD ["npm", "run", "dev"]
