from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.db.models import Q      
from django.db import transaction
from django.core.paginator import Paginator
from .models import Question as que
from .models import CustomUser, Survey, MultiChoiceQuestion, LikertQuestion
from .forms import MultiChoiceQuestionForm, SurveyForm, MultiFormset
from django.views import View
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView
from django.shortcuts import redirect
 
# Create your views here.
class SurveyCreateView(CreateView):
    model = Survey
    form_class = SurveyForm
    template_name = 'CreateSurvey.html'
    success_url = '/Dashboard'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['question_type_list'] = que.get_available_type_names()
        context['question_count'] = 0 
        print(self.request.POST)
        if self.request.POST:
            context["multi_formset"] = MultiFormset(self.request.POST, prefix="multi")
            # context["likert_formset"] = LikertFormset(self.request.POST, prefix="likert")
        else:
            context["multi_formset"] = MultiFormset(prefix="multi")
            # context["likert_formset"] = LikertFormset(prefix="likert")

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        # print("context",context)
        multi_formset = context["multi_formset"]
        # likert_formset = context["likert_formset"]

        if not multi_formset.is_valid():
            print("errors : ",multi_formset.errors)
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.created_by = CustomUser.objects.first()
            self.object.question_count = len(multi_formset)
            self.object.save()

            for form in multi_formset:
                if form.cleaned_data:
                    question = form.save(commit=False)
                    question.survey = self.object
                    question.save()
        
        print(context['multi_formset'].errors)
        return redirect('Dashboard')


        

class AddQuestionFormView(View):
    def post(self, request, *args, **kwargs):
        # Get the question index (count) from the POST data.
        # This value represents the current number of questions *before* adding the new one,
        # and will be used as the index for the new formset prefix.
        question_index_str = request.POST.get('question_count')
        question_index = int(question_index_str) if question_index_str else 0
        print("koko : ", request.POST)
        print(f"Received question_count from frontend: {question_index}")

        question_type_name = request.POST.get('question_type')

        # Map question type names to their respective form classes
        form_map = {
            "Multi-Choice Question": MultiChoiceQuestionForm(prefix=f"multi-{question_index - 1}"),
            # "Likert Question": forms.LikertQuestionForm, # Now that LikertQuestionForm is defined
        }
        
        if question_type_name not in [MultiChoiceQuestion.NAME, LikertQuestion.NAME]:
            return HttpResponse("Invalid question type provided.", status=400)

        template_name = question_type_name.replace(' ', '_')
        context = {
            'form': form_map[question_type_name],
            'question_count': question_index, # Pass the index back if the partial needs it, though not strictly for the prefix
            'question_type_name': question_type_name, # Also pass this for potential frontend logic

        }
        return render(request, f'partials/Create_survey/Questions/{template_name}.html', context)

def Index(request, page_number=1):
    query = request.GET.get('search', '').strip()

    if query:
        survey_list = Survey.objects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        ).order_by('-last_updated')
    else:
        survey_list = Survey.objects.order_by('-last_updated')

    paginator = Paginator(survey_list, 5)
    page = paginator.get_page(page_number)

    context = {
        'page': page,
        'query': query, # Add this
    }

    is_htmx = request.headers.get('HX-Request') == 'true'

    if is_htmx:
        return render(request, 'partials/Dashboard/table_with_oob_pagination.html', context)

    # For initial page loads, add any extra context needed.
    context['recent_surveys'] = survey_list[:4]
    return render(request, 'index.html', context)

def Responses(request):
    return render(request, 'Responses.html')

# HTMX 
@require_POST
def DeleteSurvey(request, uuid):
    item = get_object_or_404(Survey, uuid=uuid)
    item.delete()
    return HttpResponse(status=200)

def CallTheModal(request):
    return render(request, 'partials/Modalfile.html')

def CreateFile(request):
    filename = request.POST.get('filename')
    context = {'filename': filename}
    return render(request, 'partials/subFile.html',context)