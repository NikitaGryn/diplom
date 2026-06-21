import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from apps.tasks.models import Task
from apps.goals.models import Goal


class GoalListViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='goallist', password='pass')
        self.other = User.objects.create_user(username='other_list', password='pass')
        self.client.force_login(self.user)

    def test_returns_only_own_goals(self):
        Goal.objects.create(user=self.user, title='My Goal')
        Goal.objects.create(user=self.other, title='Other Goal')
        response = self.client.get(reverse('goal-list'))
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertEqual(len(body['goals']), 1)
        self.assertEqual(body['goals'][0]['title'], 'My Goal')

    def test_empty_list_returns_success(self):
        response = self.client.get(reverse('goal-list'))
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertEqual(body['goals'], [])

    def test_response_includes_progress_fields(self):
        goal = Goal.objects.create(user=self.user, title='Goal With Tasks', target_tasks=3)
        Task.objects.create(user=self.user, title='T1', status=Task.STATUS_DONE, goal=goal)
        response = self.client.get(reverse('goal-list'))
        body = json.loads(response.content)
        g = body['goals'][0]
        self.assertIn('progress_percent', g)
        self.assertIn('completed_tasks', g)
        self.assertIn('total_tasks', g)
        self.assertIn('target_tasks', g)

    def test_goal_list_redirects_anonymous(self):
        self.client.logout()
        response = self.client.get(reverse('goal-list'))
        self.assertEqual(response.status_code, 302)


class GoalCreateViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='goalcreate', password='pass')
        self.client.force_login(self.user)

    def test_create_goal_with_title_succeeds(self):
        data = {'title': 'New Goal'}
        response = self.client.post(
            reverse('goal-create'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertTrue(Goal.objects.filter(title='New Goal', user=self.user).exists())

    def test_create_goal_without_title_fails(self):
        data = {'title': ''}
        response = self.client.post(
            reverse('goal-create'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        self.assertFalse(body['success'])
        self.assertIn('error', body)

    def test_create_goal_assigns_existing_tasks(self):
        task = Task.objects.create(user=self.user, title='Task to assign')
        data = {'title': 'Goal', 'existing_task_ids': [task.pk]}
        self.client.post(
            reverse('goal-create'), data=json.dumps(data), content_type='application/json'
        )
        task.refresh_from_db()
        goal = Goal.objects.get(title='Goal', user=self.user)
        self.assertEqual(task.goal, goal)

    def test_create_goal_creates_new_subtasks(self):
        data = {'title': 'Parent Goal', 'new_task_titles': ['Sub-task 1', 'Sub-task 2']}
        self.client.post(
            reverse('goal-create'), data=json.dumps(data), content_type='application/json'
        )
        goal = Goal.objects.get(title='Parent Goal', user=self.user)
        self.assertEqual(goal.total_tasks, 2)

    def test_create_goal_with_target_tasks(self):
        data = {'title': 'Targeted Goal', 'target_tasks': 5}
        response = self.client.post(
            reverse('goal-create'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        self.assertEqual(body['goal']['target_tasks'], 5)

    def test_create_goal_does_not_assign_other_users_tasks(self):
        other = User.objects.create_user(username='other_create', password='pass')
        other_task = Task.objects.create(user=other, title='Private task')
        data = {'title': 'Goal', 'existing_task_ids': [other_task.pk]}
        self.client.post(
            reverse('goal-create'), data=json.dumps(data), content_type='application/json'
        )
        other_task.refresh_from_db()
        self.assertIsNone(other_task.goal)

    def test_create_goal_returns_goal_data(self):
        data = {'title': 'Resp Goal', 'description': 'Desc text'}
        response = self.client.post(
            reverse('goal-create'), data=json.dumps(data), content_type='application/json'
        )
        body = json.loads(response.content)
        goal_data = body['goal']
        self.assertEqual(goal_data['title'], 'Resp Goal')
        self.assertIn('progress_percent', goal_data)
        self.assertIn('completed_tasks', goal_data)


class GoalDeleteViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='goaldel', password='pass')
        self.client.force_login(self.user)

    def test_delete_own_goal_succeeds(self):
        goal = Goal.objects.create(user=self.user, title='To Delete')
        response = self.client.post(reverse('goal-delete', args=[goal.pk]))
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertFalse(Goal.objects.filter(pk=goal.pk).exists())

    def test_cannot_delete_other_users_goal(self):
        other = User.objects.create_user(username='other_del', password='pass')
        other_goal = Goal.objects.create(user=other, title='Private Goal')
        response = self.client.post(reverse('goal-delete', args=[other_goal.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Goal.objects.filter(pk=other_goal.pk).exists())

    def test_delete_nonexistent_goal_returns_404(self):
        response = self.client.post(reverse('goal-delete', args=[99999]))
        self.assertEqual(response.status_code, 404)
