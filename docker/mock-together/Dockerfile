FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install --omit=dev && npm cache clean --force

RUN apk add --no-cache curl

COPY server.js ./

ENV NODE_ENV=production
EXPOSE 7500
CMD ["npm", "start"]
