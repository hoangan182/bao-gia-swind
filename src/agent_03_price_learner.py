import os
import sys
from agent_09_price_learner import (
    Agent09_PriceLearner,
    resolve_path,
    COMMERCIAL_TECH_PATH,
    PRICES_DIR,
    get_latest_commercial_price_file,
    run_learner
)

__all__ = [
    "Agent09_PriceLearner",
    "resolve_path",
    "COMMERCIAL_TECH_PATH",
    "PRICES_DIR",
    "get_latest_commercial_price_file",
    "run_learner"
]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent_09_price_learner.py <path_to_excel_file>")
        sys.exit(1)

    excel_path = sys.argv[1]
    if not os.path.exists(excel_path):
        print(f"[LỖI] Không tìm thấy file: {excel_path}")
        sys.exit(1)

    run_learner(excel_path)
