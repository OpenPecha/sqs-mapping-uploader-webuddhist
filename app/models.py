from pydantic import BaseModel

class Span(BaseModel):
    start: int
    end: int 

class MappingSegment(BaseModel):
    segment_id: str
    span: Span

class Mapping(BaseModel):
    manifestation_id: str
    segments: list[MappingSegment]

class SegmentsRelation(BaseModel):
    segment_id: str
    mappings: list[Mapping]

class AllTextSegmentRelationMapping(BaseModel):
    manifestation_id: str
    segments: list[SegmentsRelation]