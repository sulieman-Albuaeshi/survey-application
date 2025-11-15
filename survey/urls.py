from django.urls import include, path
from . import views

# app_name = "survey" 

urlpatterns = [
    path('__debug__/', include('debug_toolbar.urls')),
    path('Dashboard', views.Index, name='Dashboard'),
    path('Dashboard/<int:page_number>', views.Index, name='Dashboard_Page'),
    path('CreateSurvey', views.SurveyCreateView.as_view(), name='CreateSurvey'),
    path('create-survey/add-question/', views.AddQuestionFormView.as_view(), name='add_question'),

    # the views need to be Change
    path('responses', views.Responses, name='Responses'),
]

url_for_htmx = [
    path('CreateSubFile', views.CreateFile, name='CreateSubFile'),
    path("surveys/<uuid:uuid>/delete", views.DeleteSurvey, name="DeleteSurvey"),
]

urlpatterns += url_for_htmx
print(urlpatterns)