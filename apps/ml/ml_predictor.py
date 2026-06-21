import numpy as np

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder


class MLDurationPredictor:

    MIN_SAMPLES = 10

    PRIORITY_MAP = {'high': 3, 'medium': 2, 'low': 1}

    ALL_CATEGORIES = ['study', 'work', 'household', 'health', 'personal', 'other']

    def __init__(self, user):
        self.user = user
        self._model = None
        self._category_encoder = None
        self._n_samples = 0
        self._model_name = None

    def _load_history(self):
        from apps.tasks.models import ExecutionHistory
        return list(
            ExecutionHistory.objects.filter(
                user=self.user,
                estimated_duration__isnull=False,
                actual_duration__isnull=False,
            ).order_by('-completed_at')[:500]
        )

    def _make_encoder(self, categories_in_data):
        """Создать LabelEncoder, гарантированно включающий все известные категории."""
        enc = LabelEncoder()
        all_cats = list(set(self.ALL_CATEGORIES) | set(categories_in_data))
        enc.fit(all_cats)
        return enc

    def _encode_category(self, category):
        if self._category_encoder is None:
            return 0
        try:
            return int(self._category_encoder.transform([category])[0])
        except ValueError:
            return 0

    def _build_features(self, estimated_duration, priority, category):
        return [
            float(estimated_duration),
            float(self.PRIORITY_MAP.get(priority, 2)),
            float(self._encode_category(category)),
        ]

    def train(self):
        """Обучить модель на истории выполнения. Возвращает True если успешно."""
        history = self._load_history()
        self._n_samples = len(history)

        if self._n_samples < self.MIN_SAMPLES:
            return False

        categories = [h.category for h in history]
        self._category_encoder = self._make_encoder(categories)

        X = np.array([
            self._build_features(
                h.estimated_duration,
                h.priority or 'medium',
                h.category,
            )
            for h in history
        ], dtype=float)

        y = np.array([h.actual_duration for h in history], dtype=float)

        if self._n_samples >= 50:
            self._model = RandomForestRegressor(
                n_estimators=100,
                min_samples_leaf=3,
                random_state=42,
            )
            self._model_name = 'RandomForest'
        else:
            self._model = LinearRegression()
            self._model_name = 'LinearRegression'

        self._model.fit(X, y)
        return True

    def predict(self, category, estimated_duration, priority='medium'):
        """
        Возвращает (predicted_duration, factor, has_enough_data).
        Совместим с интерфейсом старого DurationPredictor.
        """
        if self._model is None:
            trained = self.train()
            if not trained:
                return estimated_duration, 1.0, False

        features = np.array(
            [self._build_features(estimated_duration, priority, category)],
            dtype=float,
        )
        predicted = max(1, round(float(self._model.predict(features)[0])))
        factor = round(predicted / estimated_duration, 2) if estimated_duration else 1.0
        return predicted, factor, True

    def predict_with_meta(self, category, estimated_duration, priority='medium'):
        """
        Расширенный вариант для API — возвращает также имя модели и кол-во образцов.
        """
        predicted, factor, has_data = self.predict(category, estimated_duration, priority)
        return {
            'predicted_duration': predicted,
            'factor': factor,
            'has_enough_data': has_data,
            'model_name': self._model_name,
            'n_samples': self._n_samples,
        }

    def feature_importances(self):
        """
        Возвращает dict {'estimated_duration': ..., 'priority': ..., 'category': ...}
        или None если модель не RandomForest.
        """
        if not isinstance(self._model, RandomForestRegressor):
            return None
        names = ['estimated_duration', 'priority', 'category']
        return {n: round(float(v), 3) for n, v in zip(names, self._model.feature_importances_)}
