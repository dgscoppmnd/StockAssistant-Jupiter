import logging
from typing import Any
from fastapi import  APIRouter, HTTPException
from DataBaseManagement.dbConectionPostgres import get_db_users
from DataBaseManagement.schemasUsers import UserCreate, UserUpdate, UserResponse
from DataBaseManagement.dbservicesUsers import UserServicesManager
from fastapi import Depends, status
from typing import List

router = APIRouter()
logger = logging.getLogger("api.endpointsUsers")

# Endpoints de la API para crear un usuario
@router.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def crear_usuario(user: UserCreate, db=Depends(get_db_users)):
    logger.info("event=create_user_start email=%s", user.email)
    manager: UserServicesManager = UserServicesManager(db)
    created_user = manager.add_User(user)
    logger.info("event=create_user_success user_id=%s", created_user.get("id"))
    return created_user

# Actualización de usuario (no requerida en los tests pero implementada para completar la API)
@router.put("/users/{user_id}", response_model=UserResponse, status_code=status.HTTP_202_ACCEPTED)
def actualizar_usuario(user_id: int, user_update: UserUpdate, db=Depends(get_db_users)):
    logger.info("event=update_user_start user_id=%s", user_id)
    manager: UserServicesManager = UserServicesManager(db)
    try:
        updated_user = manager.update_User(user_id, user_update)
        logger.info("event=update_user_success user_id=%s", user_id)
        return updated_user
    except ValueError as e:
        logger.warning("event=update_user_not_found user_id=%s detail=%s", user_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )   
      
# Endpoint para eliminar un usuario
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_usuario(user_id: int, db=Depends(get_db_users)):
    logger.info("event=delete_user_start user_id=%s", user_id)
    manager: UserServicesManager = UserServicesManager(db)
    try:
        manager.delete_User(user_id)
        logger.info("event=delete_user_success user_id=%s", user_id)
    except ValueError as e:
        logger.warning("event=delete_user_not_found user_id=%s detail=%s", user_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    return None

# cambiar el status de un usuario
@router.put("/users/status/{user_id}", response_model=UserResponse)
def set_user_status(user_id: int, db=Depends(get_db_users)):
    logger.info("event=set_user_status user_id=%s", user_id)
    manager: UserServicesManager = UserServicesManager(db)
    try:
        updated_user = manager.set_User_status(user_id)
        logger.info("event=set_user_status_success user_id=%s", user_id)
        return updated_user
    except ValueError as e:
        logger.warning("event=set_user_status_not_found user_id=%s detail=%s", user_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

# Endpoint para listar todos los usuarios    
@router.get("/users/", response_model=List[UserResponse])
def listar_usuarios(db=Depends(get_db_users)):
    logger.info("event=list_users")
    manager: UserServicesManager = UserServicesManager(db)
    return manager.get_all_Users()

# Endpoint para listar usuarios caducados
@router.get("/users/caducados", response_model=List[UserResponse])
def obtener_usuarios_caducados(db=Depends(get_db_users)):
    logger.info("event=list_expired_users")
    manager: UserServicesManager = UserServicesManager(db)
    return manager.get_expired_Users()

# Endpoint para contar usuarios caducados
@router.get("/users/caducados/count")
def contar_caducados(db=Depends(get_db_users)):
    logger.info("event=count_expired_users")
    manager: UserServicesManager = UserServicesManager(db)
    return {"overdue": manager.count_overdue_Users()}

# Endpoint para obtener detalles de un usuario específico
@router.get("/users/{user_id}", response_model=UserResponse)
def obtener_usuario(user_id: int, db=Depends(get_db_users)):
    logger.info("event=get_user_start user_id=%s", user_id)
    manager: UserServicesManager = UserServicesManager(db)
    try:
        user = manager.get_User(user_id)
        logger.info("event=get_user_success user_id=%s", user_id)
        return user
    except ValueError as e:
        logger.warning("event=get_user_not_found user_id=%s detail=%s", user_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


