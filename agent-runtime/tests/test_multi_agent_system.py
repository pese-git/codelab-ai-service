"""
Tests for multi-agent system.

Tests agent initialization, routing, and switching.
"""
import pytest
from app.agents.base_agent import AgentType
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.coder_agent import CoderAgent
from app.agents.architect_agent import ArchitectAgent
from app.agents.debug_agent import DebugAgent
from app.agents.ask_agent import AskAgent
from app.services.agent_router import AgentRouter
from app.services.agent_context_async import AgentContext, AsyncAgentContextManager


class TestAgentInitialization:
    """Test agent initialization and configuration"""
    
    def test_orchestrator_agent_init(self):
        """Test Orchestrator agent initialization"""
        agent = OrchestratorAgent()
        
        assert agent.agent_type == AgentType.ORCHESTRATOR
        assert "read_file" in agent.allowed_tools
        assert "list_files" in agent.allowed_tools
        assert "search_in_code" in agent.allowed_tools
        assert "write_file" not in agent.allowed_tools
        assert len(agent.file_restrictions) == 0
    
    def test_coder_agent_init(self):
        """Test Coder agent initialization"""
        agent = CoderAgent()
        
        assert agent.agent_type == AgentType.CODER
        assert "read_file" in agent.allowed_tools
        assert "write_file" in agent.allowed_tools
        assert "execute_command" in agent.allowed_tools
        assert agent.can_use_tool("write_file")
        assert agent.can_use_tool("execute_command")
    
    def test_architect_agent_init(self):
        """Test Architect agent initialization"""
        agent = ArchitectAgent()
        
        assert agent.agent_type == AgentType.ARCHITECT
        assert "write_file" in agent.allowed_tools
        assert len(agent.file_restrictions) > 0
        assert agent.can_edit_file("docs/architecture.md")
        assert agent.can_edit_file("README.md")
        assert not agent.can_edit_file("lib/main.dart")
        assert not agent.can_edit_file("src/app.py")
    
    def test_debug_agent_init(self):
        """Test Debug agent initialization"""
        agent = DebugAgent()
        
        assert agent.agent_type == AgentType.DEBUG
        assert "read_file" in agent.allowed_tools
        assert "execute_command" in agent.allowed_tools
        assert "write_file" not in agent.allowed_tools
        assert not agent.can_use_tool("write_file")
    
    def test_ask_agent_init(self):
        """Test Ask agent initialization"""
        agent = AskAgent()
        
        assert agent.agent_type == AgentType.ASK
        assert "read_file" in agent.allowed_tools
        assert "write_file" not in agent.allowed_tools
        assert "execute_command" not in agent.allowed_tools
        assert not agent.can_use_tool("write_file")
        assert not agent.can_use_tool("execute_command")


class TestAgentRouter:
    """Test agent router functionality"""
    
    def test_agent_registration(self):
        """Test agent registration"""
        router = AgentRouter()
        agent = CoderAgent()
        
        router.register_agent(agent)
        
        assert router.has_agent(AgentType.CODER)
        assert AgentType.CODER in router.list_agents()
    
    def test_get_agent(self):
        """Test getting registered agent"""
        router = AgentRouter()
        agent = CoderAgent()
        router.register_agent(agent)
        
        retrieved = router.get_agent(AgentType.CODER)
        
        assert retrieved is agent
        assert retrieved.agent_type == AgentType.CODER
    
    def test_get_nonexistent_agent(self):
        """Test getting non-existent agent raises error"""
        router = AgentRouter()
        
        with pytest.raises(ValueError, match="not found"):
            router.get_agent(AgentType.CODER)
    
    def test_agent_info(self):
        """Test getting agent information"""
        router = AgentRouter()
        agent = CoderAgent()
        router.register_agent(agent)
        
        info = router.get_agent_info(AgentType.CODER)
        
        assert info["type"] == "coder"
        assert "allowed_tools" in info
        assert isinstance(info["allowed_tools"], list)


class TestAgentContext:
    """Test agent context management"""
    
    def test_context_creation(self):
        """Test creating agent context"""
        context = AgentContext(session_id="test_session")
        
        assert context.session_id == "test_session"
        assert context.current_agent == AgentType.ORCHESTRATOR
        assert len(context.agent_history) == 0
        assert context.switch_count == 0
    
    def test_agent_switch(self):
        """Test switching agents"""
        context = AgentContext(session_id="test_session")
        
        context.switch_agent(AgentType.CODER, "Test switch")
        
        assert context.current_agent == AgentType.CODER
        assert context.switch_count == 1
        assert len(context.agent_history) == 1
        assert context.agent_history[0]["from"] == "orchestrator"
        assert context.agent_history[0]["to"] == "coder"
        assert context.agent_history[0]["reason"] == "Test switch"
    
    def test_multiple_switches(self):
        """Test multiple agent switches"""
        context = AgentContext(session_id="test_session")
        
        context.switch_agent(AgentType.CODER, "First switch")
        context.switch_agent(AgentType.DEBUG, "Second switch")
        context.switch_agent(AgentType.ASK, "Third switch")
        
        assert context.current_agent == AgentType.ASK
        assert context.switch_count == 3
        assert len(context.agent_history) == 3
    
    def test_same_agent_switch_skipped(self):
        """Test switching to same agent is skipped"""
        context = AgentContext(session_id="test_session")
        
        context.switch_agent(AgentType.ORCHESTRATOR, "Same agent")
        
        assert context.switch_count == 0
        assert len(context.agent_history) == 0


