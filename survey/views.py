from django import forms
from django.forms import BooleanField, HiddenInput
import json
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
from django.urls import reverse
from .utility import normalize_formset_indexes, get_dashboard_surveys
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin



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

@login_required
def create_survey(request):
    template_name = 'CreateSurvey.html'

    if request.method == 'GET':
        form = SurveyForm()
        question_formset = QuestionFormSet(queryset=que.objects.none())

        context = {
            'form': form,
            'Question_formset': question_formset,
            'question_type_list': que.get_available_type_names(),
            'form_action_url': reverse('CreateSurvey'),
        }
        return render(request, template_name, context)

    form = SurveyForm(request.POST)
    question_formset = QuestionFormSet(request.POST, instance=form.instance, queryset=que.objects.none())

    if form.is_valid() and question_formset.is_valid():
        if request.POST.get('action') == 'preview':
            with transaction.atomic():
                survey = form.save(commit=False)
                survey.state = 'draft' # Previewing now saves as draft
                survey.created_by = request.user
                survey.question_count = question_formset.total_form_count()
                survey.save()
                
                question_formset.instance = survey
                question_formset.save()

            # Redirect to the dedicated preview view, passing the Edit URL as the "back" link
            preview_url = reverse('SurveyPreview', args=[survey.uuid])
            edit_url = reverse('EditSurvey', args=[survey.uuid])
            return redirect(f"{preview_url}?back_url={edit_url}")

        with transaction.atomic():
            survey = form.save(commit=False)
            action = request.POST.get('action')
            survey.state = 'published' if action == 'publish' else 'draft'
            survey.created_by = request.user
            survey.question_count = question_formset.total_form_count()
            survey.save()

            question_formset.instance = survey
            question_formset.save()

        return redirect('/Dashboard')

    return render(request, template_name, {
        'form': form,
        'Question_formset': question_formset,
        'question_type_list': que.get_available_type_names(),
        'form_action_url': reverse('CreateSurvey'),

    })

@login_required
def edit_survey(request, uuid):
    template_name = 'CreateSurvey.html'
    survey = get_object_or_404(Survey, uuid=uuid)

    if request.method == 'GET':
        form = SurveyForm(instance=survey)
        question_formset = QuestionFormSet(instance=survey, queryset=survey.questions.all())

        return render(request, template_name, {
            'form': form,
            'Question_formset': question_formset,
            'question_type_list': que.get_available_type_names(),
            'form_action_url': reverse('EditSurvey', kwargs={'uuid': survey.uuid}),
        })

    form = SurveyForm(request.POST, instance=survey)
    question_formset = QuestionFormSet(request.POST, instance=survey, queryset=survey.questions.all())

    if form.is_valid() and question_formset.is_valid():
        if request.POST.get('action') == 'preview':
            with transaction.atomic():
                updated_survey = form.save(commit=False)
                updated_survey.question_count = question_formset.total_form_count()
                updated_survey.save()

                question_formset.instance = updated_survey
                question_formset.save()

            # Redirect to the dedicated preview view, passing the Edit URL as the "back" link
            preview_url = reverse('SurveyPreview', args=[updated_survey.uuid])
            edit_url = reverse('EditSurvey', args=[updated_survey.uuid])
            return redirect(f"{preview_url}?back_url={edit_url}")

        with transaction.atomic():
            updated_survey = form.save(commit=False)
            action = request.POST.get('action')
            updated_survey.state = 'published' if action == 'publish' else 'draft'
            updated_survey.question_count = question_formset.total_form_count()
            updated_survey.save()

            question_formset.instance = updated_survey
            question_formset.save()

        return redirect('/Dashboard')

    return render(request, template_name, {
        'form': form,
        'Question_formset': question_formset,
        'question_type_list': que.get_available_type_names(),
        'form_action_url': reverse('EditSurvey', kwargs={'uuid': survey.uuid}),
    })

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
def delete_survey_confirm(request, uuid):
    """
    Renders a confirmation modal for survey deletion.
    """
    survey = get_object_or_404(Survey, uuid=uuid)
    context = {'survey': survey}
    return render(request, 'partials/Dashboard/delete_modal.html', context)

