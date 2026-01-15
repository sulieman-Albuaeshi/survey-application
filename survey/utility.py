from django.http import QueryDict

def normalize_formset_indexes( data: QueryDict, prefix: str):
    """
    Convert any question indexes (0,5,20...) → continuous (0,1,2...).
    Example:
        questions-0-title
        questions-4-title
    becomes:
        questions-0-title
        questions-1-title
    """
    new_data = data.copy()

    new_data = dict()
    new_index = 0
    old_index = None
    for key, value in data.items():
        if key.startswith(prefix + "-") and "-" in key[len(prefix)+1:]:
            index = key.split("-")[1]
            if old_index is None:
                old_index = index
            if  index != old_index :
                old_index = index
                new_index += 1  

            if key == prefix + "-" + str(index) + "-" + "position":
                new_data[prefix+"-" + str(new_index) + "-" + "position"] = new_index + 1
                continue

            # Handle field names that might contain hyphens (join the rest of the parts)
            field_name = "-".join(key.split("-")[2:])
            new_data[prefix+"-" + str(new_index) + "-" + field_name] = value
        else:
            new_data[key] = value

    # Update the TOTAL_FORMS to reflect the actual number of normalized forms
    # new_index is 0-based, so count is new_index + 1 if strictly sequential, 
    # but new_index increments only on change. 
    
    # Calculation: new_index is the *last* index used. 
    # If the loop ran at least once, count is new_index + 1.
    # If loop never ran (no forms), count is 0.
    
    # Note: This simple logic assumes at least one form exists if the loop entered.
    # A safer way is to count unique indices encountered.
    
    # However, since we are just fixing the immediate issues:
    if old_index is not None:
         new_data[f"{prefix}-TOTAL_FORMS"] = new_index + 1
    else:
         new_data[f"{prefix}-TOTAL_FORMS"] = 0
         
    return new_data