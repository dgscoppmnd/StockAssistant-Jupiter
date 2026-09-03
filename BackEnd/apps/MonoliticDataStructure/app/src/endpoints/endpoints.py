from fastapi import FastAPI, APIRouter, Depends
from security import require_api_key
from .endpointsAuth import router as auth_router
from .endpointsProms import router as proms_router
from .endpointsProducts import router as product_router
from .endpointsUsers import router as user_router
from .endpointWebs import router as web_router
from .endpointTools import router as tools_router
from .endpointagentes import router as agents_router
from .endpointsInventory import router as inventory_router
from .endpointsAgentsIntelligence import router as intelligence_agents_router
from .endpointsCommercialAgents import router as commercial_agents_router
    
router = APIRouter(dependencies=[Depends(require_api_key)])
public_router = APIRouter()
public_router.include_router(auth_router)
router.include_router(proms_router)
router.include_router(product_router)
router.include_router(user_router)
router.include_router(web_router)
router.include_router(tools_router)
router.include_router(agents_router)
router.include_router(inventory_router)
router.include_router(intelligence_agents_router)
router.include_router(commercial_agents_router)

def init_fastapi():
    description = """
    Proyecto Jupiter integra el backend operativo del proyecto local con las
    capacidades comerciales, inventario transaccional, autenticación y agentes
    analíticos de StockAssistant.
    """
    app = FastAPI(
        title="Proyecto Jupiter API",
        description=description,
        version="2.0.0",
    )
    return app


@router.get("/")
def root():
    return {"status": "ok", "project": "Proyecto Jupiter", "hint": "Ir a /docs o usar POST /analyze-system"}

