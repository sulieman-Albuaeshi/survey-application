from django import forms
from django.forms import BooleanField, HiddenInput
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Avg, Max, Prefetch
from django.db import transaction
from django.core.paginator import Paginator
from .models import Question as que, Survey, Response, Answer, MultiChoiceQuestion, LikertQuestion, CustomUser, Question, SectionHeader, RatingQuestion, RankQuestion, MatrixQuestion, TextQuestion
from .forms import MultiChoiceQuestionForm, RatingQuestionForm, SurveyForm,  LikertQuestionForm,  QuestionFormSet, MatrixQuestionForm, RankQuestionForm, TextQuestionForm, SectionHeaderForm, CustomUserCreationForm
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta, datetime
from django.views import View
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .utility import normalize_formset_indexes



from django.contrib.auth import login

# Create your views here.
class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('Dashboard')
    template_name = 'registration/signup.html'

    def form_valid(self, form):
        # Save user and log them in
        user = form.save()
        login(self.request, user)
        return redirect(self.success_url)



class SurveyCreateView(LoginRequiredMixin, CreateView):
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
        self.object = None
        # data = normalize_formset_indexes(request.POST.copy(), prefix="questions")

        # # Replace the request.POST with cleaned data
        # request._post = data

        form = self.get_form()
        question_formset = QuestionFormSet(request.POST, instance=self.object)

        if form.is_valid() and question_formset.is_valid():
            if request.POST.get('action') == 'preview':
                request.session['survey_backup_data'] = request.POST.copy()

                survey = form.save(commit=False)
                questions = question_formset.save(commit=False)
                
                # Sort questions by position to ensure correct order in preview
                questions.sort(key=lambda x: x.position)

                context = {
                    'survey': survey,
                    'questions': questions,
                }

                return render(request, 'Survey_preview.html', context)
            return super().post(request, *args, **kwargs)
        else:
            return super().form_invalid(form)
    

    def get(self, request, *args, **kwargs):
        # Check for backup data in session
        backup_data = request.session.get('survey_backup_data')
        if request.GET.get('action') == 'edit' and  backup_data:
            # If backup data exists, use it to pre-fill the form and formset
            form = SurveyForm(backup_data)
            question_formset = QuestionFormSet(backup_data)

            # Manually sort the forms in the formset by their 'position' field value
            # This ensures that when the user returns to edit, the questions are in the correct order
            # even if they were added out of sequence (e.g. inserted in the middle).
            def get_pos(f):
                try:
                    val = f['position'].value()
                    return int(val) if val is not None else 9999
                except (ValueError, TypeError):
                    return 9999
            
            # Sort the internal list of forms
            question_formset.forms.sort(key=get_pos)

            context ={
                'form': form,
                'Question_formset': question_formset,
                'question_type_list': que.get_available_type_names(),
            }
            return render(request, self.template_name, context)
        else:
            return super().get(request, *args, **kwargs)

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
                
                # Determine state based on user action
                action = self.request.POST.get('action')
                if action == 'publish':
                    self.object.state = 'published'
                else:
                    self.object.state = 'draft'

                self.object.created_by = self.request.user
                
                # Calculate valid questions count (excluding SectionHeader)
                valid_questions = 0
                for f in formset:
                    # check if the form is marked for deletion
                    if f.cleaned_data.get('DELETE'):
                         continue
                    # Check question type if available in cleaned_data
                    q_type = f.cleaned_data.get('question_type')
                    if q_type != 'Section Header':
                        valid_questions += 1
                        
                self.object.question_count = valid_questions
                self.object.save()
                
                # 2. Link the FormSet to the newly created Survey
                formset.instance = self.object
                
                formset.save()
                
            if 'survey_backup_data' in self.request.session:
                 del self.request.session['survey_backup_data']
            return  redirect(self.get_success_url()) # Redirects to success_url
        else:
            return self.form_invalid(form)  
        

