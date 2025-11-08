FROM node:18-alpine

WORKDIR /app

# Copy package files first (for better Docker layer caching)
COPY package.json package-lock.json* ./

# Install dependencies (uses package-lock.json if available)
RUN npm ci --only=production || npm install

COPY . .

EXPOSE 3000

CMD ["npm", "start"]

