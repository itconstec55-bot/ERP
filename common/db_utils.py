import logging
from functools import wraps

from django.db import transaction

logger = logging.getLogger('accounting')


def atomic_transaction(using=None, savepoint=True):
    """
    Decorator that wraps a function in a Django database transaction.
    Logs any errors and reraises them after rollback.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                with transaction.atomic(using=using, savepoint=savepoint):
                    return func(*args, **kwargs)
            except Exception as e:
                logger.error('Transaction failed in %s: %s', func.__name__, str(e), exc_info=True)
                raise

        return wrapper

    return decorator
