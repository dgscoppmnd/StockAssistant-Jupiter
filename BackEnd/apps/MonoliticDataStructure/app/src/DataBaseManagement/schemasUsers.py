from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field   

# Modelos Pydantic para la gestión de usuarios
# Modelo para crear un usuario de forma simplificada, sin campos de ID o timestamps
class UserCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100, description="Nombre del usuario")
    apellido: str = Field(min_length=1, max_length=100, description="Apellido del usuario")
    email: str = Field(min_length=1, max_length=255, description="Email del usuario")
    descripcion: str = Field(min_length=1, max_length=200, description="Descripción del usuario")
    password: str = Field(min_length=6, max_length=100, description="Contraseña del usuario")
    status: int = Field(description="Status del usuario")
    startline: Optional[datetime] = Field(default=None, description="Fecha de inicio del usuario")
    deadline: Optional[datetime] = Field(default=None, description="Fecha de vencimiento del usuario")


# Modelo para actualizar un usuario, permitiendo editar todos los campos excepto el ID y los timestamps
class UserUpdate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100, description="Edita nombre del usuario") 
    apellido: str = Field(min_length=1, max_length=100, description="Edita apellido del usuario")
    email: str = Field(min_length=1, max_length=255, description="Edita email del usuario")
    descripcion: str = Field(min_length=1, max_length=200, description="Edita descripción del usuario")
    password: str = Field(min_length=6, max_length=100, description="Edita contraseña del usuario")
    status: int = Field(description="Edita status del usuario")
    startline: Optional[datetime] = Field(default=None, description="Edita fecha de inicio del usuario")
    deadline: Optional[datetime] = Field(default=None, description="Edita fecha de vencimiento del usuario")
    


# Modelo para la respuesta de la API, incluyendo todos los campos del usuario
class UserResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    descripcion: str
    password: str
    status: int
    startline: Optional[datetime] = None
    deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    auth_provider: Optional[str] = None
    google_sub: Optional[str] = None
    avatar_url: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email_verified: Optional[bool] = None
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserPublicResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    descripcion: str
    status: int
    startline: Optional[datetime] = None
    deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    auth_provider: Optional[str] = None
    google_sub: Optional[str] = None
    avatar_url: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email_verified: Optional[bool] = None
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=1, description="ID token emitido por Google")


class PasswordLoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255, description="Correo electrónico del usuario")
    password: str = Field(min_length=1, max_length=100, description="Contraseña del usuario")


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserPublicResponse
