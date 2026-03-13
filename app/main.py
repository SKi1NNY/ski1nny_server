from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ingredient, product, user, recommendation
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="화장품 성분 분석 및 안전한 스킨케어 추천 서비스",
    version=settings.app_version,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    ingredient.router,
    prefix=f"{settings.api_v1_prefix}/ingredients",
    tags=["ingredients"],
)
app.include_router(
    product.router,
    prefix=f"{settings.api_v1_prefix}/products",
    tags=["products"],
)
app.include_router(
    user.router,
    prefix=f"{settings.api_v1_prefix}/users",
    tags=["users"],
)
app.include_router(
    recommendation.router,
    prefix=f"{settings.api_v1_prefix}/recommendations",
    tags=["recommendations"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
