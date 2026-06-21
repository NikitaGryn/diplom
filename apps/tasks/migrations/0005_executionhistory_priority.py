from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0004_executionhistory_nullable_durations'),
    ]

    operations = [
        migrations.AddField(
            model_name='executionhistory',
            name='priority',
            field=models.CharField(blank=True, default='medium', max_length=10),
        ),
    ]
