from django.db import models
from django.contrib.auth.models import User

class ClientGroup(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')

    def __str__(self):
        return self.name

class Client(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_hold', 'On Hold'),
    ]

    name = models.CharField(max_length=100)
    website_url = models.URLField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    group = models.ForeignKey(ClientGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='clients')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class SEOData(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='seo_data')
    date = models.DateField()
    traffic = models.IntegerField()
    keywords = models.IntegerField()
    rankings = models.JSONField()  # Store rankings as JSON

    class Meta:
        unique_together = ['client', 'date']

class AIProvider(models.Model):
    name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=255)
    model = models.CharField(max_length=100)
    parameters = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class GoogleAnalyticsCredentials(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='ga_credentials')
    view_id = models.CharField(max_length=100, blank=True, null=True)  # Allow null values
    access_token = models.TextField(blank=True, null=True)  # Allow null for service accounts
    refresh_token = models.TextField(blank=True, null=True)  # Allow null for service accounts
    token_uri = models.URLField(blank=True, null=True)  # Allow null for service accounts
    ga_client_id = models.CharField(max_length=100, blank=True, null=True)  # Allow null for service accounts
    client_secret = models.CharField(max_length=100, blank=True, null=True)  # Allow null for service accounts
    use_service_account = models.BooleanField(default=False)
    service_account_json = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"GA Credentials for {self.client.name}"

# Add this new model
class SearchConsoleCredentials(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='sc_credentials')
    property_url = models.URLField()
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_uri = models.URLField(blank=True, null=True)
    sc_client_id = models.CharField(max_length=100, blank=True, null=True)  # Renamed from client_id
    client_secret = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Search Console Credentials for {self.client.name}"
