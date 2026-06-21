let currentWeekOffset = typeof SERVER_WEEK_OFFSET !== 'undefined' ? SERVER_WEEK_OFFSET : 0;
let scheduleTasksData = [];
let draggingTaskId = null;

document.addEventListener('DOMContentLoaded', () => {
    const dataEl = document.getElementById('scheduleData');
    if (dataEl) {
        try {
            scheduleTasksData = JSON.parse(dataEl.textContent);
        } catch(e) {
            scheduleTasksData = [];
        }
    }

    renderAll();

    document.getElementById('prevWeekBtn')?.addEventListener('click', () => {
        currentWeekOffset--;
        fetchWeek();
    });
    document.getElementById('nextWeekBtn')?.addEventListener('click', () => {
        currentWeekOffset++;
        fetchWeek();
    });

    setInterval(fetchWeek, 30000);
});

async function fetchWeek() {
    try {
        const resp = await fetch(`/schedule/?week=${currentWeekOffset}`, {
            headers: { 'Accept': 'application/json', 'X-CSRFToken': getCsrfToken() }
        });
        const data = await resp.json();
        if (data.success) {
            scheduleTasksData = data.tasks;
            renderAll();
        }
    } catch(e) {
        console.error('Failed to fetch week data', e);
    }
}

function getWeekDays() {
    const today = new Date(SERVER_TODAY);
    const day = today.getDay();
    const diff = today.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(today);
    monday.setDate(diff + currentWeekOffset * 7);
    monday.setHours(0, 0, 0, 0);

    const days = [];
    for (let i = 0; i < 7; i++) {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);
        days.push(d);
    }
    return days;
}

function renderAll() {
    const days = getWeekDays();
    updateWeekLabel(days);
    renderGrid(days);
    renderTaskSidebar();
}

function updateWeekLabel(days) {
    const label = document.getElementById('weekLabel');
    if (!label) return;
    const first = days[0];
    const last = days[6];
    const fmt = (d) => d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
    label.textContent = `${fmt(first)} — ${fmt(last)}`;
}

