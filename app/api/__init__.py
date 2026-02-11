from fastapi import APIRouter
from .users import router as users_router
from .question import router as question_router
from .chat import router as chat_router
from .organization import router as organization_router
from .answer import router as answer_router
from .points import router as points_router
from .payment import router as payment_router
from .feature import router as feature_router
from .news_interpretation import router as news_interpretation_router
from .self_selected_stock import router as self_selected_stock_router
from .stock import router as stock_router
from .wechat import router as wechat_router
from .hot_spot import router as hot_spot_router
from .index import router as index_router
from .concept import router as concept_router
from .right import router as right_router
from .research_report import router as research_report_router
from .concept_group import router as concept_group_router
from .wind_direction_ball import router as wind_direction_ball_router
from .badge import router as badge_router
from .sentiment import router as sentiment_router
from .chart import router as chart_router
from .internal import router as internal_router
from .tenant import router as tenant_router

router = APIRouter()

# 直接包含用户相关的路由，去掉v1层级
router.include_router(users_router, prefix="/user")
router.include_router(question_router, prefix="/question")
router.include_router(chat_router, prefix="/chat")
router.include_router(organization_router, prefix="/organization")
router.include_router(answer_router, prefix="/answer")
router.include_router(points_router, prefix="/points")
router.include_router(payment_router, prefix="/payment")
router.include_router(feature_router, prefix="/feature")
router.include_router(news_interpretation_router, prefix="/news_interpretation")
router.include_router(self_selected_stock_router, prefix="/self_selected_stock")
router.include_router(stock_router, prefix="/stock")
router.include_router(wechat_router, prefix="/wechat")
router.include_router(hot_spot_router, prefix="/hot_spot")
router.include_router(index_router, prefix="/index")
router.include_router(concept_router, prefix="/concept")
router.include_router(right_router, prefix="/right")
router.include_router(research_report_router, prefix="/research_report")
router.include_router(concept_group_router, prefix="/concept_group")
router.include_router(wind_direction_ball_router, prefix="/wind/direction/ball")
router.include_router(badge_router, prefix="/badge")
router.include_router(sentiment_router, prefix="/sentiment")
router.include_router(chart_router, prefix="/chart")
router.include_router(internal_router, prefix="/internal")
router.include_router(tenant_router, prefix="/tenant")
