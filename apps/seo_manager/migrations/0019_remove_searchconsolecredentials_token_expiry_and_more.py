# Generated by Django 4.2.9 on 2024-11-12 19:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_manager', '0018_searchconsolecredentials_token_expiry'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='searchconsolecredentials',
            name='token_expiry',
        ),
        migrations.AlterField(
            model_name='searchconsolecredentials',
            name='property_url',
            field=models.TextField(),
        ),
    ]