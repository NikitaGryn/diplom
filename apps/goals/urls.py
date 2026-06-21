from django.urls import path
from . import views

urlpatterns = [
    path('', views.GoalListView.as_view(), name='goal-list'),
    path('create/', views.GoalCreateView.as_view(), name='goal-create'),
    path('<int:pk>/delete/', views.GoalDeleteView.as_view(), name='goal-delete'),
]
