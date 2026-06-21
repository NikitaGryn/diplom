from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.tasks.urls')),
    path('api/goals/', include('apps.goals.urls')),
    path('schedule/', include('apps.schedule.urls')),
    path('statistics/', include('apps.statistics.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('', include('apps.chat.urls')),
]
