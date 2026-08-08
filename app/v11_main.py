from contextlib import asynccontextmanager
from typing import Any
from fastapi import Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import v10_main as v10
from .candidate_store import (
    assign_candidate, candidate_for_search_job, delete_candidate, ensure_candidate_schema,
    get_candidate, list_candidates, mapping_for_jobs, save_candidate,
)
from .intelligence import analyze_job, ensure_intelligence_schema, get_analysis, list_analyses
from .search_job_store import get_search_job
from .security import require_admin

app=v10.app
_original_lifespan=app.router.lifespan_context

@asynccontextmanager
async def v11_lifespan(application):
    async with _original_lifespan(application):
        ensure_candidate_schema(); ensure_intelligence_schema(); yield

app.router.lifespan_context=v11_lifespan
app.version='11.0.0'

class CandidatePayload(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    headline:str=''
    cv_text:str=Field(default='',max_length=50000)
    skills:list[str]=[]
    languages:dict[str,str]={}
    target_roles:list[str]=[]
    notes:str=Field(default='',max_length=10000)

class CandidateAssignmentPayload(BaseModel):
    candidate_profile_id:int|None=None
    enabled:bool=True

@app.get('/intelligence-ui.js')
def intelligence_ui(_:str=Depends(require_admin)):
    from pathlib import Path
    return Response(Path('app/intelligence-ui.js').read_text(encoding='utf-8'),media_type='application/javascript')

@app.get('/api/candidates')
def api_candidates(_:str=Depends(require_admin)):
    return {'candidates':list_candidates(),'assignments':mapping_for_jobs()}

@app.post('/api/candidates')
def create_candidate(payload:CandidatePayload,_:str=Depends(require_admin)):
    try:return {'ok':True,'id':save_candidate(payload.model_dump())}
    except Exception as exc: raise HTTPException(400,str(exc)) from exc

@app.put('/api/candidates/{candidate_id}')
def update_candidate(candidate_id:int,payload:CandidatePayload,_:str=Depends(require_admin)):
    if not get_candidate(candidate_id): raise HTTPException(404,'Candidate profile not found')
    try:save_candidate(payload.model_dump(),candidate_id);return {'ok':True}
    except Exception as exc: raise HTTPException(400,str(exc)) from exc

@app.delete('/api/candidates/{candidate_id}')
def remove_candidate(candidate_id:int,_:str=Depends(require_admin)):
    try:delete_candidate(candidate_id);return {'ok':True}
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@app.put('/api/search-jobs/{search_job_id}/candidate')
def map_candidate(search_job_id:int,payload:CandidateAssignmentPayload,_:str=Depends(require_admin)):
    if not get_search_job(search_job_id,True): raise HTTPException(404,'Search job not found')
    if payload.candidate_profile_id and not get_candidate(payload.candidate_profile_id): raise HTTPException(404,'Candidate profile not found')
    assign_candidate(search_job_id,payload.candidate_profile_id,payload.enabled); return {'ok':True}

@app.get('/api/search-jobs/{search_job_id}/candidate')
def get_search_job_candidate(search_job_id:int,_:str=Depends(require_admin)):
    return {'candidate':candidate_for_search_job(search_job_id)}

@app.post('/api/intelligence/analyze')
def analyze(payload:dict[str,Any],_:str=Depends(require_admin)):
    try:return {'ok':True,'analysis':analyze_job(str(payload['job_key']),int(payload['candidate_profile_id']),payload.get('search_job_id'))}
    except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc)) from exc

@app.get('/api/intelligence')
def intelligence(candidate_profile_id:int|None=None,limit:int=300,_:str=Depends(require_admin)):
    return {'analyses':list_analyses(candidate_profile_id,limit)}

@app.get('/api/intelligence/{candidate_profile_id}/{job_key:path}')
def intelligence_detail(candidate_profile_id:int,job_key:str,_:str=Depends(require_admin)):
    data=get_analysis(job_key,candidate_profile_id)
    if not data: raise HTTPException(404,'Analysis not found')
    return data

@app.get('/api/v11-health')
def v11_health(_:str=Depends(require_admin)):
    return {'status':'ok','version':'11.0.0','candidate_profiles':len(list_candidates()),'analyses':len(list_analyses(limit=10000))}
