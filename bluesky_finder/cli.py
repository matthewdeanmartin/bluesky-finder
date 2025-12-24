import argparse
import sys
from .pipeline import Pipeline


def run_discover(args):
    """Run seed discovery loop (hashtags)."""
    p = Pipeline()
    p.run_discovery()


def run_fetch(args):
    """Fetch profiles and posts for queued candidates."""
    p = Pipeline()
    p.run_fetch(force=args.force)


def run_evaluate(args):
    """Run LLM evaluation on fetched candidates."""
    p = Pipeline()
    p.run_evaluation(force=args.force)


def run_all(args):
    """Run the full pipeline: Discover -> Fetch -> Eval -> Export."""
    p = Pipeline()
    print("--- Step 1: Discover ---")
    p.run_discovery()
    print("\n--- Step 2: Fetch ---")
    p.run_fetch(force=args.force)
    print("\n--- Step 3: Evaluate ---")
    p.run_evaluation(force=args.force)
    print("\n--- Step 4: Export ---")
    p.export_results(format=args.format)


def run_export(args):
    """Export results to HTML or JSONL."""
    p = Pipeline()
    p.export_results(format=args.format)


def main():
    parser = argparse.ArgumentParser(
        description="DC-Area Techies Discovery on Bluesky",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # Command: discover
    parser_discover = subparsers.add_parser(
        "discover", help="Run seed discovery loop (hashtags)"
    )
    parser_discover.set_defaults(func=run_discover)

    # Command: fetch
    parser_fetch = subparsers.add_parser(
        "fetch", help="Fetch profiles and posts for queued candidates"
    )
    parser_fetch.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch of profiles/posts regardless of TTL",
    )
    parser_fetch.set_defaults(func=run_fetch)

    # Command: evaluate
    parser_eval = subparsers.add_parser(
        "evaluate", help="Run LLM evaluation on fetched candidates"
    )
    parser_eval.add_argument(
        "--force",
        action="store_true",
        help="Force re-evaluation even if already scored",
    )
    parser_eval.set_defaults(func=run_evaluate)

    # Command: run-all
    parser_all = subparsers.add_parser(
        "run-all", help="Run the full pipeline sequentially"
    )
    parser_all.add_argument(
        "--force", action="store_true", help="Force fetch and evaluation"
    )
    parser_all.add_argument(
        "--format",
        choices=["html", "jsonl"],
        default="html",
        help="Export format (default: html)",
    )
    parser_all.set_defaults(func=run_all)

    # Command: export
    parser_export = subparsers.add_parser(
        "export", help="Export qualified candidates to HTML or JSONL"
    )
    parser_export.add_argument(
        "--format",
        choices=["html", "jsonl"],
        default="html",
        help="Export format (default: html)",
    )
    parser_export.set_defaults(func=run_export)

    # Parse args
    args = parser.parse_args()

    # Execute the selected function
    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
