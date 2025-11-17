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

logger = logging.getLogger(__name__)

def upload_all_segments_mapping_to_webuddhist(manifestation_id: str):
    try:
        logger.info("Getting all the segments relations by manifestation")
        relations = get_all_segments_relation_by_manifestation(
            manifestation_id = manifestation_id
        )
        logger.info("Preparing the webuddhist mapping payload")
        mapping = _prepare_webuddhist_mapping_payload(
            relations = relations
        )
        response = _upload_mapping_to_webuddhist(
            mapping = mapping
        )
        return mapping
    except Exception as e:
        raise e

def _upload_mapping_to_webuddhist(mapping):
    try:
        token = get_token()
        we_buddhist_url = get("WEBUDDHIST_API_ENDPOINT")
        headers = {
            "Authorization": f"Bearer {token}"
        }
        response = requests.post(f"{we_buddhist_url}/mapping", json=mapping, headers=headers)
        return response.json()
    except Exception as e:
        raise e

def _prepare_webuddhist_mapping_payload(relations):
    try:

        payload = {
            "text_mappings": []
        }
        for relation in relations.segments:
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
            payload["text_mappings"].append(text_mapping)
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
        email = get("WEBUDDHIST_LOG_IN_EMAIL")
        password = get("WEBUDDHIST_LOG_IN_PASSWORD")

        we_buddhist_url = get("WEBUDDHIST_API_ENDPOINT")

        response = requests.post(f"{we_buddhist_url}/auth/login", json={"email": email, "password": password})

        token = response.json()["accessToken"]

        return token
    except Exception as e:
        raise e

if __name__ == "__main__":
    manifestation_id = input("Enter the manifestation id: ")

    mapping_payload = upload_all_segments_mapping_to_webuddhist(
        manifestation_id = manifestation_id
    )

    import json

    with open("mapping_payload.json", "w", encoding='utf-8') as f:
        # Use .model_dump() if this is a Pydantic model, otherwise fallback to .__dict__ or as appropriate
        try:
            payload_dict = mapping_payload.model_dump()
        except AttributeError:
            try:
                payload_dict = mapping_payload.__dict__
            except Exception:
                payload_dict = mapping_payload
        json.dump(payload_dict, f, ensure_ascii=False, indent=4)
    print("mapping_payload has been written to mapping_payload.json")