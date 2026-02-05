from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.forms import UserCreationForm
from polymorphic.formsets import polymorphic_inlineformset_factory, PolymorphicFormSetChild
from . import models

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = models.CustomUser
        fields = ("username",)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the confusing help text about 150 characters
        self.fields['username'].help_text = ''

class SurveyForm(forms.ModelForm):
    class Meta:
        model = models.Survey
        fields = ['title', 'description', 'shuffle_questions', 'anonymous_responses']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input input-primary block', 'placeholder': _('e.g. Customer Satisfaction')}),
            'description': forms.Textarea(attrs={'class': 'textarea textarea-primary w-full h-16', 'placeholder': _('e.g. This survey is about customer satisfaction.')}),
            'shuffle_questions': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'anonymous_responses': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
        }
        labels = {
            'title': _('Survey Name'),
            'description': _('Description'),
            'shuffle_questions': _('Shuffle Questions'),
            'anonymous_responses': _('Anonymous Responses'),
        }

class BaseQuestionForm(forms.ModelForm):
    question_type = forms.CharField(widget=forms.HiddenInput()) 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Map class names to English keys used in templates/views
            class_name = self.instance.__class__.__name__
            mapped_key = class_name
            
            if class_name == 'MultiChoiceQuestion': mapped_key = 'Multi-Choice Question'
            elif class_name == 'LikertQuestion': mapped_key = 'Likert Question'
            elif class_name == 'MatrixQuestion': mapped_key = 'Matrix Question'
            elif class_name == 'RatingQuestion': mapped_key = 'Rating Question'
            elif class_name == 'RankQuestion': mapped_key = 'Ranking Question'
            elif class_name == 'TextQuestion': mapped_key = 'Text Question'
            elif class_name == 'SectionHeader': mapped_key = 'Section Header'
            
            self.initial['question_type'] = mapped_key

    class Meta:
        model = models.Question
        fields = ['label', 'helper_text', 'required', 'position']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'input input-md input-primary w-full', 'placeholder': _('Enter the label of the question')}),
            'helper_text': forms.TextInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': _('Enter the helper text of the question')}),
            'required': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'position': forms.HiddenInput(),
        }
        labels = {
            'label': _('Label'),
            'helper_text': _('Helper Text'),
            'required': _('Required'),
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
                                                                                    'placeholder': _('Enter the minimum number of options to be selected')}),
        }
        labels = {
            'options': _('Options'),
            'allow_multiple': _('Allow Multiple Selections'),
            'randomize_options': _('Randomize Options'),
            'the_minimum_number_of_options_to_be_selected': _('Minimum Options Required'),
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
                _("The Options field is required for a multiple choice question.")
            )
        elif len(options) <= 1:
            self.add_error(
                'options',
                _("At least two options are required for a multiple choice question."),
            )


        # This validation only runs if both fields are present
        if min_selected is not None and options:
            # The 'options' field is a JSON list
            if min_selected >= len(options):
                self.add_error(
                    'the_minimum_number_of_options_to_be_selected',
                    _("The minimum number of required options cannot be greater than the total number of available options."),)
            elif min_selected < 0:
                self.add_error(
                    'the_minimum_number_of_options_to_be_selected',
                    _("The minimum number of required options cannot be negative."),)
            
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

    def clean(self):
        cleaned_data = super().clean()
        options = cleaned_data.get('options')

        if self.cleaned_data.get('DELETE'):
            return cleaned_data

        if not options:
            self.add_error(
                'options',
                _("The Options field is required for a Likert question.")
            )
        elif len(options) <= 1:
            self.add_error(
                'options',
                _("At least two options are required for a Likert question."),
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
                _("The Rows fields are required for a Matrix question.")
            )
        elif len(rows) <= 1:
            self.add_error(
                'rows',
                _("At least two rows are required for a Matrix question."),
            )
        if not columns:
            self.add_error(
                'columns',
                _("The Columns fields are required for a Matrix question.")
            )
        elif len(columns) <= 1:
            self.add_error(
                'columns',
                _("At least two columns are required for a Matrix question."),
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
                'placeholder': _('e.g. Poor'),
                'x-model': 'minLabel'
            }),
            'max_label': forms.TextInput(attrs={
                'class': 'input input-bordered input-sm w-full bg-white',
                'placeholder': _('e.g. Excellent'),
                'x-model': 'maxLabel'
            }),
        }
        labels = {
            'range_min': _('Range Minimum'),
            'range_max': _('Range Maximum'),
            'min_label': _('Minimum Label'),
            'max_label': _('Maximum Label'),
        }

    def clean(self):
        cleaned_data = super().clean()
        min_val = cleaned_data.get('range_min')
        max_val = cleaned_data.get('range_max')
        if min_val is not None and max_val is not None:
            if min_val >= max_val:
                self.add_error('range_max', _("Max value must be greater than Min value."))
            if (max_val - min_val) > 20: # Prevent crazy huge scales
                self.add_error('range_max', _("Scale range is too large (max 20 steps)."))
        
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
            self.add_error('options', _("You need at least two options to rank."))

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
            'min_length': forms.NumberInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': _('Min Length')}),
            'max_length': forms.NumberInput(attrs={'class': 'input input-sm input-info focus:ring-0 focus:ring-offset-0', 'placeholder': _('Max Length')}),
        }


class SectionHeaderForm(BaseQuestionForm):
    polymorphic_ctype = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ctype = ContentType.objects.get_for_model(self._meta.model)
        self.initial['polymorphic_ctype'] = ctype.id

        # Section headers are not answerable questions.
        self.fields.pop('required', None)

    class Meta(BaseQuestionForm.Meta):
        model = models.SectionHeader
        fields = ['label',  'helper_text', 'position']
        widgets = {
            **BaseQuestionForm.Meta.widgets,
            'label': forms.TextInput(attrs={'class': 'input input-md input-primary w-full font-semibold', 'placeholder': _('Section Title')}),
            'helper_text': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': _('Optional subtitle'),
            }),
            'position': forms.HiddenInput(),
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
        PolymorphicFormSetChild(models.SectionHeader, SectionHeaderForm),
    ),
    extra=0,
    can_delete=True,
    fields=['label', 'helper_text', 'required', 'position']
)