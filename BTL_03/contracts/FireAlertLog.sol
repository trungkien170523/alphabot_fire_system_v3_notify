// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract FireAlertLog {
    struct AlertRecord {
        uint256 id;
        uint256 localBlockIndex;
        string localBlockHash;
        string dangerLevel;
        string robotCommand;
        string messageText;
        string imagePath;
        uint256 timestamp;
        address reporter;
    }

    address public owner;
    uint256 public alertCount;

    mapping(uint256 => AlertRecord) private alerts;
    mapping(string => bool) public hashExists;

    event AlertStored(
        uint256 indexed id,
        uint256 indexed localBlockIndex,
        string localBlockHash,
        string dangerLevel,
        string robotCommand,
        address indexed reporter,
        uint256 timestamp
    );

    constructor() {
        owner = msg.sender;
    }

    function storeAlert(
        uint256 localBlockIndex,
        string memory localBlockHash,
        string memory dangerLevel,
        string memory robotCommand,
        string memory messageText,
        string memory imagePath
    ) public {
        require(bytes(localBlockHash).length > 0, "Hash is required");
        require(hashExists[localBlockHash] == false, "This alert hash already exists");

        alertCount += 1;

        alerts[alertCount] = AlertRecord({
            id: alertCount,
            localBlockIndex: localBlockIndex,
            localBlockHash: localBlockHash,
            dangerLevel: dangerLevel,
            robotCommand: robotCommand,
            messageText: messageText,
            imagePath: imagePath,
            timestamp: block.timestamp,
            reporter: msg.sender
        });

        hashExists[localBlockHash] = true;

        emit AlertStored(
            alertCount,
            localBlockIndex,
            localBlockHash,
            dangerLevel,
            robotCommand,
            msg.sender,
            block.timestamp
        );
    }

    function getAlert(uint256 id) public view returns (
        uint256,
        uint256,
        string memory,
        string memory,
        string memory,
        string memory,
        string memory,
        uint256,
        address
    ) {
        require(id > 0 && id <= alertCount, "Invalid alert id");

        AlertRecord memory item = alerts[id];

        return (
            item.id,
            item.localBlockIndex,
            item.localBlockHash,
            item.dangerLevel,
            item.robotCommand,
            item.messageText,
            item.imagePath,
            item.timestamp,
            item.reporter
        );
    }

    function getLatestAlert() public view returns (
        uint256,
        uint256,
        string memory,
        string memory,
        string memory,
        string memory,
        string memory,
        uint256,
        address
    ) {
        require(alertCount > 0, "No alert stored yet");

        AlertRecord memory item = alerts[alertCount];

        return (
            item.id,
            item.localBlockIndex,
            item.localBlockHash,
            item.dangerLevel,
            item.robotCommand,
            item.messageText,
            item.imagePath,
            item.timestamp,
            item.reporter
        );
    }
}