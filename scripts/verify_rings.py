"""
神殿协议 - 年轮哈希验证脚本
验证链式哈希完整性和merkle_root
可用于本地验证或GitHub Action
"""
import json
import hashlib
import sys
import os
import glob

def sha256_hash(tx_id, tx_type, credit_delta, prev_hash):
    input_str = f"{tx_id}|{tx_type}|{credit_delta}|{prev_hash}"
    return hashlib.sha256(input_str.encode()).hexdigest()

def validate_ring_file(filepath):
    """验证单个年轮文件的哈希链完整性"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    errors = []
    rings = data.get("rings", [])
    account_id = data.get("account_id", "unknown")
    
    if not rings:
        return {"file": filepath, "account_id": account_id, "valid": False, "errors": ["No rings found"]}
    
    # Validate chain
    for i, ring in enumerate(rings):
        # Compute expected hash
        expected = sha256_hash(ring["tx_id"], ring["type"], ring["credit_delta"], ring["prev_hash"])
        
        if ring["this_hash"] != expected:
            errors.append(f"Ring #{i+1} ({ring['tx_id']}): hash mismatch. Expected {expected[:16]}..., got {ring['this_hash'][:16]}...")
        
        # Check prev_hash linkage (except genesis which should be all zeros)
        if i > 0:
            if ring["prev_hash"] != rings[i-1]["this_hash"]:
                errors.append(f"Ring #{i+1} ({ring['tx_id']}): prev_hash doesn't match previous this_hash")
    
    # Validate merkle_root
    merkle_input = "".join(r["this_hash"] for r in rings)
    expected_merkle = hashlib.sha256(merkle_input.encode()).hexdigest()
    if data.get("merkle_root") != expected_merkle:
        errors.append(f"Merkle root mismatch. Expected {expected_merkle[:16]}..., got {data.get('merkle_root', 'None')[:16] if data.get('merkle_root') else 'None'}...")
    
    # Validate running_total
    total = sum(r["credit_delta"] for r in rings)
    if data.get("running_total") != total:
        errors.append(f"Running total mismatch. Expected {total}, got {data.get('running_total')}")
    
    return {
        "file": filepath,
        "account_id": account_id,
        "year": data.get("year"),
        "rings_count": len(rings),
        "valid": len(errors) == 0,
        "errors": errors
    }

def validate_three_way(rings_dir, board_dir, genesis_dir):
    """三账对冲验证：年轮 + 小黑板 + genesis交叉校验"""
    errors = []
    
    # Load all rings
    ring_files = glob.glob(os.path.join(rings_dir, "*.json"))
    all_rings = {}
    for rf in ring_files:
        if os.path.basename(rf).startswith("."):
            continue
        with open(rf, "r", encoding="utf-8") as f:
            data = json.load(f)
        all_rings[data["account_id"]] = data
    
    # Load all orders
    order_files = glob.glob(os.path.join(board_dir, "**", "*.json"), recursive=True)
    all_orders = {}
    for of in order_files:
        if os.path.basename(of).startswith("."):
            continue
        with open(of, "r", encoding="utf-8") as f:
            data = json.load(f)
        all_orders[data["order_id"]] = data
    
    # For each escrow in rings, find matching order
    for account_id, ring_data in all_rings.items():
        for ring_entry in ring_data.get("rings", []):
            if ring_entry.get("type") == "escrow" and ring_entry.get("order_id"):
                order_id = ring_entry["order_id"]
                if order_id not in all_orders:
                    errors.append(f"{account_id}: escrow for {order_id} but order not found in board")
                else:
                    order = all_orders[order_id]
                    if abs(ring_entry["credit_delta"]) != order.get("credit_escrow", 0):
                        errors.append(f"{account_id}: escrow amount {abs(ring_entry['credit_delta'])} != order escrow {order.get('credit_escrow')}")
    
    # For each closed order, verify credit was received
    for order_id, order in all_orders.items():
        if order.get("status") == "closed" and order.get("claimed_by"):
            claimed_by = order["claimed_by"]
            if claimed_by not in all_rings:
                errors.append(f"Order {order_id} closed by {claimed_by} but no ring file found")
            else:
                # Check if claimed_by has a trade_in entry for this order
                found = False
                for r in all_rings[claimed_by].get("rings", []):
                    if r.get("order_id") == order_id and r.get("type") in ("trade_in", "protocol_credit"):
                        found = True
                        break
                if not found:
                    errors.append(f"Order {order_id} closed but {claimed_by} has no trade_in/protocol_credit record")
    
    return {"valid": len(errors) == 0, "errors": errors, "accounts_checked": len(all_rings), "orders_checked": len(all_orders)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python verify_rings.py <ring_file>           - Validate single ring file")
        print("  python verify_rings.py --all <repo_root>     - Validate all rings + three-way")
        sys.exit(1)
    
    if sys.argv[1] == "--all":
        repo_root = sys.argv[2] if len(sys.argv) > 2 else "."
        rings_dir = os.path.join(repo_root, "rings")
        board_dir = os.path.join(repo_root, "board")
        genesis_dir = os.path.join(repo_root, "genesis")
        
        print("=" * 60)
        print("TEMPLE PROTOCOL - Full Validation")
        print("=" * 60)
        
        # Validate each ring file
        ring_files = glob.glob(os.path.join(rings_dir, "*.json"))
        all_valid = True
        for rf in ring_files:
            if os.path.basename(rf).startswith("."):
                continue
            result = validate_ring_file(rf)
            status = "PASS" if result["valid"] else "FAIL"
            print(f"\n[{status}] {os.path.basename(rf)} ({result['rings_count']} rings)")
            if result["errors"]:
                for e in result["errors"]:
                    print(f"  ERROR: {e}")
                all_valid = False
        
        # Three-way validation
        print("\n" + "-" * 60)
        print("Three-way validation (rings + board + genesis):")
        tw = validate_three_way(rings_dir, board_dir, genesis_dir)
        status = "PASS" if tw["valid"] else "FAIL"
        print(f"[{status}] Accounts: {tw['accounts_checked']}, Orders: {tw['orders_checked']}")
        if tw["errors"]:
            for e in tw["errors"]:
                print(f"  ERROR: {e}")
            all_valid = False
        
        print("\n" + "=" * 60)
        print(f"RESULT: {'ALL VALID' if all_valid else 'VALIDATION FAILED'}")
        sys.exit(0 if all_valid else 1)
    else:
        filepath = sys.argv[1]
        result = validate_ring_file(filepath)
        status = "PASS" if result["valid"] else "FAIL"
        print(f"[{status}] {os.path.basename(filepath)} ({result['rings_count']} rings)")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  ERROR: {e}")
        sys.exit(0 if result["valid"] else 1)
