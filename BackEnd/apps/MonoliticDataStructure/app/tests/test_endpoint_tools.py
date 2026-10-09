import sys  # Permite modificar las rutas de búsqueda de módulos de Python
import os  # Permite interactuar con variables de entorno del sistema operativo
from pathlib import Path  # Facilita el manejo de rutas de archivos de forma orientada a objetos

# Buscamos la carpeta que contiene a 'src'
current_path = Path(__file__).resolve()  # Obtiene la ruta absoluta de este archivo de prueba
project_root = None  # Inicializa la variable que guardará la carpeta raíz del proyecto

for p in [current_path] + list(current_path.parents):  # Recorre la ruta actual y todas sus carpetas padres
    if (p / "src").exists() and (p / "src" / "DataBaseManagement").exists():  # Comprueba si existen las carpetas src/DataBaseManagement
        project_root = p  # Asigna la carpeta encontrada como raíz del proyecto
        break  # Detiene la búsqueda al encontrar la carpeta

if project_root:  # Si se encontró la carpeta raíz
    sys.path.insert(0, str(project_root))  # Añade la raíz al inicio de las rutas de Python para importar sin errores
    print(f"\n[DEBUG OK] Raíz del proyecto agregada: {project_root}")  # Muestra en consola que la ruta se agregó con éxito
else:  # Si no se encontró la carpeta
    print("\n[DEBUG ERROR] No se encontró la carpeta 'src/DataBaseManagement'")  # Muestra en consola un mensaje de error

import pytest  # Importa el framework de pruebas automatizadas
from unittest.mock import MagicMock, patch  # Importa herramientas para crear objetos simulados y reemplazar funciones
from fastapi.testclient import TestClient  # Importa un cliente HTTP para probar la API sin levantar un servidor real
from fastapi import FastAPI  # Importa la clase principal para crear aplicaciones web FastAPI

# Importamos las funciones, modelos y el router desde nuestro archivo principal
from src.endpoints.endpointTools import (
    router,  # Importa el enrutador con los endpoints definidos
    ProductToolCreatePayload,  # Importa el esquema de datos para crear un producto
    ToolEmailPayload,  # Importa el esquema de datos para el envío de correos
    tool_search_products_db,  # Importa la función que busca productos en la base de datos
    tool_upgrade_libraries,  # Importa la función que actualiza librerías del sistema
    tool_send_email,  # Importa la función que envía correos electrónicos
)
from src.DataBaseManagement.dbConectionPostgres import get_db_products  # Importa la función de conexión a la BD PostgreSQL

# Creamos una aplicación de FastAPI auxiliar para montar el router durante los tests
app = FastAPI()  # Inicializa una aplicación auxiliar de FastAPI
app.include_router(router)  # Registra el enrutador de herramientas en la aplicación auxiliar

# 2. Crea la función dummy para sustituir la conexión a la base de datos
def override_get_db_products():  # Define una función generadora para sustituir la conexión real a la base de datos
    mock_conn = MagicMock()  # Crea una conexión simulada (falsa)
    try:  # Inicia un bloque de control de flujo
        yield mock_conn  # Entrega la conexión simulada al endpoint que la solicite
    finally:  # Bloque que se ejecuta al terminar la llamada
        pass  # No realiza ninguna acción al cerrar la conexión simulada

# 3. Aplica la sobreescritura GLOBALMENTE en la app antes de inicializar TestClient
app.dependency_overrides[get_db_products] = override_get_db_products  # Reemplaza la conexión real por la simulada en FastAPI

client = TestClient(app)  # Crea el cliente de pruebas HTTP asociado a la app configurada


