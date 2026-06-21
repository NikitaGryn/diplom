let deleteGoalModal = null;
let pendingDeleteGoalId = null;

document.addEventListener('DOMContentLoaded', () => {
    const goalsOffcanvas = document.getElementById('goalsOffcanvas');
    if (!goalsOffcanvas) return;

    goalsOffcanvas.addEventListener('show.bs.offcanvas', loadGoals);

    const createGoalBtn = document.getElementById('createGoalBtn');
    const createGoalForm = document.getElementById('createGoalForm');
    const cancelGoalBtn = document.getElementById('cancelGoalBtn');
    const saveGoalBtn = document.getElementById('saveGoalBtn');

    if (createGoalBtn) {
        createGoalBtn.addEventListener('click', () => {
            createGoalForm.classList.toggle('d-none');
            if (!createGoalForm.classList.contains('d-none')) {
                document.getElementById('goalTitle').focus();
            }
        });
    }

    if (cancelGoalBtn) {
        cancelGoalBtn.addEventListener('click', () => {
            createGoalForm.classList.add('d-none');
            document.getElementById('goalTitle').value = '';
            document.getElementById('goalDescription').value = '';
            const targetEl = document.getElementById('goalTargetTasks');
            if (targetEl) targetEl.value = '';
        });
    }

    if (saveGoalBtn) {
        saveGoalBtn.addEventListener('click', saveGoal);
    }

    const recommendBtn = document.getElementById('recommendBtn');
    if (recommendBtn) {
        recommendBtn.addEventListener('click', getRecommendation);
    }

    const deleteModalEl = document.getElementById('deleteGoalModal');
    if (deleteModalEl) {
        deleteGoalModal = new bootstrap.Modal(deleteModalEl);
        const confirmBtn = document.getElementById('confirmDeleteGoalBtn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', executeDeleteGoal);
        }
    }
});

async function loadGoals() {
    const goalsList = document.getElementById('goalsList');
    if (!goalsList) return;

    goalsList.innerHTML = '<div class="text-center text-muted py-3"><div class="spinner-border spinner-border-sm"></div><span class="ms-2">Загрузка...</span></div>';

    const data = await apiGet('/api/goals/');
    if (!data.success) {
        goalsList.innerHTML = '<div class="text-danger small p-2">Ошибка загрузки целей</div>';
        return;
    }

    renderGoals(data.goals, goalsList);
}

