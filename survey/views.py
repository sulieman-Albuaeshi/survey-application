from django.shortcuts import render

# Create your views here.
def MySurvey(request):
    return render(request, 'mysurvey/MySurvey.html')

# Create your views here.
def index(request):
    return render(request, 'base.html')

def CreateSurvey(request):
    pass

def CallTheModal(request):
    return render(request, 'partials/Modalfile.html')

def CreateFile(request):
    filename = request.POST.get('filename')
    context = {'filename': filename}
    return render(request, 'partials/subFile.html',context)