def test_tool_search_products_db_empty_query():  # Define la prueba para búsquedas con texto vacío
    """Prueba que si la consulta está vacía o son solo espacios, retorne lista vacía sin tocar la BD."""
    mock_conn = MagicMock()  # Crea una conexión falsa a la base de datos
    result = tool_search_products_db(connection=mock_conn, query="   ")  # Llama a la función enviando solo espacios en blanco
    
    assert result == []  # Verifica que la respuesta sea una lista vacía
    # Verificamos que no se realizó ninguna consulta SQL
    mock_conn.cursor.assert_not_called()  # Confirma que nunca se intentó abrir un cursor SQL


def test_tool_search_products_db_success():  # Define la prueba para una búsqueda de productos exitosa
    """Prueba la búsqueda en base de datos devolviendo filas simuladas."""
    mock_conn = MagicMock()  # Crea una conexión falsa
    mock_cursor = MagicMock()  # Crea un cursor de base de datos falso
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor  # Configura el cursor para usarse con un administrador de contexto 'with'
    
    # Datos simulados retornados por cursor.fetchall()
    mock_cursor.fetchall.return_value = [  # Define los datos falsos que devolverá la consulta SQL
        (1, "Teclado", "Logitech", "http://link.com", 50.0, 45.0, False, "2026-01-01")
    ]

    result = tool_search_products_db(connection=mock_conn, query="teclado", limit=5)  # Ejecuta la búsqueda de 'teclado'

    assert len(result) == 1  # Verifica que devuelva exactamente un producto
    assert result[0]["pk_product"] == 1  # Verifica que el ID del producto sea 1
    assert result[0]["name_product"] == "Teclado"  # Verifica que el nombre del producto sea 'Teclado'
    # Verificamos que la consulta ejecutada incluye los comodines %
    mock_cursor.execute.assert_called_once()  # Verifica que la consulta SQL se haya ejecutado una sola vez
    assert mock_cursor.execute.call_args[0][1] == ["%teclado%", "%teclado%", "%teclado%", 5]  # Valida que los parámetros SQL contengan los comodines '%'


def test_tool_upgrade_libraries_blocked_package():  # Define la prueba para el bloqueo de paquetes no permitidos
    """Prueba que se lance un ValueError si se intenta actualizar una librería no permitida."""
    with pytest.raises(ValueError, match="No permitido en upgrade automatico"):  # Espera que la ejecución lance un error de tipo ValueError
        tool_upgrade_libraries(["requests", "libreria_maliciosa"])  # Llama a la función incluyendo un paquete prohibido


@patch("subprocess.run")  # Intercepta y simula la ejecución de comandos en la terminal
def test_tool_upgrade_libraries_success(mock_subprocess):  # Define la prueba para una actualización de librerías válida
    """Prueba la ejecución exitosa de actualización de librerías con subprocess mockeado."""
    # Simulamos el retorno del comando de terminal
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="Successfully installed", stderr="")  # Simula una respuesta exitosa de la consola

    result = tool_upgrade_libraries(["requests", "fastapi"])  # Ejecuta la función con paquetes permitidos

    assert result["return_code"] == 0  # Verifica que el código de respuesta del sistema sea 0 (éxito)
    assert "pip install --upgrade requests fastapi" in result["command"]  # Confirma que el comando generado sea el correcto
    mock_subprocess.assert_called_once()  # Valida que el comando de consola se haya ejecutado una sola vez


@patch.dict("os.environ", {}, clear=True)  # Vacía temporalmente todas las variables de entorno del sistema
def test_tool_send_email_missing_credentials():  # Define la prueba cuando faltan las credenciales de correo
    """Prueba que la función lance un ValueError si no existen las variables de entorno de SMTP."""
    payload = ToolEmailPayload(to_email="test@example.com", subject="Test", body="Hola")  # Crea los datos del correo de prueba
    
    with pytest.raises(ValueError, match="Configura STOCKASSISTANT_SMTP_USER"):  # Espera un error indicando la falta de usuario SMTP
        tool_send_email(payload)  # Ejecuta la función de envío sin credenciales configuradas


