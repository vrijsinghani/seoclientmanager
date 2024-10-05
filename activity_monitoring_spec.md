# Activity Monitoring Framework Specification

## 1. UserActivity Model

Create a new model in `apps/seo_manager/models.py`:

```python
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
```

## 2. Update Views

Modify `apps/seo_manager/views.py` to include activity logging:

1. Create a utility function for logging activities:

```python
def log_user_activity(user, category, action, client=None, details=None):
    UserActivity.objects.create(
        user=user,
        client=client,
        category=category,
        action=action,
        details=details
    )
```

2. Update existing view functions to log activities. For example:

```python
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    log_user_activity(request.user, 'view', 'Viewed client details', client=client)
    # ... rest of the view logic
```

## 3. Activity Categorization

Activities are categorized using the `CATEGORY_CHOICES` in the `UserActivity` model. Ensure that all logged activities use appropriate categories.

## 4. Client Association

Activities are associated with clients using the `client` field in the `UserActivity` model. When logging activities related to a specific client, make sure to include the client object.

## 5. Activity Display View

Create a new view in `apps/seo_manager/views.py` to display user activities:

```python
def activity_log(request):
    activities = UserActivity.objects.all().order_by('-timestamp')
    return render(request, 'seo_manager/activity_log.html', {'activities': activities})
```

## 6. Update Templates

1. Create a new template `apps/seo_manager/templates/seo_manager/activity_log.html`:

```html
{% extends 'base.html' %}
{% load static %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <div class="col-12">
            <div class="card">
                <div class="card-header">
                    <h4 class="card-title">Activity Log</h4>
                </div>
                <div class="card-body">
                    <div class="activity-timeline">
                        {% for activity in activities %}
                            <div class="activity-item">
                                <div class="activity-content">
                                    <small class="text-muted">{{ activity.timestamp|date:"F d, Y H:i" }}</small>
                                    <p class="mt-0 mb-2">{{ activity.action }}</p>
                                    <p class="mb-0">
                                        <strong>User:</strong> {{ activity.user.username }}<br>
                                        <strong>Client:</strong> {{ activity.client.name|default:"N/A" }}<br>
                                        <strong>Category:</strong> {{ activity.get_category_display }}
                                    </p>
                                </div>
                            </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/activity_timeline.css' %}">
{% endblock %}
```

2. Update `apps/seo_manager/urls.py` to include the new activity log view:

```python
path('activity-log/', views.activity_log, name='activity_log'),
```

3. Add a link to the activity log in the main navigation menu.

## 7. Styling

Create a new CSS file `static/css/activity_timeline.css`:

```css
.activity-timeline {
    position: relative;
    padding-left: 30px;
}

.activity-timeline::before {
    content: '';
    position: absolute;
    left: 15px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #e9ecef;
    border-radius: 1px;
}

.activity-item {
    position: relative;
    padding-bottom: 30px;
}

.activity-item::before {
    content: '';
    position: absolute;
    left: -23px;
    top: 8px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #007bff;
    border: 2px solid #fff;
}

.activity-content {
    padding: 15px;
    background-color: #f8f9fa;
    border-radius: 4px;
}

.activity-content p {
    margin-bottom: 0;
}
```

## Implementation Steps

1. Create the `UserActivity` model and run migrations.
2. Implement the `log_user_activity` utility function.
3. Update existing views to log relevant activities.
4. Create the `activity_log` view.
5. Create the activity_log.html template with the "Timeline with dotted line" component.
6. Create the activity_timeline.css file for styling.
7. Update URLs and navigation menu.
8. Test the activity logging and timeline display functionality.

## Future Enhancements

1. Implement filtering and searching in the activity log view.
2. Add user-specific activity views.
3. Create an API endpoint for activity data.
4. Implement activity analytics and visualizations.
5. Add pagination to the timeline view for better performance with large datasets.
6. Implement real-time updates using WebSockets for live activity feeds.
7. Add color-coding for different activity categories in the timeline.