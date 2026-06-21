from django.db import models
from django.contrib.auth.models import User


class Goal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_achieved = models.BooleanField(default=False)
    achieved_at = models.DateTimeField(null=True, blank=True)
    target_tasks = models.PositiveIntegerField(null=True, blank=True, help_text='Целевое количество задач')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def total_tasks(self):
        return self.tasks.count()

    @property
    def completed_tasks(self):
        return self.tasks.filter(status='done').count()

    @property
    def progress_percent(self):
        if self.target_tasks:
            if self.target_tasks == 0:
                return 0
            return min(int((self.completed_tasks / self.target_tasks) * 100), 100)
        total = self.total_tasks
        if total == 0:
            return 0
        return int((self.completed_tasks / total) * 100)

    def check_achieved(self):
        if self.target_tasks:
            achieved = self.completed_tasks >= self.target_tasks
        else:
            achieved = self.total_tasks > 0 and self.completed_tasks == self.total_tasks

        if achieved:
            from django.utils import timezone
            self.is_achieved = True
            self.achieved_at = timezone.now()
            self.save()
