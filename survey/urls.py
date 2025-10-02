from django.urls import include, path
from . import views

# app_name = "survey" 

urlpatterns = [
    path('__debug__/', include('debug_toolbar.urls')),
    path('', views.Index, name='Dashboard'),
    # the views need to be Change
    path('CreateSurvey', views.CreateSurvey, name='CreateSurvey'),
    path('responses', views.Responses, name='Responses'),

]

url_for_htmx = [
    path('CreateSubFile', views.CreateFile, name='CreateSubFile'),
]

urlpatterns += url_for_htmx
print(urlpatterns)