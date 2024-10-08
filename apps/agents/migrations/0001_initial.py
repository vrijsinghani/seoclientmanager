# Generated by Django 4.2.9 on 2024-10-07 17:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('seo_manager', '0013_client_target_audience'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Agent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('role', models.CharField(max_length=100)),
                ('goal', models.TextField()),
                ('backstory', models.TextField()),
                ('llm', models.CharField(max_length=100)),
                ('verbose', models.BooleanField(default=False)),
                ('allow_delegation', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Crew',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('process', models.CharField(choices=[('sequential', 'Sequential'), ('hierarchical', 'Hierarchical')], default='sequential', max_length=20)),
                ('verbose', models.BooleanField(default=False)),
                ('max_rpm', models.IntegerField(blank=True, null=True)),
                ('memory', models.BooleanField(default=False)),
                ('cache', models.BooleanField(default=True)),
                ('full_output', models.BooleanField(default=False)),
                ('share_crew', models.BooleanField(default=False)),
                ('planning', models.BooleanField(default=False)),
                ('agents', models.ManyToManyField(to='agents.agent')),
            ],
        ),
        migrations.CreateModel(
            name='CrewExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inputs', models.JSONField()),
                ('outputs', models.JSONField(blank=True, null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')], default='PENDING', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='seo_manager.client')),
                ('crew', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.crew')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Tool',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('function', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField()),
                ('expected_output', models.TextField()),
                ('async_execution', models.BooleanField(default=False)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.agent')),
                ('context', models.ManyToManyField(blank=True, to='agents.task')),
                ('tools', models.ManyToManyField(blank=True, to='agents.tool')),
            ],
        ),
        migrations.CreateModel(
            name='CrewMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('execution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.crewexecution')),
            ],
        ),
        migrations.AddField(
            model_name='crew',
            name='tasks',
            field=models.ManyToManyField(to='agents.task'),
        ),
        migrations.AddField(
            model_name='agent',
            name='tools',
            field=models.ManyToManyField(blank=True, to='agents.tool'),
        ),
    ]
