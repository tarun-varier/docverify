#!/usr/bin/env node
/**
 * Deploy DocRegistry to the local Hardhat node and print the contract address.
 * Usage: node scripts/deploy.mjs
 */
import { execSync } from "child_process";
import { readFileSync, readdirSync } from "fs";
import { join } from "path";

const ROOT = new URL("..", import.meta.url).pathname;

console.log("Deploying DocRegistry to localhost...\n");

try {
  const output = execSync(
    `${join(ROOT, "node_modules/.bin/hardhat")} ignition deploy ignition/modules/DocRegistry.ts --network localhost`,
    { cwd: ROOT, encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"] }
  );
  console.log(output);

  // Try to extract address from the deployed_addresses.json
  const deploymentsDir = join(ROOT, "ignition/deployments");
  try {
    const chains = readdirSync(deploymentsDir);
    for (const chain of chains) {
      const addrFile = join(deploymentsDir, chain, "deployed_addresses.json");
      try {
        const addrs = JSON.parse(readFileSync(addrFile, "utf-8"));
        const contractAddr = Object.values(addrs)[0];
        if (contractAddr) {
          console.log(`\n=== CONTRACT ADDRESS: ${contractAddr} ===\n`);
          console.log(`Set this in your .env or docker-compose:`);
          console.log(`  LEDGER_CONTRACT_ADDRESS=${contractAddr}`);
        }
      } catch { /* skip */ }
    }
  } catch { /* no deployments dir yet */ }
} catch (err) {
  console.error("Deployment failed:", err.message);
  process.exit(1);
}
