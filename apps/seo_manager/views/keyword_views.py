from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from ..models import Client, TargetedKeyword
from ..forms import TargetedKeywordForm  # We'll create this next

class KeywordListView(LoginRequiredMixin, ListView):
    model = TargetedKeyword
    template_name = 'seo_manager/keywords/list.html'
    context_object_name = 'keywords'

    def get_queryset(self):
        self.client = get_object_or_404(Client, pk=self.kwargs['client_id'])
        return TargetedKeyword.objects.filter(client=self.client)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = self.client
        return context

class KeywordCreateView(LoginRequiredMixin, CreateView):
    model = TargetedKeyword
    form_class = TargetedKeywordForm
    template_name = 'seo_manager/keywords/form.html'

    def get_success_url(self):
        return reverse_lazy('seo_manager:keyword_list', kwargs={'client_id': self.object.client.id})

    def form_valid(self, form):
        form.instance.client_id = self.kwargs['client_id']
        return super().form_valid(form)

class KeywordUpdateView(LoginRequiredMixin, UpdateView):
    model = TargetedKeyword
    form_class = TargetedKeywordForm
    template_name = 'seo_manager/keywords/form.html'

    def get_success_url(self):
        return reverse_lazy('seo_manager:keyword_list', kwargs={'client_id': self.object.client.id})
