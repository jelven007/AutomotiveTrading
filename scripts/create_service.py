#!/usr/bin/env python3
import argparse
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = PROJECT_ROOT / "services" / "_template"
SERVICE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
TEXT_SUFFIXES = {".ini", ".md", ".mako", ".py", ".toml"}


def service_name(value: str) -> str:
    if not SERVICE_NAME_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "service name must be lowercase kebab-case (for example, sample-service)"
        )
    return value


def render_service(name: str, output_root: Path) -> Path:
    destination = output_root / name
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")

    shutil.copytree(
        TEMPLATE_ROOT,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "service.db"),
    )
    for path in destination.rglob("*"):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            content = path.read_text()
            path.write_text(content.replace("qt-service-template", name))
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a FastAPI service from the template")
    parser.add_argument("name", type=service_name)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "services",
        help="directory that will contain the generated service",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        destination = render_service(args.name, args.output_root)
    except FileExistsError as error:
        raise SystemExit(str(error)) from error
    print(f"Created {args.name} at {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
