from datetime import datetime, timedelta
from django.utils import timezone


class TaskScheduler:

    WORK_START = 7
    WORK_END   = 23

    def __init__(self, user):
        self.user = user

    def schedule_task(self, task):
        from apps.tasks.models import Task

        now_utc   = timezone.now()
        now_local = timezone.localtime(now_utc)
        tz        = timezone.get_current_timezone()

        duration_minutes = task.estimated_duration or 60

        occupied = set()
        for start, end in (
            Task.objects
            .filter(user=self.user, scheduled_start__isnull=False)
            .exclude(pk=task.pk)
            .exclude(status='done')
            .values_list('scheduled_start', 'scheduled_end')
        ):
            s = timezone.localtime(start)
            e = timezone.localtime(end)
            h = s
            while h < e:
                occupied.add((h.date(), h.hour))
                h += timedelta(hours=1)

        start_hour = now_local.hour
        if now_local.minute > 0:
            start_hour += 1

        hours_needed = max(1, -(-duration_minutes // 60))  # округление вверх

        for day_offset in range(60):
            check_date = (now_local + timedelta(days=day_offset)).date()
            h_from = start_hour if day_offset == 0 else self.WORK_START

            for h in range(h_from, self.WORK_END + 1):
                if h < self.WORK_START:
                    continue
                if h > self.WORK_END:
                    break
                if all((check_date, h + i) not in occupied for i in range(hours_needed)):
                    scheduled_start = timezone.make_aware(
                        datetime(check_date.year, check_date.month, check_date.day, h, 0),
                        tz
                    )
                    scheduled_end = scheduled_start + timedelta(minutes=duration_minutes)
                    is_overdue_risk = bool(
                        task.deadline and scheduled_end > task.deadline
                    )
                    task.scheduled_start = scheduled_start
                    task.scheduled_end   = scheduled_end
                    task.is_overdue_risk = is_overdue_risk
                    task.save(update_fields=[
                        'scheduled_start', 'scheduled_end', 'is_overdue_risk', 'updated_at'
                    ])
                    return scheduled_start, scheduled_end, is_overdue_risk

        task.is_overdue_risk = True
        task.save(update_fields=['is_overdue_risk', 'updated_at'])
        return None, None, True

    def reschedule_all(self):
        from apps.tasks.models import Task

        tasks = list(Task.objects.filter(
            user=self.user,
            status__in=[Task.STATUS_PLANNED, Task.STATUS_IN_PROGRESS],
        ).order_by('deadline', '-priority'))

        for task in tasks:
            task.scheduled_start = None
            task.scheduled_end   = None
            task.save(update_fields=['scheduled_start', 'scheduled_end', 'updated_at'])

        for task in tasks:
            self.schedule_task(task)
