from functools import wraps


def employee_required(view):
    """Gate staff-only routes. Authentication will be added in a future release."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        # TODO: require authenticated StartHere employee session
        return view(*args, **kwargs)

    return wrapped
