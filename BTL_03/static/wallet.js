let provider = null;
let signer = null;
let fireContract = null;
let connectedAccount = null;

// Dán địa chỉ contract đã deploy ở Remix vào đây
const FIRE_ALERT_CONTRACT_ADDRESS = "DAN_DIA_CHI_CONTRACT_CUA_BAN_VAO_DAY";

// ABI tối giản, chỉ gồm các hàm cần dùng
const FIRE_ALERT_ABI = [
  {
    "inputs": [],
    "stateMutability": "nonpayable",
    "type": "constructor"
  },
  {
    "inputs": [],
    "name": "alertCount",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "string",
        "name": "",
        "type": "string"
      }
    ],
    "name": "hashExists",
    "outputs": [
      {
        "internalType": "bool",
        "name": "",
        "type": "bool"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "uint256",
        "name": "localBlockIndex",
        "type": "uint256"
      },
      {
        "internalType": "string",
        "name": "localBlockHash",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "dangerLevel",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "robotCommand",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "messageText",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "imagePath",
        "type": "string"
      }
    ],
    "name": "storeAlert",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "getLatestAlert",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      },
      {
        "internalType": "string",
        "name": "",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "",
        "type": "string"
      },
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      },
      {
        "internalType": "address",
        "name": "",
        "type": "address"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  }
];

