import logging
import os
from os import getenv

if os.getenv("LOG_LEVEL") is None:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=int(os.getenv("LOG_LEVEL")))

from time import sleep

from dotenv import load_dotenv
from pymongo import MongoClient
from requests import get
from slack_sdk.webhook import WebhookClient

from fediseer_alerts.models import ActivityReport, Report_Activity, Report_Type


def start():
    load_dotenv()

    webhook = False

    if getenv('SLACK_WEBHOOK_URL'):
        webhook = WebhookClient(getenv('SLACK_WEBHOOK_URL'), timeout=60)
    db = MongoClient(host=getenv('MONGO_URI'))
    db.login()
    db = db['fediseer-notifications']['censures']
    logging.info("Starting...")
    while True:
        censures = get_censures()
        if len(censures) > 0:
            logging.info("Censures found")
            for c in censures:
                censure = ActivityReport(
                    source_domain=c['source_domain'],
                    target_domain=c['target_domain'],
                    report_type=Report_Type(c['report_type']),
                    report_activity=Report_Activity(c['report_activity']),
                    created=c['created'],
                )
                found_censure = db.find_one(
                    {
                        "$and": [
                            {"created": censure.created},
                            {"source_domain": censure.source_domain},
                            {"target_domain": censure.target_domain},
                            {"report_type": censure.report_type.value},
                            {"report_activity": censure.report_activity.value},
                        ]
                    }
                )
                if not found_censure:
                    db.insert_one(
                        {
                            "created": censure.created,
                            "source_domain": censure.source_domain,
                            "target_domain": censure.target_domain,
                            "report_type": censure.report_type.value,
                            "report_activity": censure.report_activity.value,
                        }
                    )
                    logging.info(f"New censure found: {str(censure)}")
                    if webhook:
                        webhook.send(
                            text=f"From: {censure.source_domain}\n"
                            f"To: {censure.report_activity.value}\n"
                            f"Action{censure.target_domain}"
                        )

        else:
            logging.info("No censures found")
        logging.info("Waiting 60 seconds...")
        sleep(60)


def get_censures():
    response = get('https://fediseer.com/api/v1/reports?report_type=CENSURE&page=1', timeout=60)
    if response.status_code == 200:
        return response.json()
    else:
        return []


if __name__ == "__main__":
    logging.info("START")
    start()
