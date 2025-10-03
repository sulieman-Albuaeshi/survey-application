import time
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.db.models import Q      

from .models import Survey

# Create your views here.
def Index(request):
    context = Survey.objects.order_by('-last_updated')[:5]
    return render(request, 'index.html', {'surveys': context})

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


def SearchSurveys(request):
    query = request.GET.get('search', '').strip()
    time.sleep(3)
    if query:
        result = Survey.objects.filter(
            Q( title__icontains=query) |
            Q( description__icontains=query)
        )
    else:
        result = Survey.objects.all()

    
    return render(request, 'partials/tableContent.html', {'surveys': result})

def CallTheModal(request):
    return render(request, 'partials/Modalfile.html')

def CreateFile(request):
    filename = request.POST.get('filename')
    context = {'filename': filename}
    return render(request, 'partials/subFile.html',context)