@login_required
def DeleteSurvey(request, uuid):
    item = get_object_or_404(Survey, uuid=uuid)
    item.delete()
    return redirect('/Dashboard')

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
    
    # CALL HELPER
    context = get_dashboard_surveys(request.user, request.GET, page_number)

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
    paginator = Paginator(surveys, 10)
    page = paginator.get_page(page_number)
    
    # Use get_elided_page_range for better pagination
    elided_page_range = paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)

    context = {
        'page': page,
        'elided_page_range': elided_page_range,
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
        survey.state = 'archived'
    elif survey.state == 'draft':
        survey.state = 'published'
    elif survey.state == 'archived':
        survey.state = 'draft'
        
    survey.save()

    saved_state = request.session.get('dashboard_last_state', {})
    saved_page = saved_state.get('page_number', 1)
    saved_params = saved_state.get('params', {})

    # 3. Re-fetch Data using Helper
    context = get_dashboard_surveys(request.user, saved_params, saved_page)

    # 4. Add Recent Surveys (since these might have changed order/status too)
    context['recent_surveys'] = Survey.objects.filter(created_by=request.user).order_by('-last_updated')[:4]
    
    return render(request, 'partials/Dashboard/tabel_with_recnt_survey.html', context)

@require_POST
@login_required
def ToggleSurveyStatusConfirm(request, uuid):
    """
    Renders a confirmation modal for toggling survey status.
    """
    survey = get_object_or_404(Survey, uuid=uuid, created_by=request.user)
    return render(request, 'partials/Dashboard/status_modal.html', {'survey': survey})

@login_required 
def survey_Start_View(request, uuid):
    """View to start taking the survey."""
    survey = get_object_or_404(Survey, uuid=uuid, state='published')
    questions = survey.questions.all().order_by('position')
    
    context = {
        'survey': survey,
        'questions': questions,
    }

    return render(request, 'Survey_Start.html', context)

@login_required
def survey_preview_view(request, uuid):
    """Read-only preview of a saved survey"""
    survey = get_object_or_404(Survey, uuid=uuid)
    questions = survey.questions.all().order_by('position')
    
    # Allow overriding the back link (default to Dashboard)
    back_url = request.GET.get('back_url', '/Dashboard')

    return render(request, 'Survey_preview.html', {
        'survey': survey,
        'questions': questions,
        'back_url': back_url, 
    })

@login_required
def CopySurveyView(request, uuid):
    """View to copy an existing survey."""
    original_survey = get_object_or_404(Survey, uuid=uuid)

    new_survey = Survey.objects.create(
        title=f"Copy of {original_survey.title}",
        description=original_survey.description,
        created_by=CustomUser.objects.first(),
        state='draft',
        question_count=original_survey.question_count,
    )

    # Copy questions
    for question in original_survey.questions.all():
        question.pk = None  # Clear PK to create a new instance
        question.survey = new_survey
        question.save()

    form = SurveyForm(instance=new_survey)
    question_formset = QuestionFormSet(instance=form.instance, queryset=new_survey.questions.all())

    context = {
        'form': form,
        'Question_formset': question_formset,
        'question_type_list': que.get_available_type_names(),
        'form_action_url': reverse('EditSurvey', kwargs={'uuid': new_survey.uuid}),
    }

    return render(request, 'CreateSurvey.html', context)

def survey_submit(request, uuid):
    """Submit the survey responses."""
    survey = get_object_or_404(Survey, uuid=uuid)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                response = Response.objects.create(survey=survey)
                
                for question in survey.questions.all():
                    base_key = f'question_{question.position}'
                    values = request.POST.getlist(base_key)
                    
                    if question.NAME == 'Matrix Question':
                        answer_data = {}
                        for i, row_label in enumerate(question.rows, start=1):
                            row_key = f'{row_label}_row{i}' # e.g., row-label_1_row1
                            val = request.POST.get(row_key)
                            if val:
                                answer_data[row_key] = val # Store { "Row Label": "Value" }
                        # If empty dict, set to None so validation catches it
                        if not answer_data: 
                            answer_data = None

                    elif question.NAME == 'Ranking Question':
                        if values:
                            # Save as dict where key is the rank (1-based)
                            answer_data = {str(i): val for i, val in enumerate(values[::-1], start=1)}
                        else:
                            answer_data = None

                    else:
                        if len(values) > 1:
                            answer_data = values 
                        elif len(values) == 1:
                            answer_data = values[0] # Single string handling
                        else:
                            answer_data = None
                    
                    # 2. Server-side Validation
                    if question.required and not answer_data:
                        redirect_url = reverse('Survey_Start', args=[survey.uuid])
                        return redirect(redirect_url)

                    if answer_data is not None:
                        Answer.objects.create(
                            response=response,
                            question=question,
                            answer_data=answer_data
                        )
        
        except Exception as e:
            # Handle exceptions, possibly logging or user feedback
            return HttpResponse("An error occurred while submitting the survey.", status=500)
            
        return render(request, 'Thanks.html', {'survey': survey})
