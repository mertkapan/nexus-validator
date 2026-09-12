"""
High-Scale Dataset Chunker and Sanitizer
Splits massive combo files (e.g. 900,000+ accounts) into clean, GitHub-friendly chunks
(<50MB each) to prevent GitHub 100MB file push rejections and enable cloud matrix parallelism.
"""

import os
import sys
from pathlib import Path

def split_combo_file(input_file: str, chunk_size: int = 150000, output_dir: str = "chunks"):
    in_path = Path(input_file)
    if not in_path.exists():
        print(f"Error: Input file '{input_file}' not found.")
        return

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[SPLITTER] Reading and partitioning '{in_path.name}' into chunks of {chunk_size:,} lines...")

    chunk_idx = 1
    current_lines = []
    total_valid = 0

    with open(in_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            current_lines.append(stripped + "\n")
            total_valid += 1

            if len(current_lines) >= chunk_size:
                chunk_file = out_dir / f"chunk_{chunk_idx}.txt"
                with open(chunk_file, "w", encoding="utf-8") as cf:
                    cf.writelines(current_lines)
                print(f"  ✓ Written {chunk_file.name} ({len(current_lines):,} accounts)")
                chunk_idx += 1
                current_lines = []

    if current_lines:
        chunk_file = out_dir / f"chunk_{chunk_idx}.txt"
        with open(chunk_file, "w", encoding="utf-8") as cf:
            cf.writelines(current_lines)
        print(f"  ✓ Written {chunk_file.name} ({len(current_lines):,} accounts)")

    print(f"\n[COMPLETE] Partitioned {total_valid:,} accounts into {chunk_idx} chunk files in '{output_dir}'.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/split_combos.py <combo_file.txt> [chunk_size]")
        sys.exit(1)

    file_arg = sys.argv[1]
    size_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 150000
    split_combo_file(file_arg, chunk_size=size_arg)
