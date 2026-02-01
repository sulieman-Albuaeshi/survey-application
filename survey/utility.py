from django.http import QueryDict

from survey.models import Survey
from django.core.paginator import Paginator
from django.db.models import Q, Count
from datetime import  datetime
from .models import SectionHeader, Response, LikertQuestion, MultiChoiceQuestion, MatrixQuestion, RankQuestion, Answer, RatingQuestion
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import seaborn as sns
import matplotlib.pyplot as plt
import io
import urllib, base64

def normalize_formset_indexes( data: QueryDict, prefix: str):
    """
    Convert any question indexes (0,5,20...) → continuous (0,1,2...).
    Example:
        questions-0-title
        questions-4-title
    becomes:
        questions-0-title
        questions-1-title
    """
    new_data = data.copy()

    new_data = dict()
    new_index = 0
    old_index = None
    for key, value in data.items():
        if key.startswith(prefix + "-") and "-" in key[len(prefix)+1:]:
            index = key.split("-")[1]
            if old_index is None:
                old_index = index
            if  index != old_index :
                old_index = index
                new_index += 1  

            if key == prefix + "-" + str(index) + "-" + "position":
                new_data[prefix+"-" + str(new_index) + "-" + "position"] = new_index + 1
                continue

            # Handle field names that might contain hyphens (join the rest of the parts)
            field_name = "-".join(key.split("-")[2:])
            new_data[prefix+"-" + str(new_index) + "-" + field_name] = value
        else:
            new_data[key] = value

    # Update the TOTAL_FORMS to reflect the actual number of normalized forms
    # new_index is 0-based, so count is new_index + 1 if strictly sequential, 
    # but new_index increments only on change. 
    
    # Calculation: new_index is the *last* index used. 
    # If the loop ran at least once, count is new_index + 1.
    # If loop never ran (no forms), count is 0.
    
    # Note: This simple logic assumes at least one form exists if the loop entered.
    # A safer way is to count unique indices encountered.
    
    # However, since we are just fixing the immediate issues:
    if old_index is not None:
         new_data[f"{prefix}-TOTAL_FORMS"] = new_index + 1
    else:
         new_data[f"{prefix}-TOTAL_FORMS"] = 0
         
    return new_data

def get_dashboard_surveys(user, params, page_number=1):
    """
    Reusable logic to filter surveys and return pagination data.
    """
    query = params.get('search', '').strip()
    state_filter = params.get('state_filter', '').strip()
    responses_filter = params.get('responses_filter', '').strip()
    start_date = params.get('start_date', '').strip()
    end_date = params.get('end_date', '').strip()

    surveys = Survey.objects.filter(created_by=user).annotate(
        responses_count=Count('responses')
    )

    # 1. Date Filter
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            surveys = surveys.filter(last_updated__date__gte=start_date_obj)
        except ValueError:
            pass
            
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            surveys = surveys.filter(last_updated__date__lte=end_date_obj)
        except ValueError:
            pass

    # 2. State Filter
    if state_filter and state_filter.lower() in ['draft', 'published', 'archived', 'closed']:
         surveys = surveys.filter(state=state_filter.lower())

    # 3. Responses Filter
    if responses_filter == 'has_responses':
        surveys = surveys.filter(responses_count__gt=0)
    elif responses_filter == 'no_responses':
        surveys = surveys.filter(responses_count=0)

    # 4. Search
    if query:
        surveys = surveys.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )

    surveys = surveys.order_by('-last_updated')

    paginator = Paginator(surveys, 10)
    page = paginator.get_page(page_number)
    elided_page_range = paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)

    return {
        'page': page,
        'elided_page_range': elided_page_range,
        # Return params back so template inputs are populated
        'query': query,
        'state_filter': state_filter,
        'responses_filter': responses_filter,
        'start_date': start_date,
        'end_date': end_date,
    }

def get_header_table(survey, format_type, questions_id: list = None):
    """Helper to get headers for the table."""
    header = [ 'Respondent', 'Submitted At']
    questions = survey.questions.all().order_by('position').select_related('polymorphic_ctype')
   
    # 2. Database Filter (if IDs provided)
    if questions_id:
        questions = questions.filter(id__in=questions_id)

    data_questions = [q for q in questions if not isinstance(q, SectionHeader)]

    for q in data_questions:
        # Build Header
        if format_type == "raw":
            header.append(q.label)
        else:
            if isinstance(q, (LikertQuestion, MultiChoiceQuestion)):
                for option in q.options:
                    header.append(f"{q.label} [{option}]")
            elif isinstance(q, MatrixQuestion):
                for row in q.rows:
                    for col in q.columns:
                        header.append(f"{q.label} [{row} - {col}]")
            elif isinstance(q, RankQuestion):
                for op in q.options:
                    header.append(f"{q.label} [{op}]")
            else:
                header.append(q.label)

    return header, data_questions

