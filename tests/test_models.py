from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from apps.tasks.models import Task, ExecutionHistory
from apps.goals.models import Goal


class TaskModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')

    def _make_task(self, **kwargs):
        defaults = dict(user=self.user, title='Test Task', category=Task.CATEGORY_WORK)
        defaults.update(kwargs)
        return Task.objects.create(**defaults)

    def test_default_status_is_new(self):
        task = self._make_task()
        self.assertEqual(task.status, Task.STATUS_NEW)

    def test_default_priority_is_medium(self):
        task = self._make_task()
        self.assertEqual(task.priority, Task.PRIORITY_MEDIUM)

    def test_default_overdue_risk_is_false(self):
        task = self._make_task()
        self.assertFalse(task.is_overdue_risk)

    def test_priority_color_high(self):
        task = self._make_task(priority=Task.PRIORITY_HIGH)
        self.assertEqual(task.priority_color, 'danger')

    def test_priority_color_medium(self):
        task = self._make_task(priority=Task.PRIORITY_MEDIUM)
        self.assertEqual(task.priority_color, 'warning')

    def test_priority_color_low(self):
        task = self._make_task(priority=Task.PRIORITY_LOW)
        self.assertEqual(task.priority_color, 'success')

    def test_status_label_new(self):
        task = self._make_task(status=Task.STATUS_NEW)
        self.assertEqual(task.status_label, 'Новая')

    def test_status_label_planned(self):
        task = self._make_task(status=Task.STATUS_PLANNED)
        self.assertEqual(task.status_label, 'Запланированная')

    def test_status_label_in_progress(self):
        task = self._make_task(status=Task.STATUS_IN_PROGRESS)
        self.assertEqual(task.status_label, 'В работе')

    def test_status_label_done(self):
        task = self._make_task(status=Task.STATUS_DONE)
        self.assertEqual(task.status_label, 'Выполненная')

    def test_str_returns_title(self):
        task = self._make_task(title='My Important Task')
        self.assertEqual(str(task), 'My Important Task')


class GoalModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='goaluser', password='pass123')
        self.goal = Goal.objects.create(user=self.user, title='Test Goal')

    def _done_task(self):
        return Task.objects.create(
            user=self.user, title='Done', status=Task.STATUS_DONE, goal=self.goal
        )

    def _new_task(self):
        return Task.objects.create(
            user=self.user, title='New', status=Task.STATUS_NEW, goal=self.goal
        )

    def test_progress_with_no_tasks_is_zero(self):
        self.assertEqual(self.goal.progress_percent, 0)

    def test_total_tasks_count(self):
        self._done_task()
        self._new_task()
        self.assertEqual(self.goal.total_tasks, 2)

    def test_completed_tasks_count(self):
        self._done_task()
        self._new_task()
        self.assertEqual(self.goal.completed_tasks, 1)

    def test_progress_all_done_equals_100(self):
        self._done_task()
        self._done_task()
        self.assertEqual(self.goal.progress_percent, 100)

    def test_progress_partial_completion(self):
        self._done_task()
        self._new_task()
        self.assertEqual(self.goal.progress_percent, 50)

    def test_progress_with_target_tasks(self):
        self.goal.target_tasks = 4
        self.goal.save()
        self._done_task()
        self._done_task()
        self.assertEqual(self.goal.progress_percent, 50)

    def test_progress_capped_at_100_with_target(self):
        self.goal.target_tasks = 2
        self.goal.save()
        self._done_task()
        self._done_task()
        self._done_task()
        self.assertEqual(self.goal.progress_percent, 100)

    def test_check_achieved_marks_goal_when_all_tasks_done(self):
        self._done_task()
        self.goal.check_achieved()
        self.goal.refresh_from_db()
        self.assertTrue(self.goal.is_achieved)
        self.assertIsNotNone(self.goal.achieved_at)

    def test_check_achieved_does_not_trigger_when_incomplete(self):
        self._done_task()
        self._new_task()
        self.goal.check_achieved()
        self.goal.refresh_from_db()
        self.assertFalse(self.goal.is_achieved)

    def test_check_achieved_with_target_tasks(self):
        self.goal.target_tasks = 2
        self.goal.save()
        self._done_task()
        self._done_task()
        self.goal.check_achieved()
        self.goal.refresh_from_db()
        self.assertTrue(self.goal.is_achieved)

    def test_check_achieved_not_triggered_below_target(self):
        self.goal.target_tasks = 3
        self.goal.save()
        self._done_task()
        self.goal.check_achieved()
        self.goal.refresh_from_db()
        self.assertFalse(self.goal.is_achieved)

    def test_str_returns_title(self):
        self.assertEqual(str(self.goal), 'Test Goal')


class ExecutionHistoryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='histuser', password='pass')
        self.task = Task.objects.create(
            user=self.user, title='Hist Task', status=Task.STATUS_DONE
        )

    def test_str_with_task(self):
        h = ExecutionHistory.objects.create(
            user=self.user,
            task=self.task,
            category=Task.CATEGORY_WORK,
            completed_at=timezone.now(),
        )
        self.assertIn('Hist Task', str(h))

    def test_str_without_task(self):
        h = ExecutionHistory.objects.create(
            user=self.user,
            task=None,
            category=Task.CATEGORY_WORK,
            completed_at=timezone.now(),
        )
        self.assertIn('deleted', str(h))

    def test_correction_factor_stored(self):
        h = ExecutionHistory.objects.create(
            user=self.user,
            task=self.task,
            category=Task.CATEGORY_WORK,
            estimated_duration=60,
            actual_duration=90,
            correction_factor=1.5,
            completed_at=timezone.now(),
        )
        self.assertAlmostEqual(h.correction_factor, 1.5)
