FROM node:18-alpine

WORKDIR /app

# Copy package files first (for better Docker layer caching)
COPY package.json package-lock.json* ./

# Install dependencies (including react-scripts)
RUN npm install

# Copy source files
COPY . .

EXPOSE 3000

CMD ["npm", "start"]