def get_survey_data_by_sections(survey, format_type='raw', responses=None):     
    """Helper to organize data by survey sections."""
    sections_struct = []
    
    # 1. Group questions by section
    current_section = {"title": f"{survey.title} / Start", "questions": []}
    sections_struct.append(current_section)
    
    all_questions = survey.questions.all().select_related('polymorphic_ctype').order_by('position')
    
    for q in all_questions:
        if isinstance(q, SectionHeader):
            current_section = {"title": f"{survey.title} / {q.label}", "questions": []}
            sections_struct.append(current_section)
        else:
            current_section["questions"].append(q)
            
    # Remove empty sections
    sections_struct = [s for s in sections_struct if s["questions"]]
    
    # 2. Build data for each section
    if responses is None:
        responses = Response.objects.filter(survey=survey).prefetch_related('answers').order_by('-created_at')

    results = []
    
    for section in sections_struct:
        title = section['title']
        questions = section['questions']
        
        # Headers
        header = ['Respondent', 'Submitted At']
        
        if format_type == 'numeric':
            for q in questions:
                # IMPORTANT: Polymorphic 'q' required for attribute access (options, rows, etc.)
                if q.NAME in ["Likert Question", "Multi-Choice Question"]:
                    for option in q.options:
                        header.append(f"{q.label} [{option}]")
                elif q.NAME == "Matrix Question":
                    for row in q.rows:
                        for col in q.columns:
                            header.append(f"{q.label} [{row} - {col}]")
                elif q.NAME == "Ranking Question":
                    for op in q.options:
                        header.append(f"{q.label} [{op}]")
                else:
                    header.append(q.label)
        else:
            header.extend([q.label for q in questions])

        section_rows = []
        for resp in responses:
            base_info = [
                resp.respondent.username if resp.respondent else 'Anonymous',
                resp.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ]
            
            answers_map = {ans.question_id: ans for ans in resp.answers.all()}
            
            row_cells = []
            for q in questions:
                ans = answers_map.get(q.id)
                val = ans.answer_data if ans else None

                if format_type == 'numeric':
                    row_data = q.get_numeric_answer(val)
                    if isinstance(row_data, list):
                        row_cells.extend(row_data)
                    else:
                        row_cells.append(row_data)     
                else:
                    if isinstance(val, list):
                         row_cells.append(" | ".join([str(v) for v in val]))
                    elif isinstance(val, dict):
                         # Format dicts nicely (e.g. for Matrix or Ranking)
                         formatted_items = []
                         for k, v in val.items():
                             formatted_items.append(f"{k}: '{v}'")
                         row_cells.append(" | ".join(formatted_items))
                    else:
                        row_cells.append(val)

            section_rows.append(base_info + row_cells)

        results.append({
            'title': title,
            'header': header,
            'rows': section_rows
        })
        
    return results

def get_survey_export_data(survey, format_type='raw', responses=None, questions_id: list = None):
    """Helper to generate rows for survey data export/view."""

    header, data_questions = get_header_table(survey, format_type, questions_id)
      

    # Optimized Data Fetching: Prefetch answers to avoid N+1 queries
    if responses is None:
        responses = Response.objects.filter(survey=survey).prefetch_related('answers').order_by('-created_at')
    
    rows = []
    for resp in responses:
        row = [
            resp.respondent.username if resp.respondent else 'Anonymous',
            resp.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ]
        
        answers_map = {ans.question_id: ans for ans in resp.answers.all()}
        
        for q in data_questions:
            ans = answers_map.get(q.id)
            val = ans.answer_data if ans else None

            if format_type == 'numeric':
                row_data = q.get_numeric_answer(val)
                if isinstance(row_data, list):
                    row.extend(row_data)
                else:
                    row.append(row_data)     
            else:
                if isinstance(val, list):
                     row.append(" | ".join([str(v) for v in val]))
                elif isinstance(val, dict):
                     # Format dicts nicely (e.g. for Matrix or Ranking)
                     formatted_items = []
                     for k, v in val.items():
                         formatted_items.append(f"{k}: {v}")
                     row.append(" | ".join(formatted_items))
                else:
                    row.append(val)
        rows.append(row)        
        
    return header, rows, data_questions

def organize_survey_sections(survey):
    """
    Organize survey questions into sections based on SectionHeader questions.
    Returns a list of section dictionaries.
    """
    all_questions = survey.questions.all().order_by('position')
    sections = []
    # Create a default "General" or first section
    current_section = {'id': 'initial', 'label': 'General / Introduction', 'questions': []}
    sections.append(current_section)
    
    for q in all_questions:
        if isinstance(q, SectionHeader):
            # Start a new section
            current_section = {'id': str(q.id), 'label': q.label, 'questions': []}
            sections.append(current_section)
        else:
            # Add to current section
            current_section['questions'].append(q)
            
    # Remove empty initial section if the first question is a SectionHeader
    if not sections[0]['questions'] and len(sections) > 1:
        sections.pop(0)
    
    return sections

