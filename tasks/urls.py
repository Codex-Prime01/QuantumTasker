from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

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
    path('settings/', views.userp_settings, name='userp_settings'),  
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
    # Notes URLs
path('notes/', views.notes_list, name='notes_list'),
path('notes/create/', views.create_note, name='create_note'),
path('notes/<int:pk>/update/', views.update_note, name='update_note'),
path('notes/<int:pk>/delete/', views.delete_note, name='delete_note'),
path('notes/<int:pk>/toggle-pin/', views.toggle_pin_note, name='toggle_pin_note'),

    path('notes/<int:pk>/archive/', views.archive_note, name='archive_note'),
    path('notes/<int:pk>/unarchive/', views.unarchive_note, name='unarchive_note'),
    path('notes/archived/', views.archived_notes, name='archived_notes'),
    
    path('notes/<int:pk>/export/', views.export_note_as_text, name='export_note'),
    path('notes/export-all/', views.export_all_notes, name='export_all_notes'),
    path('notes/<int:pk>/convert-to-task/', views.convert_note_to_task, name='convert_note_to_task'),
    
    
    
]

if settings.DEBUG:
    # Development: Django serves media files
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Production: Still need to serve media files
    # WhiteNoise handles static files, but NOT media files
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)