from django.urls import include, path
from django.views.generic import RedirectView
from . import views

# app_name = "survey" 

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='Dashboard'), name='home'),
    path('__debug__/', include('debug_toolbar.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('Dashboard', views.Index, name='Dashboard'),
    path('Dashboard/<int:page_number>', views.Index, name='Dashboard_Page'),
    path('CreateSurvey', views.create_survey, name='CreateSurvey'),
    path('CreateSurvey/<uuid:uuid>/', views.edit_survey, name='EditSurvey'),
    path('create-survey/add-question/', views.AddQuestionFormView.as_view(), name='add_question'),
    path('survey/<uuid:uuid>', views.survey_Start_View, name='survey_start'),
    path('survey/<uuid:uuid>/preview', views.survey_preview_view, name='SurveyPreview'),
    path("survey/<uuid:uuid>/copy", views.CopySurveyView, name="Copy"),
    path('surveys/<uuid:uuid>/delete-confirm', views.delete_survey_confirm, name='DeleteSurveyConfirmModal'),
    path("surveys/<uuid:uuid>/delete", views.DeleteSurvey, name="DeleteSurvey"),
    path('survey/<uuid:uuid>/submit', views.survey_submit, name='survey_submit'),
    
    # the views need to be Change
    path('responses', views.Responses, name='Responses'),
    path('responses/<int:page_number>', views.Responses, name='Responses_Page'),
    path('responses/survey/<uuid:uuid>', views.SurveyResponseDetail, name='SurveyResponseDetail'),
    path('responses/survey/<uuid:uuid>/overview', views.SurveyResponsesOverviewTable, name='SurveyResponsesOverviewTable'),
    path('responses/survey/<uuid:uuid>/analytics', views.SurveyAnalytics, name='SurveyAnalytics'),

    # API endpoint for chart data
    path('api/survey/<uuid:uuid>/question/<int:question_id>/chart-data', views.GetChartData, name='GetChartData'),
]

url_for_htmx = [
    path("surveys/<uuid:uuid>/toggle-status", views.ToggleSurveyStatus, name="ToggleSurveyStatus"),
    path("surveys/<uuid:uuid>/toggle-status-table", views.ToggleSurveyStatusFromTable, name="ToggleSurveyStatusFromTable"),
]

urlpatterns += url_for_htmx
print(urlpatterns)