class TestAgentContextManager:
    """Test agent context manager"""
    
    @pytest.mark.asyncio
    async def test_get_or_create(self):
        """Test getting or creating context"""
        manager = AsyncAgentContextManager()
        await manager.initialize()
        
        context = await manager.get_or_create("session_1")
        
        assert context.session_id == "session_1"
        assert context.current_agent == AgentType.ORCHESTRATOR
    
    @pytest.mark.asyncio
    async def test_get_existing_context(self):
        """Test getting existing context"""
        manager = AsyncAgentContextManager()
        await manager.initialize()
        
        context1 = await manager.get_or_create("session_1")
        context2 = await manager.get_or_create("session_1")
        
        assert context1 is context2
    
    @pytest.mark.asyncio
    async def test_delete_context(self):
        """Test deleting context"""
        manager = AsyncAgentContextManager()
        await manager.initialize()
        
        await manager.get_or_create("session_1")
        assert manager.exists("session_1")
        
        deleted = await manager.delete("session_1")
        
        # Context should be deleted from memory even if DB delete returns False (mocked)
        assert not manager.exists("session_1")
    
    @pytest.mark.asyncio
    async def test_session_count(self):
        """Test session count"""
        manager = AsyncAgentContextManager()
        await manager.initialize()
        
        await manager.get_or_create("session_1")
        await manager.get_or_create("session_2")
        await manager.get_or_create("session_3")
        
        assert manager.get_session_count() == 3


class TestOrchestratorClassification:
    """Test Orchestrator task classification"""
    
    def test_classify_coding_task(self):
        """Test classification of coding tasks"""
        orchestrator = OrchestratorAgent()
        
        # Test various coding keywords
        assert orchestrator.classify_task("create a new widget") == AgentType.CODER
        assert orchestrator.classify_task("implement the login function") == AgentType.CODER
        assert orchestrator.classify_task("fix the bug in main.dart") == AgentType.CODER
        assert orchestrator.classify_task("refactor this code") == AgentType.CODER
    
    def test_classify_architecture_task(self):
        """Test classification of architecture tasks"""
        orchestrator = OrchestratorAgent()
        
        # Test with clear architecture keywords (avoiding coding keywords like "create", "write")
        assert orchestrator.classify_task("design the system architecture") == AgentType.ARCHITECT
        assert orchestrator.classify_task("design and plan the architecture") == AgentType.ARCHITECT
    
    def test_classify_debug_task(self):
        """Test classification of debugging tasks"""
        orchestrator = OrchestratorAgent()
        
        assert orchestrator.classify_task("why is this error happening?") == AgentType.DEBUG
        assert orchestrator.classify_task("debug this issue") == AgentType.DEBUG
        assert orchestrator.classify_task("investigate the crash") == AgentType.DEBUG
    
    def test_classify_question_task(self):
        """Test classification of question tasks"""
        orchestrator = OrchestratorAgent()
        
        assert orchestrator.classify_task("explain how Flutter works") == AgentType.ASK
        assert orchestrator.classify_task("what is dependency injection?") == AgentType.ASK
        # "understand" is a question keyword
        assert orchestrator.classify_task("explain and help me understand this") == AgentType.ASK
    
    def test_classify_ambiguous_task(self):
        """Test classification of ambiguous tasks defaults to Coder"""
        orchestrator = OrchestratorAgent()
        
        # No clear keywords - should default to Coder
        result = orchestrator.classify_task("hello")
        assert result == AgentType.CODER


class TestToolRestrictions:
    """Test tool access restrictions for agents"""
    
    def test_coder_has_all_tools(self):
        """Test Coder has access to all necessary tools"""
        agent = CoderAgent()
        
        assert agent.can_use_tool("read_file")
        assert agent.can_use_tool("write_file")
        assert agent.can_use_tool("execute_command")
        assert agent.can_use_tool("create_directory")
    
    def test_architect_file_restrictions(self):
        """Test Architect can only edit markdown files"""
        agent = ArchitectAgent()
        
        # Can edit markdown
        assert agent.can_edit_file("README.md")
        assert agent.can_edit_file("docs/architecture.md")
        assert agent.can_edit_file("specs/design.md")
        
        # Cannot edit code
        assert not agent.can_edit_file("lib/main.dart")
        assert not agent.can_edit_file("src/app.py")
        assert not agent.can_edit_file("index.html")
    
    def test_debug_cannot_write(self):
        """Test Debug agent cannot write files"""
        agent = DebugAgent()
        
        assert not agent.can_use_tool("write_file")
        assert agent.can_use_tool("read_file")
        assert agent.can_use_tool("execute_command")
    
    def test_ask_minimal_tools(self):
        """Test Ask agent has minimal tool set"""
        agent = AskAgent()
        
        assert agent.can_use_tool("read_file")
        assert agent.can_use_tool("search_in_code")
        assert not agent.can_use_tool("write_file")
        assert not agent.can_use_tool("execute_command")
