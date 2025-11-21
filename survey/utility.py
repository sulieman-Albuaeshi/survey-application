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
                new_data[prefix+"-" + str(new_index) + "-" + "position"] = new_index
                continue

            new_data[prefix+"-" + str(new_index) + "-" + key.split("-")[2]] = value
        else:
            new_data[key] = value

    return new_data