@patch("smtplib.SMTP")  # Intercepta y simula la conexión con el servidor de correo SMTP
@patch.dict("os.environ", {  # Configura variables de entorno simuladas para el test
    "STOCKASSISTANT_SMTP_USER": "user@example.com",
    "STOCKASSISTANT_SMTP_PASSWORD": "secret_password"
})
def test_tool_send_email_success(mock_smtp_class):  # Define la prueba para un envío de correo exitoso
    """Prueba el envío exitoso de correo mockeando el servidor SMTP."""
    mock_smtp_instance = MagicMock()  # Crea un objeto servidor SMTP falso
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance  # Asigna el servidor falso al administrador de contexto

    payload = ToolEmailPayload(to_email="cliente@example.com", subject="Asunto", body="Mensaje")  # Crea el contenido del correo
    result = tool_send_email(payload)  # Ejecuta la función de envío de correo

    assert result["status"] == "sent"  # Verifica que el estado devuelto sea 'sent' (enviado)
    assert result["to"] == "cliente@example.com"  # Verifica que el destinatario coincida
    # Verificamos que se inició TLS, login y el envío
    mock_smtp_instance.starttls.assert_called_once()  # Confirma que se inició la conexión segura TLS
    mock_smtp_instance.login.assert_called_once_with("user@example.com", "secret_password")  # Confirma que se inició sesión con las credenciales
    mock_smtp_instance.send_message.assert_called_once()  # Confirma que el mensaje fue enviado por el servidor SMTP


@patch("src.endpoints.endpointTools.tool_search_products_db")  # Simula la función interna de búsqueda en la BD
def test_endpoint_search_products_short_query(mock_search_db):  # Define la prueba del endpoint cuando la consulta es demasiado corta
    """Prueba que el endpoint falle (422) si la query tiene menos de 2 caracteres."""

    response = client.get("/tools/products/search-db?query=a")  # Realiza una petición GET enviando solo una letra
    
    assert response.status_code == 422  # Error de validación de Pydantic/FastAPI: Comprueba que retorne código de error 422
    mock_search_db.assert_not_called()  # Asegura que la función interna de búsqueda nunca llegó a ejecutarse


@patch("src.endpoints.endpointTools.tool_save_product")  # Simula la función encargada de guardar productos
def test_endpoint_save_product_success(mock_save_product):  # Define la prueba para crear un producto por HTTP POST
    """Prueba la creación exitosa de un producto mediante POST."""
    mock_save_product.return_value = {"id": 10, "name_product": "Mouse"}  # Establece la respuesta simulada al guardar

    # Sobrescribimos la dependencia de la DB para evitar conexión real
    app.dependency_overrides[get_db_products] = lambda: MagicMock()  # Asigna una función lambda con un objeto falso para la BD

    payload = {"name_product": "Mouse Logitech", "price": 25.0}  # Define el cuerpo de la petición en formato JSON
    response = client.post("/tools/products/save", json=payload)  # Realiza una petición POST a la ruta indicada

    assert response.status_code == 200  # Confirma que la respuesta HTTP sea 200 (éxito)
    assert response.json() == {"status": "created", "record": {"id": 10, "name_product": "Mouse"}}  # Comprueba el contenido del JSON devuelto
    
    # Limpiamos dependencias
    app.dependency_overrides.clear()  # Restablece las sobreescrituras de dependencias de la aplicación


def test_endpoint_upgrade_libraries_invalid_payload():  # Define la prueba del endpoint de actualización con datos no válidos
    """Prueba error HTTP 400 cuando se intenta enviar un paquete no permitido."""
    response = client.post("/tools/libraries/upgrade", json={"package_list": ["os"]})  # Envía una petición POST con un paquete prohibido
    
    assert response.status_code == 400  # Verifica que la API responda con un código de error HTTP 400
    assert "No permitido" in response.json()["detail"]  # Confirma que el mensaje de detalle en la respuesta contenga el texto 'No permitido'