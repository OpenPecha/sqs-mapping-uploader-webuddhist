from aws_sqs_consumer import Consumer, Message
from app.uploader import upload_all_segments_mapping_to_webuddhist
from app.config import get
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

queue_url = get("SQS_QUEUE_URL")
region = get("AWS_REGION")

logger.info(f"Initializing SQS Consumer")
logger.info(f"Queue URL: {queue_url}")
logger.info(f"Region: {region}")

if not queue_url:
    logger.error("SQS_QUEUE_URL is not set in environment variables!")
    raise ValueError("SQS_QUEUE_URL environment variable is required")

if not region:
    logger.error("AWS_REGION is not set in environment variables!")
    raise ValueError("AWS_REGION environment variable is required")

class SimpleConsumer(Consumer):
    def handle_message(self, message: Message):
        logger.info(f"Received message: {message.MessageId}")
        try:
            json_content = json.loads(message.Body)
            logger.info(f"Message body: {json_content}")

            manifestation_id = json_content["manifestation_id"]
            logger.info(f"Processing manifestation_id: {manifestation_id}")

            upload_all_segments_mapping_to_webuddhist(
                manifestation_id = manifestation_id
            )

            logger.info(f"Mapping uploaded to Webuddhist for manifestation: {manifestation_id}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise
    
consumer = SimpleConsumer(
    queue_url = queue_url,
    region = region,
    polling_wait_time_ms = 50
)

if __name__ == "__main__":
    logger.info("Consumer started.. Waiting for messages...")
    consumer.start()