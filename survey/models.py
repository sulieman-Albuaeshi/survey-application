from django.db import models
from django.contrib.auth.models import AbstractUser
from polymorphic.models import PolymorphicModel
from django.utils.translation import gettext_lazy as _

import uuid

class CustomUser(AbstractUser):
    pass


STATE_CHOICES = [
    ("draft", _("Draft")),
    ("published", _("Published")),
    ("archived", _("Archived")),
]

# Create your models here.
class Survey(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, null=True)
    title = models.CharField(max_length=100, verbose_name=_("Title"))
    description = models.TextField(verbose_name=_("Description"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    last_updated = models.DateTimeField(auto_now=True, verbose_name=_("Last Updated"))
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default="draft", verbose_name=_("State"))
    created_by =  models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='surveys', verbose_name=_("Created By"))
    question_count = models.IntegerField(default=0, verbose_name=_("Question Count"))
    shuffle_questions = models.BooleanField(default=False, verbose_name=_("Shuffle Questions"))
    anonymous_responses = models.BooleanField(default=False, verbose_name=_("Anonymous Responses"))

    class Meta:
        verbose_name = _("Survey")
        verbose_name_plural = _("Surveys")

    @property
    def status_badge_class(self):
        if self.state == 'published':
            return 'bg-primary text-black'
        elif self.state == 'draft':
            return 'bg-yellow-200 text-black'
        elif self.state == 'archived':
            return 'bg-red-200 text-black'
        return 'bg-gray-100 text-black'
    
    @property
    def response_count(self):
        return self.responses.count()
    
    def get_response_stats(self):
        """Get statistics about responses for this survey"""
        return {
            'total_responses': self.response_count,
            'completion_rate': self.get_completion_rate(),
            'avg_response_time': self.get_avg_response_time(),
        }
    
    def get_completion_rate(self):
        """Calculate completion rate (placeholder)"""
        return 100 if self.response_count > 0 else 0
    
    def get_avg_response_time(self):
        """Calculate average response time (placeholder)"""
        return "N/A"
    


