import logging
from django.core.cache import cache
from .models import Company

logger = logging.getLogger('accounting')

COMPANY_CACHE_KEY = 'company_context_data'
COMPANY_CACHE_TIMEOUT = 300  # 5 minutes


def company_context(request):
    try:
        company = cache.get(COMPANY_CACHE_KEY)
        if company is None:
            company = Company.objects.first()
            if not company:
                company = Company.get_company()
            cache.set(COMPANY_CACHE_KEY, company, COMPANY_CACHE_TIMEOUT)
    except Exception as e:
        logger.exception('Company context error: %s', e)
        company = None
    return {'company': company}
