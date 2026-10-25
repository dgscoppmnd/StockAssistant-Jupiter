#  Configuración de Infraestructura con Docker y PostgreSQL

##  Descripción General

Este documento documenta la configuración de la infraestructura para el TFM de Supply Chain Management, utilizando Docker para contenerizar PostgreSQL y pgAdmin, junto con los scripts de inicialización de la base de datos.

---

##  Estructura del Proyecto

```text
docker/
├── docker-compose.yml          # Orquestación de contenedores
├── postgres/
│   ├── init.sql               # Script de inicialización de BD
│   ├── postgresql.conf        # Configuración de PostgreSQL
│   └── pg_hba.conf            # Configuración de autenticación
└── pgadmin/
    └── servers.json           # Configuración automática de pgAdmin
```

---

##  Configuración de Servicios

### 1. PostgreSQL

| Configuración     | Valor                |
| ----------------- | -------------------- |
| **Imagen**        | `postgres:15-alpine` |
| **Contenedor**    | `supply_chain_db`    |
| **Puerto**        | `5432:5432`          |
| **Usuario**       | `admin`              |
| **Contraseña**    | `admin123`           |
| **Base de datos** | `supply_chain`       |

### 2. pgAdmin

| Configuración  | Valor                   |
| -------------- | ----------------------- |
| **Imagen**     | `dpage/pgadmin4:latest` |
| **Contenedor** | `supply_chain_pgadmin`  |
| **Puerto**     | `5050:80`               |
| **Email**      | `admin@supplychain.com` |
| **Contraseña** | `admin123`              |

---

##  Comandos de Gestión

### Levantar la Infraestructura
```bash
cd docker
docker-compose up -d
```

### Verificar Estado
```bash
docker-compose ps
docker-compose logs -f postgres
```

### Detener la Infraestructura
```bash
docker-compose down
```

### Reiniciar desde Cero
```bash
docker-compose down -v  # Elimina volúmenes (¡cuidado!)
docker-compose up -d
```

---

##  Esquema de la Base de Datos

### Tablas Principales

| Tabla                  | Descripción                      |
| ---------------------- | -------------------------------- |
| `products`             | Catálogo de productos            |
| `suppliers`            | Información de proveedores       |
| `warehouses`           | Datos de almacenes               |
| `inventory`            | Stock y métricas de inventario   |
| `sales`                | Histórico de ventas              |
| `logistics`            | Datos logísticos y de transporte |
| `supply_chain_metrics` | Métricas de rendimiento          |

### Vistas de Análisis

- `v_critical_stock` - Productos con stock crítico
- `v_product_performance` - Rendimiento por producto
- `v_supplier_efficiency` - Eficiencia de proveedores

---

##  Configuraciones Importantes

### postgresql.conf
```conf
listen_addresses = '*'          # Acepta conexiones externas
max_connections = 100
shared_buffers = 256MB
```

### pg_hba.conf
```conf
host    all    all    0.0.0.0/0    md5  # Permite conexiones
```

---

##  Conexión a la Base de Datos

### Desde la Terminal
```bash
# Conexión directa al contenedor
docker exec -it supply_chain_db psql -U admin -d supply_chain

# Conexión desde el host (requiere psql instalado)
psql -h localhost -p 5432 -U admin -d supply_chain
```

### Desde pgAdmin (Web)

1. Abrir: http://localhost:5050
2. Credenciales: `admin@supplychain.com` / `admin123`
3.  **IMPORTANTE**: Usar `postgres` como host (NO `localhost`)

---

##  Verificación de la Instalación

### Script de Diagnóstico
```python
# scripts/check_db.py
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "admin",
    "password": "admin123",
    "database": "supply_chain"
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    print("✅ Conexión exitosa")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")
```

### Verificar Tablas
```sql
-- Listar todas las tablas
\dt

-- Verificar estructura de una tabla
\d products

-- Contar registros
SELECT COUNT(*) FROM products;
```

---

##  Resolución de Problemas Comunes

### Error: "Connection refused"

**Causa**: PostgreSQL no acepta conexiones externas.

**Solución**:
- Verificar `listen_addresses = '*'` en `postgresql.conf`
- Usar `postgres` como host en pgAdmin
- Reiniciar contenedores: `docker-compose restart`

### Error: "Database does not exist"

**Causa**: La base de datos no se creó correctamente.

**Solución**:
```bash
# Reconstruir desde cero
docker-compose down -v
docker-compose up -d
```

### Error de Autenticación

**Causa**: Contraseña incorrecta o configuración de `pg_hba.conf`.

**Solución**:
- Verificar credenciales en `docker-compose.yml`
- Revisar `pg_hba.conf`
- Reiniciar el servicio

---

##  Recursos Relacionados

- [Documentación PostgreSQL](https://www.postgresql.org/docs/)
- [Docker PostgreSQL Image](https://hub.docker.com/_/postgres)
- [pgAdmin Documentation](https://www.pgadmin.org/docs/)

---

##  Checklist de Configuración

- [ ] Docker instalado y funcionando
- [ ] `docker-compose.yml` configurado
- [ ] `init.sql` con todas las tablas y vistas
- [ ] PostgreSQL y pgAdmin corriendo
- [ ] Conexión exitosa desde pgAdmin
- [ ] Verificación de tablas creadas
- [ ] Script de diagnóstico funcionando

---

##  Estado Actual

- **Estado**: ✅ Infraestructura configurada y funcionando
- **Fecha**: 2026-08-13
- **Siguiente Paso**: [[Fase 3 - Generación de datos]]

---

##  Etiquetas
#docker #postgresql #pgadmin #infrastructure #supply-chain #tfm