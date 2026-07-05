import { expect } from "chai";
import { network } from "hardhat";

const { ethers } = await network.create();

// A sample SHA-256 hash as bytes32
const SAMPLE_HASH = ethers.zeroPadValue("0xabcdef1234567890", 32);
const SAMPLE_HASH_2 = ethers.zeroPadValue("0x1234567890abcdef", 32);

describe("DocRegistry", function () {
  async function deployRegistry() {
    const registry = await ethers.deployContract("DocRegistry");
    return registry;
  }

  it("Should start with zero records", async function () {
    const registry = await deployRegistry();
    expect(await registry.totalRecords()).to.equal(0n);
  });

  it("Should record a document and emit DocumentRecorded event", async function () {
    const registry = await deployRegistry();
    const [signer] = await ethers.getSigners();

    await expect(
      registry.recordDocument(
        SAMPLE_HASH,
        42,
        "MEDIUM",
        "case_abc123",
        '{"fraud_score": 42, "risk_band": "MEDIUM"}'
      )
    )
      .to.emit(registry, "DocumentRecorded")
      .withArgs(SAMPLE_HASH, 42, "MEDIUM", "case_abc123", signer.address);

    expect(await registry.totalRecords()).to.equal(1n);
  });

  it("Should return true for documentExists after recording", async function () {
    const registry = await deployRegistry();

    expect(await registry.documentExists(SAMPLE_HASH)).to.equal(false);

    await registry.recordDocument(
      SAMPLE_HASH,
      10,
      "LOW",
      "case_001",
      '{"result": "clean"}'
    );

    expect(await registry.documentExists(SAMPLE_HASH)).to.equal(true);
  });

  it("Should retrieve the stored document record", async function () {
    const registry = await deployRegistry();
    const [signer] = await ethers.getSigners();

    const resultJson = '{"fraud_score": 75, "risk_band": "HIGH"}';

    await registry.recordDocument(
      SAMPLE_HASH,
      75,
      "HIGH",
      "case_xyz",
      resultJson
    );

    const [fraudScore, riskBand, caseId, storedResult, analyzedAt, analyzedBy] =
      await registry.getDocument(SAMPLE_HASH);

    expect(fraudScore).to.equal(75);
    expect(riskBand).to.equal("HIGH");
    expect(caseId).to.equal("case_xyz");
    expect(storedResult).to.equal(resultJson);
    expect(analyzedAt).to.be.greaterThan(0n);
    expect(analyzedBy).to.equal(signer.address);
  });

  it("Should revert when recording a duplicate hash", async function () {
    const registry = await deployRegistry();

    await registry.recordDocument(
      SAMPLE_HASH,
      20,
      "LOW",
      "case_dup",
      "{}"
    );

    await expect(
      registry.recordDocument(SAMPLE_HASH, 30, "MEDIUM", "case_dup2", "{}")
    ).to.be.revertedWith("DocRegistry: hash already recorded");
  });

  it("Should revert when fraud score exceeds 100", async function () {
    const registry = await deployRegistry();

    await expect(
      registry.recordDocument(SAMPLE_HASH, 150, "CRITICAL", "case_bad", "{}")
    ).to.be.revertedWith("DocRegistry: score out of range");
  });

  it("Should revert when querying a non-existent hash", async function () {
    const registry = await deployRegistry();

    await expect(registry.getDocument(SAMPLE_HASH)).to.be.revertedWith(
      "DocRegistry: hash not found"
    );
  });

  it("Should support multiple document records", async function () {
    const registry = await deployRegistry();

    await registry.recordDocument(SAMPLE_HASH, 10, "LOW", "case_1", "{}");
    await registry.recordDocument(SAMPLE_HASH_2, 80, "HIGH", "case_2", "{}");

    expect(await registry.totalRecords()).to.equal(2n);
    expect(await registry.hashAtIndex(0)).to.equal(SAMPLE_HASH);
    expect(await registry.hashAtIndex(1)).to.equal(SAMPLE_HASH_2);
  });

  it("Should revert hashAtIndex for out-of-bounds index", async function () {
    const registry = await deployRegistry();

    await expect(registry.hashAtIndex(0)).to.be.revertedWith(
      "DocRegistry: index out of bounds"
    );
  });
});
