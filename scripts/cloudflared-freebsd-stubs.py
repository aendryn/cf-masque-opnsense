#!/usr/bin/env python3
"""Apply FreeBSD build stubs to a cloudflared source tree.
Usage: cloudflared-freebsd-stubs.py <cloudflared-src-dir>
"""
import sys
import os

stubs = [
    (
        "diagnostic/network/collector_unix.go",
        "diagnostic/network/collector_freebsd.go",
        "darwin || linux",
        "freebsd",
    ),
    (
        "diagnostic/system_collector_linux.go",
        "diagnostic/system_collector_freebsd.go",
        "//go:build linux",
        "//go:build freebsd",
    ),
]

root = sys.argv[1] if len(sys.argv) > 1 else "."
for src, dst, old, new in stubs:
    with open(os.path.join(root, src)) as f:
        content = f.read()
    with open(os.path.join(root, dst), "w") as f:
        f.write(content.replace(old, new, 1))
    print(f"  {dst}")

print("FreeBSD stubs applied.")
