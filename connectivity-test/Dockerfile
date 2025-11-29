FROM node:20-slim
WORKDIR /app
COPY debug-redis.js .
RUN npm install ioredis
CMD ["node", "debug-redis.js"]
