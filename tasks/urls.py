from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='list'),
    path('update/', views.updateTask, name='update'),
    path('delete/', views.deleteTask, name='delete'),
    path('register/', views.registerUser, name='register'),    
    path('login/', views.loginUser, name='login'),
    path('logout/', views.logoutUser, name='logout' )
]





