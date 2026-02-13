#!/usr/bin/env python3

import sys
import zipfile
from pathlib import Path

OUT_ZIP = "code.zip"

DOCKERFILE = Path("Dockerfile")

FROM_LINE = "COPY echo-flag-src/echo-real-flag.c /tmp/echo-flag.c"
TO_LINE = "COPY echo-flag-src/echo-fake-flag.c /tmp/echo-flag.c"

INCLUDE_PATHS = [
    "Dockerfile",
    "app.py",
    "data/example-code.c",
    "docker-compose.yaml",
    "echo-flag-src/echo-fake-flag.c",
    "requirements.txt",
    "run-dev.sh",
    "static/app.js",
    "static/codicon.ttf",
    "static/style.css",
    "templates/index.html",
]


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def read_lines(path: Path):
    return path.read_text().splitlines()


def write_lines(path: Path, lines):
    path.write_text("\n".join(lines) + "\n")


# ---- validations ----
if not DOCKERFILE.is_file():
    fail("Dockerfile not found")

for p in INCLUDE_PATHS:
    if not Path(p).is_file():
        fail(f"Missing file: {p}")

docker_lines = read_lines(DOCKERFILE)

if FROM_LINE not in docker_lines:
    fail(f"Dockerfile does not contain expected line:\n{FROM_LINE}")

if TO_LINE in docker_lines:
    fail("Dockerfile already contains the fake flag line")

# ---- modify Dockerfile ----
modified = False
new_lines = []

for line in docker_lines:
    if line == FROM_LINE:
        new_lines.append(TO_LINE)
        modified = True
    else:
        new_lines.append(line)

if not modified:
    fail("Failed to replace line in Dockerfile")

write_lines(DOCKERFILE, new_lines)

# ---- zip + restore ----
try:
    zip_path = Path(OUT_ZIP)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in INCLUDE_PATHS:
            zf.write(p, arcname=p)

    print(f"Created: {OUT_ZIP}")

finally:
    # restore Dockerfile
    restored_lines = []
    for line in read_lines(DOCKERFILE):
        if line == TO_LINE:
            restored_lines.append(FROM_LINE)
        else:
            restored_lines.append(line)

    write_lines(DOCKERFILE, restored_lines)
    print("Dockerfile restored")
