from celery import Celery
import csv
import time

celery = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery.task
def process_csv(filepath):
    with open(filepath, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # simulate long processing
            print(f"Processing row: {row}")
            time.sleep(1)  # simulate work (DB insert, API call, etc.)
    print("CSV processing done.")
