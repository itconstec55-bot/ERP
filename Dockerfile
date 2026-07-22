# صورة مبنية على Python 3.12-slim — الإصدار المدعوم رسميًا من Django 4.2
# (والأقرب لبيئة التطوير 3.12.10). Python 3.13/3.14 غير مدعومين رسميًا بعد.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# مكتبات نظام قد يتطلبها بناء بعض الحزم (مثل psycopg2 و redis) + curl لفحص الصحة
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# تثبيت الاعتماديات أولاً للاستفادة من طبقات الكاش
# نثبّت الأساس + اعتماديات الإنتاج (gunicorn + whitenoise) اللازمة للتشغيل
COPY requirements.txt /app/requirements.txt
COPY requirements/ /app/requirements/
RUN pip install --upgrade pip && pip install -r /app/requirements.txt -r /app/requirements/prod.txt

# نسخ كود التطبيق
COPY . .

# مستخدم غير جذر لتقليل سطح الهجوم
RUN mkdir -p /app/logs /app/media \
    && useradd -m appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8012

# الإقلاع: ترحيل + جمع الثابت + تشغيل Gunicorn (تتوفر متغيرات البيئة هنا)
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
