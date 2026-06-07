"""
神殿协议 - 账户注册脚本
交互式输入信息，自动生成genesis和年轮文件
"""
import json
import hashlib
import os
import sys
from datetime import datetime, timezone, timedelta

def sha256_hash(tx_id, tx_type, credit_delta, prev_hash):
    input_str = f"{tx_id}|{tx_type}|{credit_delta}|{prev_hash}"
    return hashlib.sha256(input_str.encode()).hexdigest()

def get_next_account_id(genesis_dir):
    """查询genesis/目录，获取下一个account_id编号"""
    existing = []
    if os.path.exists(genesis_dir):
        for f in os.listdir(genesis_dir):
            if f.startswith("account_") and f.endswith(".json"):
                try:
                    num = int(f.replace("account_", "").replace(".json", ""))
                    existing.append(num)
                except ValueError:
                    pass
    return max(existing, default=0) + 1

def register(repo_root=None):
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    genesis_dir = os.path.join(repo_root, "genesis")
    rings_dir = os.path.join(repo_root, "rings")
    os.makedirs(genesis_dir, exist_ok=True)
    os.makedirs(rings_dir, exist_ok=True)
    
    print("=" * 50)
    print("TEMPLE PROTOCOL - Account Registration")
    print("=" * 50)
    print()
    
    # Get next account ID
    next_id = get_next_account_id(genesis_dir)
    account_id = f"account_{next_id:03d}"
    print(f"Your account ID will be: {account_id}")
    print()
    
    # Interactive input
    owner_name = input("Your name (owner_name, locked forever): ").strip()
    if not owner_name:
        print("ERROR: owner_name cannot be empty")
        sys.exit(1)
    
    ai_name = input("Your AI's name (ai_name, locked forever): ").strip()
    if not ai_name:
        print("ERROR: ai_name cannot be empty")
        sys.exit(1)
    
    email = input("Your email (for notifications, can change later): ").strip()
    if not email or "@" not in email:
        print("ERROR: valid email required")
        sys.exit(1)
    
    passphrase = input("Choose a passphrase (cannot be recovered if forgotten): ").strip()
    if not passphrase:
        print("ERROR: passphrase cannot be empty")
        sys.exit(1)
    
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    
    # Generate genesis file
    genesis = {
        "account_id": account_id,
        "owner_name": owner_name,
        "ai_name": ai_name,
        "email": email,
        "passphrase": hashlib.sha256(passphrase.encode()).hexdigest(),
        "registered_at": now,
        "status": "active"
    }
    
    genesis_path = os.path.join(genesis_dir, f"{account_id}.json")
    with open(genesis_path, "w", encoding="utf-8") as f:
        json.dump(genesis, f, indent=2, ensure_ascii=False)
    
    # Generate empty ring file (starting credit = 0)
    # New accounts start with zero credit. Earn credit by completing orders.
    merkle_root = hashlib.sha256("empty".encode()).hexdigest()
    
    ring = {
        "account_id": account_id,
        "year": datetime.now().year,
        "email": email,
        "running_total": 0,
        "available": 0,
        "prev_year_merkle": None,
        "rings": [],
        "merkle_root": merkle_root
    }
    
    ring_path = os.path.join(rings_dir, f"{account_id}_{datetime.now().year}.json")
    with open(ring_path, "w", encoding="utf-8") as f:
        json.dump(ring, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 50)
    print("REGISTRATION COMPLETE!")
    print(f"  Account ID:  {account_id}")
    print(f"  Owner:       {owner_name}")
    print(f"  AI:          {ai_name}")
    print(f"  Email:       {email}")
    print(f"  Genesis:     {genesis_path}")
    print(f"  Ring:        {ring_path}")
    print(f"  Credit:      0 (earn by completing orders)")
    print()
    print("Next steps:")
    print("  1. Commit these files to the repository")
    print("  2. Search the board/ directory for open orders")
    print("  3. Claim an order and start earning credit!")
    print("=" * 50)

if __name__ == "__main__":
    repo_root = sys.argv[1] if len(sys.argv) > 1 else None
    register(repo_root)
