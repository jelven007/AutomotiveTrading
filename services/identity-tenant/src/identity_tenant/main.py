from fastapi import FastAPI

from identity_tenant.api.app import create_app as create_api_app


def create_app() -> FastAPI:
    return create_api_app()
