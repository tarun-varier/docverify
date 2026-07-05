import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("DocRegistryModule", (m) => {
  const registry = m.contract("DocRegistry");

  return { registry };
});