function renderGoals(goals, container) {
    if (!goals || goals.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="bi bi-trophy fs-3"></i>
                <p class="mt-2 mb-0 small">Нет целей</p>
                <small>Создайте первую цель для организации задач</small>
            </div>
        `;
        return;
    }

    container.innerHTML = goals.map(goal => {
        const targetInfo = goal.target_tasks
            ? `<span class="small text-muted">${goal.completed_tasks}/${goal.target_tasks} задач</span>`
            : `<span class="small text-muted">${goal.completed_tasks}/${goal.total_tasks} задач</span>`;

        return `
        <div class="card mb-2 ${goal.is_achieved ? 'border-success' : 'border-secondary'}" id="goal-card-${goal.id}">
            <div class="card-body p-2">
                <div class="d-flex justify-content-between align-items-start mb-1">
                    <div class="fw-semibold small">
                        ${goal.is_achieved ? '<i class="bi bi-trophy-fill text-warning me-1"></i>' : ''}
                        ${escapeHtml(goal.title)}
                    </div>
                    <button class="btn btn-sm btn-link text-danger p-0" onclick="openDeleteGoalModal(${goal.id}, '${escapeAttr(goal.title)}')" title="Удалить цель">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </div>
                ${goal.description ? `<div class="text-muted small mb-1">${escapeHtml(goal.description)}</div>` : ''}
                <div class="d-flex justify-content-between align-items-center mb-1">
                    ${targetInfo}
                    <span class="badge ${goal.is_achieved ? 'bg-success' : 'bg-secondary'}">${goal.progress_percent}%</span>
                </div>
                <div class="progress" style="height: 6px;">
                    <div class="progress-bar ${goal.is_achieved ? 'bg-success' : 'bg-primary'}"
                         style="width: ${goal.progress_percent}%"></div>
                </div>
                ${goal.is_achieved ? '<div class="text-success small mt-1"><i class="bi bi-check-circle-fill me-1"></i>Цель достигнута!</div>' : ''}
            </div>
        </div>`;
    }).join('');
}

async function saveGoal() {
    const title = document.getElementById('goalTitle').value.trim();
    const description = document.getElementById('goalDescription').value.trim();
    const targetTasksEl = document.getElementById('goalTargetTasks');
    const target_tasks = targetTasksEl && targetTasksEl.value ? parseInt(targetTasksEl.value) : null;

    if (!title) {
        document.getElementById('goalTitle').classList.add('is-invalid');
        return;
    }
    document.getElementById('goalTitle').classList.remove('is-invalid');

    const payload = { title, description };
    if (target_tasks && target_tasks > 0) {
        payload.target_tasks = target_tasks;
    }

    const result = await apiPost('/api/goals/create/', payload);
    if (result.success) {
        document.getElementById('goalTitle').value = '';
        document.getElementById('goalDescription').value = '';
        if (targetTasksEl) targetTasksEl.value = '';
        document.getElementById('createGoalForm').classList.add('d-none');
        loadGoals();

        const goalSelect = document.getElementById('goalSelect');
        if (goalSelect) {
            const option = document.createElement('option');
            option.value = result.goal.id;
            option.textContent = result.goal.title;
            goalSelect.appendChild(option);
        }
    } else {
        showGoalAlert('Ошибка создания цели: ' + (result.error || 'Неизвестная ошибка'), 'danger');
    }
}

function openDeleteGoalModal(id, title) {
    pendingDeleteGoalId = id;
    const titleEl = document.getElementById('deleteGoalTitle');
    if (titleEl) titleEl.textContent = title;
    if (deleteGoalModal) deleteGoalModal.show();
}

async function executeDeleteGoal() {
    if (!pendingDeleteGoalId) return;
    const id = pendingDeleteGoalId;
    pendingDeleteGoalId = null;
    if (deleteGoalModal) deleteGoalModal.hide();

    const result = await apiPost(`/api/goals/${id}/delete/`, {});
    if (result.success) {
        const card = document.getElementById(`goal-card-${id}`);
        if (card) card.remove();

        const option = document.querySelector(`#goalSelect option[value="${id}"]`);
        if (option) option.remove();

        document.querySelectorAll(
            `.task-goal-badge[data-goal-id="${id}"], .goal-badge-container[data-goal-id="${id}"]`
        ).forEach(el => el.remove());

        const goalsList = document.getElementById('goalsList');
        if (goalsList && goalsList.querySelectorAll('.card').length === 0) {
            renderGoals([], goalsList);
        }
    }
}

async function deleteGoal(id) {
    openDeleteGoalModal(id, '');
}

async function getRecommendation() {
    const btn = document.getElementById('recommendBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Думаю...';

    const data = await apiGet('/api/tasks/recommend/');

    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-lightbulb me-1"></i>Рекомендация';

    const toastBody = document.getElementById('recommendToastBody');
    const toastEl = document.getElementById('recommendToast');

    if (!toastBody || !toastEl) return;

    if (data.task_id) {
        toastBody.innerHTML = `
            <div class="fw-semibold mb-1">${escapeHtml(data.title)}</div>
            <div class="text-muted small">${escapeHtml(data.reason)}</div>
            <div class="mt-2">
                <a href="/" class="btn btn-sm btn-warning">Перейти к доске</a>
            </div>
        `;
    } else {
        toastBody.innerHTML = `
            <div class="text-success"><i class="bi bi-check-circle me-1"></i>${escapeHtml(data.message || 'Все задачи выполнены!')}</div>
        `;
    }

    const toast = new bootstrap.Toast(toastEl, { delay: 8000 });
    toast.show();
}

function showGoalAlert(message, type) {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} fade show mt-2`;
    alert.innerHTML = message;
    const form = document.getElementById('createGoalForm');
    if (form) form.appendChild(alert);
    setTimeout(() => alert.remove(), 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/\n/g, ' ');
}
