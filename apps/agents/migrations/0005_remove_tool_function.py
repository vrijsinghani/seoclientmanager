# Generated by Django 4.2.9 on 2024-10-07 21:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0004_tool_schema_tool_tool_class'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tool',
            name='function',
        ),
    ]
