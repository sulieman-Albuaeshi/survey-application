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
            'options': forms.HiddenInput(attrs={'name' : '{{form.prefix}}options'}),
            'position': forms.HiddenInput(),
            'allow_multiple': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'randomize_options': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'the_minimum_number_of_options_to_be_selected': forms.NumberInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': 'Enter the minimum number of options to be selected'}),

        }

    def clean(self):
        cleaned_data = super().clean()
        min_selected = cleaned_data.get('the_minimum_number_of_options_to_be_selected')
        options = cleaned_data.get('options')
        if len(options) <= 1:
            self.add_error(
                'options',
                "At least two options are required for a multiple choice question.",
            )

        # This validation only runs if both fields are present
        if min_selected is not None and options:
            # The 'options' field is a JSON list
            if min_selected >= len(options):
                self.add_error(
                    'the_minimum_number_of_options_to_be_selected',
                    "The minimum number of required options cannot be greater than the total number of available options.",)
            
        return cleaned_data

class LikertQuestionForm(forms.ModelForm):
    class Meta:
        model = models.LikertQuestion
        fields = ['label', 'helper_text', 'required', 'position', 'options']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'input input-md input-primary w-full', 'placeholder': 'Enter the label of the question'}),
            'helper_text': forms.TextInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': 'Enter the helper text of the question'}),
            'required': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'position': forms.HiddenInput(),
            'options': forms.HiddenInput(), # This will be handled by JS
        }

    def clean(self):
        cleaned_data = super().clean()
        options = cleaned_data.get('options')
        if len(options) <= 1:
            self.add_error(
                'options',
                "At least two options are required for a likert question.",
            )
        return cleaned_data


MultiFormset = formset_factory(MultiChoiceQuestionForm, extra=0)
LikertFormset = formset_factory(LikertQuestionForm, extra=0)