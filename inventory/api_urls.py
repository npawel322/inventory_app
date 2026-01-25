from rest_framework.routers import DefaultRouter
from .api_views import (
    AssetViewSet, AssetCategoryViewSet, PersonViewSet,
    OfficeViewSet, RoomViewSet, DeskViewSet, LoanViewSet
)

router = DefaultRouter()
router.register(r"categories", AssetCategoryViewSet, basename="category")
router.register(r"assets", AssetViewSet, basename="asset")
router.register(r"persons", PersonViewSet, basename="person")
router.register(r"offices", OfficeViewSet, basename="office")
router.register(r"rooms", RoomViewSet, basename="room")
router.register(r"desks", DeskViewSet, basename="desk")
router.register(r"loans", LoanViewSet, basename="loan")

urlpatterns = router.urls
