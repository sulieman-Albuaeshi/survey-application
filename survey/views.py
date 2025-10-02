from django.shortcuts import render
from .models import Survey

# Create your views here.
def Index(request):
    context = Survey.objects.order_by('-last_updated')[:5]
    return render(request, 'index.html', {'surveys': context})

def Responses(request):
    return render(request, 'Responses.html')

def CreateSurvey(request):
    return render(request, 'CreateSurvey.html')

def CallTheModal(request):
    return render(request, 'partials/Modalfile.html')

def CreateFile(request):
    filename = request.POST.get('filename')
    context = {'filename': filename}
    return render(request, 'partials/subFile.html',context)

