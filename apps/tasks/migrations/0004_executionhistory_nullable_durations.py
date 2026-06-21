from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0003_executionhistory_task_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='executionhistory',
            name='estimated_duration',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='executionhistory',
            name='actual_duration',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='executionhistory',
            name='correction_factor',
            field=models.FloatField(null=True, blank=True),
        ),
    ]
