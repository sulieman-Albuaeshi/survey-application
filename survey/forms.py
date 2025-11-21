from django import forms
from django.contrib.contenttypes.models import ContentType
from polymorphic.formsets import polymorphic_inlineformset_factory, PolymorphicFormSetChild
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

class BaseQuestionForm(forms.ModelForm):
    question_type = forms.CharField(widget=forms.HiddenInput()) 
    class Meta:
        model = models.Question
        fields = ['label', 'helper_text', 'required', 'position']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'input input-md input-primary w-full', 'placeholder': 'Enter the label of the question'}),
            'helper_text': forms.TextInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': 'Enter the helper text of the question'}),
            'required': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'position': forms.HiddenInput(),
        }
       
class MultiChoiceQuestionForm(BaseQuestionForm):
    polymorphic_ctype = forms.IntegerField(widget=forms.HiddenInput())
    def __init__(self, *args, **kwargs):
        """
            Override __init__ to dynamically set the initial value for 'polymorphic_ctype'.
        """
        super().__init__(*args, **kwargs)
        
        # Get the ContentType for the model associated with this form
        ctype = ContentType.objects.get_for_model(self._meta.model)
        
        # Set the initial value for the polymorphic_ctype field
        # The field itself is added by the polymorphic_inlineformset_factory
        self.initial['polymorphic_ctype'] = ctype.id

    class Meta(BaseQuestionForm.Meta):
        model = models.MultiChoiceQuestion
        fields = BaseQuestionForm.Meta.fields +  [ 'options', 'allow_multiple', 'randomize_options', 'the_minimum_number_of_options_to_be_selected']
        widgets = {
            **BaseQuestionForm.Meta.widgets,
            'options': forms.HiddenInput(attrs={'name' : '{{form.prefix}}options'}),
            'allow_multiple': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'randomize_options': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'the_minimum_number_of_options_to_be_selected': forms.NumberInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 
                                                                                    'placeholder': 'Enter the minimum number of options to be selected'}),
        }
    def clean(self):
        cleaned_data = super().clean()
        min_selected = cleaned_data.get('the_minimum_number_of_options_to_be_selected')
        options = cleaned_data.get('options')

        if  options is None:
            self.add_error(
                'options',
                "the Options field is required for a multiple choice question."
            )
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

class LikertQuestionForm(BaseQuestionForm):
    polymorphic_ctype = forms.IntegerField(widget=forms.HiddenInput())
    def __init__(self, *args, **kwargs):
        """
        Override __init__ to dynamically set the initial value for 'polymorphic_ctype'.
        """
        super().__init__(*args, **kwargs)
        ctype = ContentType.objects.get_for_model(self._meta.model)
        self.initial['polymorphic_ctype'] = ctype.id


    class Meta(BaseQuestionForm.Meta):
        model = models.LikertQuestion
        fields = BaseQuestionForm.Meta.fields + ['options']
        widgets = {
            **BaseQuestionForm.Meta.widgets,
            'options': forms.HiddenInput(), # This will be handled by JS
        }

    def save(self, commit=True):
        """
        Override the save method to set scale_max based on the number of options.
        """
        # First, get the model instance but don't save it to the DB yet.
        instance = super().save(commit=False)

        # Add custom logic: set scale_max to the number of options.
        instance.scale_max = len(self.cleaned_data.get('options', []))

        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()
        options = cleaned_data.get('options')
        if not options:
            self.add_error(
                'options',
                "The Options field is required for a Likert question."
            )
        elif len(options) <= 1:
            self.add_error(
                'options',
                "At least two options are required for a Likert question.",
            )

        return cleaned_data
    
# class SurveyQuestionFormSet(BaseInlineFormSet):
#     """
#         A custom FormSet that handles multiple question types (Polymorphism)
#         and manages the ordering/indexing.
#     """
#     def _construct_form(self, i, **kwargs):
#         # 1. Let the parent build the default form (BaseQuestionForm) first.
#         #    This calculates all the prefixes, instances, and data binding for us.
#         form = super()._construct_form(i, **kwargs)

#         # 2. Determine the Desired Class (Polymorphism)
#         desired_class = self.get_desired_form_class(form, i)

#         # 3. If the form created is not the type we want, Re-build it!
#         if not isinstance(form, desired_class):
#             # Extract the standard arguments from the already built form
#             new_form = desired_class(
#                 data=form.data if self.is_bound else None,
#                 files=form.files if self.is_bound else None,
#                 auto_id=form.auto_id,
#                 prefix=form.prefix,
#                 initial=form.initial,
#                 error_class=self.error_class,
#                 empty_permitted=form.empty_permitted,
#                 instance=form.instance, # Pass the model instance
#                 use_required_attribute=False if form.empty_permitted else self.use_required_attribute,


#                 renderer=self.renderer
#             )
#             return new_form
        
#         return form

#     def get_desired_form_class(self, form, i):
#         """
#         Helper logic to decide if we need MultiChoice, Likert, or Base.
#         """
#         # Case A: Submitting Data (POST) -> Check hidden 'question_type' field
#         if self.data:
#             # Use the specific prefix of the form to find the correct input field
#             # name format: "questions-0-question_type"
#             type_key = f"{form.prefix}-question_type"
#             type_value = self.data.get(type_key)
            
#             if type_value == 'Multi-Choice Question':
#                 return MultiChoiceQuestionForm
#             elif type_value == 'Likert Question':
#                 return LikertQuestionForm

#         # Case B: Existing Data (GET/Edit) -> Check the database instance
#         elif form.instance and form.instance.pk:
#             # Check for Child Models using hasattr (Django Inheritance)
#             if hasattr(form.instance, 'multichoicequestion'):
#                 return MultiChoiceQuestionForm
#             elif hasattr(form.instance, 'likertquestion'):
#                 return LikertQuestionForm

#         # Default fallback
#         return BaseQuestionForm 

# QuestionFormSetFactory = inlineformset_factory(
#     parent_model=models.Survey,
#     model=models.Question, # Point to parent model
#     formset=SurveyQuestionFormSet, # Use our custom polymorphic class
#     form=BaseQuestionForm, # Default fallback form
#     extra=0,
#     can_delete=True,
# )


QuestionFormSet = polymorphic_inlineformset_factory(
    models.Survey,  # Parent Model
    models.Question, # Base Child Model
    formset_children=(
        PolymorphicFormSetChild(models.MultiChoiceQuestion, MultiChoiceQuestionForm),
        PolymorphicFormSetChild(models.LikertQuestion, LikertQuestionForm),
    ),
    extra=0,
    can_delete=True,
    fields=['label', 'helper_text', 'required', 'position']
)