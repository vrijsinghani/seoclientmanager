# Generated by Django 4.2.9 on 2024-10-17 22:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0020_tool_module_path'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='output_file',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]