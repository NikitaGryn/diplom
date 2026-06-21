from django.db import models
from django.contrib.auth.models import User


class Task(models.Model):
    CATEGORY_STUDY = 'study'
    CATEGORY_WORK = 'work'
    CATEGORY_HOUSEHOLD = 'household'
    CATEGORY_HEALTH = 'health'
    CATEGORY_PERSONAL = 'personal'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_STUDY, 'Учёба'),
        (CATEGORY_WORK, 'Работа'),
        (CATEGORY_HOUSEHOLD, 'Быт'),
        (CATEGORY_HEALTH, 'Здоровье'),
        (CATEGORY_PERSONAL, 'Личное'),
        (CATEGORY_OTHER, 'Другое'),
    ]

    PRIORITY_HIGH = 'high'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_LOW = 'low'
    PRIORITY_CHOICES = [
        (PRIORITY_HIGH, 'Высокий'),
        (PRIORITY_MEDIUM, 'Средний'),
        (PRIORITY_LOW, 'Низкий'),
    ]

    STATUS_NEW = 'new'
    STATUS_PLANNED = 'planned'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Новая'),
        (STATUS_PLANNED, 'Запланированная'),
        (STATUS_IN_PROGRESS, 'В работе'),
        (STATUS_DONE, 'Выполненная'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    deadline = models.DateTimeField(null=True, blank=True)
    estimated_duration = models.PositiveIntegerField(null=True, blank=True, help_text='В минутах')
    actual_duration = models.PositiveIntegerField(null=True, blank=True, help_text='В минутах')
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    goal = models.ForeignKey('goals.Goal', null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    is_overdue_risk = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def priority_color(self):
        colors = {
            self.PRIORITY_HIGH: 'danger',
            self.PRIORITY_MEDIUM: 'warning',
            self.PRIORITY_LOW: 'success',
        }
        return colors.get(self.priority, 'secondary')

    @property
    def status_label(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


class ExecutionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='history')
    category = models.CharField(max_length=20)
    priority = models.CharField(max_length=10, blank=True, default='medium')
    estimated_duration = models.PositiveIntegerField(null=True, blank=True)
    actual_duration = models.PositiveIntegerField(null=True, blank=True)
    correction_factor = models.FloatField(null=True, blank=True)
    completed_at = models.DateTimeField()

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f'History: {self.task.title if self.task else "deleted"}'
