from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from django.db.models import Avg
import logging
from dateutil.relativedelta import relativedelta
import json
from datetime import datetime

logger = logging.getLogger(__name__)


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

    def get_keyword_rankings_summary(self):
        """Get summary of current keyword rankings"""
        latest_rankings = KeywordRankingHistory.objects.filter(
            client=self,
            keyword__isnull=False,  # Only targeted keywords
            date=KeywordRankingHistory.objects.filter(
                client=self,
                keyword__isnull=False
            ).values('date').order_by('-date').first()['date']
        ).select_related('keyword')

        return {
            'total_keywords': latest_rankings.count(),
            'avg_position': latest_rankings.aggregate(
                Avg('average_position')
            )['average_position__avg'],
            'rankings': latest_rankings
        }

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

    def get_monthly_rankings(self, months=12):
        """Get monthly ranking history"""
        end_date = timezone.now().date()
        start_date = end_date - relativedelta(months=months)
        
        # logger.debug(
        #     f"Fetching monthly rankings for keyword '{self.keyword}' (ID: {self.id})"
        #     f"\nDate range: {start_date} to {end_date}"
        # )
        
        rankings = self.ranking_history.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        # logger.debug(f"Found {rankings.count()} ranking records")
        
        # Group by month and get the monthly record
        monthly_data = {}
        for ranking in rankings:
            month_key = ranking.date.strftime('%Y-%m')
            if month_key not in monthly_data:
                data = {
                    'date': ranking.date,
                    'position': float(ranking.average_position),
                    'impressions': int(ranking.impressions),
                    'clicks': int(ranking.clicks),
                    'ctr': float(ranking.ctr)
                }
                monthly_data[month_key] = data
                # logger.debug(
                #     f"Added data for {month_key}:"
                #     f"\nPosition: {data['position']}"
                #     f"\nImpressions: {data['impressions']}"
                #     f"\nClicks: {data['clicks']}"
                #     f"\nCTR: {data['ctr']}"
                # )
        
        result = [monthly_data[k] for k in sorted(monthly_data.keys())]
        # logger.debug(
        #     f"Returning {len(result)} months of data for {self.keyword}"
        # )
        return result

    @property
    def current_position(self):
        """Get the most recent average position"""
        latest = self.ranking_history.order_by('-date').first()
        return round(latest.average_position, 1) if latest else None

    def get_position_change(self, months=1):
        """Calculate position change over specified number of months"""
        monthly_data = self.get_monthly_rankings(months + 1)
        
        if len(monthly_data) < 2:
            return None
            
        current = monthly_data[-1]['position']
        previous = monthly_data[-2]['position']
        
        return round(previous - current, 1)

    @property
    def position_trend(self):
        """Returns trend indicator based on 30-day change"""
        change = self.get_position_change()
        if change is None:
            return 'neutral'
        if change > 0.5:  # Improved by more than 0.5 positions
            return 'up'
        if change < -0.5:  # Declined by more than 0.5 positions
            return 'down'
        return 'neutral'

    class Meta:
        unique_together = ['client', 'keyword']
        ordering = ['priority', 'keyword']

    def __str__(self):
        return f"{self.keyword} ({self.client.name})"

class KeywordRankingHistory(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='keyword_rankings'
    )
    keyword = models.ForeignKey(
        TargetedKeyword,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ranking_history'
    )
    keyword_text = models.CharField(
        max_length=255,
        help_text="Actual keyword text, useful when no TargetedKeyword reference exists"
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
        unique_together = ['client', 'keyword_text', 'date']
        ordering = ['-date']
        get_latest_by = 'date'
        indexes = [
            models.Index(fields=['-date']),  # Optimize date-based queries
            models.Index(fields=['client', '-date']),  # Optimize client+date queries
        ]

    @classmethod
    def get_rankings_for_period(cls, client, start_date, end_date, keyword=None):
        """Get rankings for a specific period"""
        query = cls.objects.filter(
            client=client,
            date__range=[start_date, end_date]
        )
        
        if keyword:
            query = query.filter(
                Q(keyword=keyword) | Q(keyword_text=keyword.keyword)
            )
            
        return query.order_by('date')

    def __str__(self):
        return f"{self.keyword_text} - {self.client.name} - {self.date}"

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

    # Add method to analyze project impact
    def analyze_impact(self):
        implementation_date = self.implementation_date
        pre_period = implementation_date - relativedelta(months=1)
        post_period = implementation_date + relativedelta(months=1)

        results = {}
        for keyword in self.targeted_keywords.all():
            rankings = keyword.ranking_history.filter(
                date__range=[pre_period, post_period]
            ).order_by('date')

            pre_avg = rankings.filter(date__lt=implementation_date).aggregate(
                Avg('average_position'))['average_position__avg']
            post_avg = rankings.filter(date__gte=implementation_date).aggregate(
                Avg('average_position'))['average_position__avg']

            results[keyword.keyword] = {
                'pre_implementation_avg': pre_avg,
                'post_implementation_avg': post_avg,
                'improvement': pre_avg - post_avg if pre_avg and post_avg else None,
                'impressions_change': self._calculate_impressions_change(rankings),
                'clicks_change': self._calculate_clicks_change(rankings)
            }

        return results




