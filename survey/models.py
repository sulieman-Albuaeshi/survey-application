from django.db import models
from django.contrib.auth.models import AbstractUser
from polymorphic.models import PolymorphicModel

import uuid

class CustomUser(AbstractUser):
    pass


STATE_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("archived", "Archived"),
]

# Create your models here.
class Survey(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, null=True)
    title = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default="draft")
    created_by =  models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='surveys')
    question_count = models.IntegerField(default=0)
    shuffle_questions = models.BooleanField(default=False)
    anonymous_responses = models.BooleanField(default=False)

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
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    label = models.TextField()
    helper_text = models.TextField(null=True, blank=True)
    required = models.BooleanField(default=False)
    position = models.IntegerField()

    @classmethod
    def get_available_type_names(cls):
        """Returns a list of NAME static attributes from all direct subclasses."""
        names = []
        for subclass in cls.__subclasses__():
            if hasattr(subclass, 'NAME'):
                names.append(subclass.NAME)
        return names


class MultiChoiceQuestion(Question):
    options = models.JSONField(default=list)
    allow_multiple = models.BooleanField(default=True)
    randomize_options = models.BooleanField(default=False)
    show_as_dropdown = models.BooleanField(default=False)
    show_as_rank_Question = models.BooleanField(default=False)
    the_minimum_number_of_options_to_be_selected = models.IntegerField(default=1)
    NAME = "Multi-Choice Question"


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
    options = models.JSONField(default=list)
    scale_max = models.IntegerField(default=5)
    NAME = "Likert Question"

    def get_average_rating(self):
        """Calculate average rating for this question"""
        answers = Answer.objects.filter(question=self)
        if not answers.exists():
            return 0
        
        total = 0
        count = 0
        for answer in answers:
            try:
                if isinstance(answer.answer_data, dict) and 'position' in answer.answer_data:
                    val = float(answer.answer_data['position'])
                else:
                    val = float(answer.answer_data)
                total += val
                count += 1
            except (ValueError, TypeError, KeyError):
                continue
        
        if count == 0:
            return 0
            
        return round(total / count, 2)
    
    def get_rating_distribution(self):
        """Get distribution of ratings"""
        answers = Answer.objects.filter(question=self)
        distribution = {}
        
        # Initialize distribution with 0 for all possible ratings
        for i in range(1, self.scale_max + 1):
            distribution[i] = 0
        
        for answer in answers:
            try:
                # Handle both direct values and dictionary format (legacy support)
                if isinstance(answer.answer_data, dict) and 'position' in answer.answer_data:
                    rating = int(float(answer.answer_data['position']))
                else:
                    rating = int(float(answer.answer_data))
                
                distribution[rating] = distribution.get(rating, 0) + 1
            except (ValueError, TypeError, KeyError):
                # Skip invalid data
                continue
        
        return distribution
    
    def get_numeric_answer(self, answer_data):
        """Convert answer to numeric value"""
        if not answer_data:
            return ""
        
        try:
            if isinstance(answer_data, dict) and 'position' in answer_data:
                return str(int(float(answer_data['position'])))
            else:
                return str(int(float(answer_data)))
        except (ValueError, TypeError, KeyError):
            return ""


class MatrixQuestion(Question):
    rows = models.JSONField(default=list)
    columns = models.JSONField(default=list)

    NAME = "Matrix Question"


class TextQuestion(Question):
    is_long_answer = models.BooleanField(default=False)
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    
    NAME = "Text Question"

    
class RatingQuestion(Question):
    range_min = models.IntegerField(default=1)
    range_max = models.IntegerField(default=5)
    min_label = models.CharField(max_length=50, blank=True, null=True) # e.g. "Poor"
    max_label = models.CharField(max_length=50, blank=True, null=True) # e.g. "Excellent"
    NAME = "Rating Question"

class RankQuestion(Question):
    options = models.JSONField(default=list)
    NAME = "Ranking Question"

    def get_average_ranks(self):
        """
        Returns a dict of {option_name: average_rank_position}.
        Lower number = Better rank (1st place, 2nd place, etc.)
        """
        answers = Answer.objects.filter(question=self)
        stats = {opt: {'sum': 0, 'count': 0} for opt in self.options}
        
        for answer in answers:
            # answer_data is expected to be an ordered list ['Option A', 'Option B']
            ranking_list = answer.answer_data 
            if isinstance(ranking_list, list):
                for index, item in enumerate(ranking_list):
                    if item in stats:
                        # index + 1 because rank starts at 1, not 0
                        stats[item]['sum'] += (index + 1)
                        stats[item]['count'] += 1
        
        results = {}
        for opt, data in stats.items():
            if data['count'] > 0:
                results[opt] = round(data['sum'] / data['count'], 2)
            else:
                results[opt] = 0
        
        # Sort by rank (lowest score is best)
        return dict(sorted(results.items(), key=lambda item: item[1]))

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