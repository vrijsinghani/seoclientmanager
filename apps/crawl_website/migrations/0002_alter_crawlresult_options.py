# Generated by Django 4.2.9 on 2024-10-06 18:03

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crawl_website', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='crawlresult',
            options={'ordering': ['-created_at']},
        ),
    ]
