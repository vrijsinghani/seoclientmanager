# Generated by Django 4.2.9 on 2024-10-07 03:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crawl_website', '0002_alter_crawlresult_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='crawlresult',
            name='result_file_path',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
