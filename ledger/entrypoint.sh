#!/bin/bash
set -e

echo "=== Starting Hardhat Node ==="
node_modules/.bin/hardhat node --hostname 0.0.0.0 --port 8545 &
HARDHAT_PID=$!

# Wait for the node to be ready
echo "Waiting for Hardhat node to start..."
for i in $(seq 1 30); do
  if curl -sf -X POST http://localhost:8545 \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}' > /dev/null 2>&1; then
    echo "Hardhat node is ready!"
    break
  fi
  sleep 1
done

# Deploy the DocRegistry contract using Ignition
echo "=== Deploying DocRegistry contract ==="
DEPLOY_OUTPUT=$(node_modules/.bin/hardhat ignition deploy ignition/modules/DocRegistry.ts --network localhost 2>&1) || true
echo "$DEPLOY_OUTPUT"

# Extract the deployed contract address from the output
CONTRACT_ADDR=$(echo "$DEPLOY_OUTPUT" | grep -oP '0x[0-9a-fA-F]{40}' | tail -1)

if [ -n "$CONTRACT_ADDR" ]; then
  echo ""
  echo "================================================"
  echo "  DocRegistry deployed at: $CONTRACT_ADDR"
  echo "================================================"
  echo ""
  # Write to the shared volume so the backend container can pick it up at
  # startup without a manual LEDGER_CONTRACT_ADDRESS env var.
  mkdir -p /shared
  echo "$CONTRACT_ADDR" > /shared/contract_address.txt
else
  echo "WARNING: Could not extract contract address from deployment output"
fi

# Keep the node running
wait $HARDHAT_PID
