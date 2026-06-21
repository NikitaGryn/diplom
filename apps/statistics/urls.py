from django.urls import path
from . import views

urlpatterns = [
    path('', views.StatisticsView.as_view(), name='statistics'),
    path('analytics/', views.AnalyticsView.as_view(), name='analytics'),
]
