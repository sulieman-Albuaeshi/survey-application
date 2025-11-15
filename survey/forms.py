from django import forms
from django.forms import formset_factory
from . import models


class SurveyForm(forms.ModelForm):
    class Meta:
        model = models.Survey
        fields = ['title', 'description', 'shuffle_questions', 'anonymous_responses']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input input-primary ', 'placeholder': 'e.g. Customer Satisfaction'}),
            'description': forms.Textarea(attrs={'class': 'textarea textarea-primary w-full h-32', 'placeholder': 'e.g. This survey is about customer satisfaction.'}),
            'shuffle_questions': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'anonymous_responses': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
        }

class MultiChoiceQuestionForm(forms.ModelForm):
    class Meta:
        model = models.MultiChoiceQuestion
        fields = ['label', 'helper_text', 'required' ,'options', 'allow_multiple', 'position','randomize_options', 'show_as_dropdown', 'show_as_rank_Question']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'input input-md input-primary w-full', 'placeholder': 'Enter the label of the question'}),
            'helper_text': forms.TextInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': 'Enter the helper text of the question'}),
            'required': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'options': forms.HiddenInput(),
            'position': forms.HiddenInput(),
            'allow_multiple': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'randomize_options': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'show_as_dropdown': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'show_as_rank_Question': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
        }


MultiFormset = formset_factory(MultiChoiceQuestionForm, extra=0)
# LikertFormset = formset_factory(LikertForm, extra=0)