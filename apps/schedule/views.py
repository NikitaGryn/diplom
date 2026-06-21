import io
import json as json_lib
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from apps.tasks.models import Task


class ScheduleView(LoginRequiredMixin, View):
    def get(self, request):
        week_offset = int(request.GET.get('week', 0))

        all_tasks = Task.objects.filter(
            user=request.user,
            status__in=[Task.STATUS_NEW, Task.STATUS_PLANNED, Task.STATUS_IN_PROGRESS],
        ).select_related('goal')

        today = timezone.localtime(timezone.now()).date()
        monday = today - timedelta(days=today.weekday())
        week_days = [monday + timedelta(days=i + week_offset * 7) for i in range(7)]

        tasks_data = []
        for task in all_tasks:
            tasks_data.append({
                'id': task.id,
                'title': task.title,
                'priority_color': task.priority_color,
                'scheduled_start': task.scheduled_start.isoformat() if task.scheduled_start else None,
                'scheduled_end': task.scheduled_end.isoformat() if task.scheduled_end else None,
                'estimated_duration': task.estimated_duration or 60,
                'status': task.status,
                'deadline': task.deadline.isoformat() if task.deadline else None,
            })

        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({
                'success': True,
                'tasks': tasks_data,
                'today': today.isoformat(),
                'weekOffset': week_offset,
            })

        return render(request, 'schedule/index.html', {
            'all_tasks': all_tasks,
            'today': today,
            'week_days': week_days,
            'week_offset': week_offset,
            'tasks_json': json_lib.dumps(tasks_data, ensure_ascii=False),
        })


class SchedulePDFView(LoginRequiredMixin, View):

    HOURS = list(range(7, 24))
    DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

    def get(self, request):
        week_offset = int(request.GET.get('week', 0))

        today = timezone.localtime(timezone.now()).date()
        monday = today - timedelta(days=today.weekday())
        week_days = [monday + timedelta(days=i + week_offset * 7) for i in range(7)]

        tasks = Task.objects.filter(
            user=request.user,
            scheduled_start__isnull=False,
            status__in=[Task.STATUS_NEW, Task.STATUS_PLANNED, Task.STATUS_IN_PROGRESS],
        )

        # Индекс: (date, hour) -> title
        slot_map = {}
        for task in tasks:
            local_start = timezone.localtime(task.scheduled_start)
            key = (local_start.date(), local_start.hour)
            slot_map[key] = task.title

        # Регистрируем шрифт с поддержкой кириллицы
        import os
        font_path = os.path.join(os.path.dirname(__file__), 'DejaVuSans.ttf')
        # Fallback — берём из системы Windows
        if not os.path.exists(font_path):
            font_path = r'C:\Windows\Fonts\arial.ttf'
        try:
            pdfmetrics.registerFont(TTFont('CustomFont', font_path))
            font_name = 'CustomFont'
        except Exception:
            font_name = 'Helvetica'

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            leftMargin=10*mm, rightMargin=10*mm,
            topMargin=12*mm, bottomMargin=12*mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('title', fontName=font_name, fontSize=14, spaceAfter=4)
        sub_style   = ParagraphStyle('sub',   fontName=font_name, fontSize=9,  textColor=colors.grey, spaceAfter=8)
        cell_style  = ParagraphStyle('cell',  fontName=font_name, fontSize=7.5, leading=10)
        head_style  = ParagraphStyle('head',  fontName=font_name, fontSize=8,  alignment=1)

        first = week_days[0].strftime('%d.%m.%Y')
        last  = week_days[-1].strftime('%d.%m.%Y')

        story = [
            Paragraph(f'Расписание на неделю', title_style),
            Paragraph(f'{first} — {last}', sub_style),
        ]

        # Заголовок таблицы
        header_row = [Paragraph('', head_style)]
        for i, day in enumerate(week_days):
            label = f"{self.DAY_NAMES[i]}\n{day.strftime('%d.%m')}"
            header_row.append(Paragraph(label, head_style))

        table_data = [header_row]

        for hour in self.HOURS:
            row = [Paragraph(f'{hour}:00', cell_style)]
            for day in week_days:
                title = slot_map.get((day, hour), '')
                row.append(Paragraph(title, cell_style))
            table_data.append(row)

        page_w = landscape(A4)[0] - 20*mm
        time_col = 12*mm
        day_col  = (page_w - time_col) / 7

        col_widths = [time_col] + [day_col] * 7
        row_heights = [10*mm] + [8*mm] * len(self.HOURS)

        table = Table(table_data, colWidths=col_widths, rowHeights=row_heights)

        # Стили таблицы
        today_cols = [i+1 for i, d in enumerate(week_days) if d == today]

        ts = TableStyle([
            ('FONTNAME',       (0, 0), (-1, -1), font_name),
            ('FONTSIZE',       (0, 0), (-1, -1), 8),
            ('BACKGROUND',     (0, 0), (-1, 0),  colors.HexColor('#b0c4de')),
            ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.HexColor('#1a1a2e')),
            ('ALIGN',          (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',          (1, 1), (-1, -1), 'LEFT'),
            ('GRID',           (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('BACKGROUND',     (0, 1), (0, -1),  colors.HexColor('#ecf0f1')),
            ('FONTNAME',       (0, 1), (0, -1),  font_name),
            ('TEXTCOLOR',      (0, 1), (0, -1),  colors.HexColor('#555555')),
        ])

        # Подсветка сегодняшнего дня
        for col in today_cols:
            ts.add('BACKGROUND', (col, 0), (col, 0),  colors.HexColor('#4a90d9'))
            ts.add('BACKGROUND', (col, 1), (col, -1), colors.HexColor('#eaf4ff'))

        # Подсветка ячеек с задачами
        for (date, hour), _ in slot_map.items():
            if date in week_days:
                col = week_days.index(date) + 1
                row = self.HOURS.index(hour) + 1
                ts.add('BACKGROUND', (col, row), (col, row), colors.HexColor('#d4edda'))
                ts.add('TEXTCOLOR',  (col, row), (col, row), colors.HexColor('#155724'))

        table.setStyle(ts)
        story.append(table)

        doc.build(story)
        buf.seek(0)

        filename = f'schedule_{first}-{last}.pdf'
        response = HttpResponse(buf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
