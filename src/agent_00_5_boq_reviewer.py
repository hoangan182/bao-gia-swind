import sys
from agent_02_boq_reviewer import (
    Agent02_BOQReviewer,
    resolve_path,
    similar,
    get_catalogs,
    find_ambiguous_items,
    save_learned_keyword,
    resolve_ambiguous_interactive,
    run_reviewer
)

__all__ = [
    "Agent02_BOQReviewer",
    "resolve_path",
    "similar",
    "get_catalogs",
    "find_ambiguous_items",
    "save_learned_keyword",
    "resolve_ambiguous_interactive",
    "run_reviewer"
]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent_02_boq_reviewer.py <path_to_boq_excel> [--interactive]")
        sys.exit(1)
    is_interactive = "--interactive" in sys.argv
    success = run_reviewer(sys.argv[1], interactive=is_interactive)
    sys.exit(0 if success else 1)
