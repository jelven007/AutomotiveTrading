from dataclasses import dataclass

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/market", tags=["market-data"])


@dataclass(frozen=True)
class DatasetView:
    key: str
    name: str
    primary_store: str
    raw_archive: bool
    completeness: str


DATASETS = (
    DatasetView("quote", "实时行情与五档盘口", "clickhouse", True, "best_effort"),
    DatasetView("bar", "K 线与分时", "clickhouse", True, "validated"),
    DatasetView("transaction", "当前及历史分笔", "clickhouse", True, "partial_possible"),
    DatasetView("instrument", "证券主数据", "mysql", True, "tushare_completed"),
    DatasetView("block", "板块与成分", "mysql", True, "source_dependent"),
    DatasetView("corporate_action", "除权除息", "clickhouse", True, "validated"),
    DatasetView("financial", "财务摘要与专业财务", "clickhouse", True, "validated"),
    DatasetView("f10", "F10 目录与正文", "minio", True, "source_dependent"),
)


@router.get("/data-catalog")
def data_catalog() -> dict[str, object]:
    return {
        "provider": "mootdx",
        "verification_provider": "tushare",
        "datasets": [dataset.__dict__ for dataset in DATASETS],
    }