class AddQuestionFormView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        # Get the question index (count) from the POST data.
        # This value represents the current number of questions *before* adding the new one,
        # and will be used as the index for the new formset prefix.
        question_index = int(request.POST.get('question_count_position', 0))

        data = normalize_formset_indexes(request.POST.copy(), prefix="questions")
        # Replace the request.POST with cleaned data
        request._post = data

        print("question_index:", question_index)

        question_type_name = request.POST.get('question_type')      
  
        if question_type_name not in Question.get_available_type_names():
            return HttpResponse(status=400)
        
        # Map question type names to their corresponding Model and Form classes
        ModelFormMap = {
           'Multi-Choice Question': MultiChoiceQuestionForm,
            'Likert Question': LikertQuestionForm,
            'Matrix Question': MatrixQuestionForm,
            'Rating Question': RatingQuestionForm,
            'Ranking Question': RankQuestionForm,
            'Text Question': TextQuestionForm,
            'Section Header': SectionHeaderForm,
        }

        print(question_type_name)
        FormClass = ModelFormMap[question_type_name]

        form = FormClass(
            prefix=f'questions-{question_index}', 
            initial={
                'question_type': question_type_name, 
                'position': question_index + 1,
            }
        )

        template_name = question_type_name.replace(' ', '_')
        context = {
            # 'question_count': question_index + 1, # Pass the index back if the partial needs it, though not strictly for the prefix
            'form': form,
        }

        if 'DELETE' not in form.fields:
            form.fields['DELETE'] = BooleanField(
                widget=HiddenInput, 
                required=False, 
                initial=False
            )

        return render(request, f'partials/Create_survey/Questions/{template_name}.html', context)

@login_required
def Index(request, page_number=1):
    from urllib.parse import urlencode

    # --- Session Persistence Logic ---
    FILTER_KEYS = ['search', 'state_filter', 'responses_filter', 'start_date', 'end_date']
    
    # Check if request has any filter parameters (including page via URL path)
    has_filters = any(request.GET.get(key) for key in FILTER_KEYS) or page_number > 1
    
    # If no filters provided AND it's a standard navigation (no HTMX) to page 1:
    # Try to restore from session
    if not has_filters and page_number == 1 and not request.headers.get('HX-Request'):
        saved_state = request.session.get('dashboard_last_state')
        if saved_state:
            # Construct redirect URL
            saved_page = saved_state.get('page_number', 1)
            saved_params = saved_state.get('params', {})
            
            # Use 'Dashboard_Page' or 'Dashboard' based on saved page number
            if saved_page > 1:
                url = redirect('Dashboard_Page', page_number=saved_page).url
            else:
                url = redirect('Dashboard').url
            
            # Append query parameters if any
            clean_params = {k: v for k, v in saved_params.items() if v}
            
            # Check if saved state is different from current default state
            if saved_page != 1 or clean_params:
                if clean_params:
                    url += f"?{urlencode(clean_params)}"
                return redirect(url)

    # If parameters exist (or we are just rendering the current state), save to session
    # We save even if it's the "default" state (clearing the previous state)
    # UNLESS we just restored it in the previous block (but that block returns redirect)
    current_params = {key: request.GET.get(key, '').strip() for key in FILTER_KEYS}
    
    # Save to session (only if it's not a background API call - but here it's fine)
    request.session['dashboard_last_state'] = {
        'page_number': page_number,
        'params': current_params
    }
    # --- End Session Persistence Logic ---

    query = request.GET.get('search', '').strip()
    state_filter = request.GET.get('state_filter', '').strip()
    responses_filter = request.GET.get('responses_filter', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    # Base queryset with response counts
    # We need annotate to filter by responses count
    surveys = Survey.objects.filter(created_by=request.user).annotate(
        responses_count=Count('responses')
    )

    # 1. Apply Date Filter (based on last_updated)
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            surveys = surveys.filter(last_updated__date__gte=start_date_obj)
        except ValueError:
            pass # Ignore invalid date format
            
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            # Add one day to include the end date itself
            surveys = surveys.filter(last_updated__date__lte=end_date_obj)
        except ValueError:
            pass # Ignore invalid date format

    # 2. Apply State Filter
    if state_filter and state_filter.lower() in ['draft', 'published', 'archived', 'closed']:
         surveys = surveys.filter(state=state_filter.lower())
    
    # 3. Apply Responses Count Filter
    if responses_filter == 'has_responses':
        surveys = surveys.filter(responses_count__gt=0)
    elif responses_filter == 'no_responses':
        surveys = surveys.filter(responses_count=0)

    # 4. Apply Search Query
    if query:
        surveys = surveys.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )
    
    surveys = surveys.order_by('-last_updated')

    paginator = Paginator(surveys, 5)
    page = paginator.get_page(page_number)

    context = {
        'page': page,
        'query': query,
        'state_filter': state_filter,
        'responses_filter': responses_filter,
        'start_date': start_date,
        'end_date': end_date,
    }

    is_htmx = request.headers.get('HX-Request') == 'true'

    if is_htmx:
        return render(request, 'partials/Dashboard/table_with_oob_pagination.html', context)

    # For initial page loads, add any extra context needed.
    # We fetch fresh recent surveys so they are NOT affected by the search query
    context['recent_surveys'] = Survey.objects.filter(created_by=request.user).order_by('-last_updated')[:4]
    return render(request, 'index.html', context)

