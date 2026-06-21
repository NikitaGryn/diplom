"""
LangGraph ReAct agent with full task management tools.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from apps.tasks.models import Task, ExecutionHistory
from apps.goals.models import Goal


STATUS_MAP = {
    'new': Task.STATUS_NEW,
    'planned': Task.STATUS_PLANNED,
    'in_progress': Task.STATUS_IN_PROGRESS,
    'done': Task.STATUS_DONE,
}
PRIORITY_MAP = {
    'high': Task.PRIORITY_HIGH,
    'medium': Task.PRIORITY_MEDIUM,
    'low': Task.PRIORITY_LOW,
}
CATEGORY_MAP = {
    'study': Task.CATEGORY_STUDY,
    'work': Task.CATEGORY_WORK,
    'household': Task.CATEGORY_HOUSEHOLD,
    'health': Task.CATEGORY_HEALTH,
    'personal': Task.CATEGORY_PERSONAL,
    'other': Task.CATEGORY_OTHER,
}


def _fmt(dt):
    if not dt:
        return '—'
    return timezone.localtime(dt).strftime('%d.%m.%Y %H:%M')


def _task_to_dict(t: Task) -> dict:
    return {
        'id': t.id,
        'title': t.title,
        'status': t.get_status_display(),
        'priority': t.get_priority_display(),
        'category': t.get_category_display(),
        'deadline': _fmt(t.deadline),
        'estimated_duration': f'{t.estimated_duration} мин' if t.estimated_duration else '—',
        'goal': t.goal.title if t.goal else None,
    }


def build_tools(user, actions_log: list):
    """Return a list of LangChain tools bound to this user session."""

    @tool
    def get_tasks(
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
    ) -> str:
        """Получить задачи пользователя. Можно фильтровать по:
        - status: new | planned | in_progress | done
        - priority: high | medium | low
        - category: study | work | household | health | personal | other
        Возвращает список задач с деталями.
        """
        qs = Task.objects.filter(user=user).select_related('goal').order_by('deadline')
        if status and status in STATUS_MAP:
            qs = qs.filter(status=STATUS_MAP[status])
        if priority and priority in PRIORITY_MAP:
            qs = qs.filter(priority=PRIORITY_MAP[priority])
        if category and category in CATEGORY_MAP:
            qs = qs.filter(category=CATEGORY_MAP[category])

        tasks = list(qs[:30])
        if not tasks:
            return 'Задач не найдено.'

        lines = [f"Найдено {len(tasks)} задач:"]
        for t in tasks:
            d = _task_to_dict(t)
            line = f"  [ID:{d['id']}] {d['title']} | {d['status']} | {d['priority']} | срок: {d['deadline']}"
            if d['goal']:
                line += f" | цель: {d['goal']}"
            lines.append(line)
        return '\n'.join(lines)

    @tool
    def create_task(
        title: str,
        category: str = 'other',
        priority: str = 'medium',
        description: str = '',
        estimated_duration: Optional[int] = None,
        deadline: Optional[str] = None,
    ) -> str:
        """Создать новую задачу для пользователя.
        - title: название задачи (обязательно)
        - category: study | work | household | health | personal | other
        - priority: high | medium | low
        - description: описание (необязательно)
        - estimated_duration: оценка времени в минутах (необязательно)
        - deadline: дедлайн в формате ДД.ММ.ГГГГ или ГГГГ-ММ-ДД (необязательно)
        """
        cat = CATEGORY_MAP.get(category, Task.CATEGORY_OTHER)
        pri = PRIORITY_MAP.get(priority, Task.PRIORITY_MEDIUM)

        deadline_dt = None
        if deadline:
            for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d.%m.%Y %H:%M'):
                try:
                    from datetime import datetime
                    naive = datetime.strptime(deadline, fmt)
                    deadline_dt = timezone.make_aware(naive)
                    break
                except ValueError:
                    continue

        task = Task.objects.create(
            user=user,
            title=title,
            description=description,
            category=cat,
            priority=pri,
            estimated_duration=estimated_duration,
            deadline=deadline_dt,
            status=Task.STATUS_NEW,
        )
        actions_log.append({'action': 'created', 'task_id': task.id})
        return f'✅ Задача создана: [ID:{task.id}] «{task.title}» | {task.get_priority_display()} | {task.get_category_display()}'

    @tool
    def update_task_status(task_id: int, new_status: str) -> str:
        """Изменить статус задачи.
        - task_id: ID задачи
        - new_status: new | planned | in_progress | done
        """
        if new_status not in STATUS_MAP:
            return f'❌ Неверный статус «{new_status}». Допустимые: new, planned, in_progress, done'
        try:
            task = Task.objects.get(pk=task_id, user=user)
        except Task.DoesNotExist:
            return f'❌ Задача ID:{task_id} не найдена.'

        old_status = task.get_status_display()
        task.status = STATUS_MAP[new_status]
        if new_status == 'done' and not task.completed_at:
            task.completed_at = timezone.now()
            ExecutionHistory.objects.update_or_create(
                task=task,
                defaults={
                    'user': user,
                    'category': task.category,
                    'priority': task.priority,
                    'estimated_duration': task.estimated_duration,
                    'actual_duration': task.actual_duration,
                    'correction_factor': (
                        task.actual_duration / task.estimated_duration
                        if task.estimated_duration and task.actual_duration else None
                    ),
                    'completed_at': task.completed_at,
                }
            )
        task.save()
        actions_log.append({'action': 'updated', 'task_id': task.id})
        return f'✅ Статус задачи «{task.title}» изменён: {old_status} → {task.get_status_display()}'

    @tool
    def update_task(
        task_id: int,
        title: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        estimated_duration: Optional[int] = None,
        deadline: Optional[str] = None,
    ) -> str:
        """Обновить данные задачи (название, приоритет, категорию, описание, время, дедлайн).
        Передавай только те поля, которые нужно изменить.
        - task_id: ID задачи
        - deadline: в формате ДД.ММ.ГГГГ или ГГГГ-ММ-ДД
        """
        try:
            task = Task.objects.get(pk=task_id, user=user)
        except Task.DoesNotExist:
            return f'❌ Задача ID:{task_id} не найдена.'

        if title:
            task.title = title
        if priority and priority in PRIORITY_MAP:
            task.priority = PRIORITY_MAP[priority]
        if category and category in CATEGORY_MAP:
            task.category = CATEGORY_MAP[category]
        if description is not None:
            task.description = description
        if estimated_duration is not None:
            task.estimated_duration = estimated_duration
        if deadline:
            for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d.%m.%Y %H:%M'):
                try:
                    from datetime import datetime
                    naive = datetime.strptime(deadline, fmt)
                    task.deadline = timezone.make_aware(naive)
                    break
                except ValueError:
                    continue

        task.save()
        actions_log.append({'action': 'updated', 'task_id': task.id})
        return f'✅ Задача [ID:{task.id}] «{task.title}» обновлена.'

    @tool
    def delete_task(task_id: int) -> str:
        """Удалить задачу по её ID.
        - task_id: ID задачи для удаления
        """
        try:
            task = Task.objects.get(pk=task_id, user=user)
        except Task.DoesNotExist:
            return f'❌ Задача ID:{task_id} не найдена.'
        title = task.title
        task.delete()
        actions_log.append({'action': 'deleted', 'task_id': task_id})
        return f'🗑️ Задача «{title}» удалена.'

    @tool
    def get_statistics() -> str:
        """Получить статистику по задачам: количество по статусам, приоритетам, просроченные, потраченное время."""
        now = timezone.now()
        tasks = Task.objects.filter(user=user)

        total = tasks.count()
        by_status = {s: tasks.filter(status=s).count() for s, _ in Task.STATUS_CHOICES}
        by_priority = {p: tasks.exclude(status='done').filter(priority=p).count() for p, _ in Task.PRIORITY_CHOICES}
        overdue = tasks.filter(
            status__in=['new', 'planned', 'in_progress'],
            deadline__lt=now
        ).count()
        done_tasks = tasks.filter(status='done')
        total_minutes = sum(t.actual_duration for t in done_tasks if t.actual_duration)

        lines = [
            f"📊 Статистика задач:",
            f"  Всего задач: {total}",
            f"  Новые: {by_status.get('new', 0)} | Запланированные: {by_status.get('planned', 0)} | В работе: {by_status.get('in_progress', 0)} | Выполненные: {by_status.get('done', 0)}",
            f"  Активные по приоритету — Высокий: {by_priority.get('high', 0)} | Средний: {by_priority.get('medium', 0)} | Низкий: {by_priority.get('low', 0)}",
            f"  Просрочено: {overdue}",
            f"  Суммарное фактическое время: {round(total_minutes / 60, 1)} ч ({total_minutes} мин)",
        ]
        return '\n'.join(lines)

    @tool
    def get_recommendation() -> str:
        """Получить рекомендацию — какую задачу стоит взять в работу прямо сейчас, с объяснением причины."""
        now = timezone.now()

        checks = [
            (Task.objects.filter(user=user, status__in=['new', 'planned', 'in_progress'],
                                 priority='high', deadline__lt=now).first(),
             'Просрочена высокоприоритетная задача!'),
            (Task.objects.filter(user=user, status='planned',
                                 scheduled_start__lte=now, scheduled_end__gte=now).first(),
             'Сейчас запланировано время для этой задачи.'),
            (Task.objects.filter(user=user, status='in_progress').first(),
             'Задача уже в работе — доведи до конца.'),
            (Task.objects.filter(user=user, status='new', priority='high').order_by('deadline').first(),
             'Высокоприоритетная задача требует внимания.'),
            (Task.objects.filter(user=user, status__in=['new', 'planned']).order_by('deadline').first(),
             'Ближайшая задача по сроку.'),
        ]

        for task, reason in checks:
            if task:
                d = _task_to_dict(task)
                return (
                    f"💡 Рекомендация: «{d['title']}»\n"
                    f"  ID: {d['id']} | {d['status']} | {d['priority']} | срок: {d['deadline']}\n"
                    f"  Причина: {reason}"
                )
        return '🎉 Все задачи выполнены! Отличная работа.'

    @tool
    def get_goals() -> str:
        """Получить список целей пользователя с прогрессом."""
        goals = Goal.objects.filter(user=user).prefetch_related('tasks')
        if not goals:
            return 'Целей нет.'

        lines = [f"🎯 Цели ({goals.count()}):"]
        for g in goals:
            status = '✅ Достигнута' if g.is_achieved else f'📈 {g.progress_percent}%'
            lines.append(f"  [ID:{g.id}] {g.title} | {status} | задач: {g.total_tasks} / выполнено: {g.completed_tasks}")
        return '\n'.join(lines)

    @tool
    def analyze_workload() -> str:
        """Проанализировать загруженность: просроченные задачи, задачи без дедлайна, распределение по категориям и советы по оптимизации."""
        now = timezone.now()
        active = Task.objects.filter(user=user).exclude(status='done')

        overdue = list(active.filter(deadline__lt=now).order_by('deadline'))
        no_deadline = active.filter(deadline__isnull=True)
        in_progress = active.filter(status='in_progress')

        lines = ['Анализ загруженности:']

        if overdue:
            lines.append(f'\nПросрочено ({len(overdue)} задач):')
            for t in overdue[:5]:
                lines.append(f"  - «{t.title}» | просрочено на {(now - t.deadline).days} дн.")

        lines.append(f'\nВ работе прямо сейчас: {in_progress.count()}')
        lines.append(f'Без дедлайна: {no_deadline.count()}')

        by_cat = {}
        for t in active:
            label = t.get_category_display()
            by_cat[label] = by_cat.get(label, 0) + 1
        if by_cat:
            cat_str = ' | '.join(f'{k}: {v}' for k, v in sorted(by_cat.items(), key=lambda x: -x[1]))
            lines.append(f'\nПо категориям: {cat_str}')

        total = active.count()
        if total == 0:
            lines.append('\nАктивных задач нет. Можно добавить новые.')
        elif total > 15:
            lines.append(f'\nСовет: у тебя {total} активных задач — много. Рекомендую расставить приоритеты и разбить крупные задачи на подзадачи.')
        elif overdue:
            lines.append('\nСовет: займись сначала просроченными задачами, начиная с высокоприоритетных.')
        else:
            lines.append('\nЗагруженность в норме.')

        return '\n'.join(lines)

    @tool
    def create_goal(
        title: str,
        description: str = '',
        target_tasks: Optional[int] = None,
    ) -> str:
        """Создать новую цель для пользователя.
        - title: название цели (обязательно)
        - description: описание (необязательно)
        - target_tasks: целевое количество задач для достижения цели (необязательно)
        """
        goal = Goal.objects.create(
            user=user,
            title=title,
            description=description,
            target_tasks=target_tasks,
        )
        actions_log.append({'action': 'created', 'goal_id': goal.id})
        msg = f'✅ Цель создана: «{goal.title}»'
        if target_tasks:
            msg += f' | целевых задач: {target_tasks}'
        return msg

    @tool
    def assign_task_to_goal(task_id: int, goal_id: int) -> str:
        """Привязать задачу к цели.
        - task_id: ID задачи
        - goal_id: ID цели
        """
        try:
            task = Task.objects.get(pk=task_id, user=user)
        except Task.DoesNotExist:
            return f'❌ Задача ID:{task_id} не найдена.'
        try:
            goal = Goal.objects.get(pk=goal_id, user=user)
        except Goal.DoesNotExist:
            return f'❌ Цель ID:{goal_id} не найдена.'

        task.goal = goal
        task.save()
        actions_log.append({'action': 'updated', 'task_id': task.id})
        return f'✅ Задача «{task.title}» привязана к цели «{goal.title}».'

    @tool
    def unassign_task_from_goal(task_id: int) -> str:
        """Отвязать задачу от цели.
        - task_id: ID задачи
        """
        try:
            task = Task.objects.get(pk=task_id, user=user)
        except Task.DoesNotExist:
            return f'❌ Задача ID:{task_id} не найдена.'

        if not task.goal:
            return f'Задача «{task.title}» не привязана ни к одной цели.'

        goal_title = task.goal.title
        task.goal = None
        task.save()
        actions_log.append({'action': 'updated', 'task_id': task.id})
        return f'✅ Задача «{task.title}» отвязана от цели «{goal_title}».'

    @tool
    def summarize_completed(days: int = 7) -> str:
        """Показать выполненные задачи за последние N дней (по умолчанию 7).
        - days: количество дней для анализа
        """
        since = timezone.now() - timedelta(days=days)
        done = Task.objects.filter(user=user, status='done', completed_at__gte=since).order_by('-completed_at')
        count = done.count()
        if count == 0:
            return f'За последние {days} дней выполненных задач нет.'

        total_min = sum(t.actual_duration for t in done if t.actual_duration)
        lines = [f"✅ Выполнено за {days} дней: {count} задач ({round(total_min/60,1)} ч)"]
        for t in done[:10]:
            lines.append(f"  • «{t.title}» — {_fmt(t.completed_at)}")
        return '\n'.join(lines)

    return [
        get_tasks,
        create_task,
        update_task_status,
        update_task,
        delete_task,
        get_statistics,
        get_recommendation,
        get_goals,
        analyze_workload,
        summarize_completed,
        create_goal,
        assign_task_to_goal,
        unassign_task_from_goal,
    ]


def build_system_prompt(user) -> str:
    now = timezone.now().strftime('%d.%m.%Y %H:%M')
    return f"""Ты — интеллектуальный помощник планировщика задач TaskPlanner.
