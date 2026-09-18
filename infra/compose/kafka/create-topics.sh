#!/usr/bin/env bash

set -euo pipefail

bootstrap_server=${KAFKA_BOOTSTRAP_SERVER:-kafka:29092}
topics=(
  audit.recorded.v1
  market.quote.updated.v1
  model.decision.created.v1
  order.command.created.v1
  order.status.changed.v1
  risk.decision.created.v1
)

for topic in "${topics[@]}"; do
  rpk topic create "$topic" \
    --brokers "$bootstrap_server" \
    --partitions 3 \
    --replicas 1
done
