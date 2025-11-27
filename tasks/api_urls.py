from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import TaskViewSet, CategoryViewSet

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'categories', CategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),
]