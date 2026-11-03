"""Production entry point:  gunicorn wsgi:app --workers 2 --threads 4"""
import logging

from studysync import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = create_app()
