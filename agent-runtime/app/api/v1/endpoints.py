"""
API v1 endpoints for agent runtime service.
"""
import json
import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import func

from app.core.config import AppConfig
from app.core.dependencies import DBSession, DBService, SessionManagerDep, AgentContextManagerDep
from app.models.schemas import AgentStreamRequest, HealthResponse, AgentInfo
from app.models.hitl_models import HITLUserDecision, HITLDecision
from app.services.llm_stream_service import stream_response
from app.services.multi_agent_orchestrator import multi_agent_orchestrator
from app.services.agent_router import agent_router
from app.services.hitl_manager import hitl_manager
from app.services.database import SessionModel, MessageModel
from app.agents.base_agent import AgentType

logger = logging.getLogger("agent-runtime.api")
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    logger.debug("Health check called")
    return HealthResponse.model_construct(
        status="healthy", 
        service="agent-runtime", 
        version=AppConfig.VERSION
    )


@router.post("/agent/message/stream")
async def message_stream_sse(request: AgentStreamRequest):
    """
    SSE streaming endpoint for Agent Runtime with multi-agent support.
    
    Accepts:
    - user_message: Regular user message
    - tool_result: Tool execution result from Gateway
    - switch_agent: Explicit agent switch request
    
    Returns:
    - SSE stream with chunks (assistant_message, tool_call, agent_switched, error)
    
    Multi-agent flow:
    1. User message → Orchestrator analyzes → Routes to specialist
    2. Specialist processes → May call tools or switch agents
    3. Tool results continue with current agent
    """
    async def event_generator():
        try:
            logger.info(f"SSE stream started for session: {request.session_id}")
            logger.debug(f"Message type: {request.message.get('type', 'user_message')}")
            
            # Get async session manager
            from app.services.session_manager_async import session_manager as async_session_mgr
            
            if async_session_mgr is None:
                raise RuntimeError("SessionManager not initialized")
            
            # Get or create session (system prompt will be set by agent)
            session = await async_session_mgr.get_or_create(
                request.session_id,
                system_prompt=""  # Agent will set its own prompt
            )
            
            # Process incoming message
            message_type = request.message.get("type", "user_message")
            
            if message_type == "plan_decision":
                # Plan user decision (approve/edit/reject)
                plan_id = request.message.get("plan_id")
                decision_str = request.message.get("decision")
                modified_subtasks = request.message.get("modified_subtasks")
                feedback = request.message.get("feedback")
                
                logger.info(
                    f"Received plan decision: plan_id={plan_id}, "
                    f"decision={decision_str}, session={request.session_id}"
                )
                
                # Validate decision
                try:
                    from app.models.plan_models import PlanDecision
                    decision = PlanDecision(decision_str)
                except ValueError:
                    error_msg = f"Invalid plan decision: {decision_str}"
                    logger.error(error_msg)
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "type": "error",
                            "error": error_msg,
                            "is_final": True
                        })
                    }
                    return
                
                # Get plan from session manager
                plan = async_session_mgr.get_plan(request.session_id)
                if not plan or plan.plan_id != plan_id:
                    error_msg = f"No plan found with id={plan_id}"
                    logger.error(error_msg)
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "type": "error",
                            "error": error_msg,
                            "is_final": True
                        })
                    }
                    return
                
                # Log decision to audit
                from app.services.plan_manager import plan_manager
                await plan_manager.log_decision(
                    session_id=request.session_id,
                    plan_id=plan_id,
                    original_task=plan.original_task,
                    decision=decision,
                    modified_subtasks=modified_subtasks,
                    feedback=feedback
                )
                
                # Clear pending confirmation
                async_session_mgr.clear_pending_plan_confirmation(request.session_id)
                
                # Process decision
                if decision == PlanDecision.APPROVE:
                    logger.info(f"Plan APPROVED: executing {len(plan.subtasks)} subtasks")
                    
                    # Mark plan as approved
                    plan.is_approved = True
                    
                    # Update plan in session manager to persist the change
                    async_session_mgr.set_plan(request.session_id, plan)
                    
                    # Reset current agent to Orchestrator to avoid re-entering Architect
                    from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
                    if async_ctx_mgr:
                        context = await async_ctx_mgr.get_or_create(request.session_id)
                        context.switch_agent(AgentType.ORCHESTRATOR, "Plan approved, starting execution")
                        logger.info(f"Switched to Orchestrator for plan execution in session {request.session_id}")
                    
                    # Continue with plan execution (orchestrator will handle it)
                    async for chunk in multi_agent_orchestrator.process_message(
                        session_id=request.session_id,
                        message=""  # Empty message to trigger plan execution
                    ):
                        chunk_dict = chunk.model_dump(exclude_none=True)
                        chunk_json = json.dumps(chunk_dict)
                        
                        yield {
                            "event": "message",
                            "data": chunk_json
                        }
                        
                        if chunk.is_final:
                            break
                    
                elif decision == PlanDecision.EDIT:
                    logger.info(f"Plan EDITED: updating subtasks")
                    
                    if modified_subtasks:
                        # Update plan with modified subtasks
                        from app.models.schemas import Subtask, SubtaskStatus
                        plan.subtasks = [
                            Subtask(
                                id=st.get("id", f"subtask_{i+1}"),
                                description=st["description"],
                                agent=st["agent"],
                                estimated_time=st.get("estimated_time"),
                                status=SubtaskStatus.PENDING,
                                dependencies=st.get("dependencies", [])
                            )
                            for i, st in enumerate(modified_subtasks)
                        ]
                        plan.is_approved = True
                        
                        # Update plan in session manager to persist the change
                        async_session_mgr.set_plan(request.session_id, plan)
                        
                        # Reset current agent to Orchestrator to avoid re-entering Architect
                        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
                        if async_ctx_mgr:
                            context = await async_ctx_mgr.get_or_create(request.session_id)
                            context.switch_agent(AgentType.ORCHESTRATOR, "Plan edited and approved, starting execution")
                            logger.info(f"Switched to Orchestrator for plan execution in session {request.session_id}")
                        
                        # Continue with modified plan execution
                        async for chunk in multi_agent_orchestrator.process_message(
                            session_id=request.session_id,
                            message=""
                        ):
                            chunk_dict = chunk.model_dump(exclude_none=True)
                            chunk_json = json.dumps(chunk_dict)
                            
                            yield {
                                "event": "message",
                                "data": chunk_json
                            }
                            
                            if chunk.is_final:
                                break
                    else:
                        error_msg = "EDIT decision requires modified_subtasks"
                        logger.error(error_msg)
                        yield {
                            "event": "error",
                            "data": json.dumps({
                                "type": "error",
                                "error": error_msg,
                                "is_final": True
                            })
                        }
                    
                elif decision == PlanDecision.REJECT:
                    logger.info(f"Plan REJECTED: {feedback}")
                    
                    # Clear plan
                    async_session_mgr.clear_plan(request.session_id)
                    
                    # Send rejection message
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "assistant_message",
                            "content": f"План отменен. {feedback or 'Чем могу помочь?'}",
                            "is_final": True
                        })
                    }
                
            elif message_type == "hitl_decision":
                # HITL user decision (approve/edit/reject)
                call_id = request.message.get("call_id")
                decision_str = request.message.get("decision")
                modified_arguments = request.message.get("modified_arguments")
                feedback = request.message.get("feedback")
                
                logger.info(
                    f"Received HITL decision: call_id={call_id}, "
                    f"decision={decision_str}, session={request.session_id}"
                )
                
                # Validate decision
                try:
                    decision = HITLDecision(decision_str)
                except ValueError:
                    error_msg = f"Invalid HITL decision: {decision_str}"
                    logger.error(error_msg)
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "type": "error",
                            "error": error_msg,
                            "is_final": True
                        })
                    }
                    return
                
                # Get pending state
                pending_state = hitl_manager.get_pending(request.session_id, call_id)
                if not pending_state:
                    error_msg = f"No pending HITL state found for call_id={call_id}"
                    logger.error(error_msg)
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "type": "error",
                            "error": error_msg,
                            "is_final": True
                        })
                    }
                    return
                
                # Log decision to audit
                await hitl_manager.log_decision(
                    session_id=request.session_id,
                    call_id=call_id,
                    tool_name=pending_state.tool_name,
                    original_arguments=pending_state.arguments,
                    decision=decision,
                    modified_arguments=modified_arguments,
                    feedback=feedback
                )
                
                # Process decision
                if decision == HITLDecision.APPROVE:
                    # Execute tool with original arguments
                    logger.info(f"HITL APPROVED: executing {pending_state.tool_name}")
                    result = {
                        "status": "approved",
                        "tool_name": pending_state.tool_name,
                        "arguments": pending_state.arguments
                    }
                    
                elif decision == HITLDecision.EDIT:
                    # Execute tool with modified arguments
                    logger.info(f"HITL EDITED: executing {pending_state.tool_name} with modified args")
                    result = {
                        "status": "approved_with_edits",
                        "tool_name": pending_state.tool_name,
                        "arguments": modified_arguments or pending_state.arguments
                    }
                    
                elif decision == HITLDecision.REJECT:
                    # Don't execute, send feedback to LLM
                    logger.info(f"HITL REJECTED: {pending_state.tool_name}, feedback={feedback}")
                    result = {
                        "status": "rejected",
                        "tool_name": pending_state.tool_name,
                        "feedback": feedback or "User rejected this operation"
                    }
                
                # Remove pending state
                await hitl_manager.remove_pending(request.session_id, call_id)
                
                # Add tool result to history
                result_str = json.dumps(result)
                await async_session_mgr.append_tool_result(
                    request.session_id,
                    call_id=call_id,
                    tool_name=pending_state.tool_name,
                    result=result_str
                )
                
                # Continue with LLM (empty message to continue after decision)
                async for chunk in multi_agent_orchestrator.process_message(
                    session_id=request.session_id,
                    message=""
                ):
                    chunk_dict = chunk.model_dump(exclude_none=True)
                    chunk_json = json.dumps(chunk_dict)
                    
                    yield {
                        "event": "message",
                        "data": chunk_json
                    }
                    
                    if chunk.is_final:
                        break
                
            elif message_type == "tool_result":
                # Tool execution result from Gateway
                call_id = request.message.get("call_id")
                tool_name = request.message.get("tool_name")
                result = request.message.get("result")
                error = request.message.get("error")
                
                logger.info(
                    f"Received tool_result: call_id={call_id}, "
                    f"tool={tool_name}, has_error={error is not None}, session={request.session_id}"
                )
                
                # CRITICAL: Validate call_id presence
                if not call_id:
                    error_msg = "tool_result must contain call_id"
                    logger.error(f"Missing call_id in tool_result: {request.message}")
                    raise ValueError(error_msg)
                
                # Check if this was a pending approval (restored request)
                was_pending = hitl_manager.has_pending(request.session_id, call_id)
                if was_pending:
                    logger.info(f"Removing pending approval for restored tool: call_id={call_id}")
                    await hitl_manager.remove_pending(request.session_id, call_id)
                
                # Add tool_result to history as tool message
                result_str = json.dumps(result) if not isinstance(result, str) else result
                await async_session_mgr.append_tool_result(
                    request.session_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    result=result_str
                )
                
                # Check if this is a rejection from restored tool
                # If error message contains "User rejected", don't continue with LLM
                is_user_rejection = error and isinstance(error, str) and "User rejected" in error
                
                if was_pending and is_user_rejection:
                    logger.info(
                        f"Tool was rejected by user, not continuing with LLM: "
                        f"call_id={call_id}, tool={tool_name}"
                    )
                    # Send final message indicating rejection was processed
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "assistant_message",
                            "text": f"Tool {tool_name} was rejected by user.",
                            "is_final": True
                        })
                    }
                else:
                    # Continue with current agent (empty message)
                    async for chunk in multi_agent_orchestrator.process_message(
                        session_id=request.session_id,
                        message=""  # Empty message, continue after tool_result
                    ):
                        chunk_dict = chunk.model_dump(exclude_none=True)
                        chunk_json = json.dumps(chunk_dict)
                        
                        yield {
                            "event": "message",
                            "data": chunk_json
                        }
                        
                        # Break on is_final (plan_completed, error, or regular completion)
                        if chunk.is_final:
                            break
                
            elif message_type == "switch_agent":
                # Explicit agent switch request
                agent_type_str = request.message.get("agent_type")
                content = request.message.get("content", "")
                
                try:
                    target_agent = AgentType(agent_type_str)
                except ValueError:
                    error_msg = f"Invalid agent type: {agent_type_str}"
                    logger.error(error_msg)
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "type": "error",
                            "error": error_msg,
                            "is_final": True
                        })
                    }
                    return
                
                logger.info(
                    f"Explicit agent switch requested: {target_agent.value} "
                    f"for session {request.session_id}"
                )
                
                # Add user message to history
                if content:
                    await async_session_mgr.append_message(
                        request.session_id,
                        role="user",
                        content=content
                    )
                
                # Process with specified agent
                async for chunk in multi_agent_orchestrator.process_message(
                    session_id=request.session_id,
                    message=content,
                    agent_type=target_agent
                ):
                    chunk_dict = chunk.model_dump(exclude_none=True)
                    chunk_json = json.dumps(chunk_dict)
                    
                    yield {
                        "event": "message",
                        "data": chunk_json
                    }
                    
                    if chunk.is_final:
                        break
                
            else:
                # Regular user message
                content = request.message.get("content", "")
                logger.info(
                    f"Received user_message: session={request.session_id}, "
                    f"length={len(content)}"
                )
                
                await async_session_mgr.append_message(
                    request.session_id,
                    role="user",
                    content=content
                )
                
                # Process through multi-agent system
                async for chunk in multi_agent_orchestrator.process_message(
                    session_id=request.session_id,
                    message=content
                ):
                    chunk_dict = chunk.model_dump(exclude_none=True)
                    chunk_json = json.dumps(chunk_dict)
                    
                    logger.debug(
                        f"Sending chunk: type={chunk.type}, is_final={chunk.is_final}"
                    )
                    
                    yield {
                        "event": "message",
                        "data": chunk_json
                    }
                    
                    # Break on plan_completed, error, or regular is_final (for non-plan tasks)
                    if chunk.is_final:
                        logger.info(
                            f"Stream completed for session {request.session_id}: "
                            f"final_type={chunk.type}"
                        )
                        break
            
            # Send done event
            yield {
                "event": "done",
                "data": json.dumps({"status": "completed"})
            }
            
        except Exception as e:
            logger.error(
                f"Exception in SSE stream for session {request.session_id}: {e}",
                exc_info=True
            )
            
            # Send error event
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": str(e),
                    "is_final": True
                })
            }
    
    return EventSourceResponse(event_generator())


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents():
    """
    Get information about all registered agents.
    
    Returns:
        List of agent information including capabilities and restrictions
    """
    logger.debug("Listing all registered agents")
    
    agents_info = []
    for agent_type in agent_router.list_agents():
        agent = agent_router.get_agent(agent_type)
        agents_info.append(AgentInfo(
            type=agent.agent_type.value,
            name=f"{agent.agent_type.value.capitalize()} Agent",
            description=agent.system_prompt.split('\n')[0],  # First line of prompt
            allowed_tools=agent.get_allowed_tools(),
            has_file_restrictions=bool(agent.file_restrictions)
        ))
    
    logger.info(f"Returning info for {len(agents_info)} agents")
    return agents_info


