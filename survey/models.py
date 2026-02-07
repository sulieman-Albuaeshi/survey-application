from django.db import models
from django.contrib.auth.models import AbstractUser
from polymorphic.models import PolymorphicModel
import math
import statistics
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
    view_count = models.IntegerField(default=0, verbose_name=_("View Count"))
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
    def real_question_count(self):
        return self.questions.exclude(polymorphic_ctype__model='sectionheader').count()
    
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
        """Calculate completion rate: (Responses / Views) * 100"""
        if self.view_count > 0:
            return round((self.response_count / self.view_count) * 100, 2)
        return 0
    
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
        
        # Initialize with 0 for all existing options
        distribution = {option: 0 for option in self.options}
        
        for answer in answers:
            answer_data = answer.answer_data
            if not answer_data: # Skip None or empty string
                continue
                
            if isinstance(answer_data, list):
                for item in answer_data:
                    if item in distribution:
                        distribution[item] += 1
            else:
                if answer_data in distribution:
                    distribution[answer_data] += 1
        
        return distribution

    def get_numeric_answer(self, val):
        """Convert answer text to a single numeric value using 0/1"""    
        if isinstance(val, list):
            return ['1' if option in val else "0" for option in self.options]
        else: 
            return ['1' if val == option else '0' for option in self.options]

class LikertQuestion(Question):
    options = models.JSONField(default=list, verbose_name=_("Options"))
    NAME = _("Likert Question")

    def get_all_scores(self):
        """Helper to get all numeric scores (1-based index) from answers."""
        scores = []
        answers = Answer.objects.filter(question=self)
        for answer in answers:
            val_str = str(answer.answer_data)
            if val_str in self.options:
                scores.append(self.options.index(val_str) + 1)
        return scores

    def get_mean(self, scores=None):
        if scores is None:
            scores = self.get_all_scores()
        return round(statistics.mean(scores), 3) if scores else 0

    def get_median(self, scores=None):
        if scores is None:
            scores = self.get_all_scores()
        return round(statistics.median(scores), 3) if scores else 0

    def get_statistic(self):
        """Return mean, median and CI as a dict."""
        score = self.get_all_scores()
        return {
            'mean': self.get_mean(score),
            'median': self.get_median(score),
            'interpretation': self.get_interpretation(score),
            't_test': self.get_t_test(scores=score)
        }

    def get_t_test(self, scores=None, hypothetical_mean=3.0):
        """One-sample T-test against neutral midpoint (default 3.0 for 5-pt scale)"""
        if scores is None:
            scores = self.get_all_scores()
        n = len(scores)
        if n < 2:
            return None
            
        mean = statistics.mean(scores)
        std_dev = statistics.stdev(scores)
        
        if std_dev == 0:
            return 0 # Avoid division by zero
            
        t_stat = (mean - hypothetical_mean) / (std_dev / math.sqrt(n))
        return round(t_stat, 5)
    
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
    
    def get_numeric_answer(self, val):
        """Convert answer text to a single numeric value using 0/1"""

        return ['1' if val == option else '0' for option in self.options]

    def get_interpretation(self, score=None):
        """
        Returns text interpretation of mean score based on interval formula:
        (Max Score - Min Score) / Number of Options.
        Example: (5 - 1) / 5 = 0.80 per option.
        Range 1: 1.00 - 1.79 (Strongly Disagree)
        Range 2: 1.80 - 2.59 (Disagree)
        ...etc
        """
        if score is None:
            scores = self.get_all_scores()
        elif isinstance(score, list):
            scores = score
        else:
            scores = [score]

        if not scores:
            return "N/A"
            
        mean = self.get_mean(scores)
        
        count = len(self.options)
        if count == 0:
            return "N/A"
            
        # Formula: Interval = (Max - Min) / Count
        # Standard Likert Scale: Min=1, Max=Count
        min_score = 1
        max_score = count
        interval = (max_score - min_score) / count
        
        if interval == 0:
            return self.options[0]
            
        # Determine index based on the user's formula
        # Index = floor((Mean - Min) / Interval)
        raw_index = (mean - min_score) / interval
        index = int(raw_index)
        
        # Clamp index to handle edge case of Mean == Max Score
        if index >= count:
            index = count - 1
        if index < 0:
            index = 0
            
        return self.options[index]

