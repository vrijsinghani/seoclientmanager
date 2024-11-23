# Generated by Django 5.1.2 on 2024-11-22 20:14

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0026_chatmessage'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExecutionStage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stage_type', models.CharField(choices=[('task_start', 'Task Start'), ('thinking', 'Thinking'), ('tool_usage', 'Tool Usage'), ('tool_results', 'Tool Results'), ('human_input', 'Human Input'), ('completion', 'Completion')], max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('content', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('metadata', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='agents.agent')),
                ('execution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stages', to='agents.crewexecution')),
            ],
            options={
                'verbose_name': 'Execution Stage',
                'verbose_name_plural': 'Execution Stages',
                'ordering': ['created_at'],
            },
        ),
    ]