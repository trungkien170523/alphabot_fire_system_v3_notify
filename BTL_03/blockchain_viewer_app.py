import json
import os
from flask import Flask, render_template_string

app = Flask(__name__)

BLOCKCHAIN_FILE = "blockchain_log.json"


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Alphabot Fire Blockchain Viewer</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #101820;
            color: white;
            padding: 20px;
        }

        h1 {
            color: #F2AA4C;
            text-align: center;
        }

        .summary {
            background: #1e2a35;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }

        .block {
            background: #1e2a35;
            border-left: 6px solid #F2AA4C;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 10px;
        }

        .block h2 {
            color: #F2AA4C;
        }

        .label {
            color: #00d4ff;
            font-weight: bold;
        }

        pre {
            background: #0b1117;
            padding: 10px;
            border-radius: 8px;
            overflow-x: auto;
            color: #d7f9ff;
        }

        .hash {
            word-break: break-all;
            color: #9cff9c;
        }

        .danger {
            color: #ff4d4d;
            font-weight: bold;
        }

        .image {
            margin-top: 10px;
            max-width: 350px;
            border: 2px solid #F2AA4C;
            border-radius: 8px;
        }
    </style>
</head>
<body>

<h1>Alphabot Fire Blockchain Viewer</h1>

<div class="summary">
    <p><span class="label">Tổng số block:</span> {{ total_blocks }}</p>
    <p><span class="label">File blockchain:</span> {{ file_name }}</p>
</div>

{% for block in chain %}
<div class="block">
    <h2>Block #{{ block.index }}</h2>

    <p><span class="label">Thời gian:</span> {{ block.timestamp }}</p>

    <p><span class="label">Dữ liệu cảnh báo:</span></p>
    <pre>{{ block.data_pretty }}</pre>

    <p><span class="label">Previous Hash:</span></p>
    <p class="hash">{{ block.previous_hash }}</p>

    <p><span class="label">Hash:</span></p>
    <p class="hash">{{ block.hash }}</p>

    {% if block.image_path %}
        <p><span class="label">Ảnh cảnh báo:</span></p>
        <img class="image" src="{{ block.image_path }}">
    {% endif %}
</div>
{% endfor %}

</body>
</html>
"""


@app.route("/")
def index():
    if not os.path.exists(BLOCKCHAIN_FILE):
        return "Chưa có file blockchain_log.json. Hãy chạy hệ thống phát hiện cháy trước."

    with open(BLOCKCHAIN_FILE, "r", encoding="utf-8") as file:
        raw_chain = json.load(file)

    chain = []

    for block in raw_chain:
        data = block.get("data", {})

        image_path = None

        if isinstance(data, dict):
            image_path = data.get("image_path")

        chain.append({
            "index": block.get("index"),
            "timestamp": block.get("timestamp"),
            "data_pretty": json.dumps(data, indent=4, ensure_ascii=False),
            "previous_hash": block.get("previous_hash"),
            "hash": block.get("hash"),
            "image_path": image_path
        })

    return render_template_string(
        HTML_TEMPLATE,
        chain=chain,
        total_blocks=len(chain),
        file_name=BLOCKCHAIN_FILE
    )


if __name__ == "__main__":
    app.run(debug=True, port=5050)