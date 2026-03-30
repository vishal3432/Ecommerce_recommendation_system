from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from ecommerce.views import (
    CategoryViewSet, ProductViewSet, ReviewViewSet,
    RecommendationTaskViewSet, UserProfileViewSet, SearchViewSet
)

# Create router for ViewSets
router = routers.DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'recommendations/tasks', RecommendationTaskViewSet, basename='recommendation-task')
router.register(r'users/profile', UserProfileViewSet, basename='user-profile')
router.register(r'search', SearchViewSet, basename='search')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API
    path('api/', include(router.urls)),
    
    # Authentication
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Health check
    path('api/health/', lambda r: JsonResponse({'status': 'healthy'})),
]
