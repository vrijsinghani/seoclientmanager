from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from ..models import SEOProject, Client
from ..forms import SEOProjectForm  # We'll create this next

class ProjectListView(LoginRequiredMixin, ListView):
    model = SEOProject
    template_name = 'seo_manager/projects/list.html'
    context_object_name = 'projects'

    def get_queryset(self):
        self.client = get_object_or_404(Client, pk=self.kwargs['client_id'])
        return SEOProject.objects.filter(client=self.client)

class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = SEOProject
    template_name = 'seo_manager/projects/detail.html'
    context_object_name = 'project'

class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = SEOProject
    form_class = SEOProjectForm
    template_name = 'seo_manager/projects/form.html'

    def form_valid(self, form):
        form.instance.client_id = self.kwargs['client_id']
        return super().form_valid(form)