@login_required
def Responses(request, page_number=1):
    """Main responses view showing all surveys with response counts and filters"""
    from urllib.parse import urlencode
    
    # --- Session Persistence Logic ---
    FILTER_KEYS = ['search', 'state_filter', 'responses_filter', 'start_date', 'end_date']
    
    # Check if request has any filter parameters (including page via URL path)
    has_filters = any(request.GET.get(key) for key in FILTER_KEYS) or page_number > 1
    
    # If no filters provided AND it's a standard navigation (no HTMX) to page 1:
    # Try to restore from session
    if not has_filters and page_number == 1 and not request.headers.get('HX-Request'):
        saved_state = request.session.get('responses_last_state')
        if saved_state:
            # Construct redirect URL
            saved_page = saved_state.get('page_number', 1)
            saved_params = saved_state.get('params', {})
            
            # Use 'Responses_Page' or 'Responses' based on saved page number
            if saved_page > 1:
                url = redirect('Responses_Page', page_number=saved_page).url
            else:
                url = redirect('Responses').url
            
            # Append query parameters if any
            # Filter out empty strings to keep URL clean, though saved params likely have values
            clean_params = {k: v for k, v in saved_params.items() if v}
            
            # Check if saved state is different from current default state
            if saved_page != 1 or clean_params:
                if clean_params:
                    url += f"?{urlencode(clean_params)}"
                return redirect(url)

    # If parameters exist (or we are just rendering the current state), save to session
    # We save even if it's the "default" state (clearing the previous state)
    # UNLESS we just restored it in the previous block (but that block returns redirect)
    
    current_params = {key: request.GET.get(key, '').strip() for key in FILTER_KEYS}
    
    # Save to session (only if it's not a background API call - but here it's fine)
    request.session['responses_last_state'] = {
        'page_number': page_number,
        'params': current_params
    }
    
    # --- End Session Persistence Logic ---

    # Get filters and search query
    query = request.GET.get('search', '').strip()

    state_filter = request.GET.get('state_filter', '').strip()
    responses_filter = request.GET.get('responses_filter', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    
    print(f"DEBUG: query='{query}', state='{state_filter}', responses='{responses_filter}'")

    # Base queryset with response counts
    surveys = Survey.objects.filter(created_by=request.user).annotate(
        responses_count=Count('responses')
    )
    
    # 0. Apply Date Filter (based on last_updated)
    from datetime import datetime
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            surveys = surveys.filter(last_updated__date__gte=start_date_obj)
        except ValueError:
            pass # Ignore invalid date format
            
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            # Add one day to include the end date itself
            surveys = surveys.filter(last_updated__date__lte=end_date_obj)
        except ValueError:
            pass # Ignore invalid date format
    
    # 1. Apply State Filter
    if state_filter in ['published', 'draft', 'closed']:
        surveys = surveys.filter(state=state_filter)
    
    # 2. Apply Responses Count Filter
    if responses_filter == 'has_responses':
        surveys = surveys.filter(responses_count__gt=0)
    elif responses_filter == 'no_responses':
        surveys = surveys.filter(responses_count=0)
    
    # 3. Apply Search Query
    if query:
        surveys = surveys.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )
    
    surveys = surveys.order_by('-last_updated')
    
    # Get recent surveys with responses (not affected by search/filters for the card section)
    recent_surveys_with_responses = Survey.objects.filter(created_by=request.user).annotate(
        responses_count=Count('responses')
    ).filter(responses_count__gt=0).order_by('-last_updated')[:4]
    
    # Pagination
    paginator = Paginator(surveys, 5)
    page = paginator.get_page(page_number)
    
    context = {
        'page': page,
        'query': query,
        'state_filter': state_filter,
        'responses_filter': responses_filter,
        'start_date': start_date,
        'end_date': end_date,
        'recent_surveys': recent_surveys_with_responses,
    }
    
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if is_htmx:
        # عند طلب htmx، نرسل فقط الجزء الذي يحتاج إلى التحديث، وهو الجدول وشريط التنقل
        # هذا الملف هو الذي يحتوي على الحاوية (#responses-table-and-pagination-container)
        return render(request, 'partials/Responses/responses_table_body.html', context)
    
    return render(request, 'Responses.html', context)

