from django.urls import path
from . import views

urlpatterns = [
    path('', views.ScheduleView.as_view(), name='schedule'),
    path('pdf/', views.SchedulePDFView.as_view(), name='schedule_pdf'),
]