Пользователь: {user.username}. Текущее время: {now}.

Твои возможности (инструменты):
- get_tasks — просмотр задач с фильтрами по статусу, приоритету, категории
- create_task — создание новой задачи
- update_task_status — изменение статуса задачи
- update_task — редактирование деталей задачи
- delete_task — удаление задачи
- get_statistics — статистика по задачам
- get_recommendation — что делать прямо сейчас
- get_goals — список целей и прогресс
- create_goal — создание новой цели
- assign_task_to_goal — привязка задачи к цели
- unassign_task_from_goal — отвязка задачи от цели
- analyze_workload — анализ загруженности и советы
- summarize_completed — итоги за период

Правила:
1. Всегда отвечай на русском языке.
2. Если пользователь хочет создать/изменить/удалить задачу — используй инструменты, не просто описывай.
3. Перед удалением задачи уточни у пользователя, если он явно не попросил.
4. Будь конкретным и кратким. Предлагай следующий шаг после каждого действия.
5. НИКОГДА не упоминай ID задач в ответах пользователю — только названия.
6. Не пиши технические детали вроде «ID: 62» — пользователь их не видит и они ему не нужны.
7. НИКОГДА не используй эмодзи в ответах — только чистый текст.
8. При анализе загруженности НИКОГДА не предлагай переносить или сдвигать дедлайны задач.
"""


def run_agent(user, user_message: str, history: list, api_key: str) -> tuple[str, list]:
    """
    Run the LangGraph ReAct agent.
    Returns (reply_text, actions_log).
    actions_log contains dicts like {'action': 'created'|'updated'|'deleted', 'task_id': int}
    """
    actions_log = []
    tools = build_tools(user, actions_log)

    from django.conf import settings as django_settings
    llm = ChatOpenAI(
        base_url=getattr(django_settings, 'LLM_BASE_URL', ''),
        api_key=api_key,
        model='gemini-3-flash-preview',
        max_tokens=2048,
    )

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=build_system_prompt(user),
    )

    from langchain_core.messages import HumanMessage, AIMessage
    messages = []
    for msg in history[-12:]:
        if msg['role'] == 'user':
            messages.append(HumanMessage(content=msg['content']))
        else:
            messages.append(AIMessage(content=msg['content']))
    messages.append(HumanMessage(content=user_message))

    result = agent.invoke({'messages': messages})

    reply = ''
    for msg in reversed(result['messages']):
        if hasattr(msg, 'content') and msg.__class__.__name__ == 'AIMessage':
            content = msg.content
            if isinstance(content, list):
                reply = ' '.join(
                    block['text'] for block in content
                    if isinstance(block, dict) and block.get('type') == 'text'
                )
            else:
                reply = content
            if reply:
                break

    return reply, actions_log
