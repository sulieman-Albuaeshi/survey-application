from django.urls import include, path
from . import views

# app_name = "survey" 

urlpatterns = [
    path('__debug__/', include('debug_toolbar.urls')),
    path('', views.MySurvey, name='Dashboard'),
    # the views need to be Change 
    path('CreateSurvey', views.MySurvey, name='CreateSurvey'),
    path('responses', views.MySurvey, name='Responses'),

]

url_for_htmx = [
    path('CreateSubFile', views.CreateFile, name='CreateSubFile'),
]

urlpatterns += url_for_htmx
print(urlpatterns)