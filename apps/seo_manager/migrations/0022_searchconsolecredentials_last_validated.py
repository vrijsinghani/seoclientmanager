# Generated by Django 4.2.9 on 2024-11-25 16:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_manager', '0021_remove_googleanalyticscredentials_ga_property_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='searchconsolecredentials',
            name='last_validated',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
