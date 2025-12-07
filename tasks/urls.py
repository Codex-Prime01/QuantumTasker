from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('', views.index, name='list'),
    path('update/<int:pk>/', views.updateTask, name='update'),  # ✅ CORRECT
    path('delete/<int:pk>/', views.deleteTask, name='delete'),  # ✅ CORRECT
    path('quick-toggle/<int:pk>/', views.quick_toggle_complete, name='quick_toggle'),
    path('register/', views.registerUser, name='register'),    
    path('login/', views.loginUser, name='login'),
    path('logout/', views.logoutUser, name='logout' ),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),  
    path('settings/', views.settings, name='settings'),  
    path('create/', views.create_task, name='create'),
    # 👇 NEW! Email verification URLs
    path('verification-sent/', views.verification_sent, name='verification_sent'),
    path('verify-email/<uuid:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),

     # 👇 NEW! Password reset URLs
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-link-sent/', views.reset_link_sent, name='reset_link_sent'),
    path('reset-password/<uuid:token>/', views.reset_password, name='reset_password'), 
    path('api/update-theme/', views.update_theme, name='update_theme'),

    path('templates/', views.templates_list, name='templates_list'),
    path('templates/<int:pk>/', views.template_detail, name='template_detail'),
    path('templates/<int:pk>/use/', views.use_template, name='use_template'),
    path('templates/create/', views.create_template, name='create_template'),
    path('templates/<int:pk>/edit/', views.edit_template, name='edit_template'),
    path('templates/<int:pk>/delete/', views.delete_template, name='delete_template'),
    path('templates/<int:template_id>/items/<int:item_id>/delete/', views.delete_template_item, name='delete_template_item'),
    path('templates/from-tasks/', views.create_template_from_tasks, name='create_template_from_tasks'),
    
    path('achievements/', views.achievements_view, name='achievements'),
      
    path('offline/', views.offline_page, name='offline'),

]