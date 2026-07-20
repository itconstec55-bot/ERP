"""
هذا الملف يُعيد تصدير أدوات توليد الأرقام التسلسلية.
النموذج الحقيقي هو SequenceNumber في common.models.
"""
from datetime import date
from common.models import SequenceNumber

__all__ = ['SequenceNumber', 'generate_auto_number']


def generate_auto_number(prefix, model=None):
    """توليد رقم تسلسلي ببادئة السنة. يُستخدم من نماذج الوحدات عند الحفظ."""
    year = date.today().year
    return SequenceNumber.get_next_number(prefix, year)
