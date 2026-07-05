FROM node:22-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files and install dependencies
COPY ledger/package.json ledger/package-lock.json ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install

# Copy project files
COPY ledger/ .

# Compile contracts
RUN node_modules/.bin/hardhat compile

# Copy the entrypoint script
COPY ledger/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8545

ENTRYPOINT ["/entrypoint.sh"]
