# Seleccion temporal del predictor de despachos

El agente conserva el calculo heredado como fallback y compara cuatro metodos cuando hay historial suficiente: media de 90 dias, media de 30 dias, repeticion semanal y recta por minimos cuadrados sobre 90 dias, con predicciones negativas recortadas a cero.

La comparacion usa hasta cinco ventanas temporales disjuntas del horizonte solicitado. En cada ventana el predictor solo recibe los 90 dias anteriores. Se selecciona por MAE, manteniendo un orden estable en empates. Este MAE es evidencia para seleccionar, no un intervalo de confianza ni una prueba final independiente.

Se requieren al menos 30 dias con despachos positivos y tres ventanas de validacion completas. Los candidatos solo se activan con horizontes de hasta 90 dias; otros horizontes conservan el fallback. Estas son salvaguardas operativas, no garantias estadisticas. El historial se limita a 540 dias y se excluye el dia actual en UTC.

El objetivo son despachos registrados, no demanda libre de restricciones. Un dia sin movimientos se representa como cero despachos registrados, manteniendo cobertura y disponibilidad como desconocidas. No debe interpretarse automaticamente como demanda cero. La ausencia de movimientos recientes puede afectar al ajuste y debe contrastarse con la operacion.

Los campos forecast_method, forecast_validation, forecast_history y forecast_warnings explican la seleccion. daily_average y evidence conservan el resumen descriptivo heredado; no son la prediccion diaria del modelo seleccionado. forecast_baseline_qty permite comparar el candidato con la media sobre los mismos dias completos.

## Evidencia sintetica previa a la integracion

Se compararon seis escenarios de 240 dias y una continuacion artificial adicional de 30 dias, generada fuera de la BD siguiendo las mismas recetas. La continuacion no se utilizo para seleccionar el metodo. Las recetas ideales no demuestran generalizacion comercial.

| Escenario | Elegido | MAE historico | Error absoluto adicional | Error media90 |
|---|---|---:|---:|---:|
| Constante | mean_90 | 0 | 0 | 0 |
| Creciente | linear_90 | 3.11 | 4.43 | 93.33 |
| Decreciente | linear_90 | 3.11 | 26.88 | 53.33 |
| Semanal | weekly_repeat | 0 | 0 | 3.33 |
| Sin ventas | mean_90 | 0 | 0 | 0 |
| Una venta | mean_90 | 0.20 | 0.33 | 0.33 |

La caida del error en crecimiento y descenso es especifica de estos escenarios. La recta sigue equivocandose en el descenso con suelo de una unidad diaria. El tiempo transcurrido desde la generacion del lote afecta las previsiones en GUI: los dias posteriores sin movimientos se computan como cero despachos registrados. Los valores actuales no tienen por que reproducir una evaluacion fijada al 14 de octubre.

## Comprobacion

Ejecutar test_sales_forecasting.py junto con test_sales_forecast_ai.py y test_database_schema.py. Despues, ejecutar la suite completa con PostgreSQL de pruebas, comprobar el agente real en sandbox y revisar el check Integration del Pull Request antes de integrar. Las pruebas de modelo no hacen llamadas de pago a OpenAI.
