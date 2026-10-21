from django.urls import path

from . import list_views, views

urlpatterns = [
    # Tasks
    path('', views.index, name='list'),
    path('create/', views.create_task, name='create'),
    path('share/', views.share_target, name='share_target'),
    path('calendar/', views.calendar_view, name='calendar_view'),
    path('api/shortcut/add/', views.shortcut_add, name='shortcut_add'),
    path('task/<int:pk>/calendar.ics', views.task_ics, name='task_ics'),
    path('calendar/<str:token>.ics', views.calendar_feed, name='calendar_feed'),
    path('update/<int:pk>/', views.updateTask, name='update'),
    path('delete/<int:pk>/', views.deleteTask, name='delete'),
    path('quick-toggle/<int:pk>/', views.quick_toggle_complete, name='quick_toggle'),
    path('subtask/<int:pk>/toggle/', views.subtask_toggle, name='subtask_toggle'),

    # Auth
    path('register/', views.registerUser, name='register'),
    path('login/', views.loginUser, name='login'),
    path('logout/', views.logoutUser, name='logout'),
    path('verification-sent/', views.verification_sent, name='verification_sent'),
    path('verify-email/<uuid:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-link-sent/', views.reset_link_sent, name='reset_link_sent'),
    path('reset-password/<uuid:token>/', views.reset_password, name='reset_password'),

    # Account
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('settings/', views.userp_settings, name='userp_settings'),
    path('api/update-theme/', views.update_theme, name='update_theme'),

    # Templates
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

    # Notes
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

    # Alarms
    path('alarms/', views.alarms_list, name='alarms'),
    path('bedtime/', views.bedtime, name='bedtime'),

    # Shared lists
    path('lists/', list_views.lists_index, name='lists'),
    path('lists/<int:pk>/', list_views.list_detail, name='list_detail'),
    path('lists/<int:pk>/state/', list_views.list_state, name='list_state'),
    path('lists/<int:pk>/items/', list_views.list_add_item, name='list_add_item'),
    path('lists/<int:pk>/clear-done/', list_views.list_clear_done, name='list_clear_done'),
    path('lists/<int:pk>/manage/', list_views.list_manage, name='list_manage'),
    path('lists/item/<int:item_id>/toggle/', list_views.list_toggle_item, name='list_toggle_item'),
    path('lists/item/<int:item_id>/delete/', list_views.list_delete_item, name='list_delete_item'),
    path('lists/join/<str:token>/', list_views.list_join, name='list_join'),
    path('api/toggle-alarm/<int:pk>/', views.toggle_alarm, name='toggle_alarm'),
    path('api/check-due-tasks/', views.check_due_tasks, name='check_due_tasks'),
    path('api/snooze-alarm/<int:pk>/', views.snooze_alarm, name='snooze_alarm'),
    path('api/dismiss-alarm/<int:pk>/', views.dismiss_alarm, name='dismiss_alarm'),

    # Push alarms (work with the app closed)
    path('api/push/subscribe/', views.push_subscribe, name='push_subscribe'),
    path('api/push/unsubscribe/', views.push_unsubscribe, name='push_unsubscribe'),
    path('api/push/test/', views.push_test, name='push_test'),
    path('api/alarm-action/', views.alarm_action, name='alarm_action'),
    path('api/cron/tick/', views.cron_tick, name='cron_tick'),
]
