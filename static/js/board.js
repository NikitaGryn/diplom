const COLUMNS = ['new', 'planned', 'in_progress', 'done'];
let taskModal = null;
let completeModal = null;
let assignGoalModal = null;
let deleteTaskModal = null;
let pendingDeleteTaskId = null;
let pendingScheduleTaskId = null;
let scheduleTaskModal = null;

function getTaskModal() {
    if (!taskModal) taskModal = new bootstrap.Modal(document.getElementById('taskModal'));
    return taskModal;
}
function getCompleteModal() {
    if (!completeModal) completeModal = new bootstrap.Modal(document.getElementById('completeModal'));
    return completeModal;
}
function getAssignGoalModal() {
    if (!assignGoalModal) assignGoalModal = new bootstrap.Modal(document.getElementById('assignGoalModal'));
    return assignGoalModal;
}

document.addEventListener('DOMContentLoaded', () => {

    const deleteModalEl = document.getElementById('deleteTaskModal');
    if (deleteModalEl) {
        deleteTaskModal = new bootstrap.Modal(deleteModalEl);
    }

    document.getElementById('confirmScheduleTaskBtn')?.addEventListener('click', executeScheduleTask);

    COLUMNS.forEach(status => {
        const el = document.getElementById(`column-${status}`);
        if (!el) return;

        Sortable.create(el, {
            group: {
                name: 'tasks',
                pull: status === 'done' ? false : true,
                put: true,
            },
            animation: 150,
            ghostClass: 'task-ghost',
            chosenClass: 'task-chosen',
            dragClass: 'task-drag',
            handle: '.task-card',
            onMove: (evt) => {
                if (evt.from.dataset.status === 'done') {
                    return false;
                }
            },
            onEnd: async (evt) => {
                const taskEl = evt.item;
                const taskId = taskEl.dataset.taskId;
                const newStatus = evt.to.dataset.status;
                const oldStatus = evt.from.dataset.status;

                if (oldStatus === 'done') {
                    evt.from.insertBefore(taskEl, evt.from.children[evt.oldIndex] || null);
                    return;
                }

                if (newStatus === oldStatus) return;

                if (newStatus === 'done') {
                    const originalCol = evt.from;
                    const refChild = originalCol.children[evt.oldIndex] || null;
                    originalCol.insertBefore(taskEl, refChild);
                    taskEl.dataset.status = oldStatus;
                    updateColumnCount(oldStatus);
                    updateColumnCount('done');
                    updateEmptyPlaceholders(oldStatus);
                    updateEmptyPlaceholders('done');
                    openCompleteModal(taskId);
                    return;
                }

                updateColumnCount(oldStatus);
                updateColumnCount(newStatus);
                updateEmptyPlaceholders(oldStatus);
                updateEmptyPlaceholders(newStatus);

                const result = await apiPost('/api/tasks/status/', {
                    task_id: parseInt(taskId),
                    status: newStatus,
                });

                if (result.success) {
                    taskEl.dataset.status = newStatus;
                    if (newStatus === 'in_progress') {
                        removeStartButton(taskEl);
                    }
                    if (result.scheduled_start) {
                        updateCardSchedule(taskEl, result.scheduled_start, result.scheduled_end);
                    }
                    if (result.is_overdue_risk) {
                        addOverdueRiskBadge(taskEl);
                    } else {
                        removeOverdueRiskBadge(taskEl);
                    }
                } else {
                    const originalCol = document.getElementById(`column-${oldStatus}`);
                    originalCol.appendChild(taskEl);
                    taskEl.dataset.status = oldStatus;
                    updateColumnCount(oldStatus);
                    updateColumnCount(newStatus);
                    updateEmptyPlaceholders(oldStatus);
                    updateEmptyPlaceholders(newStatus);
                    showAlert('Ошибка изменения статуса задачи', 'danger');
                }
            },
        });
    });

    document.getElementById('saveTaskBtn').addEventListener('click', saveTask);
    document.getElementById('confirmCompleteBtn').addEventListener('click', completeTask);
    document.getElementById('confirmAssignGoalBtn').addEventListener('click', assignGoal);
    document.getElementById('predictBtn').addEventListener('click', predictTime);
    document.getElementById('taskCategory').addEventListener('change', clearPrediction);
    document.getElementById('taskDuration').addEventListener('input', clearPrediction);

    const confirmDeleteBtn = document.getElementById('confirmDeleteTaskBtn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', executeDeleteTask);
    }
});

