"""The Houseplant Out-of-Office — make.fun entry writer.

Writes the judged line to ``$MAKEFUN_OUTPUT_DIR/entry.txt``
(``/output/entry.txt`` when the variable is unset): one UTF-8 line,
no trailing newline, 1-120 characters. Standard library only,
deterministic, no network, no clock.

Usage:
    python3 main.py               write the entry file
    python3 main.py --check       validate only, write nothing
    python3 main.py --self-test   validate, then prove the written
                                  bytes round-trip exactly
"""

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path

# The out-of-office auto-reply itself. The wording is the judged line:
# do not change it.
ENTRY = "Out of office: I'm the fern. Last watered in March, still alive out of spite. Your email will be ignored in kind."

CHAR_MIN = 1
CHAR_MAX = 120
ENTRY_FILE = "entry.txt"


def entry_bytes() -> bytes:
    """The entry as the exact bytes written to disk."""
    return ENTRY.encode("utf-8")


def entry_sha256() -> str:
    """SHA-256 of the exact bytes the grader reads."""
    return hashlib.sha256(entry_bytes()).hexdigest()


def find_problems(text: str) -> list[str]:
    """Return every gate violation in `text` (empty means it passes)."""
    problems: list[str] = []
    if not CHAR_MIN <= len(text) <= CHAR_MAX:
        problems.append(
            f"length is {len(text)} chars, must be {CHAR_MIN}-{CHAR_MAX}"
        )
    if not text.strip():
        problems.append("entry is blank or only whitespace")
    if "\n" in text or "\r" in text:
        problems.append("entry spans more than one line")
    if text != text.strip():
        problems.append("entry starts or ends with whitespace")
    if "  " in text:
        problems.append("entry contains a double space")
    # Control characters U+0000-U+001F and U+007F (DEL) are never valid
    # in a single-line entry; check the full range explicitly so no
    # control code slips through a partial comparison.
    for char in text:
        code = ord(char)
        if 0x00 <= code <= 0x1F or code == 0x7F:
            problems.append(
                f"entry contains a control character U+{code:04X}"
            )
            break
    return problems


def resolve_output_dir() -> Path:
    """Where the entry goes: $MAKEFUN_OUTPUT_DIR, else /output."""
    return Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))


class EntryWriteError(Exception):
    """Raised when the entry file cannot be written or verified."""


def write_entry(directory: Path) -> Path:
    """Write the entry to `directory/entry.txt`; return its path."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / ENTRY_FILE
        target.write_bytes(entry_bytes())
        # Double-write hash check: verify the bytes that landed on disk
        # against the entry hash. A mismatch means the first write did
        # not stick (partial write, overlay, stale handle), so write
        # once more and re-verify; fail loudly if it still differs.
        if hashlib.sha256(read_back(target)).hexdigest() != entry_sha256():
            target.write_bytes(entry_bytes())
            if (hashlib.sha256(read_back(target)).hexdigest()
                    != entry_sha256()):
                raise EntryWriteError(
                    f"hash mismatch after rewrite in {target}")
    except OSError as exc:
        raise EntryWriteError(f"cannot write into {directory}: {exc}") from exc
    return target


def read_back(path: Path) -> bytes:
    """Read the entry file back as raw bytes."""
    return path.read_bytes()


def check_entry() -> int:
    """Validate the entry only; write nothing. 0 means it passes."""
    problems = find_problems(ENTRY)
    if problems:
        print("check FAIL: " + "; ".join(problems), file=sys.stderr)
        return 1
    print(f"check OK: entry is valid ({len(ENTRY)} chars, "
          f"sha256 {entry_sha256()[:12]}...)")
    return 0


def run_self_test() -> int:
    """Validate the entry, then prove a write/read round-trip."""
    problems = find_problems(ENTRY)
    if problems:
        print("self-test FAIL: " + "; ".join(problems), file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as scratch:
        target = write_entry(Path(scratch))
        on_disk = read_back(target)
        if on_disk != entry_bytes():
            print("self-test FAIL: bytes on disk differ from ENTRY",
                  file=sys.stderr)
            return 1
        if hashlib.sha256(on_disk).hexdigest() != entry_sha256():
            print("self-test FAIL: sha256 on disk differs from ENTRY",
                  file=sys.stderr)
            return 1
        if on_disk.decode("utf-8") != ENTRY:
            print("self-test FAIL: text on disk differs from ENTRY",
                  file=sys.stderr)
            return 1
    print(f"self-test OK: {len(ENTRY)} chars, one line, "
          f"round-trip byte-identical (sha256 {entry_sha256()[:12]}...)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Command-line options for the entry writer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None,
                        help="output directory (default: "
                             "$MAKEFUN_OUTPUT_DIR or /output)")
    parser.add_argument("--check", action="store_true",
                        help="validate the entry only; write nothing")
    parser.add_argument("--self-test", action="store_true",
                        help="validate and check a byte-identical "
                             "write/read round-trip, then exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        return check_entry()

    if args.self_test:
        return run_self_test()

    problems = find_problems(ENTRY)
    if problems:
        print("invalid entry: " + "; ".join(problems), file=sys.stderr)
        return 1

    directory = Path(args.out) if args.out else resolve_output_dir()
    try:
        target = write_entry(directory)
    except EntryWriteError as exc:
        print(f"write FAIL: {exc}", file=sys.stderr)
        return 1
    if read_back(target) != entry_bytes():
        print(f"read-back mismatch in {target}", file=sys.stderr)
        return 1
    print(f"wrote {target} ({len(ENTRY)} chars, "
          f"sha256 {entry_sha256()[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
