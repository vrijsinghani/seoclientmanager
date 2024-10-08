# Generated by Django 4.2.9 on 2024-10-08 04:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0005_remove_tool_function'),
    ]

    operations = [
        migrations.AddField(
            model_name='crew',
            name='config',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='embedder',
            field=models.JSONField(default={'provider': 'openai'}),
        ),
        migrations.AddField(
            model_name='crew',
            name='function_calling_llm',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='language',
            field=models.CharField(default='English', max_length=50),
        ),
        migrations.AddField(
            model_name='crew',
            name='language_file',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='manager_agent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_crews', to='agents.agent'),
        ),
        migrations.AddField(
            model_name='crew',
            name='manager_callbacks',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='manager_llm',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='output_log_file',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='planning_llm',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='prompt_file',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='step_callback',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='crew',
            name='task_callback',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