@router.get("/agents/{session_id}/current")
async def get_current_agent(
    session_id: str,
    agent_ctx_mgr: AgentContextManagerDep
):
    """
    Get current active agent for a session.
    
    Args:
        session_id: Session identifier
        agent_ctx_mgr: Async agent context manager (injected)
        
    Returns:
        Current agent information and switch history
    """
    logger.debug(f"Getting current agent for session {session_id}")
    
    # Get agent context (direct access to async manager)
    agent_context = agent_ctx_mgr.get(session_id)
    
    if not agent_context:
        return JSONResponse(
            content={"error": "Session not found"},
            status_code=404
        )
    
    return {
        "session_id": session_id,
        "current_agent": agent_context.current_agent.value,
        "agent_history": agent_context.get_agent_history(),
        "switch_count": agent_context.switch_count
    }


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    session_mgr: SessionManagerDep,
    agent_ctx_mgr: AgentContextManagerDep
):
    """
    Get message history for a session.
    
    This endpoint allows the IDE to restore chat history after restart.
    
    Args:
        session_id: Session identifier
        session_mgr: Async session manager (injected)
        agent_ctx_mgr: Async agent context manager (injected)
        
    Returns:
        Session history with messages and metadata
    """
    logger.debug(f"Getting history for session {session_id}")
    
    # Check if session exists (direct access to async manager)
    if not session_mgr.exists(session_id):
        return JSONResponse(
            content={"error": f"Session {session_id} not found"},
            status_code=404
        )
    
    # Get session state (direct access)
    session_state = session_mgr.get(session_id)
    
    # Get message history (direct access)
    messages = session_mgr.get_history(session_id)
    
    # Get current agent info (direct access)
    agent_context = agent_ctx_mgr.get(session_id)
    current_agent = agent_context.current_agent if agent_context else None
    agent_history = agent_context.get_agent_history() if agent_context else []
    
    return {
        "session_id": session_id,
        "messages": messages,
        "message_count": len(messages),
        "last_activity": session_state.last_activity.isoformat() if session_state else None,
        "current_agent": current_agent.value if current_agent else None,
        "agent_history": agent_history
    }


