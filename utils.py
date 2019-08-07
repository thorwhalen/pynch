__author__ = 'thorwhalen'


def ascertain_list(x):
    """
    ascertain_list(x) blah blah returns [x] if x is not already a list, and x itself if it's already a list
    Use: This is useful when a function expects a list, but you want to also input a single element without putting this
    this element in a list
    """
    if not isinstance(x, list):
        ## The "all but where it's a problem approach"
        if hasattr(x, '__iter__') and not isinstance(x, dict):
            x = list(x)
        else:
            x = [x]
            ## The (less safe) "just force what you want to do differently in those cases only" approach
            # if isinstance(x, np.ndarray):
            #     x = list(x)
            # else:
            #     x = [x]
    return x
