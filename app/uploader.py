import requests
from app.config import get
import logging
from time import sleep
from app.db.models import SegmentMapping
from app.db.postgres import SessionLocal
from app.models import (
    AllTextSegmentRelationMapping,
    SegmentsRelation,
    Mapping,
)

logger = logging.getLogger(__name__)


def upload_all_segments_mapping_to_webuddhist(
    text_id: str,
    segment_ids: list[str],
    destination_environment: str
):
    try:
        logger.info(f"Total number of segment ids: {len(segment_ids)}")
        logger.info("Getting all the segments relations by manifestation")
        relations = get_all_segments_by_segment_ids(
            text_id=text_id,
            segment_ids=segment_ids
        )
        logger.info(f"Total number of segment record retrieved: {len(relations)}")

        logger.info("Formatting all segmentrecords fetched from the database")
        formatted_relations = _format_all_text_segment_relation_mapping(
            text_id=text_id,
            all_text_segment_relations=relations
        )

        logger.info("Preparing the webuddhist mapping payload")
        mapping = _prepare_webuddhist_mapping_payload(
            relations=formatted_relations,
            text_id=text_id
        )
        logger.info(f"Mapping: {mapping}")
        if mapping.get("text_mappings", None) is not None and len(mapping["text_mappings"]) <= 0:
            return

        logger.info("Uploading mapping to Webuddhist")
        response = _upload_mapping_to_webuddhist(
            mapping=mapping,
            destination_environment=destination_environment
        )
        return response
    except Exception as e:
        raise e


def _upload_mapping_to_webuddhist(mapping, destination_environment: str):
    try:
        token = get_token(destination_environment=destination_environment)

        logger.info(f"Destination environment: {destination_environment}")

        we_buddhist_url = get(
            f"{destination_environment.upper()}_WEBUDDHIST_API_ENDPOINT"
        )
        
        logger.info(f"WeBuddhist URL: {we_buddhist_url}")
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        logger.info(f"Uploading mapping to Webuddhist")
        
        response = requests.post(
            f"{we_buddhist_url}/mappings",
            json=mapping,
            headers=headers,
            timeout=600  # 10 minutes timeout - WeBuddhist on Render can be very slow
        )
        sleep(5)
        logger.info("Uploaded mapping to webuddhist")

        logger.info(f"Response status: {response.status_code}")
        if response.status_code == 201:
            logger.info("Mapping uploaded successfully")

        if response.status_code == 404:
            logger.error(response)

        if response.status_code not in [200, 201]:
            logger.error(f"Upload failed with status {response.status_code}")
            raise Exception(f"Upload failed: {response.status_code} - {response.text}")

        return response.json()
    except Exception as e:
        raise e


def _prepare_webuddhist_mapping_payload(relations, text_id: str):
    try:

        payload = {
            "text_mappings": []
        }
        for relation in relations.segments:
            text_mapping = {
                "text_id": text_id,
                "segment_id": relation.segment_id,
                "mappings": []
            }
            segment_mapping = []
            for mapped in relation.mappings:
                segment_mapping.append({
                    "parent_text_id": mapped.text_id,
                    "segments": [
                        segment.segment_id
                        for segment in mapped.segments
                    ]
                })
            if len(segment_mapping) == 0:
                continue
            text_mapping["mappings"] = segment_mapping
            payload["text_mappings"].append(text_mapping)
        return payload
    except Exception as e:
        raise e


def get_all_segments_by_segment_ids(text_id: str, segment_ids: list[str]):
    with SessionLocal() as session:
        segments = (
            session.query(SegmentMapping)
            .filter(
                SegmentMapping.text_id == text_id,
                SegmentMapping.segment_id.in_(segment_ids),
            )
            .all()
        )
        return segments


def _format_all_text_segment_relation_mapping(
    text_id: str,
    all_text_segment_relations
):
    """
    Format all the text segment relation mapping
    """
    response = AllTextSegmentRelationMapping(
        text_id=text_id,
        segments=[]
    )
    for task in all_text_segment_relations:
        task_dict = {
            "task_id": str(task.task_id),
            "job_id": str(task.root_job_id),
            "text_id": str(task.text_id),
            "segment_id": task.segment_id,
            "status": task.status,
            "result_json": task.result_json,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        }

        segment = SegmentsRelation(
            segment_id=task.segment_id,
            mappings=[]
        )
        for mapping in task_dict['result_json']:
            mapping_dict = Mapping(
                text_id=mapping['manifestation_id'],
                segments=mapping['segments']
            )
            segment.mappings.append(mapping_dict)
        response.segments.append(segment)
    return response


def get_token(destination_environment: str) -> str:
    """
    Get token from Webuddhist
    """
    try:
        logger.info("Getting token from Webuddhist")
        email = get("WEBUDDHIST_LOG_IN_EMAIL")
        password = get("WEBUDDHIST_LOG_IN_PASSWORD")

        we_buddhist_url = get(
            f"{destination_environment.upper()}_WEBUDDHIST_API_ENDPOINT"
        )
        logger.info(f"Signing to Webuddhist at {we_buddhist_url}/auth/login")
        response = requests.post(
            f"{we_buddhist_url}/auth/login", 
            json={"email": email, "password": password},
            timeout=120  # 2 minutes timeout for login (cold start)
        )
        sleep(5)
        if response.status_code != 200:
            logger.error(f"Login failed with status {response.status_code}: {response.text}")
            raise Exception(f"WeBuddhist login failed: {response.status_code}")
        
        response_data = response.json()
        logger.info(f"Successfully logged in to WeBuddhist")

        # Extract token from nested structure: response['auth']['access_token']
        token = response_data["auth"]["access_token"]
        logger.info("Successfully obtained authentication token")

        return token
    except Exception as e:
        raise e