function renderGrid(days) {
    const grid = document.getElementById('scheduleGrid');
    if (!grid) return;

    const now = new Date();
    const todayStr = new Date(SERVER_TODAY).toDateString();

    const hours = [];
    for (let h = 7; h < 24; h++) hours.push(h);

    let html = '<div class="table-responsive"><table class="table table-bordered table-dark table-sm mb-0" style="min-width:700px">';

    html += '<thead><tr><th style="width:55px" class="text-center text-muted small align-middle">Время</th>';
    days.forEach(day => {
        const isToday = day.toDateString() === todayStr;
        const dayName = day.toLocaleDateString('ru-RU', { weekday: 'short' });
        const dayDate = day.toLocaleDateString('ru-RU', { day: 'numeric', month: 'numeric' });
        html += `<th class="text-center small ${isToday ? 'bg-primary bg-opacity-25' : ''}">
            <div>${dayName}</div><div class="text-muted" style="font-size:0.75em">${dayDate}</div>
        </th>`;
    });
    html += '</tr></thead><tbody>';

    hours.forEach(hour => {
        html += '<tr style="height:70px">';
        html += `<td class="text-center text-muted align-middle p-0" style="font-size:0.75em;width:48px">${hour}:00</td>`;

        days.forEach(day => {
            const cellDt = new Date(day);
            cellDt.setHours(hour, 0, 0, 0);
            const isPast = cellDt < now;
            const isToday = day.toDateString() === todayStr;
            const dateStr = localDateStr(day);

            const cellTasks = scheduleTasksData.filter(t => {
                if (!t.scheduled_start) return false;
                const ts = new Date(t.scheduled_start);
                return localDateStr(ts) === dateStr && ts.getHours() === hour;
            });

            let cellClass = 'p-1 position-relative align-top';
            if (isPast) cellClass += ' bg-dark';
            else if (isToday) cellClass += ' bg-primary bg-opacity-10';

            const dropAttrs = isPast ? '' :
                `ondragover="event.preventDefault();this.classList.add('drop-hover')"
                 ondragleave="this.classList.remove('drop-hover')"
                 ondrop="dropTask(event,'${dateStr}',${hour});this.classList.remove('drop-hover')"`;

            html += `<td class="${cellClass}" ${dropAttrs} data-date="${dateStr}" data-hour="${hour}">`;

            if (isPast) {
                html += `<div style="position:absolute;inset:0;background:rgba(0,0,0,0.25);pointer-events:none;"></div>`;
            }

            cellTasks.forEach(task => {
                const c = pclr(task.priority_color);
                const catIcon = CATEGORY_ICONS[task.category] || 'three-dots';
                const catName = CATEGORY_LABELS[task.category] || '';
                const durText = task.estimated_duration ? `${task.estimated_duration}м` : '';
                const deadlineText = task.deadline
                    ? new Date(task.deadline).toLocaleString('ru-RU', {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'})
                    : '';
                html += `<div class="gcell-task" draggable="true" ondragstart="dragStart(event,${task.id})"
                              style="border-left:3px solid ${c.border};"
                              title="${escapeAttr(task.title)}">
                    <div class="gcell-title">${escapeHtml(task.title)}</div>
                    <div class="gcell-meta">
                        ${catName ? `<span class="gcell-badge"><i class="bi bi-${catIcon} me-1"></i>${escapeHtml(catName)}</span>` : ''}
                        ${durText ? `<span class="gcell-badge"><i class="bi bi-hourglass-split me-1"></i>${durText}</span>` : ''}
                        ${deadlineText ? `<span class="gcell-badge text-warning"><i class="bi bi-alarm me-1"></i>${deadlineText}</span>` : ''}
                    </div>
                </div>`;
            });

            html += '</td>';
        });

        html += '</tr>';
    });

    html += '</tbody></table></div>';
    grid.innerHTML = html;
}

const PRIORITY_LABELS = { high: 'Высокий', medium: 'Средний', low: 'Низкий' };
const CATEGORY_LABELS = { study: 'Учёба', work: 'Работа', household: 'Быт', health: 'Здоровье', personal: 'Личное', other: 'Другое' };
const CATEGORY_ICONS  = { study: 'book', work: 'briefcase', household: 'house', health: 'heart-pulse', personal: 'person', other: 'three-dots' };

const PCOLOR = {
    danger:    { bg: 'rgba(220,53,69,0.18)',   border: '#dc3545', pill: '#ff6b7a', text: '#ffb3ba' },
    warning:   { bg: 'rgba(255,193,7,0.13)',   border: '#ffc107', pill: '#ffd740', text: '#ffe082' },
    success:   { bg: 'rgba(25,135,84,0.16)',   border: '#198754', pill: '#20c997', text: '#5eead4' },
    secondary: { bg: 'rgba(108,117,125,0.15)', border: '#6c757d', pill: '#adb5bd', text: '#ced4da' },
};

function pclr(priorityColor) {
    return PCOLOR[priorityColor] || PCOLOR.secondary;
}

function renderTaskSidebar() {
    const container = document.getElementById('taskSidebarList');
    if (!container) return;

    const tasks = scheduleTasksData;
    if (tasks.length === 0) {
        container.innerHTML = '<div class="text-muted small text-center py-3"><i class="bi bi-check-circle me-1"></i>Нет задач</div>';
        return;
    }

    container.innerHTML = tasks.map(t => {
        const c = pclr(t.priority_color);
        const isScheduled = !!t.scheduled_start;
        const catIcon = CATEGORY_ICONS[t.category] || 'three-dots';
        const catName = CATEGORY_LABELS[t.category] || t.category || '';
        const priorityLabel = PRIORITY_LABELS[t.priority] || '';

        const timeRow = isScheduled
            ? `<div class="scard-time scheduled"><i class="bi bi-calendar-check-fill"></i>${new Date(t.scheduled_start).toLocaleString('ru-RU',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</div>`
            : `<div class="scard-time unscheduled"><i class="bi bi-clock-dotted"></i>Не запланировано</div>`;

        const durChip = t.estimated_duration
            ? `<span class="scard-chip"><i class="bi bi-hourglass-split"></i>${t.estimated_duration}м</span>`
            : '';
        const catChip = catName
            ? `<span class="scard-chip"><i class="bi bi-${catIcon}"></i>${escapeHtml(catName)}</span>`
            : '';
        const deadlineRow = t.deadline
            ? `<div class="scard-time" style="color:#ffc107"><i class="bi bi-alarm"></i>${new Date(t.deadline).toLocaleString('ru-RU', {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'})}</div>`
            : '';

        return `<div class="scard mb-2" draggable="true" ondragstart="dragStart(event,${t.id})"
                     style="border-left:3px solid ${c.border};background:${c.bg};${isScheduled ? 'opacity:0.65' : ''}"
                     title="${escapeAttr(t.title)}">
            <div class="scard-header">
                <span class="scard-priority-dot" style="background:${c.pill}"></span>
                <span class="scard-priority-label" style="color:${c.pill}">${escapeHtml(priorityLabel)}</span>
            </div>
            <div class="scard-title">${escapeHtml(t.title)}</div>
            <div class="scard-chips">${catChip}${durChip}</div>
            ${timeRow}
            ${deadlineRow}
        </div>`;
    }).join('');
}

function dragStart(event, taskId) {
    draggingTaskId = taskId;
    event.dataTransfer.setData('text/plain', String(taskId));
    event.dataTransfer.effectAllowed = 'move';
}

async function dropTask(event, dateStr, hour) {
    event.preventDefault();
    const taskId = draggingTaskId || event.dataTransfer.getData('text/plain');
    draggingTaskId = null;
    if (!taskId) return;

    // localDt строится в локальном времени браузера, toISOString() даёт UTC для сервера
    const localDt = new Date(`${dateStr}T${String(hour).padStart(2, '0')}:00:00`);
    const scheduledStart = localDt.toISOString();

    const result = await apiPost(`/api/tasks/${taskId}/reschedule/`, {
        scheduled_start: scheduledStart,
    });

    if (result.success) {
        const task = scheduleTasksData.find(t => t.id == taskId);
        if (task) {
            task.scheduled_start = result.scheduled_start || scheduledStart;
            task.scheduled_end = result.scheduled_end || null;
        }
        renderAll();
    } else {
        showScheduleAlert(result.error || 'Не удалось перепланировать', 'danger');
    }
}

function showScheduleAlert(message, type) {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
    alert.style.zIndex = '9999';
    alert.style.minWidth = '300px';
    alert.innerHTML = `${escapeHtml(message)}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    document.body.appendChild(alert);
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 300);
    }, 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function getCsrfToken() {
    const name = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
        const [k, v] = c.trim().split('=');
        if (k === name) return decodeURIComponent(v);
    }
    return '';
}

function localDateStr(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

async function apiPost(url, data) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify(data),
    });
    return resp.json();
}
