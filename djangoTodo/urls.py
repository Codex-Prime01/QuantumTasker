from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Served from the site root so the service worker can control every page
    path(
        'sw.js',
        TemplateView.as_view(template_name='tasks/sw.js', content_type='application/javascript'),
        name='service_worker',
    ),
    path('', include('tasks.urls')),
    path('api/', include('tasks.api_urls')),
    path('api-auth/', include('rest_framework.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
