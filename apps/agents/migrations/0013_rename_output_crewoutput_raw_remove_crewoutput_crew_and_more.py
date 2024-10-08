# Generated by Django 4.2.9 on 2024-10-10 18:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0012_crewmessage_agent_alter_crewmessage_execution'),
    ]

    operations = [
        migrations.RenameField(
            model_name='crewoutput',
            old_name='output',
            new_name='raw',
        ),
        migrations.RemoveField(
            model_name='crewoutput',
            name='crew',
        ),
        migrations.RemoveField(
            model_name='crewoutput',
            name='run_result',
        ),
        migrations.AddField(
            model_name='crewoutput',
            name='execution',
            field=models.OneToOneField(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='crew_output', to='agents.crewexecution'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='crewoutput',
            name='json_dict',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crewoutput',
            name='pydantic',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='crewoutput',
            name='token_usage',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
