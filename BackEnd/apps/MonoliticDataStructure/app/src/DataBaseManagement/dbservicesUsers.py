from datetime import date, datetime, timezone
from typing import Any

from .dbManagementUsers import (
    insert_user,
    update_user,
    delete_user,
    get_user_by_id,
    get_all_users,
    get_expired_users,
    count_overdue_users
)
from .schemasUsers import UserCreate, UserUpdate
from passwords import hash_password

# Clase UserServicesManager para gestionar las operaciones CRUD de usuarios en la base de datos
# y valiar eliminar palabras ofensivas en los campos de texto
# y convertir las fechas a formato datetime con zona horaria UTC para su almacenamiento en la base de datos.
# Además, se incluye la serialización de los usuarios para convertir los campos de fecha a formato date al devolverlos en las respuestas de la API.
# se valida los json sean correctos y se maneja los errores de validación con un logger para facilitar la identificación y solución de problemas relacionados con la validación de solicitudes en la API.
class UserServicesManager:
    def __init__(self, db: Any = None):
        self.db = db

    def _clean_text(self, text: str | None) -> str:
        if text is None:
            return ""

        censored_words = ["maldicion", "tonto", "idiota", "malo", "feo"]
        cleaned_text = text.strip()
        for word in censored_words:
            cleaned_text = cleaned_text.replace(word, "****")
        return cleaned_text

    def _serialize_User(self, row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)

        deadline = result.get("deadline")
        if isinstance(deadline, datetime):
            result["deadline"] = deadline.date()

        return result

    def add_User(self, User_create: UserCreate) -> dict[str, Any]:
        payload = {
            "nombre": self._clean_text(User_create.nombre),
            "apellido": self._clean_text(User_create.apellido),
            "email": User_create.email,
            "descripcion": self._clean_text(User_create.descripcion),
            "password": hash_password(User_create.password),
            "status": User_create.status,
            "startline": datetime.combine(User_create.startline, datetime.min.time(), tzinfo=timezone.utc) if User_create.startline else None,
            "deadline": datetime.combine(User_create.deadline, datetime.min.time(), tzinfo=timezone.utc) if User_create.deadline else None,
            
        }
        created = insert_user(payload, connection=self.db)
        return self._serialize_User(created)

    def get_User(self, User_id: int) -> dict[str, Any]:
        row = get_user_by_id(User_id, connection=self.db)
        if not row:
            raise ValueError(f"Usuario con ID {User_id} no encontrado")
        return self._serialize_User(row)

    def get_all_Users(self) -> list[dict[str, Any]]:
        rows = get_all_users(connection=self.db)
        return [self._serialize_User(row) for row in rows]

    def set_User_status(self, User_id: int) -> dict[str, Any]:
        updated = update_user(
            User_id,
            {
                "status": 1,
                "updated_at": datetime.now(timezone.utc),
            },
            connection=self.db,
        )
        if not updated:
            raise ValueError(f"Usuario con ID {User_id} no encontrado")
        return self._serialize_User(updated)

    def update_User(self, User_id: int, User_update: UserUpdate) -> dict[str, Any]:
        payload = {
            "nombre": self._clean_text(User_update.nombre),
            "apellido": self._clean_text(User_update.apellido),
            "email": User_update.email,
            "descripcion": self._clean_text(User_update.descripcion),
            "password": hash_password(User_update.password),
            "status": User_update.status,
            "startline": datetime.combine(User_update.startline, datetime.min.time(), tzinfo=timezone.utc) if User_update.startline else None,
            "deadline": datetime.combine(User_update.deadline, datetime.min.time(), tzinfo=timezone.utc) if User_update.deadline else None,
            "updated_at": datetime.now(timezone.utc),
        }

        updated = update_user(User_id, payload, connection=self.db)
        if not updated:
            raise ValueError(f"Usuario con ID {User_id} no encontrado")
        return self._serialize_User(updated)

    def delete_User(self, User_id: int) -> bool:
        deleted = delete_user(User_id, connection=self.db)
        if not deleted:
            raise ValueError(f"Usuario con ID {User_id} no encontrado")
        return True

    def get_expired_Users(self) -> list[dict[str, Any]]:
        rows = get_expired_users( connection=self.db)
        return [self._serialize_User(row) for row in rows]

    def count_overdue_Users(self) -> int:
        return count_overdue_users(connection=self.db)

   
