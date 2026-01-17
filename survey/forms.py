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
            'options': forms.HiddenInput(),
            'allow_multiple': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'randomize_options': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'the_minimum_number_of_options_to_be_selected': forms.NumberInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 
                                                                                    'placeholder': 'Enter the minimum number of options to be selected'}),
        }
    def clean(self):
        cleaned_data = super().clean()
        min_selected = cleaned_data.get('the_minimum_number_of_options_to_be_selected')
        options = cleaned_data.get('options')

        if self.cleaned_data.get('DELETE'):
            return cleaned_data
        
        if not options:
            self.add_error(
                'options',
                "the Options field is required for a multiple choice question."
            )
        elif len(options) <= 1:
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
            elif min_selected < 0:
                self.add_error(
                    'the_minimum_number_of_options_to_be_selected',
                    "The minimum number of required options cannot be negative.",)
            
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

        if self.cleaned_data.get('DELETE'):
            return cleaned_data

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

class MatrixQuestionForm(BaseQuestionForm):
    polymorphic_ctype = forms.IntegerField(widget=forms.HiddenInput())
    def __init__(self, *args, **kwargs):
        """
        Override __init__ to dynamically set the initial value for 'polymorphic_ctype'.
        """
        super().__init__(*args, **kwargs)
        ctype = ContentType.objects.get_for_model(self._meta.model)
        print("ctype.id", ctype.id)
        
        self.initial['polymorphic_ctype'] = ctype.id
        

    class Meta(BaseQuestionForm.Meta):
        model = models.MatrixQuestion
        fields = BaseQuestionForm.Meta.fields + ['rows', 'columns']
        widgets = {
            **BaseQuestionForm.Meta.widgets,
            'rows': forms.HiddenInput(),    
            'columns': forms.HiddenInput(),  
        }

    def clean(self):
        cleaned_data = super().clean()
        rows = cleaned_data.get('rows')
        columns = cleaned_data.get('columns')

        if self.cleaned_data.get('DELETE'):
            return cleaned_data

        if not rows:
            self.add_error(
                'rows',
                "The Rows fields are required for a Matrix question."
            )
        elif len(rows) <= 1:
            self.add_error(
                'rows',
                "At least two rows are required for a Matrix question.",
            )
        if not columns:
            self.add_error(
                'columns',
                "The Columns fields are required for a Matrix question."
            )
        elif len(columns) <= 1:
            self.add_error(
                'columns',
                "At least two columns are required for a Matrix question.",
            )


        return cleaned_data


class RatingQuestionForm(BaseQuestionForm):
    polymorphic_ctype = forms.IntegerField(widget=forms.HiddenInput())
    def __init__(self, *args, **kwargs):
        """
        Override __init__ to dynamically set the initial value for 'polymorphic_ctype'.
        """
        super().__init__(*args, **kwargs)
        ctype = ContentType.objects.get_for_model(self._meta.model)
        self.initial['polymorphic_ctype'] = ctype.id

    class Meta(BaseQuestionForm.Meta):
        model = models.RatingQuestion
        fields = BaseQuestionForm.Meta.fields + ['range_min', 'range_max', 'min_label', 'max_label']
        widgets = {
            **BaseQuestionForm.Meta.widgets,
            'range_min': forms.NumberInput(attrs={
                'class': 'input input-bordered input-sm w-full bg-white text-center',
                'min': '1', 'max': '20', 'x-model.number': 'minVal',
                '@input': 'if(minVal > 20) minVal = 20;',

                # 2. When leaving the field: If empty or negative, reset to 0
                '@blur': 'if(minVal === "" || minVal < 0) minVal = 0;'
            }),
            'range_max': forms.NumberInput(attrs={
                'class': 'input input-bordered input-sm w-full bg-white text-center',
                'min': '2', 'max': '20', 'x-model.number': 'maxVal',
                '@input': 'if(maxVal > 20) maxVal = 20;',

                # 2. When leaving the field: If empty or negative, reset to 0
                '@blur': 'if(maxVal === "" || maxVal < 0) maxVal = 20;'
            }),
            'min_label': forms.TextInput(attrs={
                'class': 'input input-bordered input-sm w-full bg-white',
                'placeholder': 'e.g. Poor',
                'x-model': 'minLabel'
            }),
            'max_label': forms.TextInput(attrs={
                'class': 'input input-bordered input-sm w-full bg-white',
                'placeholder': 'e.g. Excellent',
                'x-model': 'maxLabel'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        min_val = cleaned_data.get('range_min')
        max_val = cleaned_data.get('range_max')

        if self.cleaned_data.get('DELETE'):
            return cleaned_data

        if min_val is not None and max_val is not None:
            if min_val >= max_val:
                self.add_error('range_max', "Max value must be greater than Min value.")
            if (max_val - min_val) > 20: # Prevent crazy huge scales
                self.add_error('range_max', "Scale range is too large (max 20 steps).")
        
        return cleaned_data

class RankQuestionForm(BaseQuestionForm):
    polymorphic_ctype = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ctype = ContentType.objects.get_for_model(self._meta.model)
        self.initial['polymorphic_ctype'] = ctype.id

    class Meta(BaseQuestionForm.Meta):
        model = models.RankQuestion
        fields = BaseQuestionForm.Meta.fields + ['options']
        widgets = {
            **BaseQuestionForm.Meta.widgets,
            'options': forms.HiddenInput(),
        }

    def clean(self):
        """
        This implements the +validateSelectionsCount() logic from your diagram
        """
        cleaned_data = super().clean()
        
        if self.cleaned_data.get('DELETE'):
            return cleaned_data

        options = cleaned_data.get('options', [])


        # 1. Validate Options
        if not options or len(options) < 2:
            self.add_error('options', "You need at least two options to rank.")

        return cleaned_data

class TextQuestionForm(BaseQuestionForm):
    polymorphic_ctype = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ctype = ContentType.objects.get_for_model(self._meta.model)
        self.initial['polymorphic_ctype'] = ctype.id

    class Meta(BaseQuestionForm.Meta):
        model = models.TextQuestion
        fields = BaseQuestionForm.Meta.fields + ['is_long_answer', 'min_length', 'max_length']
        widgets = {
            **BaseQuestionForm.Meta.widgets,
            'is_long_answer': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'min_length': forms.NumberInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': 'Min Length'}),
            'max_length': forms.NumberInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': 'Max Length'}),
        }

QuestionFormSet = polymorphic_inlineformset_factory(
    models.Survey,  # Parent Model
    models.Question, # Base Child Model
    formset_children=(
        PolymorphicFormSetChild(models.MultiChoiceQuestion, MultiChoiceQuestionForm),
        PolymorphicFormSetChild(models.LikertQuestion, LikertQuestionForm),
        PolymorphicFormSetChild(models.MatrixQuestion, MatrixQuestionForm),
        PolymorphicFormSetChild(models.RatingQuestion, RatingQuestionForm),
        PolymorphicFormSetChild(models.RankQuestion, RankQuestionForm),
        PolymorphicFormSetChild(models.TextQuestion, TextQuestionForm),
    ),
    extra=0,
    can_delete=True,
    fields=['label', 'helper_text', 'required', 'position']
)