function updateColumnCount(status) {
    const col = document.getElementById(`column-${status}`);
    const counter = document.getElementById(`count-${status}`);
    if (col && counter) {
        const count = col.querySelectorAll('.task-card').length;
        counter.textContent = count;
    }
}

function updateEmptyPlaceholders(status) {
    const col = document.getElementById(`column-${status}`);
    if (!col) return;
    const cards = col.querySelectorAll('.task-card');
    let placeholder = col.querySelector('.empty-placeholder');

    if (cards.length === 0) {
        if (!placeholder) {
            placeholder = document.createElement('div');
            placeholder.className = 'text-muted text-center small py-3 empty-placeholder';
            placeholder.innerHTML = '<i class="bi bi-inbox"></i><br>Нет задач';
            col.appendChild(placeholder);
        }
    } else {
        if (placeholder) placeholder.remove();
    }
}

function openCreateModal(status) {
    document.getElementById('taskId').value = '';
    document.getElementById('taskInitialStatus').value = status;
    document.getElementById('taskTitle').value = '';
    document.getElementById('taskDescription').value = '';
    document.getElementById('taskCategory').value = 'other';
    document.getElementById('taskPriority').value = 'medium';
    document.getElementById('taskDeadline').value = '';
    document.getElementById('taskDuration').value = '';
    document.getElementById('taskModalTitle').innerHTML = '<i class="bi bi-plus-circle me-2"></i>Новая задача';

    const predictBtn = document.getElementById('predictBtn');
    if (predictBtn) predictBtn.style.display = '';

    clearPrediction();
    getTaskModal().show();
}

async function openEditModal(taskId) {
    const data = await apiGet(`/api/tasks/${taskId}/`);
    if (!data.id) {
        showAlert('Ошибка загрузки задачи', 'danger');
        return;
    }

    document.getElementById('taskId').value = data.id;
    document.getElementById('taskTitle').value = data.title;
    document.getElementById('taskDescription').value = data.description || '';
    document.getElementById('taskCategory').value = data.category;
    document.getElementById('taskPriority').value = data.priority;
    document.getElementById('taskInitialStatus').value = data.status;
    document.getElementById('taskDuration').value = data.estimated_duration || '';

    if (data.deadline) {
        const dt = new Date(data.deadline);
        const local = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000);
        document.getElementById('taskDeadline').value = local.toISOString().slice(0, 16);
    } else {
        document.getElementById('taskDeadline').value = '';
    }

    document.getElementById('taskModalTitle').innerHTML = '<i class="bi bi-pencil me-2"></i>Редактировать задачу';

    const predictBtn = document.getElementById('predictBtn');
    if (predictBtn) predictBtn.style.display = data.status === 'done' ? 'none' : '';

    clearPrediction();
    getTaskModal().show();
}

async function saveTask() {
    const taskId = document.getElementById('taskId').value;
    const title = document.getElementById('taskTitle').value.trim();

    if (!title) {
        document.getElementById('taskTitle').classList.add('is-invalid');
        return;
    }
    document.getElementById('taskTitle').classList.remove('is-invalid');

    const status = document.getElementById('taskInitialStatus').value || 'new';

    const payload = {
        title: title,
        description: document.getElementById('taskDescription').value,
        category: document.getElementById('taskCategory').value,
        priority: document.getElementById('taskPriority').value,
        status: status,
        deadline: document.getElementById('taskDeadline').value || null,
        estimated_duration: document.getElementById('taskDuration').value || null,
    };

    const saveBtn = document.getElementById('saveTaskBtn');
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Сохранение...';

    let result;
    if (taskId) {
        result = await apiPost(`/api/tasks/${taskId}/update/`, payload);
    } else {
        result = await apiPost('/api/tasks/create/', payload);
    }

    saveBtn.disabled = false;
    saveBtn.innerHTML = '<i class="bi bi-save me-1"></i>Сохранить';

    if (result.success) {
        getTaskModal().hide();

        if (taskId) {
            const oldCard = document.querySelector(`[data-task-id="${taskId}"]`);
            if (oldCard) {
                const oldStatus = oldCard.dataset.status;
                const newStatus = payload.status;
                const tmp = document.createElement('div');
                tmp.innerHTML = result.task_html;
                const newCard = tmp.firstElementChild;

                if (oldStatus !== newStatus) {
                    oldCard.remove();
                    updateColumnCount(oldStatus);
                    updateEmptyPlaceholders(oldStatus);
                    const newCol = document.getElementById(`column-${newStatus}`);
                    if (newCol) {
                        newCol.insertBefore(newCard, newCol.firstChild);
                        updateColumnCount(newStatus);
                        updateEmptyPlaceholders(newStatus);
                    }
                } else {
                    oldCard.replaceWith(newCard);
                }
            }
        } else {
            const targetStatus = payload.status;
            const col = document.getElementById(`column-${targetStatus}`);
            if (col) {
                const tmp = document.createElement('div');
                tmp.innerHTML = result.task_html;
                const newCard = tmp.firstElementChild;
                col.insertBefore(newCard, col.firstChild);
                updateColumnCount(targetStatus);
                updateEmptyPlaceholders(targetStatus);
            }
        }
    } else {
        const errors = result.errors || {};
        const msg = Object.values(errors).flat().join(', ') || result.error || 'Ошибка сохранения';
        showAlert(msg, 'danger');
    }
}

