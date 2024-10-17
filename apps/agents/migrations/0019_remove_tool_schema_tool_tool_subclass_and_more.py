# Generated by Django 4.2.9 on 2024-10-16 13:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0018_task_crew_execution_alter_crew_input_variables_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tool',
            name='schema',
        ),
        migrations.AddField(
            model_name='tool',
            name='tool_subclass',
            field=models.CharField(default='none', max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='tool',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='tool',
            name='name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='tool',
            name='tool_class',
            field=models.CharField(max_length=255),
        ),
    ]