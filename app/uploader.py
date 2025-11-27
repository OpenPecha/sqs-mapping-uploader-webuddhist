from app.db.postgres import SessionLocal
from app.db.models import RootJob, SegmentTask
import requests
from app.models import (
    AllTextSegmentRelationMapping,
    SegmentsRelation,
    Mapping,
)
from app.config import get
import logging
from time import sleep

logger = logging.getLogger(__name__)

def upload_all_segments_mapping_to_webuddhist(manifestation_id: str):
    try:
        logger.info("Getting all the segments relations by manifestation")
        relations = get_all_segments_relation_by_manifestation(
            manifestation_id=manifestation_id
        )
        logger.info("Preparing the webuddhist mapping payload")
        mapping = _prepare_webuddhist_mapping_payload(
            relations=relations
        )
        # if mapping.get("text_mappings", None) is not None and len(mapping["text_mappings"]) <= 0:
        #     return
        # response = _upload_mapping_to_webuddhist(
        #     mapping=mapping
        # )
        # return response
        return "done"
    except Exception as e:
        raise e

def _upload_mapping_to_webuddhist(mapping):
    try:
        token = get_token()
        we_buddhist_url = get("WEBUDDHIST_API_ENDPOINT")
        headers = {
            "Authorization": f"Bearer {token}"
        }
        logger.info(f"Uploading mapping to Webuddhist")
        logger.info(f"Mapping payload: {mapping}")
        
        response = requests.post(
            f"{we_buddhist_url}/mappings", 
            json=mapping, 
            headers=headers,
            timeout=600  # 10 minutes timeout - WeBuddhist on Render can be very slow
        )
        sleep(5)
        logger.info(f"Upload response status: {response.status_code}")
        logger.info(f"Response from Webuddhist: {response.text}")
        
        if response.status_code == 404:
            logger.error(f"Endpoint not found. Check if '{we_buddhist_url}/mappings' is the correct endpoint")
            raise Exception(f"WeBuddhist API endpoint not found: {we_buddhist_url}/mappings")
        
        if response.status_code not in [200, 201]:
            logger.error(f"Upload failed with status {response.status_code}")
            raise Exception(f"Upload failed: {response.status_code} - {response.text}")
        
        return response.json()
    except Exception as e:
        raise e

def _prepare_webuddhist_mapping_payload(relations):
    try:

        payload = {
            "text_mappings": []
        }
        for relation in relations.segments:
            payload = {
                "text_mappings": []
            }
            text_mapping = {
                "text_id": relations.manifestation_id,
                "segment_id": relation.segment_id,
                "mappings": []
            }
            segment_mapping = []
            for mapped in relation.mappings:
                segment_mapping.append({
                    "parent_text_id": mapped.manifestation_id,
                    "segments": [
                        segment.segment_id
                        for segment in mapped.segments
                    ]
                })
            text_mapping["mappings"] = segment_mapping
            if len(text_mapping["mappings"]) == 0:
                continue
            payload["text_mappings"].append(text_mapping)
            if payload.get("text_mappings", None) is not None and len(payload["text_mappings"]) <= 0:
                continue
            response = _upload_mapping_to_webuddhist(
                mapping=payload
            )
            logger.info(f"Response from Webuddhist: {response}")
        return payload
    except Exception as e:
        raise e

def get_all_segments_relation_by_manifestation(manifestation_id: str):
    try:
        with SessionLocal() as session:
            root_job = session.query(RootJob).filter(RootJob.manifestation_id == manifestation_id).first()
            if root_job.completed_segments < root_job.total_segments:
                raise Exception("Job not completed")
            
            all_text_segment_relations = session.query(SegmentTask).filter(SegmentTask.job_id == root_job.job_id).all()

            response = _format_all_text_segment_relation_mapping(
                manifestation_id = manifestation_id,
                all_text_segment_relations = all_text_segment_relations
            )
            return response
    except Exception as e:
        raise e

def _format_all_text_segment_relation_mapping(manifestation_id: str, all_text_segment_relations):
    response = AllTextSegmentRelationMapping(
        manifestation_id = manifestation_id,
        segments = []
    )
    for task in all_text_segment_relations:
        task_dict = {
            "task_id": str(task.task_id),
            "job_id": str(task.job_id),
            "segment_id": task.segment_id,
            "status": task.status,
            "result_json": task.result_json,
            "result_location": task.result_location,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        }
        logger.info(f"Starting with formatting task: {task_dict}")
        segment = SegmentsRelation(
            segment_id = task.segment_id,
            mappings = []
        )
        for mapping in task_dict["result_json"]:
            mapping_dict = Mapping(
                manifestation_id = mapping["manifestation_id"],
                segments = mapping["segments"]
            )
            segment.mappings.append(mapping_dict)
        logger.info(f"Segment: {segment}")
        response.segments.append(segment)
    logger.info(f"Response: {response}")
    return response

def get_token()->str:
    try:
        logger.info("Getting token from Webuddhist")
        email = get("WEBUDDHIST_LOG_IN_EMAIL")
        password = get("WEBUDDHIST_LOG_IN_PASSWORD")

        we_buddhist_url = get("WEBUDDHIST_API_ENDPOINT")
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

if __name__ == "__main__":
    manifestation_id = input("Enter the manifestation id: ")

    mapping_payload = upload_all_segments_mapping_to_webuddhist(
        manifestation_id = manifestation_id
    )
    print("mapping_payload has been written to mapping_payload.json")