@router.get("/sessions")
async def list_sessions(
    db: DBSession,
    db_service: DBService,
    agent_ctx_mgr: AgentContextManagerDep
):
    """
    List all active sessions with metadata.
    
    Args:
        db: Database session (injected)
        db_service: Database service (injected)
        agent_ctx_mgr: Async agent context manager (injected)
        
    Returns:
        List of sessions with title, description, and basic info
    """
    logger.debug("Listing all sessions")
    
    from sqlalchemy import select
    
    session_list = []
    
    # Get all sessions with message count in one optimized query using LEFT JOIN
    result = await db.execute(
        select(
            SessionModel,
            func.count(MessageModel.id).label('message_count')
        ).outerjoin(
            MessageModel,
            SessionModel.id == MessageModel.session_db_id
        ).where(
            SessionModel.deleted_at.is_(None)
        ).group_by(
            SessionModel.id
        ).order_by(
            SessionModel.last_activity.desc()
        )
    )
    
    sessions_with_counts = result.all()
    
    for session_model, message_count in sessions_with_counts:
        session_id = session_model.session_id
        
        # Get current agent (direct access to async manager)
        agent_context = agent_ctx_mgr.get(session_id)
        current_agent = agent_context.current_agent if agent_context else None
        
        session_info = {
            "session_id": session_id,
            "message_count": message_count,
            "last_activity": session_model.last_activity.isoformat() if session_model.last_activity else None,
            "current_agent": current_agent.value if current_agent else None,
            "title": session_model.title,
            "description": session_model.description,
            "created_at": session_model.created_at.isoformat() if session_model.created_at else None
        }
        session_list.append(session_info)
    
    return {
        "sessions": session_list,
        "total": len(session_list)
    }


