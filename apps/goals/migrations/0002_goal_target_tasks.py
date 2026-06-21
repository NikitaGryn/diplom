from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('goals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='goal',
            name='target_tasks',
            field=models.PositiveIntegerField(blank=True, help_text='Целевое количество задач', null=True),
        ),
    ]
