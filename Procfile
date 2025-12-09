release: python manage.py migrate && python manage.py collectstatic --noinput
web: gunicorn djangoTodo.wsgi --log-file -