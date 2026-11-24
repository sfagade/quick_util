#!/usr/bin/env python3
import argparse
import secrets
import string
from pathlib import Path


def random_name(length: int = 12) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def rename_matching_files(
    root: Path,
    pattern: str,
    length: int = 12,
    apply: bool = False,
) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if not path.match(pattern):
            continue

        while True:
            new_name = f"{random_name(length)}{path.suffix}"
            target = path.with_name(new_name)
            if not target.exists():
                break

        if apply:
            path.rename(target)
            print(f"RENAMED: {path} -> {target.name}")
        else:
            print(f"[DRY RUN] {path} -> {target.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recursively rename matching files to random names."
    )
    parser.add_argument("folder", type=Path, help="Target directory path")
    parser.add_argument(
        "pattern",
        help='Filename glob pattern, e.g. "*.jpg" or "*draft*"',
    )
    parser.add_argument(
        "--length",
        type=int,
        default=12,
        help="Length of random base name (default: 12)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename files (without this flag, only prints a dry run)",
    )
    args = parser.parse_args()

    if not args.folder.is_dir():
        raise SystemExit(f"Error: '{args.folder}' is not a valid directory.")

    rename_matching_files(
        root=args.folder,
        pattern=args.pattern,
        length=args.length,
        apply=args.apply,
    )


if __name__ == "__main__":
    main()