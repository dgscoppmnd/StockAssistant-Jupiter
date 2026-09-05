from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from DataBaseManagement.dbConectionPostgres import get_db_products
from master_data_service import MasterDataError, MasterDataService

router = APIRouter(prefix="/master-data", tags=["master data"])


class MasterPayload(BaseModel):
    values: dict[str, Any]


def _service(db=Depends(get_db_products)) -> MasterDataService:
    return MasterDataService(db)


def _raise(exc: MasterDataError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/{resource}")
def list_records(resource: str, service: MasterDataService = Depends(_service)):
    try:
        return service.list(resource)
    except MasterDataError as exc:
        _raise(exc)


@router.post("/{resource}", status_code=status.HTTP_201_CREATED)
def create_record(resource: str, payload: MasterPayload, service: MasterDataService = Depends(_service)):
    try:
        return service.create(resource, payload.values)
    except MasterDataError as exc:
        _raise(exc)


@router.put("/{resource}/{record_id}")
def update_record(resource: str, record_id: int, payload: MasterPayload, service: MasterDataService = Depends(_service)):
    try:
        return service.update(resource, record_id, payload.values)
    except MasterDataError as exc:
        _raise(exc)


@router.delete("/{resource}/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(resource: str, record_id: int, service: MasterDataService = Depends(_service)):
    try:
        service.delete(resource, record_id)
    except MasterDataError as exc:
        _raise(exc)
