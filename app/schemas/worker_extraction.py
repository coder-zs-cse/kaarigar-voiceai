from pydantic import BaseModel , Field
from typing import Literal

class job_completion_confirmed(BaseModel):
    status : Literal["yes","no","not_applicable"] = Field(
        description='Status of completion of job',
        default='not_applicable',
    )

class scenario_completed(BaseModel):
    status : Literal["new_worker_registered", "registration_incomplete" , "out_of_scope" , "update_details_request" , "idle_callback" , "job_marked_complete","deregister_request","unclear"] = Field(
        description='Determine how this call ended based on the conversation',
        default='unclear'
    )

class additional_notes(BaseModel):
    notes : str = Field(
        description='Any other meaningful info the worker mentioned — complaints, feature requests, concerns, follow-up asks',
        default=""
    )
 
class worker_type(BaseModel):
    type : str = Field(
        description='the worker type that the worker identify as',
        default=""
    )

class locality(BaseModel):
    location : str = Field(
        description='location/locality of the worker',
        default = ''
    )

class worker_name(BaseModel):
    name : str = Field(
        description='Name of the worker',
        default=""
    )

class experience_years(BaseModel):
    experience : int = Field(
        description="worker's years of experience",
        default=0,
    )