@login_required
def SurveyResponseDetail(request, uuid):
    """Detailed view of responses for a specific survey"""
    survey = get_object_or_404(Survey, uuid=uuid, created_by=request.user)
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
    
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if is_htmx:
        # عند طلب htmx، نرسل فقط الجزء الذي يحتاج إلى التحديث (الجدول وشريط التنقل)
        return render(request, 'partials/SurveyResponseDetail/survey_responses_table_and_pagination.html', context)
    
    return render(request, 'SurveyResponseDetail.html', context)

@login_required
def SurveyAnalytics(request, uuid):
    """Analytics and charts for a specific survey"""
    survey = get_object_or_404(Survey, uuid=uuid, created_by=request.user)
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
            
        elif isinstance(question, RatingQuestion):
            rating_question = RatingQuestion.objects.get(pk=question.pk)
            distribution = rating_question.get_rating_distribution()
            average = rating_question.get_average_rating()
            question_data['distribution'] = distribution
            question_data['average'] = average
            question_data['chart_type'] = 'bar'
            
        elif isinstance(question, RankQuestion):
            rank_question = RankQuestion.objects.get(pk=question.pk)
            distribution = rank_question.get_average_ranks()
            question_data['distribution'] = distribution
            question_data['chart_type'] = 'bar'

        elif isinstance(question, MatrixQuestion):
            mx_question = MatrixQuestion.objects.get(pk=question.pk)
            distribution = mx_question.get_matrix_distribution()
            question_data['distribution'] = distribution
            # Matrix is special; chart.js needs stacked bar
            question_data['chart_type'] = 'stacked-bar'
        
        analytics_data.append(question_data)
    
    context = {
        'survey': survey,
        'analytics_data': analytics_data,
        'total_responses': survey.response_count,
    }
    
    return render(request, 'SurveyAnalytics.html', context)

