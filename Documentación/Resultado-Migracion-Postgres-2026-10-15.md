# Resultado de sincronización de PostgreSQL

Cambios aplicados el 15 de octubre de 2026 a las 19:48 (Europe/Madrid), en la base existente `supply_chain` del contenedor `proyecto_jupiter_db`.

Se añadió a `docker/init-scripts/init.sql` el bloque `EXISTING TABLE INTEGRITY MIGRATION` y se aplicó únicamente ese bloque, sin repetir semillas ni otras migraciones del archivo.

| Cambio | Aplicado |
| --- | ---: |
| CHECK | 37 |
| UNIQUE | 2 |
| NOT NULL | 7 |
| DEFAULT | 33 |

La operación se realizó en una transacción, con el bloqueo asesor del inicializador, límites de espera y bloqueo de las ocho tablas afectadas. Se repitieron las 46 comprobaciones de compatibilidad con cero incidencias. El número de filas de todas las tablas afectadas permaneció idéntico antes y después de ejecutar el bloque.

Una segunda aplicación comprobó que no cambian las entradas del catálogo: conserva los OID de restricciones y defaults. La migración es idempotente para el esquema validado y utiliza los nombres nativos de las restricciones declaradas para instalaciones nuevas. Si encuentra datos incompatibles o un tipo de restricción inesperado, aborta la transacción.

No se crearon ni eliminaron bases de datos, tablas o filas. Los dos UNIQUE añadieron sus índices de respaldo. Los DEFAULT no rellenan ni modifican valores de filas existentes.

## Verificación posterior

- 66 tablas y 619 columnas: coinciden.
- 230 restricciones: coinciden con las declaraciones del archivo.
- 41 índices explícitos y 98 índices asociados a PK/UNIQUE: 139 en total.
- 4 vistas, 5 cuerpos de funciones y 8 triggers: coinciden según la normalización de la auditoría.
- Sin diferencias pendientes de tipos, nulabilidad, identidades, columnas generadas o defaults dentro del alcance auditado.
- Nueve pruebas de regresión del inicializador superadas con conexiones simuladas.

Se mantiene el alcance de la auditoría previa: no es una comparación de permisos, propietarios, parámetros físicos de secuencias ni contenido de negocio.

## Evidencias

- [Resultado de aplicación e idempotencia](Postgres-Integrity-Migration-2026-10-15.json)
- [Catálogo posterior](Postgres-Schema-Audit-After-2026-10-15.json)
- [Comparación posterior: diferencias vacías](Postgres-Schema-Differences-After-2026-10-15.json)
- [Auditoría previa conservada](Validacion-Postgres-2026-10-15.md)
