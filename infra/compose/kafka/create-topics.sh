#!/usr/bin/env bash

set -euo pipefail

bootstrap_server=${KAFKA_BOOTSTRAP_SERVER:-kafka:29092}
topics=(
  audit.recorded.v1
  market.raw.received.v1
  market.quote.updated.v1
  market.transaction.received.v1
  market.bar.updated.v1
  market.reference.updated.v1
  market.quality.changed.v1
  market.backfill.status_changed.v1
  model.decision.created.v1
  order.command.created.v1
  order.status.changed.v1
  risk.decision.created.v1
)

for topic in "${topics[@]}"; do
  if rpk topic describe "$topic" --brokers "$bootstrap_server" >/dev/null 2>&1; then
    echo "Topic already exists: $topic"
    continue
  fi
  rpk topic create "$topic" \
    --brokers "$bootstrap_server" \
    --partitions 3 \
    --replicas 1
done
