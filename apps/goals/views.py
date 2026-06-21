import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from .models import Goal
from apps.tasks.models import Task


class GoalListView(LoginRequiredMixin, View):
    def get(self, request):
        goals = Goal.objects.filter(user=request.user).prefetch_related('tasks')
        data = []
        for goal in goals:
            data.append({
                'id': goal.id,
                'title': goal.title,
                'description': goal.description,
                'is_achieved': goal.is_achieved,
                'achieved_at': goal.achieved_at.isoformat() if goal.achieved_at else None,
                'total_tasks': goal.total_tasks,
                'completed_tasks': goal.completed_tasks,
                'progress_percent': goal.progress_percent,
                'created_at': goal.created_at.isoformat(),
                'target_tasks': goal.target_tasks,
            })
        return JsonResponse({'success': True, 'goals': data})


class GoalCreateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, Exception):
            data = request.POST.dict()

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        target_tasks = data.get('target_tasks')
        existing_task_ids = data.get('existing_task_ids', [])
        new_task_titles = data.get('new_task_titles', [])

        if not title:
            return JsonResponse({'success': False, 'error': 'Название цели обязательно'})

        goal = Goal.objects.create(
            user=request.user,
            title=title,
            description=description,
            target_tasks=int(target_tasks) if target_tasks else None,
        )

        if existing_task_ids:
            Task.objects.filter(
                pk__in=existing_task_ids,
                user=request.user,
            ).update(goal=goal)

        for task_title in new_task_titles:
            task_title = task_title.strip()
            if task_title:
                Task.objects.create(
                    user=request.user,
                    title=task_title,
                    goal=goal,
                )

        return JsonResponse({
            'success': True,
            'goal': {
                'id': goal.id,
                'title': goal.title,
                'description': goal.description,
                'is_achieved': goal.is_achieved,
                'total_tasks': goal.total_tasks,
                'completed_tasks': goal.completed_tasks,
                'progress_percent': goal.progress_percent,
                'target_tasks': goal.target_tasks,
            }
        })


class GoalDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        goal.delete()
        return JsonResponse({'success': True})
