from django.urls import path
from . import views

urlpatterns = [
    path('', views.BoardView.as_view(), name='board'),
    path('api/board/columns/', views.BoardColumnsView.as_view(), name='board-columns'),
    path('api/tasks/create/', views.TaskCreateView.as_view(), name='task-create'),
    path('api/tasks/<int:pk>/update/', views.TaskUpdateView.as_view(), name='task-update'),
    path('api/tasks/<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task-delete'),
    path('api/tasks/<int:pk>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('api/tasks/status/', views.TaskStatusView.as_view(), name='task-status'),
    path('api/tasks/complete/', views.TaskCompleteView.as_view(), name='task-complete'),
    path('api/tasks/assign-goal/', views.TaskAssignGoalView.as_view(), name='task-assign-goal'),
    path('api/tasks/predict-time/', views.TaskPredictTimeView.as_view(), name='task-predict-time'),
    path('api/tasks/recommend/', views.TaskRecommendView.as_view(), name='task-recommend'),
    path('api/tasks/<int:pk>/reschedule/', views.TaskRescheduleView.as_view(), name='task-reschedule'),
    path('tasks/export/', views.TaskExportExcelView.as_view(), name='task-export'),
]
