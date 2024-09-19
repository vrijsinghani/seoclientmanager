# Generated by Django 4.2.9 on 2024-09-18 22:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_manager', '0005_rename_property_id_googleanalyticscredentials_view_id_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='googleanalyticscredentials',
            name='access_token',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='googleanalyticscredentials',
            name='client_secret',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='googleanalyticscredentials',
            name='ga_client_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='googleanalyticscredentials',
            name='refresh_token',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='googleanalyticscredentials',
            name='token_uri',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='googleanalyticscredentials',
            name='view_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
