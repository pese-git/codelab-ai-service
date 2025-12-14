"""
Tool Manager for handling tool call lifecycle.
Manages tracking, timeouts, retries, and correlation of tool calls.
"""

import asyncio
import logging
from typing import Dict, Optional, List, Set
from datetime import datetime, timedelta
from collections import defaultdict

from app.models.schemas import (
    ToolCall, 
    ToolResult, 
    PendingToolCall,
    ToolExecutionStatus,
    SessionState
)

logger = logging.getLogger("agent-runtime")


class ToolCallTracker:
    """Tracks active tool calls and their states"""
    
    def __init__(self):
        self._pending_calls: Dict[str, PendingToolCall] = {}
        self._session_calls: Dict[str, List[str]] = defaultdict(list)
        self._results: Dict[str, ToolResult] = {}
        self._locks = defaultdict(asyncio.Lock)
    
    async def register_tool_call(
        self, 
        tool_call: ToolCall, 
        session_id: str,
        timeout_seconds: int = 30,
        max_retries: int = 3
    ) -> PendingToolCall:
        """Register a new tool call for tracking"""
        async with self._locks[session_id]:
            pending = PendingToolCall(
                tool_call=tool_call,
                session_id=session_id,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries
            )
            
            self._pending_calls[tool_call.id] = pending
            self._session_calls[session_id].append(tool_call.id)
            
            logger.info(
                f"Registered tool call {tool_call.id} for session {session_id}: "
                f"{tool_call.tool_name}({tool_call.arguments})"
            )
            
            return pending
    
    async def get_pending_call(self, call_id: str) -> Optional[PendingToolCall]:
        """Get pending tool call by ID"""
        return self._pending_calls.get(call_id)
    
    async def get_session_calls(self, session_id: str) -> List[PendingToolCall]:
        """Get all pending calls for a session"""
        async with self._locks[session_id]:
            call_ids = self._session_calls.get(session_id, [])
            return [
                self._pending_calls[call_id] 
                for call_id in call_ids 
                if call_id in self._pending_calls
            ]
    
    async def mark_executing(self, call_id: str) -> bool:
        """Mark tool call as executing"""
        if call_id in self._pending_calls:
            self._pending_calls[call_id].tool_call.status = ToolExecutionStatus.EXECUTING
            logger.info(f"Tool call {call_id} marked as executing")
            return True
        return False
    
    async def complete_tool_call(
        self, 
        call_id: str, 
        result: ToolResult
    ) -> Optional[PendingToolCall]:
        """Complete a tool call with result"""
        pending = self._pending_calls.get(call_id)
        if not pending:
            logger.warning(f"Tool call {call_id} not found in pending calls")
            return None
        
        async with self._locks[pending.session_id]:
            # Update status
            pending.tool_call.status = ToolExecutionStatus.COMPLETED
            
            # Store result
            self._results[call_id] = result
            
            # Remove from pending
            del self._pending_calls[call_id]
            self._session_calls[pending.session_id].remove(call_id)
            
            logger.info(f"Tool call {call_id} completed successfully")
            return pending
    
    async def fail_tool_call(
        self, 
        call_id: str, 
        error: str
    ) -> Optional[PendingToolCall]:
        """Mark tool call as failed"""
        pending = self._pending_calls.get(call_id)
        if not pending:
            return None
        
        async with self._locks[pending.session_id]:
            pending.tool_call.status = ToolExecutionStatus.FAILED
            
            # Create error result
            result = ToolResult(
                call_id=call_id,
                error=error
            )
            self._results[call_id] = result
            
            # Check if we should retry
            if pending.retry_count < pending.max_retries:
                pending.retry_count += 1
                pending.tool_call.status = ToolExecutionStatus.PENDING
                logger.info(f"Tool call {call_id} failed, retrying ({pending.retry_count}/{pending.max_retries})")
                return pending
            
            # Max retries reached, remove from pending
            del self._pending_calls[call_id]
            self._session_calls[pending.session_id].remove(call_id)
            
            logger.error(f"Tool call {call_id} failed after {pending.retry_count} retries: {error}")
            return None
    
    async def get_result(self, call_id: str) -> Optional[ToolResult]:
        """Get result for a completed tool call"""
        return self._results.get(call_id)
    
    async def check_timeouts(self) -> List[str]:
        """Check for timed out tool calls and return their IDs"""
        timed_out = []
        now = datetime.now()
        
        for call_id, pending in list(self._pending_calls.items()):
            timeout_at = pending.request_time + timedelta(seconds=pending.timeout_seconds)
            if now > timeout_at:
                timed_out.append(call_id)
                await self.timeout_tool_call(call_id)
        
        return timed_out
    
    async def timeout_tool_call(self, call_id: str) -> Optional[PendingToolCall]:
        """Mark tool call as timed out"""
        pending = self._pending_calls.get(call_id)
        if not pending:
            return None
        
        async with self._locks[pending.session_id]:
            pending.tool_call.status = ToolExecutionStatus.TIMEOUT
            
            # Create timeout result
            result = ToolResult(
                call_id=call_id,
                error=f"Tool call timed out after {pending.timeout_seconds} seconds"
            )
            self._results[call_id] = result
            
            # Remove from pending
            del self._pending_calls[call_id]
            self._session_calls[pending.session_id].remove(call_id)
            
            logger.warning(f"Tool call {call_id} timed out")
            return pending
    
    async def cancel_tool_call(self, call_id: str) -> bool:
        """Cancel a pending tool call"""
        pending = self._pending_calls.get(call_id)
        if not pending:
            return False
        
        async with self._locks[pending.session_id]:
            pending.tool_call.status = ToolExecutionStatus.CANCELLED
            
            # Create cancelled result
            result = ToolResult(
                call_id=call_id,
                error="Tool call cancelled"
            )
            self._results[call_id] = result
            
            # Remove from pending
            del self._pending_calls[call_id]
            self._session_calls[pending.session_id].remove(call_id)
            
            logger.info(f"Tool call {call_id} cancelled")
            return True
    
    async def cleanup_session(self, session_id: str):
        """Clean up all data for a session"""
        async with self._locks[session_id]:
            call_ids = self._session_calls.get(session_id, [])
            
            # Cancel all pending calls
            for call_id in call_ids:
                if call_id in self._pending_calls:
                    await self.cancel_tool_call(call_id)
            
            # Remove session data
            if session_id in self._session_calls:
                del self._session_calls[session_id]
            if session_id in self._locks:
                del self._locks[session_id]
            
            logger.info(f"Cleaned up session {session_id}")


