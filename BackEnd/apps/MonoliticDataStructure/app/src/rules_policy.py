"""Closed objective catalog: free text cannot extend a rule's capabilities."""

RULE_OBJECTIVES = {
    'stock_reorder_proposals': (
        'Reducir roturas manteniendo cobertura y capital',
        'Priorizar reposición según disponibilidad, pendientes y despachos observados',
    ),
    'stagnant_stock': (
        'Revisar exceso de cobertura y stock sin despachos recientes',
        'Comparar alternativas calculadas para el stock estancado',
    ),
    'daily_inventory_report': ('Observar movimientos de inventario confirmados en las últimas 24 horas',),
    'risk_alerts': ('Observar riesgos operativos con los datos confirmados disponibles',),
}


def validate_rule_objective(kind: str, objective: str) -> None:
    if objective not in RULE_OBJECTIVES.get(kind, ()):
        raise ValueError('Objetivo fuera del alcance de la regla. Selecciona un objetivo admitido para su tipo en el editor.')