def get_question_analytics(question):
    """
    Calculate and return analytics data for a single question.
    """
    data = {
        'question': question,
        'type': type(question).__name__,
        'total_question_answers': Answer.objects.filter(question=question).count()
    }
    
    # Polymorphic handling - optimization: use 'question' directly if it's already the child instance
    # (Django Polymorphic handles this if QuerySet was polymorphic, otherwise check type)
    
    if isinstance(question, MultiChoiceQuestion):
        data['distribution'] = question.get_answer_distribution()
        data['chart_type'] = 'bar'
        
    elif isinstance(question, LikertQuestion):
        data.update(question.get_statistic())
        data['distribution'] = question.get_rating_distribution()
        data['chart_type'] = 'bar'
        
    elif isinstance(question, RatingQuestion):
        data.update(question.get_statistic())
        data['distribution'] = question.get_rating_distribution()
        data['average'] = question.get_average_rating()
        data['chart_type'] = 'bar'
        
    elif isinstance(question, RankQuestion):
        data['distribution'] = question.get_average_ranks()
        data['chart_type'] = 'bar'
        
    elif isinstance(question, MatrixQuestion):
        distribution = question.get_matrix_distribution()
        stats = question.get_row_statistics()
        
        rows_data = []
        for row, cols in distribution.items():
            row_stat = stats.get(row, {'mean': 0, 'median': 0, 'interpretation': 'N/A', 't_test': 0})
            rows_data.append({
                'label': row,
                'cols': cols,
                'mean': row_stat['mean'],
                'median': row_stat['median'],
                'interpretation': row_stat.get('interpretation', 'N/A'),
                't_stat': row_stat.get('t_stat', 0)
            })

        data['matrix_rows'] = rows_data
        data['columns'] = question.columns
        data['chart_type'] = 'stacked-bar'
        
    return data

def get_correlation_table(survey, questions_id: list = None):
    head, rows, _ = get_survey_export_data(survey, format_type='numeric', questions_id=questions_id)

    # If not enough rows or columns, we can't do correlation
    if not rows or len(head) < 2:
        return None


    # head is [Col1, Col2, ...]
    # rows is [[val1, val2...], [val1, val2...]]
    df = pd.DataFrame(rows, columns=head)
    
    # Clean data: Remove non-numeric columns and convert
    cols_to_drop = ['Respondent', 'Submitted At']
    df_clean = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors='ignore')
    df_clean = df_clean.apply(pd.to_numeric, errors='coerce')
    df_clean = df_clean.dropna(axis=1, how='all') # Drop empty cols
    df_clean = df_clean.fillna(0)
    
    # Need at least 2 columns with variance for correlation
    if df_clean.shape[1] < 2:
        return None

    # ---------------------------------------------------------
    # 2. CALCULATE CORRELATION
    # ---------------------------------------------------------
    correlation_matrix = df_clean.corr().fillna(0)
    
    if correlation_matrix.empty:
        return None

    # ---------------------------------------------------------
    # 3. DYNAMIC PLOTTING CONFIGURATION
    # ---------------------------------------------------------
    num_vars = len(correlation_matrix.columns)
    
    # Define settings based on dataset size
    # Reduced figsize to increase relative font visibility
    is_large = num_vars > 12 
    
    if is_large:
        plt.figure(figsize=(16, 14)) # was (25, 20) - making it smaller makes text relatively larger
        annot_size = 9               # slightly larger font
        fmt = ".1f"
        rotation = 90
        x_label_alignment = 'center'
    else:
        plt.figure(figsize=(10, 8))  # was (12, 10)
        annot_size = 11              # larger font
        fmt = ".2f"
        rotation = 45
        x_label_alignment = 'right'

    sns.set_context("paper", font_scale=1.2) # Scale up all fonts
    
    try:
        heatmap = sns.heatmap(
            correlation_matrix, 
            annot=True, 
            fmt=fmt, 
            cmap='YlGnBu', 
            linewidths=0.5, 
            linecolor='white',
            cbar=True,
            annot_kws={"size": annot_size}
        )
        
        plt.title('Survey Correlation Matrix', fontsize=16, pad=20)
        
        # Adjust labels
        plt.xticks(rotation=rotation, fontsize=10, ha=x_label_alignment)
        plt.yticks(rotation=0, fontsize=10)
        plt.tight_layout()

        # ---------------------------------------------------------
        # 4. SAVE TO BUFFER (Base64)
        # ---------------------------------------------------------
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        string = base64.b64encode(buffer.read()).decode('utf-8')
        
    finally:
        # Clear memory
        plt.close()

        return string
