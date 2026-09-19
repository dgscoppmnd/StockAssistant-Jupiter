import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from DataBaseManagement.client_csv_import import MAX_CSV_BYTES, import_client_csv, import_client_csv_events
from DataBaseManagement.dbConectionPostgres import db_context, get_db_products
from knowledge_files import save_document
from master_data_service import MasterDataError, MasterDataService

router = APIRouter(prefix="/master-data", tags=["master data"])
logger = logging.getLogger("api.endpointsMasterData")


class MasterPayload(BaseModel):
    values: dict[str, Any]


class ClientAddressPayload(BaseModel):
    global_address_id: int
    address_type: str


def _service(db=Depends(get_db_products)) -> MasterDataService:
    return MasterDataService(db)


def _raise(exc: MasterDataError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/clients/import-csv")
async def import_clients_csv(file: UploadFile = File(...), progress: bool = Query(default=False)):
    try:
        if not (file.filename or "").lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Selecciona un archivo .csv.")
        if file.size is not None and file.size > MAX_CSV_BYTES:
            raise HTTPException(status_code=413, detail="El CSV supera el límite de 200 MB.")
        if progress:
            source = await run_in_threadpool(_duplicate_csv_file, file.file)
            return StreamingResponse(
                _stream_client_import(source), media_type="application/x-ndjson",
                headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
            )
        return await run_in_threadpool(_import_client_file, file.file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("event=import_clients_csv_failed")
        raise HTTPException(status_code=500, detail="No se pudo importar el CSV. No se ha guardado ningún cliente.") from exc
    finally:
        await file.close()


def _duplicate_csv_file(source):
    source.seek(0)
    return os.fdopen(os.dup(source.fileno()), "rb")


def _import_client_file(source):
    with db_context() as db:
        return import_client_csv(source, db)


def _stream_client_import(source):
    with source:
        try:
            with db_context() as db:
                for event in import_client_csv_events(source, db):
                    yield json.dumps(event, ensure_ascii=False) + "\n"
        except ValueError as exc:
            yield json.dumps({"stage": "error", "detail": str(exc)}, ensure_ascii=False) + "\n"
        except Exception:
            logger.exception("event=import_clients_csv_failed")
            yield json.dumps({"stage": "error", "detail": "No se pudo importar el CSV. No se ha guardado ningún cliente."}) + "\n"


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
