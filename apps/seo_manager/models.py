from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from django.db.models import Avg
import logging
from dateutil.relativedelta import relativedelta
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from googleapiclient.discovery import build
import google.auth.transport.requests

logger = logging.getLogger(__name__)

# Define AuthError at the module level
class AuthError(Exception):
    """Custom exception for authentication errors"""
    pass

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
    distilled_website = models.TextField(
        help_text="Distilled version of the client's website content for SEO purposes",
        blank=True
    )
    distilled_website_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The last time the distilled website content was modified or created"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.business_objectives is None:
            self.business_objectives = []

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if self.pk:
            old_client = Client.objects.get(pk=self.pk)
            if old_client.distilled_website != self.distilled_website:
                self.distilled_website_date = timezone.now()
        else:
            if self.distilled_website:
                self.distilled_website_date = timezone.now()
        super().save(*args, **kwargs)
        
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
    view_id = models.CharField(max_length=100, blank=True, null=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_uri = models.URLField(blank=True, null=True)
    ga_client_id = models.CharField(max_length=100, blank=True, null=True)
    client_secret = models.CharField(max_length=100, blank=True, null=True)
    use_service_account = models.BooleanField(default=False)
    service_account_json = models.TextField(blank=True, null=True)
    user_email = models.EmailField()
    scopes = models.JSONField(default=list)

    def __str__(self):
        return f"GA Credentials for {self.client.name}"

    @property
    def required_scopes(self):
        return ['https://www.googleapis.com/auth/analytics.readonly']

    def get_credentials(self):
        """Returns refreshed Google Analytics credentials"""
        try:
            # First try service account if configured
            if self.use_service_account and self.service_account_json:
                logger.info(f"Using service account for {self.client.name}")
                service_account_info = json.loads(self.service_account_json)
                return service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=self.required_scopes
                )

            # Then try OAuth credentials
            # Check for required OAuth fields
            required_fields = {
                'refresh_token': self.refresh_token,
                'token_uri': self.token_uri,
                'client_id': self.ga_client_id,
                'client_secret': self.client_secret
            }
            
            # Log which fields are missing
            missing_fields = [field for field, value in required_fields.items() if not value]
            if missing_fields:
                logger.error(f"Missing OAuth fields for {self.client.name}: {', '.join(missing_fields)}")
                return None

            logger.info(f"Using OAuth credentials for {self.client.name}")
            credentials = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri,
                client_id=self.ga_client_id,
                client_secret=self.client_secret,
                scopes=self.required_scopes
            )

            # Refresh token if needed
            if not credentials.valid:
                request = google.auth.transport.requests.Request()
                credentials.refresh(request)
                self.access_token = credentials.token
                self.save(update_fields=['access_token'])
                logger.info(f"Refreshed access token for {self.client.name}")

            return credentials

        except Exception as e:
            logger.error(f"Error getting GA credentials for {self.client.name}: {str(e)}")
            return None

    def get_property_id(self):
        """Get the clean property ID without 'properties/' prefix"""
        if self.view_id:
            return self.view_id.replace('properties/', '')
        return None

    def get_service(self):
        """Returns an authenticated Analytics service"""
        try:
            credentials = self.get_credentials()
            if not credentials:
                logger.warning(f"No valid credentials available for {self.client.name}")
                return None
                
            return BetaAnalyticsDataClient(credentials=credentials)
        except Exception as e:
            logger.error(f"Error creating Analytics service for {self.client.name}: {str(e)}")
            return None

class SearchConsoleCredentials(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='sc_credentials')
    property_url = models.TextField()
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_uri = models.URLField(blank=True, null=True)
    sc_client_id = models.CharField(max_length=100, blank=True, null=True)  # Renamed from client_id
    client_secret = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Search Console Credentials for {self.client.name}"

    def get_credentials(self):
        """Returns refreshed Google OAuth2 credentials"""
        try:
            if not self.refresh_token:
                raise AuthError("No refresh token available. Reauthorization required.")

            credentials = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri,
                client_id=self.sc_client_id,
                client_secret=self.client_secret,
                scopes=['https://www.googleapis.com/auth/webmasters.readonly']
            )

            # Only refresh if token is expired or missing
            if not self.access_token or not credentials.valid:
                request = google.auth.transport.requests.Request()
                try:
                    credentials.refresh(request)
                    
                    # Update stored credentials
                    self.access_token = credentials.token
                    self.save(update_fields=['access_token'])
                    
                    logger.info(f"Successfully refreshed Search Console OAuth credentials for {self.client.name}")
                except Exception as e:
                    if 'invalid_grant' in str(e):
                        # Clear invalid credentials to force reauthorization
                        self.access_token = None
                        self.refresh_token = None
                        self.save(update_fields=['access_token', 'refresh_token'])
                        raise AuthError("Stored credentials are no longer valid. Please reauthorize Search Console access.")
                    raise

            return credentials

        except Exception as e:
            logger.error(f"Failed to refresh Search Console credentials for {self.client.name}: {str(e)}")
            raise AuthError(f"Failed to get valid Search Console credentials: {str(e)}")

    def get_service(self):
        """Returns an authenticated Search Console service"""
        try:
            credentials = self.get_credentials()
            if not credentials:
                logger.warning(f"No valid credentials available for {self.client.name}")
                return None
                
            return build('searchconsole', 'v1', credentials=credentials)
        except Exception as e:
            logger.error(f"Error creating Search Console service for {self.client.name}: {str(e)}")
            return None

    def get_property_url(self):
        """Parse and return the correct property URL format"""
        try:
            if isinstance(self.property_url, str):
                if '{' in self.property_url:
                    # Parse JSON-like string
                    data = json.loads(self.property_url.replace("'", '"'))
                    return data.get('url')  # Use get() to safely access 'url'
                return self.property_url
            elif isinstance(self.property_url, dict):
                return self.property_url.get('url')
            return self.property_url
        except Exception as e:
            logger.error(f"Error parsing property URL for {self.client.name}: {str(e)}")
            return None

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

    def get_ranking_history(self):
        """Get all ranking history entries for this keyword"""
        return KeywordRankingHistory.objects.filter(
            Q(keyword=self) | 
            Q(keyword_text=self.keyword, client=self.client)
        ).order_by('-date')

    @property
    def current_position(self):
        """Get the most recent average position"""
        latest = self.get_ranking_history().first()
        return round(latest.average_position, 1) if latest else None

    def get_position_change(self, months=1):
        """Calculate position change over specified number of months"""
        history = self.get_ranking_history()[:2]  # Get latest two entries
        if len(history) < 2:
            return None
            
        current = history[0].average_position
        previous = history[1].average_position
        
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

    @property
    def position_change(self):
        """Calculate position change from previous entry"""
        previous = KeywordRankingHistory.objects.filter(
            client=self.client,
            keyword_text=self.keyword_text,
            date__lt=self.date
        ).order_by('-date').first()
        
        if previous:
            return previous.average_position - self.average_position
        return 0

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





