import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from datetime import timedelta

from apps.tasks.models import Task, ExecutionHistory


class StatisticsView(LoginRequiredMixin, View):
    def get(self, request):
        period = request.GET.get('period', 'week')
        now = timezone.now()

        if period == 'week':
            since = now - timedelta(days=7)
            period_label = 'за неделю'
        elif period == 'month':
            since = now - timedelta(days=30)
            period_label = 'за месяц'
        else:
            since = None
            period_label = 'за всё время'

        tasks_qs = Task.objects.filter(user=request.user)
        if since:
            tasks_qs_period = tasks_qs.filter(created_at__gte=since)
        else:
            tasks_qs_period = tasks_qs

        completed_tasks = tasks_qs_period.filter(status=Task.STATUS_DONE)

        # Count from ExecutionHistory for persistence (survives task deletion)
        history_qs = ExecutionHistory.objects.filter(user=request.user)
        if since:
            history_qs = history_qs.filter(completed_at__gte=since)
        completed_count = history_qs.count()

        overdue_count = tasks_qs_period.filter(
            status__in=[Task.STATUS_NEW, Task.STATUS_PLANNED, Task.STATUS_IN_PROGRESS],
            deadline__lt=now,
        ).count()

        active_count = tasks_qs.filter(status=Task.STATUS_IN_PROGRESS).count()

        total_minutes = sum(
            t.actual_duration for t in completed_tasks if t.actual_duration
        )
        total_hours = round(total_minutes / 60, 1)

        # Category breakdown
        category_stats = []
        for cat_key, cat_label in Task.CATEGORY_CHOICES:
            cat_tasks = tasks_qs_period.filter(category=cat_key)
            cat_done = cat_tasks.filter(status=Task.STATUS_DONE).count()
            cat_total = cat_tasks.count()
            cat_percent = int((cat_done / cat_total) * 100) if cat_total > 0 else 0
            category_stats.append({
                'key': cat_key,
                'label': cat_label,
                'total': cat_total,
                'done': cat_done,
                'percent': cat_percent,
            })

        # Priority breakdown
        priority_stats = []
        for pri_key, pri_label in Task.PRIORITY_CHOICES:
            pri_tasks = tasks_qs_period.filter(priority=pri_key)
            pri_done = pri_tasks.filter(status=Task.STATUS_DONE).count()
            pri_total = pri_tasks.count()
            pri_percent = int((pri_done / pri_total) * 100) if pri_total > 0 else 0
            priority_stats.append({
                'key': pri_key,
                'label': pri_label,
                'total': pri_total,
                'done': pri_done,
                'percent': pri_percent,
            })

        # Accuracy stats from history
        history = ExecutionHistory.objects.filter(user=request.user)
        if since:
            history = history.filter(completed_at__gte=since)
        avg_factor = None
        if history.exists():
            factors = [h.correction_factor for h in history if h.correction_factor is not None]
            if factors:
                avg_factor = round(sum(factors) / len(factors), 2)

        # Recent completed tasks
        recent_tasks = completed_tasks.order_by('-completed_at')[:10]

        # Daily completions for line chart
        daily_qs = (
            history_qs
            .annotate(day=TruncDate('completed_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        daily_labels = [str(d['day']) for d in daily_qs]
        daily_counts = [d['count'] for d in daily_qs]

        # Chart data as JSON
        chart_data = json.dumps({
            'category': {
                'labels': [c['label'] for c in category_stats if c['total'] > 0],
                'total':  [c['total'] for c in category_stats if c['total'] > 0],
                'done':   [c['done']  for c in category_stats if c['total'] > 0],
            },
            'priority': {
                'labels': [p['label'] for p in priority_stats if p['total'] > 0],
                'total':  [p['total'] for p in priority_stats if p['total'] > 0],
                'done':   [p['done']  for p in priority_stats if p['total'] > 0],
                'keys':   [p['key']   for p in priority_stats if p['total'] > 0],
            },
            'daily': {
                'labels': daily_labels,
                'counts': daily_counts,
            },
        })

        stats = {
            'completed_count': completed_count,
            'overdue_count': overdue_count,
            'total_hours': total_hours,
            'active_count': active_count,
            'avg_correction_factor': avg_factor,
            'category_stats': category_stats,
            'priority_stats': priority_stats,
            'period': period,
            'period_label': period_label,
            'recent_tasks': list(recent_tasks),
            'chart_data_json': chart_data,
        }

        if request.headers.get('Accept') == 'application/json':
            stats_json = dict(stats)
            stats_json.pop('recent_tasks')
            stats_json.pop('chart_data_json')
            return JsonResponse({'success': True, **stats_json})

        return render(request, 'statistics/index.html', stats)


class AnalyticsView(LoginRequiredMixin, View):
    def get(self, request):
        period = request.GET.get('period', 'week')
        now = timezone.now()

        if period == 'week':
            since = now - timedelta(days=7)
            period_label = 'за неделю'
        elif period == 'month':
            since = now - timedelta(days=30)
            period_label = 'за месяц'
        else:
            since = None
            period_label = 'за всё время'

        tasks_qs = Task.objects.filter(user=request.user)
        tasks_qs_period = tasks_qs.filter(created_at__gte=since) if since else tasks_qs
        period_tasks_count = tasks_qs_period.count()

        category_stats = []
        for cat_key, cat_label in Task.CATEGORY_CHOICES:
            cat_tasks = tasks_qs_period.filter(category=cat_key)
            cat_done = cat_tasks.filter(status=Task.STATUS_DONE).count()
            cat_total = cat_tasks.count()
            cat_percent = int((cat_done / cat_total) * 100) if cat_total > 0 else 0
            category_stats.append({
                'key': cat_key, 'label': cat_label,
                'total': cat_total, 'done': cat_done, 'percent': cat_percent,
            })

        priority_stats = []
        for pri_key, pri_label in Task.PRIORITY_CHOICES:
            pri_tasks = tasks_qs_period.filter(priority=pri_key)
            pri_done = pri_tasks.filter(status=Task.STATUS_DONE).count()
            pri_total = pri_tasks.count()
            pri_percent = int((pri_done / pri_total) * 100) if pri_total > 0 else 0
            priority_stats.append({
                'key': pri_key, 'label': pri_label,
                'total': pri_total, 'done': pri_done, 'percent': pri_percent,
            })

        chart_data = json.dumps({
            'category': {
                'labels': [c['label'] for c in category_stats if c['total'] > 0],
                'total':  [c['total'] for c in category_stats if c['total'] > 0],
                'done':   [c['done']  for c in category_stats if c['total'] > 0],
            },
            'priority': {
                'labels': [p['label'] for p in priority_stats if p['total'] > 0],
                'total':  [p['total'] for p in priority_stats if p['total'] > 0],
                'done':   [p['done']  for p in priority_stats if p['total'] > 0],
                'keys':   [p['key']   for p in priority_stats if p['total'] > 0],
            },
        })

        return render(request, 'statistics/analytics.html', {
            'period': period,
            'period_label': period_label,
            'has_period_tasks': period_tasks_count > 0,
            'period_tasks_count': period_tasks_count,
            'category_stats': category_stats,
            'priority_stats': priority_stats,
            'chart_data_json': chart_data,
        })
