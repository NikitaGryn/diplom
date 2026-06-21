import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.conf import settings

from .agent import run_agent


class ChatView(LoginRequiredMixin, View):

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Неверный формат запроса'}, status=400)

        user_message = data.get('message', '').strip()
        if not user_message:
            return JsonResponse({'error': 'Пустое сообщение'}, status=400)

        api_key = getattr(settings, 'LLM_API_KEY', '').strip()
        if not api_key:
            return JsonResponse(
                {'error': 'API ключ не настроен. Добавьте LLM_API_KEY в .env файл.'},
                status=503,
            )

        history = request.session.get('chat_history', [])

        try:
            reply, actions = run_agent(request.user, user_message, history, api_key)
        except Exception as e:
            return JsonResponse({'error': f'Ошибка AI: {str(e)}'}, status=503)

        # Save to session
        history.append({'role': 'user', 'content': user_message})
        history.append({'role': 'assistant', 'content': reply})
        request.session['chat_history'] = history[-24:]
        request.session.modified = True

        return JsonResponse({
            'reply': reply,
            'actions': actions,
            'refresh_board': len(actions) > 0,
        })

    def delete(self, request):
        request.session['chat_history'] = []
        request.session.modified = True
        return JsonResponse({'ok': True})
