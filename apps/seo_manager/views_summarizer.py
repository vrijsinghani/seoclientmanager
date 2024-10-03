
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from home.forms import RegistrationForm, LoginForm, UserPasswordResetForm, UserSetPasswordForm, UserPasswordChangeForm
from django.core import serializers
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordChangeView, PasswordResetConfirmView
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.conf import settings
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, RedirectView, DeleteView, View
from django.views.generic.edit import FormView
from django.utils.decorators import method_decorator
from apps.tasks.tasks import summarize_content
import mistune
from django.utils.safestring import mark_safe
from django.http import JsonResponse
from celery.result import AsyncResult
import logging
from apps.common.utils import get_models

import json  # Add this import at the top of the file
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Client, SEOData, GoogleAnalyticsCredentials, SearchConsoleCredentials, SummarizerUsage
from .services import get_analytics_service, get_analytics_data
from .google_auth import get_google_auth_flow, get_analytics_accounts_oauth, get_analytics_accounts_service_account, get_search_console_properties
from datetime import datetime, timedelta
from django.http import HttpResponse
from google_auth_oauthlib.flow import Flow
from django.urls import reverse
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError  # Add this import


@login_required
def summarize_view(request):

  models = get_models()
  logging.info(f'request.user.id: {request.user.id}')
  model_selected = settings.SUMMARIZER
  #logging.info ("Model selected: " + model_selected)
  if request.method == 'POST':

    text_to_summarize = request.POST.get('query_text_value')
    model_selected = request.POST.get('model_selected_value')
    task = summarize_content.delay(text_to_summarize, request.user.id, model_selected)
    return JsonResponse({'task_id': task.id})
  
  user = User.objects.get(id=request.user.id)
  summarizations = SummarizerUsage .objects.filter(user=user).order_by('-created_at')
  
  for summ in summarizations:
    summ.html_result = mistune.html(summ.response + '\n\n---Detail---------\n\n'+summ.compressed_content)
    
  task_result = None
  task_status = None
  model_selected =  settings.SUMMARIZER
  context = {
    'task_result': task_result,
    'task_status': task_status,
    'summarizations': summarizations,
    'models': models,
    'model_selected': model_selected
  }
  return render(request, 'pages/apps/summarize.html', context)

def task_status(request, task_id):
    current_chunk = 0
    total_chunks = 1
    task_result = AsyncResult(task_id)
    # logging.info(f"task status:{task_result.status}")
    if task_result.info is not None:
      # logging.info(f"task info:{task_result.info}")
      if task_result.state == 'SUCCESS':
          result = task_result.result
          html_result = mistune.html(result)
          return JsonResponse({'status': 'SUCCESS', 'result': html_result})
      elif task_result.state == 'FAILURE':
          error = str(task_result.result)
          return JsonResponse({'status': 'FAILURE', 'result': error})
      elif task_result.status == 'processing':
          progress = task_result.info
          current_chunk = progress.get('current_chunk', 0)
          total_chunks = progress.get('total_chunks', 0)
          return JsonResponse({'status': task_result.status, 'current': current_chunk, 'total': total_chunks})
      else:
          if task_result.status:
              return JsonResponse({'status': task_result.status})
          else:
              return JsonResponse({'status': 'PENDING'})
    else:
        return JsonResponse({'status': 'PENDING'})