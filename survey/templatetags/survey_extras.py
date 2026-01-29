from django import template
import random
from survey.models import SectionHeader


register = template.Library()

@register.filter
def get_surveys(value):
    """
        Returns the correct list of surveys whether the input is a Paginator page
        or a plain list/queryset.
    """
    # If it's a paginator page object 
    # like page.object_list
    if hasattr(value, "object_list"):
        """
        If the value has an attribute 'object_list', it's likely a Paginator page.
        We return that list of objects.
        """
        return value.object_list
    # If it's already a list or queryset
    return value

@register.filter
def shuffle_if(seq, condition):
    """Shuffle if condition is True, otherwise return original"""
    if condition:
        try:
            result = list(seq)[:] 
            random.shuffle(result)
            return result
        except:
            return seq
    return seq


@register.filter
def group_by_sections(questions, shuffle_questions=False):
    """Split a flat question list/queryset into sections using SectionHeader as page titles."""
    try:
        items = list(questions)
    except TypeError:
        return []

    # Best-effort stable ordering
    try:
        items = sorted(items, key=lambda q: (q.position is None, q.position))
    except Exception:
        pass

    sections = []
    current_title = "Section 1"
    current_description = ""
    current_questions = []
    section_index = 1

    for item in items:
        if isinstance(item, SectionHeader):
            # Close previous section if it has any questions
            if current_questions:
                if shuffle_questions:
                    random.shuffle(current_questions)

                sections.append({
                    'title': current_title,
                    'description': current_description,
                    'questions': current_questions,
                })
            section_index += 1
            current_title = item.label or f"Section {section_index}"
            current_description = item.helper_text
            current_questions = []
            continue

        current_questions.append(item)

    if current_questions:
        if shuffle_questions:
            random.shuffle(current_questions)

        sections.append({
            'title': current_title,
            'description': current_description,
            'questions': current_questions,
        })

    # Assign sequential display numbers ignoring SectionHeaders
    display_counter = 1
    for section in sections:
        new_questions_list = []
        for question in section['questions']:
            new_questions_list.append({
                'question': question,
                'visual_index': display_counter
            })
            display_counter += 1
        section['questions'] = new_questions_list

    return sections

@register.filter()
def get_range(min_val, max_val):
    """
    Returns a range of numbers from min to max.
    Usage: {% for i in 1|get_range:5 %}
    """
    try:
        min_val = int(min_val)
        max_val = int(max_val)
        return range(min_val, max_val + 1)
    except (ValueError, TypeError):
        return []

@register.filter
def random_color(value):
    """
    Returns a random tailwind color class for background.
    The 'value' argument is ignored but required for the filter syntax.
    """
    colors = [
        'bg-primary', 
        'bg-secondary', 
        'bg-accent', 
        'bg-neutral', 
        'bg-info', 
        'bg-success', 
        'bg-warning', 
        'bg-error',
        'bg-rose-500', 
        'bg-pink-500', 
        'bg-fuchsia-500', 
        'bg-purple-500', 
        'bg-violet-500', 
        'bg-indigo-500', 
        'bg-blue-500', 
        'bg-sky-500', 
        'bg-cyan-500', 
        'bg-teal-500', 
        'bg-emerald-500', 
        'bg-green-500', 
        'bg-lime-500', 
        'bg-yellow-500', 
        'bg-amber-500', 
        'bg-orange-500'
    ]
    # Use hash of value (username) to get a consistent color for the same user
    if value:
        index = hash(value) % len(colors)
        return colors[index]
    return random.choice(colors)