from django.utils import timezone


class AITaskScheduler:

    # Базовые веса приоритетов
    PRIORITY_WEIGHTS = {
        'high':   3.0,
        'medium': 1.5,
        'low':    0.5,
    }

    def __init__(self, user):
        self.user = user
        self._predictor = None

    @property
    def predictor(self):
        if self._predictor is None:
            from apps.ml.predictor import DurationPredictor
            self._predictor = DurationPredictor(self.user)
        return self._predictor

    def predict_duration(self, task):
        """
        Вернуть предсказанную длительность (мин).
        Если истории < 10 записей — вернуть исходную оценку.
        """
        estimated = task.estimated_duration or 60
        predicted, _factor, has_data = self.predictor.predict(
            task.category, estimated, priority=task.priority
        )
        return predicted if has_data else estimated

    def score_task(self, task, predicted_duration=None):
        # score = priority_weight + min(15, predicted_hours/hours_remaining * 10)
        now = timezone.now()
        duration_min = predicted_duration or self.predict_duration(task)

        p = self.PRIORITY_WEIGHTS.get(task.priority, 1.0)
        d = 0.0
        if task.deadline:
            hours_left = max(0.25, (task.deadline - now).total_seconds() / 3600)
            task_hours = duration_min / 60
            d = min(15.0, (task_hours / hours_left) * 10)

        return round(p + d, 4)

    def schedule_all(self):
        """Возвращает список [(task, score, predicted_min), ...]."""
        from apps.tasks.models import Task
        from apps.schedule.scheduler import TaskScheduler

        tasks = list(Task.objects.filter(
            user=self.user,
            status__in=[Task.STATUS_NEW, Task.STATUS_PLANNED, Task.STATUS_IN_PROGRESS],
            estimated_duration__isnull=False,
        ))

        if not tasks:
            return []

        scored = []
        for task in tasks:
            predicted = self.predict_duration(task)
            score = self.score_task(task, predicted_duration=predicted)
            scored.append((task, score, predicted))

        scored.sort(key=lambda x: x[1], reverse=True)

        for task, _, _ in scored:
            task.scheduled_start = None
            task.scheduled_end = None
            task.save(update_fields=['scheduled_start', 'scheduled_end', 'updated_at'])

        # estimated_duration подменяется предсказанным только в памяти —
        # TaskScheduler.schedule_task не записывает это поле в БД.
        base = TaskScheduler(self.user)
        for task, score, predicted in scored:
            task.estimated_duration = predicted
            base.schedule_task(task)

        return scored

    def schedule_single(self, task):
        """
        Запланировать одну задачу с учётом предсказанной длительности.
        После планирования задачи пересчитать порядок всех остальных.
        """
        return self.schedule_all()
