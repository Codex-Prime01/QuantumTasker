from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='list'),
    path('update_task/<str:pk>', views.updateTask, name='update'),
    path('delete/<str:pk>', views.deleteTask, name='delete'),
    path('register/', views.registerUser, name='register'),    
    path('login/', views.loginUser, name='login'),
    path('logout/', views.logoutUser, name='logout' ),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),  
    path('settings/', views.settings, name='settings'),  
    path('create/', views.create_task, name='create')

]







