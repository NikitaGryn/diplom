from apps.ml.ml_predictor import MLDurationPredictor


class DurationPredictor:
    """Публичный интерфейс для предсказания длительности задачи."""

    MIN_RULE_SAMPLES = 5

    def __init__(self, user):
        self.user = user
        self._ml = MLDurationPredictor(user)

    def predict(self, category, estimated_duration, priority='medium'):
        """
        Возвращает (predicted_duration, factor, has_enough_data).
        """
        predicted, factor, has_data = self._ml.predict(category, estimated_duration, priority)
        if has_data:
            return predicted, factor, True

        history = self._get_history(category)
        factors = [h.correction_factor for h in history if h.correction_factor is not None]
        if len(factors) >= self.MIN_RULE_SAMPLES:
            avg_factor = sum(factors) / len(factors)
            predicted = round(estimated_duration * avg_factor)
            return predicted, round(avg_factor, 2), True

        return estimated_duration, 1.0, False

    def predict_with_meta(self, category, estimated_duration, priority='medium'):
        """
        Расширенный вариант для API.
        """
        predicted, factor, has_data = self.predict(category, estimated_duration, priority)
        meta = self._ml.predict_with_meta(category, estimated_duration, priority)

        if has_data and meta['has_enough_data']:
            importances = self._ml.feature_importances()
            return {
                'predicted_duration': meta['predicted_duration'],
                'factor': meta['factor'],
                'has_enough_data': True,
                'model_name': meta['model_name'],
                'n_samples': meta['n_samples'],
                'feature_importances': importances,
            }

        history = self._get_history(category)
        factors = [h.correction_factor for h in history if h.correction_factor is not None]
        if len(factors) >= self.MIN_RULE_SAMPLES:
            avg_factor = sum(factors) / len(factors)
            return {
                'predicted_duration': round(estimated_duration * avg_factor),
                'factor': round(avg_factor, 2),
                'has_enough_data': True,
                'model_name': 'CorrectionFactor',
                'n_samples': len(factors),
                'feature_importances': None,
            }

        return {
            'predicted_duration': estimated_duration,
            'factor': 1.0,
            'has_enough_data': False,
            'model_name': None,
            'n_samples': meta['n_samples'],
            'feature_importances': None,
        }

    def _get_history(self, category):
        from apps.tasks.models import ExecutionHistory
        return list(
            ExecutionHistory.objects.filter(
                user=self.user,
                category=category,
            ).order_by('-completed_at')[:50]
        )