class Question(PolymorphicModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions', verbose_name=_("Survey"))
    label = models.TextField(verbose_name=_("Label"))
    helper_text = models.TextField(null=True, blank=True, verbose_name=_("Helper Text"))
    required = models.BooleanField(default=False, verbose_name=_("Required"))
    position = models.IntegerField(verbose_name=_("Position"))

    class Meta:
        ordering = ['position']
        verbose_name = _("Question")
        verbose_name_plural = _("Questions")

    @classmethod
    def get_available_type_names(cls):
        """Returns a list of NAME static attributes from all direct subclasses."""
        names = []
        for subclass in cls.__subclasses__():
            if hasattr(subclass, 'NAME'):
                names.append(subclass.NAME)
        return names


class MultiChoiceQuestion(Question):
    options = models.JSONField(default=list, verbose_name=_("Options"))
    allow_multiple = models.BooleanField(default=True, verbose_name=_("Allow Multiple"))
    randomize_options = models.BooleanField(default=False, verbose_name=_("Randomize Options"))
    show_as_dropdown = models.BooleanField(default=False, verbose_name=_("Show as Dropdown"))
    show_as_rank_Question = models.BooleanField(default=False, verbose_name=_("Show as Rank Question"))
    the_minimum_number_of_options_to_be_selected = models.IntegerField(default=1, verbose_name=_("Minimum Options to Select"))
    NAME = _("Multi-Choice Question")


    def get_answer_distribution(self):
        """Get distribution of answers for this question"""
        answers = Answer.objects.filter(question=self)
        distribution = {}
        
        for answer in answers:
            answer_data = answer.answer_data
            if isinstance(answer_data, list):
                for item in answer_data:
                    distribution[item] = distribution.get(item, 0) + 1
            else:
                distribution[answer_data] = distribution.get(answer_data, 0) + 1
        
        return distribution

    def get_numeric_answer(self, answer_data):
        """Convert answer text to a single numeric value using binary representation"""
        if not answer_data:
            return ""
        
        options = self.options
        binary_sum = 0
        
        # Ensure answer_data is a list for uniform processing
        selections = answer_data if isinstance(answer_data, list) else [answer_data]
        
        for val in selections:
            try:
                # Find index of the selection (0-based)
                idx = options.index(val)
                # Add 2^index to the sum (1, 2, 4, 8, etc.)
                binary_sum += (1 << idx)
            except ValueError:
                # Value not in options, ignore
                pass
                
        return str(binary_sum)


class LikertQuestion(Question):
    options = models.JSONField(default=list, verbose_name=_("Options"))
    scale_max = models.IntegerField(default=5, verbose_name=_("Scale Max"))
    NAME = _("Likert Question")

    def get_average_rating(self):
        """Calculate average rating for this question"""
        answers = Answer.objects.filter(question=self)
        if not answers.exists():
            return 0
        
        total = 0
        count = 0
        options_list = self.options # Expecting a list of strings
        
        for answer in answers:
            try:
                # Direct string matching
                val_str = str(answer.answer_data)
                
                # Check if it's in the options list
                if val_str in options_list:
                    # Map to 1-based index (Strongly Disagree -> 1, ..., Strongly Agree -> 5)
                    val = options_list.index(val_str) + 1
                    total += val
                    count += 1
                else:
                     # Fallback for legacy numeric data or unexpected values
                     val = float(int(answer.answer_data['position']))
                     total += val
                     count += 1

            except (ValueError, TypeError):
                continue
        
        if count == 0:
            return 0
            
        return round(total / count, 2)
    
    def get_rating_distribution(self):
        """Get distribution of ratings"""
        answers = Answer.objects.filter(question=self)
        distribution = {opt: 0 for opt in self.options} # Initialize with option labels
        
        for answer in answers:
            val_str = str(answer.answer_data)
            if val_str in distribution:
                distribution[val_str] += 1
            # If data is numeric (old format), try to map it to the label
            elif str(val_str).isdigit():
                 try:
                     # 1-based index to 0-based
                     idx = int(val_str) - 1
                     if 0 <= idx < len(self.options):
                         label = self.options[idx]
                         distribution[label] += 1
                 except (ValueError, IndexError):
                     pass

        return distribution
    
    #  TODO : Convert the values to numeric representation 
    def get_numeric_answer(self, answer_data):
        """Convert answer label to numeric value (1-based index)"""
        if not answer_data:
            return ""
        
        val_str = str(answer_data)
        if val_str in self.options:
            return str(self.options.index(val_str) + 1)
        
        # Fallback if it's already a number
        return val_str


class MatrixQuestion(Question):
    rows = models.JSONField(default=list, verbose_name=_("Rows"))
    columns = models.JSONField(default=list, verbose_name=_("Columns"))

    NAME = _("Matrix Question")

    def get_matrix_distribution(self):
        """
        Returns a heatmap-like distribution:
        {
            'Row 1': {'Col A': 5, 'Col B': 2},
            'Row 2': {'Col A': 1, 'Col B': 6}
        }
        """
        answers = Answer.objects.filter(question=self)
        
        # Initialize structure
        distribution = {row: {col: 0 for col in self.columns} for row in self.rows}
        
        for ans in answers:
            data = ans.answer_data # Expected: {'Row 1': 'Col A', 'Row 2': 'Col B'}
            if isinstance(data, dict):
                for row_key, col_val in data.items():
                    if row_key in distribution and col_val in distribution[row_key]:
                        distribution[row_key][col_val] += 1
                        
        return distribution

    def get_numeric_answer(self, answer_data):
        # Number of answered rows (best-effort)
        if not answer_data:
            return ""
        if isinstance(answer_data, dict):
            return str(len([v for v in answer_data.values() if v not in (None, "")]))
        return "1"


class TextQuestion(Question):
    is_long_answer = models.BooleanField(default=False, verbose_name=_("Is Long Answer"))
    min_length = models.IntegerField(null=True, blank=True, verbose_name=_("Minimum Length"))
    max_length = models.IntegerField(null=True, blank=True, verbose_name=_("Maximum Length"))
    
    NAME = _("Text Question")

    def get_numeric_answer(self, answer_data):
        # 1 if answered, 0 if not (simple completion metric)
        return "1" if answer_data not in (None, "") else "0"


class SectionHeader(Question):
    """A page title / separator used to split a survey into sections."""

    NAME = _("Section Header")

    def get_numeric_answer(self, answer_data):
        # Section headers do not collect answers.
        return ""

    
class RatingQuestion(Question):
    range_min = models.IntegerField(default=1, verbose_name=_("Range Min"))
    range_max = models.IntegerField(default=5, verbose_name=_("Range Max"))
    min_label = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Min Label")) # e.g. "Poor"
    max_label = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Max Label")) # e.g. "Excellent"
    NAME = _("Rating Question")

    def get_numeric_answer(self, answer_data):
        """Returns the rating value directly."""
        if answer_data is None or answer_data == "":
            return ""
        return str(answer_data)

    def get_average_rating(self):
        """Calculate average rating for this question"""
        answers = Answer.objects.filter(question=self)
        if not answers.exists():
            return 0
        
        total = 0
        count = 0
        for answer in answers:
            try:
                val = float(answer.answer_data)
                total += val
                count += 1
            except (ValueError, TypeError):
                continue
        
        if count == 0:
            return 0
            
        return round(total / count, 2)

    def get_rating_distribution(self):
        """Get distribution of ratings"""
        answers = Answer.objects.filter(question=self)
        distribution = {}
        
        # Initialize distribution
        for i in range(self.range_min, self.range_max + 1):
            distribution[i] = 0
        
        for answer in answers:
            try:
                val = int(float(answer.answer_data))
                if val in distribution:
                    distribution[val] += 1
            except (ValueError, TypeError):
                continue
        
        return distribution

class RankQuestion(Question):
    options = models.JSONField(default=list, verbose_name=_("Options"))
    NAME = _("Ranking Question")

    def get_numeric_answer(self, answer_data):
        """
        Convert ranking answer to numeric value representing the top choice's index.
        """
        
        if not answer_data or isinstance(answer_data, list) or len(answer_data) == 0:
            return ""
        
        try:
            # Return index of the first item in the ranking
            first_choice = answer_data[max(answer_data, key=int)] # Get the top-ranked item 
            if first_choice in self.options:
                 return str(self.options.index(first_choice))
        except (ValueError, AttributeError):
            pass
        return ""

    def get_average_ranks(self):
        """
        Returns a dict of {option_name: average_rank_position}.
        hi number = Better rank (1st place, 2nd place, etc.)
        """
        answers = Answer.objects.filter(question=self)
        stats = {opt: {'sum': 0, 'count': 0} for opt in self.options}
        
        for answer in answers:
            # answer_data is expected to be a dict {'5': 'Option A', '4': 'Option B'}
            ranking_dict = answer.answer_data 
            if isinstance(ranking_dict, dict):
                for score, item in ranking_dict.items():
                        try:
                            stats[item]['sum'] += int(score)
                            stats[item]['count'] += 1
                        except (ValueError, TypeError):
                            pass
        
        results = {}
        for opt, data in stats.items():
            if data['count'] > 0:
                results[opt] = round(data['sum'] / data['count'], 2)
            else:
                results[opt] = 0
        
        # Sort by rank (highest score is best)
        return dict(sorted(results.items(), key=lambda item: item[1], reverse=True))

class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses')
    respondent = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Response to {self.survey.title} at {self.created_at}"


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_data = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"Answer for {self.question.label[:30]}: {self.answer_data}"