class ToolExecutionQueue:
    """Manages queue of tool calls waiting for execution"""
    
    def __init__(self, max_parallel: int = 10):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._executing: Set[str] = set()
        self._max_parallel = max_parallel
        self._lock = asyncio.Lock()
    
    async def enqueue(self, tool_call: ToolCall, session_id: str):
        """Add tool call to execution queue"""
        await self._queue.put((tool_call, session_id))
        logger.debug(f"Enqueued tool call {tool_call.id}, queue size: {self._queue.qsize()}")
    
    async def dequeue(self) -> Optional[tuple[ToolCall, str]]:
        """Get next tool call from queue"""
        try:
            return await self._queue.get()
        except asyncio.CancelledError:
            return None
    
    async def can_execute(self) -> bool:
        """Check if we can execute another tool call"""
        async with self._lock:
            return len(self._executing) < self._max_parallel
    
    async def mark_executing(self, call_id: str):
        """Mark tool call as currently executing"""
        async with self._lock:
            self._executing.add(call_id)
            logger.debug(f"Executing {len(self._executing)} tool calls")
    
    async def mark_completed(self, call_id: str):
        """Mark tool call as completed"""
        async with self._lock:
            self._executing.discard(call_id)
    
    def qsize(self) -> int:
        """Get current queue size"""
        return self._queue.qsize()


# Global instances
_tracker = ToolCallTracker()
_queue = ToolExecutionQueue()


def get_tool_tracker() -> ToolCallTracker:
    """Get global tool call tracker instance"""
    return _tracker


def get_execution_queue() -> ToolExecutionQueue:
    """Get global tool execution queue"""
    return _queue


# Background task for checking timeouts
async def timeout_checker_task():
    """Background task that checks for timed out tool calls"""
    while True:
        try:
            await asyncio.sleep(1)  # Check every second
            timed_out = await _tracker.check_timeouts()
            if timed_out:
                logger.info(f"Timed out {len(timed_out)} tool calls: {timed_out}")
        except Exception as e:
            logger.error(f"Error in timeout checker: {e}")
