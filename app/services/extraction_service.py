import asyncio
from typing import Type

from pydantic import BaseModel

from app.services.openai_client import client
from app.services.prompts import PROMPTS
import app.schemas.worker_extraction as schemas


EXTRACTION_CONFIG = {
    "job_completion_confirmed": {
        "schema": schemas.job_completion_confirmed,
        "prompt": PROMPTS["job_completion_confirmed"],
    },
    "scenario_completed": {
        "schema": schemas.scenario_completed,
        "prompt": PROMPTS["scenario_completed"],
    },
    "additional_notes": {
        "schema": schemas.additional_notes,
        "prompt": PROMPTS["additional_notes"],
    },
    "worker_type": {
        "schema": schemas.worker_type,
        "prompt": PROMPTS["worker_type"],
    },
    "locality": {
        "schema": schemas.locality,
        "prompt": PROMPTS["locality"],
    },
    "worker_name": {
        "schema": schemas.worker_name,
        "prompt": PROMPTS["worker_name"],
    },
    "experience_years": {
        "schema": schemas.experience_years,
        "prompt": PROMPTS["experience"],
    },
}


async def extract_single(
    transcript: str,
    prompt: str,
    schema: Type[BaseModel],
) -> BaseModel:
    """
    Extract a single field using OpenAI Structured Outputs.
    """

    response = await client.responses.parse(
        model="gpt-5",
        input=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": transcript,
            },
        ],
        text_format=schema,
    )

    return response.output_parsed


async def extract_all(transcript: str) -> dict:
    """
    Extract all configured fields in parallel.

    Returns:
    {
        "status": "...",
        "notes": "...",
        "type": "...",
        ...
    }
    """

    tasks = {
        name: asyncio.create_task(
            extract_single(
                transcript=transcript,
                prompt=config["prompt"],
                schema=config["schema"],
            )
        )
        for name, config in EXTRACTION_CONFIG.items()
    }

    responses = await asyncio.gather(*tasks.values())

    extracted = {}

    for response in responses:
        extracted.update(response.model_dump())
    return extracted

if __name__ == "__main__":
    import asyncio

    transcript = """
    Hi, my name is kasim.
    I am an electrician.
    I have 6 years of experience.
    I live in Mapusa.
    """

    result = asyncio.run(extract_all(transcript))

    print(result)