function openDeleteTaskModal(taskId, taskTitle) {
    pendingDeleteTaskId = taskId;
    const titleEl = document.getElementById('deleteTaskTitle');
    if (titleEl) {
        if (!taskTitle) {
            const card = document.querySelector(`[data-task-id="${taskId}"]`);
            taskTitle = card?.querySelector('.task-title')?.textContent?.trim() || '';
        }
        titleEl.textContent = taskTitle;
    }
    if (deleteTaskModal) deleteTaskModal.show();
}

async function executeDeleteTask() {
    if (!pendingDeleteTaskId) return;
    const taskId = pendingDeleteTaskId;
    pendingDeleteTaskId = null;
    if (deleteTaskModal) deleteTaskModal.hide();

    const result = await apiPost(`/api/tasks/${taskId}/delete/`, {});
    if (result.success) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (card) {
            const status = card.dataset.status;
            card.remove();
            updateColumnCount(status);
            updateEmptyPlaceholders(status);
        }
    } else {
        showAlert('Ошибка удаления задачи', 'danger');
    }
}

async function deleteTask(taskId) {
    openDeleteTaskModal(taskId, '');
}

function openCompleteModal(taskId) {
    document.getElementById('completeTaskId').value = taskId;
    document.getElementById('actualDuration').value = '';
    getCompleteModal().show();
}

async function completeTask() {
    const taskId = document.getElementById('completeTaskId').value;
    const actualDuration = document.getElementById('actualDuration').value;

    const btn = document.getElementById('confirmCompleteBtn');
    btn.disabled = true;

    const result = await apiPost('/api/tasks/complete/', {
        task_id: parseInt(taskId),
        actual_duration: actualDuration ? parseInt(actualDuration) : null,
    });

    btn.disabled = false;

    if (result.success) {
        getCompleteModal().hide();

        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (card) {
            const oldStatus = card.dataset.status;
            card.dataset.status = 'done';

            removeStartButton(card);
            removeCompleteButton(card);
            removeOverdueRiskBadge(card);
            card.removeAttribute('draggable');

            const doneCol = document.getElementById('column-done');
            if (doneCol) {
                doneCol.insertBefore(card, doneCol.firstChild);
            }

            updateColumnCount(oldStatus);
            updateColumnCount('done');
            updateEmptyPlaceholders(oldStatus);
            updateEmptyPlaceholders('done');
        }
        showAlert('Задача выполнена!', 'success');
    } else {
        showAlert('Ошибка завершения задачи', 'danger');
    }
}