function shortAddress(address) {
  if (!address) {
    return "--";
  }

  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

function shortHash(hash) {
  if (!hash) {
    return "--";
  }

  if (hash.length <= 18) {
    return hash;
  }

  return `${hash.slice(0, 12)}...${hash.slice(-8)}`;
}

function setWalletStatus(message) {
  const box = document.getElementById("walletStatusText");

  if (box) {
    box.textContent = message;
  }
}

function setWalletAddress(address) {
  const box = document.getElementById("walletAddressText");

  if (box) {
    box.textContent = shortAddress(address);
  }
}

function setContractStatus(message) {
  const box = document.getElementById("contractStatusText");

  if (box) {
    box.textContent = message;
  }
}

async function connectWallet() {
  try {
    if (!window.ethereum) {
      alert("Chưa cài MetaMask. Hãy cài extension MetaMask trước.");
      return;
    }

    if (FIRE_ALERT_CONTRACT_ADDRESS === "0xd8b934580fcE35a11B58C6D73aDeE468a2833fa8") {
      alert("Bạn chưa dán địa chỉ contract vào file static/wallet.js");
      return;
    }

    provider = new ethers.BrowserProvider(window.ethereum);

    const accounts = await provider.send("eth_requestAccounts", []);
    connectedAccount = accounts[0];

    signer = await provider.getSigner();

    fireContract = new ethers.Contract(
      FIRE_ALERT_CONTRACT_ADDRESS,
      FIRE_ALERT_ABI,
      signer
    );

    const network = await provider.getNetwork();

    setWalletAddress(connectedAccount);
    setWalletStatus(`Connected · Chain ID: ${network.chainId.toString()}`);
    setContractStatus("Contract ready");

    await refreshContractInfo();
  } catch (error) {
    console.error("MetaMask connect error:", error);
    alert("Không kết nối được MetaMask: " + error.message);
  }
}

async function refreshContractInfo() {
  try {
    if (!fireContract) {
      return;
    }

    const count = await fireContract.alertCount();

    const countBox = document.getElementById("onchainAlertCount");
    if (countBox) {
      countBox.textContent = count.toString();
    }

    if (Number(count) > 0) {
      const latest = await fireContract.getLatestAlert();

      renderLatestOnchainAlert({
        id: latest[0].toString(),
        localBlockIndex: latest[1].toString(),
        localBlockHash: latest[2],
        dangerLevel: latest[3],
        robotCommand: latest[4],
        messageText: latest[5],
        imagePath: latest[6],
        timestamp: latest[7].toString(),
        reporter: latest[8]
      });
    }
  } catch (error) {
    console.error("Refresh contract error:", error);
  }
}

function renderLatestOnchainAlert(alertData) {
  const box = document.getElementById("latestOnchainAlert");

  if (!box) {
    return;
  }

  const date = new Date(Number(alertData.timestamp) * 1000).toLocaleString("vi-VN");

  box.innerHTML = `
    <div class="onchain-alert-card">
      <div class="onchain-alert-top">
        <strong>On-chain Alert #${alertData.id}</strong>
        <span>${alertData.dangerLevel}</span>
      </div>

      <p><b>Local block:</b> #${alertData.localBlockIndex}</p>
      <p><b>Command:</b> ${alertData.robotCommand}</p>
      <p><b>Message:</b> ${alertData.messageText}</p>
      <p><b>Time:</b> ${date}</p>
      <p><b>Reporter:</b> ${shortAddress(alertData.reporter)}</p>

      <div class="onchain-hash" title="${alertData.localBlockHash}">
        ${shortHash(alertData.localBlockHash)}
      </div>
    </div>
  `;
}

async function syncLatestLocalBlockToContract() {
  try {
    if (!fireContract) {
      alert("Bạn cần kết nối MetaMask trước.");
      return;
    }

    const response = await fetch("/api/blockchain");
    const chain = await response.json();

    if (!Array.isArray(chain) || chain.length === 0) {
      alert("Chưa có dữ liệu blockchain local.");
      return;
    }

    const alertBlocks = chain.filter((block) => {
      return block.data && block.data.danger_level;
    });

    if (alertBlocks.length === 0) {
      alert("Blockchain local chưa có alert block. Hãy bấm Test Alert hoặc để hệ thống phát hiện cháy.");
      return;
    }

    const latestBlock = alertBlocks[alertBlocks.length - 1];
    const data = latestBlock.data || {};

    const localBlockIndex = Number(latestBlock.index || 0);
    const localBlockHash = String(latestBlock.hash || "");
    const dangerLevel = String(data.danger_level || "UNKNOWN");
    const robotCommand = String(data.robot_command || "-");
    const messageText = String(data.message || "-");
    const imagePath = String(data.image_path || "-");

    if (!localBlockHash) {
      alert("Block local không có hash.");
      return;
    }

    const exists = await fireContract.hashExists(localBlockHash);

    if (exists) {
      alert("Alert hash này đã được ghi lên smart contract rồi.");
      return;
    }

    setContractStatus("Sending transaction...");

    const tx = await fireContract.storeAlert(
      localBlockIndex,
      localBlockHash,
      dangerLevel,
      robotCommand,
      messageText,
      imagePath
    );

    setContractStatus("Waiting for confirmation...");

    await tx.wait();

    setContractStatus("Transaction confirmed");

    alert("Đã ghi alert mới nhất lên smart contract.");

    await refreshContractInfo();
  } catch (error) {
    console.error("Sync alert error:", error);
    setContractStatus("Transaction failed");
    alert("Không ghi được lên smart contract: " + error.message);
  }
}

async function syncAllLocalAlertsToContract() {
  try {
    if (!fireContract) {
      alert("Bạn cần kết nối MetaMask trước.");
      return;
    }

    const response = await fetch("/api/blockchain");
    const chain = await response.json();

    if (!Array.isArray(chain) || chain.length === 0) {
      alert("Chưa có dữ liệu blockchain local.");
      return;
    }

    const alertBlocks = chain.filter((block) => {
      return block.data && block.data.danger_level;
    });

    if (alertBlocks.length === 0) {
      alert("Chưa có alert block để đồng bộ.");
      return;
    }

    let synced = 0;
    let skipped = 0;

    for (const block of alertBlocks) {
      const data = block.data || {};
      const localBlockHash = String(block.hash || "");

      if (!localBlockHash) {
        skipped += 1;
        continue;
      }

      const exists = await fireContract.hashExists(localBlockHash);

      if (exists) {
        skipped += 1;
        continue;
      }

      setContractStatus(`Syncing block #${block.index}...`);

      const tx = await fireContract.storeAlert(
        Number(block.index || 0),
        localBlockHash,
        String(data.danger_level || "UNKNOWN"),
        String(data.robot_command || "-"),
        String(data.message || "-"),
        String(data.image_path || "-")
      );

      await tx.wait();

      synced += 1;
    }

    setContractStatus("Sync completed");

    alert(`Đồng bộ xong. Ghi mới: ${synced}, bỏ qua: ${skipped}`);

    await refreshContractInfo();
  } catch (error) {
    console.error("Sync all error:", error);
    setContractStatus("Sync failed");
    alert("Không đồng bộ được: " + error.message);
  }
}

if (window.ethereum) {
  window.ethereum.on("accountsChanged", () => {
    window.location.reload();
  });

  window.ethereum.on("chainChanged", () => {
    window.location.reload();
  });
}