from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.views.generic.edit import FormView
from ..models import KeywordRankingHistory, TargetedKeyword
from ..forms import RankingImportForm  # We'll create this next

class RankingHistoryView(LoginRequiredMixin, ListView):
    model = KeywordRankingHistory
    template_name = 'seo_manager/rankings/history.html'
    context_object_name = 'rankings'

    def get_queryset(self):
        self.keyword = get_object_or_404(TargetedKeyword, pk=self.kwargs['keyword_id'])
        return KeywordRankingHistory.objects.filter(keyword=self.keyword)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['keyword'] = self.keyword
        return context

class RankingImportView(LoginRequiredMixin, FormView):
    template_name = 'seo_manager/rankings/import.html'
    form_class = RankingImportForm

    def form_valid(self, form):
        # Handle the import process
        form.process_import(self.request.user)
        return super().form_valid(form)