async function openAssignGoalModal(taskId) {
    document.getElementById('assignTaskId').value = taskId;
    document.getElementById('newGoalTitle').value = '';

    const select = document.getElementById('goalSelect');
    select.innerHTML = '<option value="">Загрузка...</option>';
    getAssignGoalModal().show();

    try {
        const resp = await fetch('/api/goals/');
        const data = await resp.json();
        select.innerHTML = '<option value="">— Выберите цель —</option>';
        if (data.goals) {
            data.goals.forEach(goal => {
                const opt = document.createElement('option');
                opt.value = goal.id;
                opt.textContent = goal.title;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        select.innerHTML = '<option value="">— Ошибка загрузки —</option>';
    }
}

async function assignGoal() {
    const taskId = document.getElementById('assignTaskId').value;
    const goalId = document.getElementById('goalSelect').value;
    const newGoalTitle = document.getElementById('newGoalTitle').value.trim();

    if (!goalId && !newGoalTitle) {
        showAlert('Выберите цель или введите название новой', 'warning');
        return;
    }

    const payload = { task_id: parseInt(taskId) };
    if (goalId) {
        payload.goal_id = parseInt(goalId);
    } else {
        payload.goal_title = newGoalTitle;
    }

    const result = await apiPost('/api/tasks/assign-goal/', payload);

    if (result.success) {
        getAssignGoalModal().hide();
        showAlert(`Задача привязана к цели "${result.goal_title}"`, 'success');

        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (card) {
            let goalBadgeContainer = card.querySelector('.task-goal-badge, .goal-badge-container');
            if (!goalBadgeContainer) {
                const flexDiv = card.querySelector('.d-flex.flex-wrap');
                if (flexDiv) {
                    goalBadgeContainer = document.createElement('div');
                    flexDiv.parentElement.insertBefore(goalBadgeContainer, flexDiv.nextSibling);
                }
            }
            if (goalBadgeContainer) {
                goalBadgeContainer.className = 'mt-1 task-goal-badge';
                goalBadgeContainer.dataset.goalId = result.goal_id;
                goalBadgeContainer.innerHTML = `
                    <span class="badge bg-info text-dark small">
                        <i class="bi bi-trophy"></i> ${escapeHtml(result.goal_title)}
                    </span>
                `;
            }
        }

        if (newGoalTitle && result.goal_id) {
            const select = document.getElementById('goalSelect');
            const existing = select.querySelector(`option[value="${result.goal_id}"]`);
            if (!existing) {
                const option = document.createElement('option');
                option.value = result.goal_id;
                option.textContent = result.goal_title;
                select.appendChild(option);
            }
        }
    } else {
        showAlert(result.error || 'Ошибка привязки к цели', 'danger');
    }
}

async function startTask(taskId) {
    const result = await apiPost('/api/tasks/status/', {
        task_id: parseInt(taskId),
        status: 'in_progress',
    });

    if (result.success) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (card) {
            const oldStatus = card.dataset.status;
            card.dataset.status = 'in_progress';
            removeStartButton(card);

            const inProgressCol = document.getElementById('column-in_progress');
            if (inProgressCol) {
                inProgressCol.insertBefore(card, inProgressCol.firstChild);
            }

            updateColumnCount(oldStatus);
            updateColumnCount('in_progress');
            updateEmptyPlaceholders(oldStatus);
            updateEmptyPlaceholders('in_progress');
        }
    } else {
        showAlert('Ошибка изменения статуса', 'danger');
    }
}

function removeStartButton(card) {
    const items = card.querySelectorAll('.start-task-item');
    items.forEach(li => li.remove());
    card.querySelectorAll('.dropdown-item').forEach(btn => {
        if (btn.textContent.trim().includes('Начать выполнение')) {
            const li = btn.closest('li');
            if (li) li.remove();
        }
    });
}

function removeCompleteButton(card) {
    card.querySelectorAll('.dropdown-item').forEach(btn => {
        if (btn.textContent.trim().includes('Отметить выполненной')) {
            const li = btn.closest('li');
            if (li) li.remove();
        }
    });
}

async function predictTime() {
    const category = document.getElementById('taskCategory').value;
    const duration = document.getElementById('taskDuration').value;

    if (!duration || parseInt(duration) < 1) {
        showAlert('Введите оценку времени для предсказания', 'warning');
        return;
    }

    const btn = document.getElementById('predictBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    const priority = document.getElementById('taskPriority')?.value || 'medium';

    const result = await apiPost('/api/tasks/predict-time/', {
        category: category,
        estimated_duration: parseInt(duration),
        priority: priority,
    });

    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-robot"></i>';

    const resultEl = document.getElementById('predictionResult');

    if (result.success) {
        resultEl.classList.remove('d-none');
        if (result.has_enough_data) {
            const modelIcon = result.model_name === 'RandomForest'
                ? '<i class="bi bi-diagram-3 me-1 text-success"></i>'
                : result.model_name === 'LinearRegression'
                    ? '<i class="bi bi-graph-up me-1 text-info"></i>'
                    : '<i class="bi bi-calculator me-1 text-warning"></i>';
            const importancesHtml = '';
            resultEl.innerHTML = `
                ${modelIcon}<strong>${result.predicted_duration} мин</strong>
                <span class="text-muted ms-1" style="font-size:0.85em">${result.message}</span>
                ${importancesHtml}
            `;
        } else {
            resultEl.innerHTML = `<i class="bi bi-info-circle me-1"></i>${result.message}`;
        }
    } else {
        resultEl.classList.remove('d-none');
        resultEl.innerHTML = `<span class="text-danger">${result.error || 'Ошибка предсказания'}</span>`;
    }
}

function clearPrediction() {
    const el = document.getElementById('predictionResult');
    if (el) {
        el.classList.add('d-none');
        el.innerHTML = '';
    }
}

function updateCardSchedule(card, scheduledStart, scheduledEnd) {
    let scheduleEl = card.querySelector('.scheduled-info');
    if (!scheduleEl) {
        scheduleEl = document.createElement('div');
        scheduleEl.className = 'mt-1 text-muted small scheduled-info';
        const cardBody = card.querySelector('.card-body');
        if (cardBody) cardBody.appendChild(scheduleEl);
    }
    if (scheduledStart) {
        const dt = new Date(scheduledStart);
        scheduleEl.innerHTML = `<i class="bi bi-calendar-check"></i> ${dt.toLocaleDateString('ru-RU')} ${dt.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})}`;
    }
}

function addOverdueRiskBadge(card) {
    if (!card.querySelector('.overdue-risk-badge')) {
        const badge = document.createElement('div');
        badge.className = 'text-danger small mb-1 overdue-risk-badge';
        badge.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> Риск срыва';
        const title = card.querySelector('.task-title');
        if (title) title.insertAdjacentElement('afterend', badge);
    }
}

function removeOverdueRiskBadge(card) {
    const badge = card.querySelector('.overdue-risk-badge');
    if (badge) badge.remove();
}

function showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
    alert.style.zIndex = '9999';
    alert.style.minWidth = '300px';
    alert.innerHTML = `
        ${escapeHtml(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alert);
    setTimeout(() => {
        if (alert.parentNode) {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 300);
        }
    }, 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

let _menuOpenForBtn = null;

function _getFloatingMenu() {
    let menu = document.getElementById('_taskFloatingMenu');
    if (!menu) {
        menu = document.createElement('ul');
        menu.id = '_taskFloatingMenu';
        menu.className = 'list-unstyled shadow rounded';
        menu.style.cssText = [
            'display:none',
            'position:fixed',
            'min-width:250px',
            'z-index:99999',
            'background:#212529',
            'border:1px solid rgba(255,255,255,.15)',
            'padding:4px 0',
            'padding-left:8px',
            'margin:0',
        ].join(';');
        document.body.appendChild(menu);
    }
    return menu;
}

function toggleTaskMenu(btn) {
    const menu = _getFloatingMenu();

    if (_menuOpenForBtn === btn) {
        menu.style.display = 'none';
        _menuOpenForBtn = null;
        return;
    }
    _menuOpenForBtn = btn;

    const card   = btn.closest('.task-card');
    const taskId = card.dataset.taskId;
    const status = card.dataset.status;
    const title  = card.querySelector('.task-title')?.textContent?.trim() || '';

    let html = `
        <li><button class="dropdown-item" onclick="openEditModal(${taskId});_closeTaskMenu()">
            <i class="bi bi-pencil me-2"></i>Редактировать</button></li>`;

    if (status !== 'in_progress' && status !== 'done') {
        html += `<li><button class="dropdown-item" onclick="startTask(${taskId});_closeTaskMenu()">
            <i class="bi bi-play-fill me-2 text-success"></i>Начать выполнение</button></li>`;
    }
    if (status !== 'done') {
        html += `<li><button class="dropdown-item" onclick="openCompleteModal(${taskId});_closeTaskMenu()">
            <i class="bi bi-check-circle me-2 text-success"></i>Отметить выполненной</button></li>`;
    }
    html += `<li><button class="dropdown-item" onclick="openAssignGoalModal(${taskId});_closeTaskMenu()">
            <i class="bi bi-trophy me-2 text-warning"></i>Добавить к цели</button></li>
        <li><button class="dropdown-item" onclick="openScheduleTaskModal(${taskId});_closeTaskMenu()">
            <i class="bi bi-calendar-plus me-2 text-info"></i>Планировать</button></li>
        <li><hr class="dropdown-divider my-1"></li>
        <li><button class="dropdown-item text-danger" onclick="openDeleteTaskModal(${taskId});_closeTaskMenu()">
            <i class="bi bi-trash me-2"></i>Удалить</button></li>`;

    menu.innerHTML = html;

    const rect      = btn.getBoundingClientRect();
    const menuW     = 258;
    const menuH     = menu.scrollHeight || 220;

    let left = rect.right + 6;
    let top  = rect.top;

    if (left + menuW > window.innerWidth - 8)  left = rect.left - menuW - 6;
    if (top  + menuH > window.innerHeight - 8)  top  = window.innerHeight - menuH - 8;
    if (top < 8) top = 8;

    menu.style.top  = top + 'px';
    menu.style.left = left + 'px';
    menu.style.display = 'block';
}

function _closeTaskMenu() {
    const menu = document.getElementById('_taskFloatingMenu');
    if (menu) menu.style.display = 'none';
    _menuOpenForBtn = null;
}

document.addEventListener('click', (e) => {
    if (!_menuOpenForBtn) return;
    const menu = document.getElementById('_taskFloatingMenu');
    if (menu && !menu.contains(e.target) && !e.target.closest('.task-menu-btn')) {
        _closeTaskMenu();
    }
});

function openScheduleTaskModal(taskId) {
    pendingScheduleTaskId = taskId;

    const card = document.querySelector(`[data-task-id="${taskId}"]`);
    const title = card?.querySelector('.task-title')?.textContent?.trim() || '';
    const titleEl = document.getElementById('scheduleTaskTitle');
    if (titleEl) titleEl.textContent = title;

    const SCHED_MIN_HOUR = 7;
    const SCHED_MAX_HOUR = 23;
    const now = new Date();
    now.setMinutes(0, 0, 0);
    let nextHour = now.getHours() + 1;
    let defaultDate = new Date(now);
    if (nextHour < SCHED_MIN_HOUR) nextHour = SCHED_MIN_HOUR;
    if (nextHour > SCHED_MAX_HOUR) {
        defaultDate.setDate(defaultDate.getDate() + 1);
        nextHour = SCHED_MIN_HOUR;
    }
    defaultDate.setHours(nextHour, 0, 0, 0);
    const pad = n => String(n).padStart(2, '0');

    const dateInput = document.getElementById('scheduleTaskDate');
    const timeInput = document.getElementById('scheduleTaskTime');
    if (dateInput) {
        dateInput.value = `${defaultDate.getFullYear()}-${pad(defaultDate.getMonth()+1)}-${pad(defaultDate.getDate())}`;
    }
    if (timeInput) {
        timeInput.value = `${pad(nextHour)}:00`;
    }

    const modalEl = document.getElementById('scheduleTaskModal');
    if (!modalEl) { showAlert('Модал не найден', 'danger'); return; }
    if (!scheduleTaskModal) scheduleTaskModal = new bootstrap.Modal(modalEl);
    scheduleTaskModal.show();
}

async function executeScheduleTask() {
    const taskId = pendingScheduleTaskId;
    if (!taskId) return;

    const dateVal = document.getElementById('scheduleTaskDate')?.value;
    const timeVal = document.getElementById('scheduleTaskTime')?.value;
    if (!dateVal || !timeVal) { showAlert('Выберите дату и время', 'warning'); return; }

    const hour = parseInt(timeVal.split(':')[0], 10);
    if (hour < 7 || hour > 23) {
        showAlert('Выберите время в диапазоне 7:00 — 23:00', 'warning');
        return;
    }

    const scheduledStart = new Date(`${dateVal}T${timeVal}:00`).toISOString();

    const btn = document.getElementById('confirmScheduleTaskBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>'; }

    const result = await apiPost(`/api/tasks/${taskId}/reschedule/`, { scheduled_start: scheduledStart });

    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-calendar-check me-1"></i>Поставить'; }

    if (result.success) {
        pendingScheduleTaskId = null;
        if (scheduleTaskModal) scheduleTaskModal.hide();
        showAlert('Задача добавлена в расписание', 'success');
    } else {
        showAlert(result.error || 'Ошибка планирования', 'danger');
    }
}