class MatrixQuestion(Question):
    rows = models.JSONField(default=list, verbose_name=_("Rows"))
    columns = models.JSONField(default=list, verbose_name=_("Columns"))

    NAME = _("Matrix Question")

    def get_row_statistics(self):
        """Returns statistics for each row: {'Row 1': {'mean': x, 'median': y}, ...}"""
        answers = Answer.objects.filter(question=self)
        row_scores = {row: [] for row in self.rows}
        
        for ans in answers:
            data = ans.answer_data 
            if isinstance(data, dict):
                for key, col_val in data.items():
                    # Match key to row
                    matched_row = None
                    if key in self.rows:
                        matched_row = key
                    else:
                        # Try matching 'Row Label_rowX' format
                        for row in self.rows:
                             if key.startswith(f"{row}_row"):
                                 matched_row = row
                                 break
                    
                    if matched_row and col_val in self.columns:
                        row_scores[matched_row].append(self.columns.index(col_val) + 1)
                        
        result = {}
        for row, scores in row_scores.items():
            if scores:
                interpretation = "N/A"
                try:
                    std_dev = statistics.stdev(scores)
                    mean = statistics.mean(scores)
                    t_stat = 0
                    
                    if len(scores) > 1 and std_dev > 0:
                        midpoint = 3.0 
                        t_stat = (mean - midpoint) / (std_dev / math.sqrt(len(scores)))
                    
                    # Calculate Interpretation using (Max-Min)/Count formula
                    if self.columns:
                        count = len(self.columns)
                        min_score = 1
                        max_score = count
                        interval = (max_score - min_score) / count
                        
                        if interval > 0:
                            raw_index = (mean - min_score) / interval
                            index = int(raw_index)
                            if index >= count: index = count - 1
                            if index < 0: index = 0
                            interpretation = self.columns[index]

                except statistics.StatisticsError:
                    std_dev = 0
                    t_stat = 0
                    interpretation = "N/A"
                    
                result[row] = {
                    'mean': round(statistics.mean(scores), 2),
                    'median': round(statistics.median(scores), 2),
                    'interpretation': interpretation, # Replaces CI
                    't_stat': round(t_stat, 5)
                }
            else:
                 result[row] = {'mean': 0, 'median': 0, 'interpretation': 'N/A', 't_stat': 0}
        return result

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
            data = ans.answer_data # Expected: {'Row 1': 'Col A', 'Row 2': 'Col B'} or {'Row 1_row1': ...}
            if isinstance(data, dict):
                for key, col_val in data.items():
                    # Match key to row
                    matched_row = None
                    if key in distribution:
                        matched_row = key
                    else:
                        for row in self.rows:
                             if key.startswith(f"{row}_row"):
                                 matched_row = row
                                 break

                    if matched_row and col_val in distribution[matched_row]:
                        distribution[matched_row][col_val] += 1
                        
        return distribution

    def get_numeric_answer(self, val):
        """convert each row to a single numeric value as a Like Question"""        
        row = []
        for i, row_label in enumerate(self.rows, start=1):
            for col in self.columns:
                # Support both legacy keys ("<row>_row<i>") and the newer plain row key
                key_legacy = f'{row_label}_row{i}'
                selected_col = '0'
                if isinstance(val, dict):
                    selected_col = val.get(row_label) or val.get(key_legacy) or '0'
                row.append("1" if (selected_col == col) else "0")
        return row       

