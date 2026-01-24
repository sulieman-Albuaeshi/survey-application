from django.http import QueryDict

from survey.models import Survey
from django.core.paginator import Paginator
from django.db.models import Q, Count
from datetime import  datetime


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

    paginator = Paginator(surveys, 5)
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