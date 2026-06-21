import json
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.tasks.models import Task, ExecutionHistory
from apps.goals.models import Goal


class TaskAuthTest(TestCase):
    """Проверяет, что анонимные запросы перенаправляются на страницу входа."""

    def test_board_redirects_anonymous_to_login(self):
        response = self.client.get(reverse('board'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_task_create_redirects_anonymous(self):
        response = self.client.post(
            reverse('task-create'), data='{}', content_type='application/json'
        )
        self.assertIn(response.status_code, [302, 403])


class TaskCreateViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='creator', password='pass')
        self.client.force_login(self.user)

    @patch('apps.tasks.views.TaskScheduler')
    def test_create_valid_task_returns_success(self, MockScheduler):
        MockScheduler.return_value.schedule_task.return_value = None
        data = {'title': 'New Task', 'category': 'work', 'priority': 'medium', 'status': 'new'}
        response = self.client.post(
            reverse('task-create'), data=json.dumps(data), content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertIn('task_id', body)

    @patch('apps.tasks.views.TaskScheduler')
    def test_create_task_saved_to_database(self, MockScheduler):
        MockScheduler.return_value.schedule_task.return_value = None
        data = {'title': 'DB Task', 'category': 'study', 'priority': 'high', 'status': 'new'}
        self.client.post(
            reverse('task-create'), data=json.dumps(data), content_type='application/json'
        )
        self.assertTrue(Task.objects.filter(title='DB Task', user=self.user).exists())

    def test_create_task_with_empty_title_returns_errors(self):
        data = {'title': '', 'category': 'work'}
        response = self.client.post(
            reverse('task-create'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        self.assertFalse(body['success'])
        self.assertIn('errors', body)

    @patch('apps.tasks.views.TaskScheduler')
    def test_create_done_task_creates_execution_history(self, MockScheduler):
        data = {
            'title': 'Done Task', 'category': 'work', 'priority': 'high',
            'status': 'done', 'estimated_duration': 60, 'actual_duration': 75,
        }
        self.client.post(
            reverse('task-create'), data=json.dumps(data), content_type='application/json'
        )
        task = Task.objects.get(title='Done Task', user=self.user)
        self.assertTrue(ExecutionHistory.objects.filter(task=task).exists())


class TaskDeleteViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='deleter', password='pass')
        self.client.force_login(self.user)

    def test_delete_own_task_succeeds(self):
        task = Task.objects.create(user=self.user, title='To Delete')
        response = self.client.post(reverse('task-delete', args=[task.pk]))
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_cannot_delete_other_users_task(self):
        other = User.objects.create_user(username='other', password='pass')
        other_task = Task.objects.create(user=other, title='Other Task')
        response = self.client.post(reverse('task-delete', args=[other_task.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=other_task.pk).exists())


class TaskStatusViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='statuser', password='pass')
        self.client.force_login(self.user)
        self.task = Task.objects.create(user=self.user, title='Status Task')

    @patch('apps.tasks.views.TaskScheduler')
    def test_change_status_to_planned(self, MockScheduler):
        MockScheduler.return_value.schedule_task.return_value = None
        data = {'task_id': self.task.pk, 'status': 'planned'}
        response = self.client.post(
            reverse('task-status'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_PLANNED)

    @patch('apps.tasks.views.TaskScheduler')
    def test_change_status_to_in_progress(self, MockScheduler):
        MockScheduler.return_value.schedule_task.return_value = None
        data = {'task_id': self.task.pk, 'status': 'in_progress'}
        self.client.post(
            reverse('task-status'), data=json.dumps(data), content_type='application/json'
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_IN_PROGRESS)

    def test_invalid_status_returns_error(self):
        data = {'task_id': self.task.pk, 'status': 'nonexistent'}
        response = self.client.post(
            reverse('task-status'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        self.assertFalse(body['success'])

    def test_missing_task_id_returns_error(self):
        data = {'status': 'planned'}
        response = self.client.post(
            reverse('task-status'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        self.assertFalse(body['success'])


class TaskCompleteViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='completer', password='pass')
        self.client.force_login(self.user)

    def _make_task(self, **kwargs):
        defaults = dict(user=self.user, title='Complete Me', estimated_duration=60)
        defaults.update(kwargs)
        return Task.objects.create(**defaults)

    def test_complete_task_sets_done_status(self):
        task = self._make_task()
        data = {'task_id': task.pk, 'actual_duration': 90}
        response = self.client.post(
            reverse('task-complete'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_DONE)

    def test_complete_task_stores_actual_duration(self):
        task = self._make_task()
        data = {'task_id': task.pk, 'actual_duration': 45}
        self.client.post(
            reverse('task-complete'), data=json.dumps(data), content_type='application/json'
        )
        task.refresh_from_db()
        self.assertEqual(task.actual_duration, 45)

    def test_complete_task_creates_execution_history(self):
        task = self._make_task()
        data = {'task_id': task.pk, 'actual_duration': 90}
        self.client.post(
            reverse('task-complete'), data=json.dumps(data), content_type='application/json'
        )
        self.assertTrue(ExecutionHistory.objects.filter(task=task).exists())

    def test_complete_task_computes_correction_factor(self):
        task = self._make_task(estimated_duration=60)
        data = {'task_id': task.pk, 'actual_duration': 120}
        self.client.post(
            reverse('task-complete'), data=json.dumps(data), content_type='application/json'
        )
        hist = ExecutionHistory.objects.get(task=task)
        self.assertAlmostEqual(hist.correction_factor, 2.0)

    def test_complete_last_task_achieves_goal(self):
        goal = Goal.objects.create(user=self.user, title='My Goal', target_tasks=1)
        task = self._make_task(goal=goal)
        data = {'task_id': task.pk, 'actual_duration': 60}
        self.client.post(
            reverse('task-complete'), data=json.dumps(data), content_type='application/json'
        )
        goal.refresh_from_db()
        self.assertTrue(goal.is_achieved)

    def test_complete_clears_overdue_risk_flag(self):
        task = self._make_task(is_overdue_risk=True)
        data = {'task_id': task.pk}
        self.client.post(
            reverse('task-complete'), data=json.dumps(data), content_type='application/json'
        )
        task.refresh_from_db()
        self.assertFalse(task.is_overdue_risk)


class TaskRecommendViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='recommender', password='pass')
        self.client.force_login(self.user)

    def test_no_tasks_returns_null_id(self):
        response = self.client.get(reverse('task-recommend'))
        body = json.loads(response.content)
        self.assertIsNone(body['task_id'])

    def test_overdue_high_priority_recommended_first(self):
        past = timezone.now() - timezone.timedelta(hours=2)
        overdue = Task.objects.create(
            user=self.user, title='Overdue High', priority=Task.PRIORITY_HIGH,
            status=Task.STATUS_NEW, deadline=past,
        )
        Task.objects.create(
            user=self.user, title='Normal Low', priority=Task.PRIORITY_LOW,
            status=Task.STATUS_NEW,
        )
        response = self.client.get(reverse('task-recommend'))
        body = json.loads(response.content)
        self.assertEqual(body['task_id'], overdue.pk)

    def test_in_progress_task_recommended_over_new(self):
        Task.objects.create(user=self.user, title='In Progress', status=Task.STATUS_IN_PROGRESS)
        Task.objects.create(user=self.user, title='New task', status=Task.STATUS_NEW)
        response = self.client.get(reverse('task-recommend'))
        body = json.loads(response.content)
        self.assertEqual(body['title'], 'In Progress')

    def test_completed_tasks_not_recommended(self):
        Task.objects.create(user=self.user, title='Done', status=Task.STATUS_DONE)
        response = self.client.get(reverse('task-recommend'))
        body = json.loads(response.content)
        self.assertIsNone(body['task_id'])

    def test_other_users_tasks_not_recommended(self):
        other = User.objects.create_user(username='other_rec', password='pass')
        Task.objects.create(
            user=other, title='Other task', status=Task.STATUS_IN_PROGRESS,
            priority=Task.PRIORITY_HIGH,
        )
        response = self.client.get(reverse('task-recommend'))
        body = json.loads(response.content)
        self.assertIsNone(body['task_id'])


class TaskDetailViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='detailer', password='pass')
        self.client.force_login(self.user)
        self.task = Task.objects.create(
            user=self.user, title='Detail Task',
            category=Task.CATEGORY_STUDY, priority=Task.PRIORITY_LOW,
        )

    def test_detail_returns_correct_fields(self):
        response = self.client.get(reverse('task-detail', args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body['title'], 'Detail Task')
        self.assertEqual(body['priority_color'], 'success')
        self.assertEqual(body['status_label'], 'Новая')

    def test_cannot_access_other_users_task(self):
        other = User.objects.create_user(username='other_det', password='pass')
        other_task = Task.objects.create(user=other, title='Private')
        response = self.client.get(reverse('task-detail', args=[other_task.pk]))
        self.assertEqual(response.status_code, 404)