class TextQuestion(Question):
    is_long_answer = models.BooleanField(default=False, verbose_name=_("Is Long Answer"))
    min_length = models.IntegerField(null=True, blank=True, verbose_name=_("Minimum Length"))
    max_length = models.IntegerField(null=True, blank=True, verbose_name=_("Maximum Length"))
    
    NAME = _("Text Question")

    def get_numeric_answer(self, answer_data):
        # 1 if answered, 0 if not (simple completion metric)
        return answer_data if answer_data else "N/A"

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

    def get_all_scores(self):
        answers = Answer.objects.filter(question=self)
        scores = []
        for answer in answers:
            try:
                if answer.answer_data == '':
                    continue
                scores.append(float(answer.answer_data))
            except (ValueError, TypeError):
                continue
        return scores

    def get_mean(self, scores=None):
        if scores is None:
            scores = self.get_all_scores()
        return round(statistics.mean(scores), 3) if scores else 0

    def get_median(self, scores=None):
        if scores is None:
            scores = self.get_all_scores()
        return round(statistics.median(scores), 3) if scores else 0

    def get_statistic(self):
        """Return mean, median and CI as a dict."""
        scores = self.get_all_scores()
        return {
            'mean': self.get_mean(scores),
            'median': self.get_median(scores),
            'interpretation': self.get_interpretation(scores),
            't_test': self.get_t_test(scores=scores)
        }

    def get_interpretation(self, scores=None):
        """
        Returns text interpretation (numeric value) based on interval formula:
        (Max - Min) / Count.
        """
        if scores is None:
            scores = self.get_all_scores()
        if not scores:
            return "N/A"
            
        mean = statistics.mean(scores)
        
        # Calculate number of options in the range (e.g. 1 to 5 is 5 options)
        num_options = self.range_max - self.range_min + 1
        if num_options == 0:
            return "N/A"

        # Formula: Interval = (Max Score - Min Score) / Number of Options
        interval = (self.range_max - self.range_min) / num_options
        
        if interval == 0:
             return str(self.range_min)

        # Determine index corresponding to the mean
        # index = floor((Mean - Min) / Interval)
        raw_index = (mean - self.range_min) / interval
        index = int(raw_index)
        
        # Clamp index
        if index >= num_options:
            index = num_options - 1
        if index < 0:
            index = 0
            
        # Map index back to the rating value
        result_value = self.range_min + index
        
        return str(result_value)

    def get_t_test(self, scores=None):
        """One-sample T-test against the range midpoint"""
        if scores is None:
            scores = self.get_all_scores()
        n = len(scores)
        if n < 2:
            return None
            
        midpoint = (self.range_min + self.range_max) / 2
        mean = statistics.mean(scores)
        std_dev = statistics.stdev(scores)
        
        if std_dev == 0:
            return 0
            
        t_stat = (mean - midpoint) / (std_dev / math.sqrt(n))
        return round(t_stat, 5)
    
    def get_numeric_answer(self, answer_data):
        """Returns the rating value directly."""
        if answer_data is None or answer_data == "":
            return "N/A"
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
                if answer.answer_data == '':
                    continue
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
                if answer.answer_data == '':
                    continue
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
        Returns the index (0-based) of the first choice in the options list.
        This treats the #1 ranked item as the 'selected' value.
        """
        if not answer_data or isinstance(answer_data, list) or len(answer_data) == 0:
            return ["N/A" for _ in self.options]
        
        row = []
        try:
            for op in self.options:
                option_rank = answer_data.get(op) if isinstance(answer_data, dict) else None
                row.append(option_rank if option_rank else "")
            
            return row
        except (ValueError, AttributeError):
            pass
        return ""

    def get_average_ranks(self):
        """
        Returns a dict of {option_name: average_rank_position}.
        weighted score = (number of options - rank) + 1
        Higher number = Better rank
        """
        answers = Answer.objects.filter(question=self)
        stats = {opt: {'sum': 0, 'count': 0} for opt in self.options}
        num_options = len(self.options)
        
        for answer in answers:
            # answer_data is expected to be a dict {'Option A': '1', 'Option B': '2'}
            ranking_dict = answer.answer_data 
            if isinstance(ranking_dict, dict):
                for item, score in ranking_dict.items():
                        try:
                            if item in stats:
                                weight = int(score)
                                stats[item]['sum'] += weight
                                stats[item]['count'] += 1
                        except (ValueError, TypeError):
                            pass
        
        results = {}
        for opt, data in stats.items():
            if data['count'] > 0:
                results[opt] = round(data['sum'] / data['count'], 2)
            else:
                results[opt] = 0
        
        # Sort by weight (highest score is best)
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