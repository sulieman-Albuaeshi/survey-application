from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Avg
from django.db import transaction
from django.core.paginator import Paginator
from .models import Question as que, Survey, Response, Answer, MultiChoiceQuestion, LikertQuestion, CustomUser, Question
from .forms import MultiChoiceQuestionForm, SurveyForm,  LikertQuestionForm,  QuestionFormSet
from django.contrib.contenttypes.models import ContentType
from django.views import View
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView
from django.shortcuts import redirect
from .utility import normalize_formset_indexes


# Create your views here.
class SurveyCreateView(CreateView):
    model = Survey
    form_class = SurveyForm
    template_name = 'CreateSurvey.html'
    success_url = '/Dashboard'  

    def get_context_data(self, **kwargs):
        """
        Adds the formset to the template context.
        """
        context = super().get_context_data(**kwargs)
        context['question_type_list'] = que.get_available_type_names()

        if self.request.POST:
            # If submitting, bind Context to the formset


            context['Question_formset'] = QuestionFormSet(self.request.POST)
        else:
            # If GET, create an empty formset
            context['Question_formset'] = QuestionFormSet()

        return context

    def post(self, request, *args, **kwargs):
        data = request.POST.copy()  # make POST mutable

        data = normalize_formset_indexes(data, prefix="questions")

        # Replace the request.POST with cleaned data
        request._post = data

        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        """
            Called if the SurveyForm is valid. 
            We must also validate and save the FormSet here.
        """
        context = self.get_context_data()
        formset = context['Question_formset']

        if formset.is_valid():
            # Use a transaction to ensure Survey and Questions are saved together
            # or rolled back if something fails.
            with transaction.atomic():
                # 1. Save the Survey (Parent)
                self.object = form.save(commit=False)
                self.object.created_by = CustomUser.objects.first()
                self.object.question_count = formset.total_form_count()
                self.object.save()
                
                # 2. Link the FormSet to the newly created Survey
                formset.instance = self.object
                
                formset.save()
                
            return  redirect(self.get_success_url()) # Redirects to success_url
        else:
            return self.form_invalid(form)  
        

class AddQuestionFormView(View):
    def post(self, request, *args, **kwargs):
        # Get the question index (count) from the POST data.
        # This value represents the current number of questions *before* adding the new one,
        # and will be used as the index for the new formset prefix.
        question_count_position = request.POST.get('question_count_position')

        # to get the count of the question even if there question been deled 
        question_index_str = request.POST.get('question_count')

        question_index = int(question_index_str) if question_index_str else 0

        question_type_name = request.POST.get('question_type')      
  
        if question_type_name not in Question.get_available_type_names():
            return HttpResponse(status=400)
        
        # Map question type names to their corresponding Model and Form classes
        ModelFormMap = {
           'Multi-Choice Question': MultiChoiceQuestionForm,
            'Likert Question': LikertQuestionForm,
        }

        FormClass = ModelFormMap[question_type_name]

        form = FormClass(
            prefix=f'questions-{question_index - 1}', 
            initial={
                'question_type': question_type_name, 
                'position': question_index,
            }
        )

        template_name = question_type_name.replace(' ', '_')
        context = {
            'question_count': question_count_position, # Pass the index back if the partial needs it, though not strictly for the prefix
            'form': form,
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
        'is_responses_page': False, # Explicitly set for Dashboard
    }

    is_htmx = request.headers.get('HX-Request') == 'true'

    if is_htmx:
        return render(request, 'partials/Dashboard/table_with_oob_pagination.html', context)

    # For initial page loads, add any extra context needed.
    context['recent_surveys'] = survey_list[:4]
    return render(request, 'index.html', context)

def Responses(request, page_number=1):
    """Main responses view showing all surveys with response counts"""
    query = request.GET.get('search', '').strip()
    
    # Get surveys with response counts
    surveys = Survey.objects.annotate(
        responses_count=Count('responses')
    ).filter(state='published')
    
    if query:
        surveys = surveys.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )
    
    surveys = surveys.order_by('-last_updated')
    
    # Get recent surveys with responses
    recent_surveys_with_responses = surveys.filter(responses_count__gt=0)[:10]
    
    # Pagination
    paginator = Paginator(surveys, 10)
    page = paginator.get_page(page_number)
    
    context = {
        'page': page,
        'query': query,
        'recent_surveys': recent_surveys_with_responses,
        'is_responses_page': True, # Added for sidebar consistency
    }
    
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if is_htmx:
        return render(request, 'partials/Responses/responses_table_body.html', context)
    
    return render(request, 'Responses.html', context)

def SurveyResponseDetail(request, uuid):
    """Detailed view of responses for a specific survey"""
    survey = get_object_or_404(Survey, uuid=uuid)
    responses = Response.objects.filter(survey=survey).order_by('-created_at')
    
    # Pagination for responses
    page_number = request.GET.get('page', 1)
    paginator = Paginator(responses, 20)
    page = paginator.get_page(page_number)
    
    # Get statistics
    total_responses = responses.count()
    
    context = {
        'survey': survey,
        'responses': page,
        'total_responses': total_responses,
        'page': page,
    }
    
    return render(request, 'SurveyResponseDetail.html', context)

def SurveyAnalytics(request, uuid):
    """Analytics and charts for a specific survey"""
    survey = get_object_or_404(Survey, uuid=uuid)
    questions = survey.questions.all()
    
    # Prepare analytics data for each question
    analytics_data = []
    
    for question in questions:
        question_data = {
            'question': question,
            'type': type(question).__name__,
        }
        
        if isinstance(question, MultiChoiceQuestion):
            # Get distribution for multiple choice
            mc_question = MultiChoiceQuestion.objects.get(pk=question.pk)
            distribution = mc_question.get_answer_distribution()
            question_data['distribution'] = distribution
            question_data['chart_type'] = 'bar'
            
        elif isinstance(question, LikertQuestion):
            # Get rating distribution and average
            likert_question = LikertQuestion.objects.get(pk=question.pk)
            distribution = likert_question.get_rating_distribution()
            average = likert_question.get_average_rating()
            question_data['distribution'] = distribution
            question_data['average'] = average
            question_data['chart_type'] = 'bar'
        
        analytics_data.append(question_data)
    
    context = {
        'survey': survey,
        'analytics_data': analytics_data,
        'total_responses': survey.response_count,
    }
    
    return render(request, 'SurveyAnalytics.html', context)

def GetChartData(request, uuid, question_id):
    """API endpoint to get chart data for a specific question"""
    survey = get_object_or_404(Survey, uuid=uuid)
    question = get_object_or_404(que, pk=question_id)
    
    data = {
        'labels': [],
        'values': [],
        'question_label': question.label,
    }
    
    if isinstance(question, MultiChoiceQuestion):
        mc_question = MultiChoiceQuestion.objects.get(pk=question.pk)
        distribution = mc_question.get_answer_distribution()
        data['labels'] = list(distribution.keys())
        data['values'] = list(distribution.values())
        
    elif isinstance(question, LikertQuestion):
        likert_question = LikertQuestion.objects.get(pk=question.pk)
        distribution = likert_question.get_rating_distribution()
        data['labels'] = [str(k) for k in distribution.keys()]
        data['values'] = list(distribution.values())
        data['average'] = likert_question.get_average_rating()
    
    return JsonResponse(data)

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