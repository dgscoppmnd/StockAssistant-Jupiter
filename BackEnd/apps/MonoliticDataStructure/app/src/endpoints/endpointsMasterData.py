import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile
from pydantic import BaseModel

from DataBaseManagement.dbConectionPostgres import get_db_products
from knowledge_files import save_document
from master_data_service import MasterDataError, MasterDataService

router = APIRouter(prefix="/master-data", tags=["master data"])


class MasterPayload(BaseModel):
    values: dict[str, Any]


class ClientAddressPayload(BaseModel):
    global_address_id: int
    address_type: str


def _service(db=Depends(get_db_products)) -> MasterDataService:
    return MasterDataService(db)


def _raise(exc: MasterDataError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/clients/{client_id}/addresses")
def list_client_addresses(client_id: int, service: MasterDataService = Depends(_service)):
    try: return service.client_addresses(client_id)
    except MasterDataError as exc: _raise(exc)


@router.post("/clients/{client_id}/addresses", status_code=status.HTTP_201_CREATED)
def add_client_address(client_id: int, payload: ClientAddressPayload, service: MasterDataService = Depends(_service)):
    try: return service.add_client_address(client_id, payload.global_address_id, payload.address_type)
    except MasterDataError as exc: _raise(exc)


@router.put("/clients/{client_id}/addresses/{association_id}")
def update_client_address(client_id: int, association_id: int, payload: ClientAddressPayload, service: MasterDataService = Depends(_service)):
    try: return service.update_client_address(client_id, association_id, payload.address_type)
    except MasterDataError as exc: _raise(exc)


@router.delete("/clients/{client_id}/addresses/{association_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_address(client_id: int, association_id: int, service: MasterDataService = Depends(_service)):
    try: service.delete_client_address(client_id, association_id)
    except MasterDataError as exc: _raise(exc)

@router.get("/suppliers/{supplier_id}/addresses")
def list_supplier_addresses(supplier_id: int, service: MasterDataService = Depends(_service)):
    try: return service.supplier_addresses(supplier_id)
    except MasterDataError as exc: _raise(exc)
@router.post("/suppliers/{supplier_id}/addresses", status_code=status.HTTP_201_CREATED)
def add_supplier_address(supplier_id: int, payload: ClientAddressPayload, service: MasterDataService = Depends(_service)):
    try: return service.add_supplier_address(supplier_id, payload.global_address_id, payload.address_type)
    except MasterDataError as exc: _raise(exc)
@router.put("/suppliers/{supplier_id}/addresses/{association_id}")
def update_supplier_address(supplier_id: int, association_id: int, payload: ClientAddressPayload, service: MasterDataService = Depends(_service)):
    try: return service.update_supplier_address(supplier_id, association_id, payload.address_type)
    except MasterDataError as exc: _raise(exc)
@router.delete("/suppliers/{supplier_id}/addresses/{association_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier_address(supplier_id: int, association_id: int, service: MasterDataService = Depends(_service)):
    try: service.delete_supplier_address(supplier_id, association_id)
    except MasterDataError as exc: _raise(exc)


def _save_knowledge(values, file, service, record_id=None):
    try:
        payload = json.loads(values)
        if not isinstance(payload, dict):
            raise ValueError("Expected an object")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="values debe ser un objeto JSON") from exc
    try:
        return save_document(service, payload, file, record_id)
    except MasterDataError as exc:
        _raise(exc)
    finally:
        if file is not None:
            file.file.close()


@router.post("/knowledge-documents/with-file", status_code=201)
def create_knowledge_document(values: str = Form(...), file: UploadFile | None = File(None), service: MasterDataService = Depends(_service)):
    return _save_knowledge(values, file, service)


@router.put("/knowledge-documents/{record_id}/with-file")
def update_knowledge_document(record_id: int, values: str = Form(...), file: UploadFile | None = File(None), service: MasterDataService = Depends(_service)):
    return _save_knowledge(values, file, service, record_id)


@router.get("/{resource}")
def list_records(resource: str, service: MasterDataService = Depends(_service)):
    try:
        return service.list(resource)
    except MasterDataError as exc:
        _raise(exc)


@router.post("/{resource}", status_code=status.HTTP_201_CREATED)
def create_record(resource: str, payload: MasterPayload, service: MasterDataService = Depends(_service)):
    try:
        if resource == "knowledge-documents" and "archivo" in payload.values:
            raise MasterDataError("Utiliza la carga de archivos para modificar archivo")
        return service.create(resource, payload.values)
    except MasterDataError as exc:
        _raise(exc)


@router.put("/{resource}/{record_id}")
def update_record(resource: str, record_id: int, payload: MasterPayload, service: MasterDataService = Depends(_service)):
    try:
        if resource == "knowledge-documents" and "archivo" in payload.values:
            raise MasterDataError("Utiliza la carga de archivos para modificar archivo")
        return service.update(resource, record_id, payload.values)
    except MasterDataError as exc:
        _raise(exc)


@router.delete("/{resource}/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(resource: str, record_id: int, service: MasterDataService = Depends(_service)):
    try:
        service.delete(resource, record_id)
    except MasterDataError as exc:
        _raise(exc)
