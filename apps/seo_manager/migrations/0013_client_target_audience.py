# Generated by Django 4.2.9 on 2024-10-05 19:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_manager', '0012_useractivity'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='target_audience',
            field=models.TextField(blank=True, null=True),
        ),
    ]
