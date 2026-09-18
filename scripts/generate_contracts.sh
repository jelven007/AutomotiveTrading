#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
contracts_dir="$repo_root/packages/contracts"
generated_dir=$(mktemp -d)
trap 'rm -rf "$generated_dir"' EXIT

uv run python - "$contracts_dir" <<'PY'
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

contracts_dir = Path(sys.argv[1])
model_schema = json.loads(
    (contracts_dir / "jsonschema/model-decision-v1.json").read_text()
)
Draft202012Validator.check_schema(model_schema)

for relative_path in ("asyncapi.yaml", "openapi/common.yaml"):
    document = yaml.safe_load((contracts_dir / relative_path).read_text())
    if not isinstance(document, dict):
        raise TypeError(f"{relative_path} must contain a YAML object")

asyncapi = yaml.safe_load((contracts_dir / "asyncapi.yaml").read_text())
required = set(asyncapi["components"]["schemas"]["EventEnvelope"]["required"])
expected = {"event_id", "tenant_id", "trace_id"}
if not expected.issubset(required):
    raise ValueError(f"EventEnvelope is missing required fields: {expected - required}")
PY

mkdir -p "$generated_dir/python"
grpc_include=$(uv run python -c \
  'import pathlib, grpc_tools; print(pathlib.Path(grpc_tools.__file__).parent / "_proto")')
uv run python -m grpc_tools.protoc \
  --proto_path="$contracts_dir/proto" \
  --proto_path="$grpc_include" \
  --python_out="$generated_dir/python" \
  --pyi_out="$generated_dir/python" \
  "$contracts_dir/proto/common/v1/envelope.proto" \
  "$contracts_dir/proto/trading/v1/trading.proto"

printf 'Contracts validated and generated successfully.\n'