@login_required
def GetChartData(request, uuid, question_id):
    """API endpoint to get chart data for a specific question"""
    survey = get_object_or_404(Survey, uuid=uuid, created_by=request.user)
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
        
    elif isinstance(question, RatingQuestion):
        rating_question = RatingQuestion.objects.get(pk=question.pk)
        distribution = rating_question.get_rating_distribution()
        data['labels'] = [str(k) for k in distribution.keys()]
        data['values'] = list(distribution.values())
        data['average'] = rating_question.get_average_rating()
        
    elif isinstance(question, RankQuestion):
        rank_question = RankQuestion.objects.get(pk=question.pk)
        distribution = rank_question.get_average_ranks()
        # distribution is {option: avg_rank}
        # We might want to sort by rank (which is already sorted in the method)
        data['labels'] = list(distribution.keys())
        data['values'] = list(distribution.values())
        data['y_label'] = 'Average Rank Position (Lower is Better)'

    elif isinstance(question, MatrixQuestion):
        mx_question = MatrixQuestion.objects.get(pk=question.pk)
        distribution = mx_question.get_matrix_distribution()
        # Complex struct for stacked bar:
        # labels = Rows
        # datasets = Columns (each col is a stack)
        data['labels'] = mx_question.rows
        data['datasets'] = []
        
        # We need a list of values for each column across all rows
        for col in mx_question.columns:
            col_values = []
            for row in mx_question.rows:
                 # get count for this cell (row, col)
                 count = distribution.get(row, {}).get(col, 0)
                 col_values.append(count)
            
            data['datasets'].append({
                'label': col,
                'data': col_values
            })
        data['is_stacked'] = True
    
    return JsonResponse(data)

# HTMX 
@require_POST
@login_required
def DeleteSurvey(request, uuid):
    item = get_object_or_404(Survey, uuid=uuid, created_by=request.user)
    item.delete()
    return HttpResponse(status=200)
@login_required

def SurveyResponsesOverviewTable(request, uuid):
    """
    Returns the HTML for the responses overview table (numeric values).
    """
    survey = get_object_or_404(Survey, uuid=uuid, created_by=request.user)
    # Exclude SectionHeader from the questions list
    questions = survey.questions.instance_of(Question).not_instance_of(SectionHeader).order_by('position')
    
    responses_list = Response.objects.filter(survey=survey).order_by('-created_at').prefetch_related('answers__question')
    
    # Pagination
    paginator = Paginator(responses_list, 20)  # Show 20 responses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Prepare data for the table
    table_data = []
    for response in page_obj:
        row = {'response': response, 'cells': []}
        # Map question_id to answer object for quick lookup
        response_answers = {a.question_id: a for a in response.answers.all()}
        
        for question in questions:
            answer = response_answers.get(question.id)
            if answer:
                # Use the new method we added to the models
                numeric_value = question.get_numeric_answer(answer.answer_data)
                row['cells'].append(numeric_value)
            else:
                row['cells'].append("-")
        table_data.append(row)
        
    context = {
        'survey': survey,
        'questions': questions,
        'table_data': table_data,
        'page_obj': page_obj,
    }
    return render(request, 'partials/SurveyResponseDetail/responses_overview_table.html', context)

@require_POST
@login_required
def ToggleSurveyStatus(request, uuid):
    """Toggle survey status between 'draft' and 'published'."""
    survey = get_object_or_404(Survey, uuid=uuid, created_by=request.user)
    
    if survey.state == 'published':
        survey.state = 'draft'
    else:
        survey.state = 'published'
        
    survey.save()
    
    # If the request is from the dashboard card, we might want to update the whole card or specific parts.
    # Here we return the button and using OOB swap, we can update the status badge as well.
    
    return render(request, 'partials/Dashboard/survey_toggle_button.html', {'survey': survey})

def survey_Start_View(request, uuid):
    """View to start taking the survey."""
    survey = get_object_or_404(Survey, uuid=uuid, state='published')
    questions = survey.questions.all().order_by('position')
    
    context = {
        'survey': survey,
        'questions': questions,
    }

    return render(request, 'Survey_Start.html', context)