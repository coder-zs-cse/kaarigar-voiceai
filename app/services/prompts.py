PROMPTS = {
    "job_completion_confirmed": """
Only relevant when the call was about a paired worker checking in on an ongoing job.

Determine whether the worker confirmed the job is finished.

Return exactly one of:
- yes: worker said the job is complete, done, or finished.
- no: worker said the job is still in progress or not yet done.
- not_applicable: this wasn't a paired-job call or the topic didn't come up.

Return only:
yes | no | not_applicable
""",

    "scenario_completed": """
Determine how this call ended.

Return exactly one of these values (no extra text):

- new_worker_registered
- registration_incomplete
- out_of_scope
- update_details_request
- idle_callback
- job_marked_complete
- deregister_request
- unclear

Definitions:

- new_worker_registered:
  The caller was a new worker and successfully completed registration.
  Name, trade, locality, and experience were all captured.

- registration_incomplete:
  Registration started but one or more required fields were not captured.

- out_of_scope:
  The caller requested something unsupported.

- update_details_request:
  An existing worker requested changes to their information.

- idle_callback:
  Existing worker asking about jobs or general status.

- job_marked_complete:
  Worker confirmed an ongoing job is finished.

- deregister_request:
  Worker requested removal from the platform.

- unclear:
  None of the above.

Return only one value.
""",

    "additional_notes": """
Extract any additional notes about the worker that are useful but are NOT already captured by:

- worker_name
- worker_type
- locality
- experience

Return a plain string.

Return an empty string if there are no additional notes.
""",

    "worker_type": """
Extract the worker type.

Match to the closest value from the list below.
Handle spelling mistakes, accent variations, and synonyms.

Return exactly one of:

electrician
plumber
painter
mason
locksmith
carpenter
ac_technician
tile_worker
welder
cctv_installer
pest_control
cleaning_service
waterproofing
false_ceiling
appliance_repair
geyser_repair
glass_fabricator
solar_installer
civil_work
interior_texture
driver
cook
tailor
gardener
none
""",

    "locality": """
Extract the Goa locality/area where the worker is based.

Match to the closest value from:

bicholim
canacona
cuncolim
curchorem
mapusa
margao
mormugao
panaji
pernem
ponda
quepem
sanguem
sanquelim
valpoi
vasco
porvorim

Return the canonical value.

Return an empty string if no matching locality exists or if it was never mentioned.
""",

    "worker_name": """
Extract the worker's full name.

Return only the full name as a string.

Return an empty string if no worker name was mentioned.
""",

    "experience": """
Extract the worker's years of experience.

Rules:
- Return a whole number as a string.
- If they said "5-7 years", return "5".
- If they said "around 10 years", return "10".
- If experience is unknown, not mentioned, or refused, return "0".

Return only the number.
""",
}