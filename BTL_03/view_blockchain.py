import json

with open("blockchain_log.json", "r", encoding="utf-8") as f:
    chain = json.load(f)

print("=" * 60)
print("ALPHABOT FIRE BLOCKCHAIN")
print("=" * 60)

for block in chain:
    print(f"\nBLOCK: {block['index']}")
    print("-" * 60)

    print("Time:")
    print(block["timestamp"])

    print("\nData:")
    print(json.dumps(block["data"], indent=4, ensure_ascii=False))

    print("\nPrevious Hash:")
    print(block["previous_hash"])

    print("\nHash:")
    print(block["hash"])

print("\n" + "=" * 60)