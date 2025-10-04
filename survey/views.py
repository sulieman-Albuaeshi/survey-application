import time
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.db.models import Q      
from django.core.paginator import Paginator

from .models import Survey



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
        return render(request, 'partials/table_with_oob_pagination.html', context)

    # For initial page loads, add any extra context needed.
    context['recent_surveys'] = survey_list[:4]
    return render(request, 'index.html', context)


def Responses(request):
    return render(request, 'Responses.html')

def CreateSurvey(request):
    return render(request, 'CreateSurvey.html')




# HTMX 

@require_http_methods(["DELETE"])
def DeleteSurvey(request, pk):
    if(request.method == 'DELETE'):
        item = get_object_or_404(Survey, pk=pk)
        item.delete()
        return HttpResponse(status=200)
    return HttpResponse(status=405)

def CallTheModal(request):
    return render(request, 'partials/Modalfile.html')

def CreateFile(request):
    filename = request.POST.get('filename')
    context = {'filename': filename}
    return render(request, 'partials/subFile.html',context)

