# Generated by Django 4.2.9 on 2024-11-21 20:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_manager', '0020_googleanalyticscredentials_ga_property_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='googleanalyticscredentials',
            name='ga_property_id',
        ),
        migrations.AddField(
            model_name='searchconsolecredentials',
            name='service_account_json',
            field=models.TextField(blank=True, null=True),
        ),
    ]
