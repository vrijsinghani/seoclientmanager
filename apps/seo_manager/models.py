from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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
    business_objectives = models.JSONField(default=list, blank=True)
    target_audience = models.TextField(blank=True, null=True)
    # New field
    client_profile = models.TextField(
        help_text="Detailed 300-500 word profile of the client's business, goals, and SEO strategy",
        blank=True
    )

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
    user_email = models.EmailField()  # Add this field if it doesn't exist
    # Add the scopes attribute with a default value
    scopes = models.JSONField(default=list)

    def __str__(self):
        return f"GA Credentials for {self.client.name}"

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

class SummarizerUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.TextField()
    compressed_content = models.TextField()
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    duration = models.DurationField()
    content_token_size = models.IntegerField()
    content_character_count = models.IntegerField()
    total_input_tokens = models.IntegerField()
    total_output_tokens = models.IntegerField()
    model_used = models.CharField(max_length=100)

class UserActivity(models.Model):
    CATEGORY_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view', 'View'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.category} - {self.action}"

class TargetedKeyword(models.Model):
    PRIORITY_CHOICES = [
        (1, 'Highest'),
        (2, 'High'),
        (3, 'Medium'),
        (4, 'Low'),
        (5, 'Lowest'),
    ]

    client = models.ForeignKey(
        Client, 
        on_delete=models.CASCADE,
        related_name='targeted_keywords'
    )
    keyword = models.CharField(max_length=255)
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=3,
        help_text="Priority level for this keyword"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['client', 'keyword']
        ordering = ['priority', 'keyword']

    def __str__(self):
        return f"{self.keyword} ({self.client.name})"

class KeywordRankingHistory(models.Model):
    keyword = models.ForeignKey(
        TargetedKeyword,
        on_delete=models.CASCADE,
        related_name='ranking_history'
    )
    date = models.DateField()
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    ctr = models.FloatField(
        verbose_name="Click-Through Rate",
        help_text="Click-through rate as a decimal (e.g., 0.15 for 15%)"
    )
    average_position = models.FloatField()
    
    class Meta:
        unique_together = ['keyword', 'date']
        ordering = ['-date']
        get_latest_by = 'date'

    def __str__(self):
        return f"{self.keyword.keyword} - {self.date}"

class SEOProject(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='seo_projects'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    implementation_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    targeted_keywords = models.ManyToManyField(
        TargetedKeyword,
        related_name='related_projects'
    )
    documentation_file = models.FileField(
        upload_to='seo_projects/%Y/%m/',
        null=True,
        blank=True
    )
    initial_rankings = models.JSONField(
        default=dict,
        help_text="Snapshot of keyword rankings before project implementation"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('planned', 'Planned'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('on_hold', 'On Hold'),
        ],
        default='planned'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-implementation_date']

    def __str__(self):
        return f"{self.title} - {self.client.name}"
