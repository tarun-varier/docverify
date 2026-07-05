// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title DocRegistry
 * @notice On-chain registry of document verification results.
 *         Stores SHA-256 hashes and their analysis outcomes so that
 *         previously-verified documents can skip the full pipeline.
 */
contract DocRegistry {

    struct DocRecord {
        bytes32  fileHash;      // SHA-256 of the raw document bytes
        uint8    fraudScore;    // 0-100
        string   riskBand;     // "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
        string   caseId;       // Pipeline case identifier
        string   resultJson;   // Full CaseResult serialised as JSON
        uint256  analyzedAt;   // Block timestamp of recording
        address  analyzedBy;   // Address that submitted the record
    }

    /// @notice fileHash → record
    mapping(bytes32 => DocRecord) private _records;

    /// @notice All hashes ever recorded (for enumeration)
    bytes32[] private _hashes;

    /// @notice Quick existence check
    mapping(bytes32 => bool) private _exists;

    /* ── Events ── */

    event DocumentRecorded(
        bytes32 indexed fileHash,
        uint8   fraudScore,
        string  riskBand,
        string  caseId,
        address indexed analyzedBy
    );

    /* ── Write ── */

    /**
     * @notice Record a new document analysis result on-chain.
     * @dev    If the hash already exists the call reverts — each document
     *         should only be analysed once.
     */
    function recordDocument(
        bytes32 fileHash,
        uint8   fraudScore,
        string  calldata riskBand,
        string  calldata caseId,
        string  calldata resultJson
    ) external {
        require(!_exists[fileHash], "DocRegistry: hash already recorded");
        require(fraudScore <= 100,  "DocRegistry: score out of range");

        _records[fileHash] = DocRecord({
            fileHash:   fileHash,
            fraudScore: fraudScore,
            riskBand:   riskBand,
            caseId:     caseId,
            resultJson: resultJson,
            analyzedAt: block.timestamp,
            analyzedBy: msg.sender
        });

        _exists[fileHash] = true;
        _hashes.push(fileHash);

        emit DocumentRecorded(fileHash, fraudScore, riskBand, caseId, msg.sender);
    }

    /* ── Read ── */

    /**
     * @notice Check whether a document hash has been recorded.
     */
    function documentExists(bytes32 fileHash) external view returns (bool) {
        return _exists[fileHash];
    }

    /**
     * @notice Retrieve the full analysis result for a document.
     * @return fraudScore  0-100
     * @return riskBand    Risk classification string
     * @return caseId      Pipeline case ID
     * @return resultJson  Full CaseResult JSON
     * @return analyzedAt  Unix timestamp
     * @return analyzedBy  Recorder address
     */
    function getDocument(bytes32 fileHash)
        external
        view
        returns (
            uint8   fraudScore,
            string  memory riskBand,
            string  memory caseId,
            string  memory resultJson,
            uint256 analyzedAt,
            address analyzedBy
        )
    {
        require(_exists[fileHash], "DocRegistry: hash not found");
        DocRecord storage r = _records[fileHash];
        return (r.fraudScore, r.riskBand, r.caseId, r.resultJson, r.analyzedAt, r.analyzedBy);
    }

    /**
     * @notice Total number of documents recorded.
     */
    function totalRecords() external view returns (uint256) {
        return _hashes.length;
    }

    /**
     * @notice Get the hash at a specific index (for enumeration).
     */
    function hashAtIndex(uint256 index) external view returns (bytes32) {
        require(index < _hashes.length, "DocRegistry: index out of bounds");
        return _hashes[index];
    }
}