@router.post("/sessions")
async def create_session(
    db: DBSession,
    db_service: DBService,
    session_mgr: SessionManagerDep,
    agent_ctx_mgr: AgentContextManagerDep
):
    """
    Create a new session explicitly.
    
    This endpoint allows the IDE to create a session before opening WebSocket.
    The session will be created in the database and a unique session_id will be returned.
    
    Args:
        db: Database session (injected)
        db_service: Database service (injected)
        session_mgr: Async session manager (injected)
        agent_ctx_mgr: Async agent context manager (injected)
        
    Returns:
        Session information with session_id
    """
    logger.info("Creating new session")
    
    # Create session in database first to get auto-generated UUID
    session_id = None
    
    try:
        new_session = SessionModel(
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            is_active=True
        )
        db.add(new_session)
        await db.flush()  # Get the auto-generated id
        session_id = new_session.id
        await db.commit()
        
        # Create in-memory session using async manager
        session = await session_mgr.create(
            session_id,
            system_prompt=""
        )
        
        # Initialize agent context with orchestrator
        await agent_ctx_mgr.get_or_create(
            session_id,
            initial_agent=AgentType.ORCHESTRATOR
        )
        
        logger.info(f"Created new session: {session_id}")
        
        return {
            "session_id": session_id,
            "message_count": 0,
            "current_agent": "orchestrator",
            "created_at": session.last_activity.isoformat()
        }
        
    except Exception as e:
        # If initialization failed after DB commit, clean up database record
        if session_id:
            logger.error(f"Failed to initialize session {session_id}, cleaning up: {e}")
            try:
                await db_service.delete_session(db, session_id, soft=False)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup session {session_id}: {cleanup_error}")
        raise


@router.get("/sessions/{session_id}/pending-approvals")
async def get_pending_approvals(
    session_id: str,
    session_mgr: SessionManagerDep
):
    """
    Get all pending approval requests for a session.
    
    This endpoint is used by the IDE to restore pending approvals
    after restart or reinstall.
    
    Args:
        session_id: Session identifier
        session_mgr: Async session manager (injected)
        
    Returns:
        List of pending approval requests with their details
    """
    logger.debug(f"Getting pending approvals for session {session_id}")
    
    # Check if session exists (direct access to async manager)
    if not session_mgr.exists(session_id):
        return JSONResponse(
            content={"error": f"Session {session_id} not found"},
            status_code=404
        )
    
    # Get pending approvals from HITL manager (which loads from database)
    try:
        pending_approvals = hitl_manager.get_all_pending(session_id)
        
        return {
            "session_id": session_id,
            "pending_approvals": [
                {
                    "call_id": p.call_id,
                    "tool_name": p.tool_name,
                    "arguments": p.arguments,
                    "reason": p.reason,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in pending_approvals
            ],
            "count": len(pending_approvals)
        }
    except Exception as e:
        logger.error(f"Failed to get pending approvals: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "Failed to retrieve pending approvals"},
            status_code=500
        )


