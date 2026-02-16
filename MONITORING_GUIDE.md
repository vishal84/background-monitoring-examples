# Background Agent Monitoring - Practical Guide

## Overview

This guide shows how to create a background monitoring agent that watches an agent's session and can inject new messages into the chat based on what it observes.

## Key Concept: How to Update Chat with New Messages

To inject messages into an agent's chat, you **call `runner.run_async()` again** with the new message. Each call to `run_async()` adds to the session's conversation history.

```python
# First message (user question)
async for event in runner.run_async(
    user_id=user_id,
    session_id=session_id,
    new_message=types.UserContent("Original question")
):
    # Process response
    pass

# Inject a new message (from monitor or system)
async for event in runner.run_async(
    user_id=user_id,
    session_id=session_id,
    new_message=types.UserContent("🤖 Monitor says: This looks risky!")
):
    # Process agent's response to the injected message
    pass
```

## Pattern 1: Simple Background Monitor

```python
import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

class SimpleMonitor:
    def __init__(self, session_service, app_name, user_id, session_id):
        self.session_service = session_service
        self.app_name = app_name
        self.user_id = user_id
        self.session_id = session_id
        self.last_event_count = 0
        self.monitoring = False
        
    async def start(self, callback):
        """Start monitoring with a callback function."""
        self.monitoring = True
        self.task = asyncio.create_task(self._monitor_loop(callback))
        
    async def stop(self):
        """Stop monitoring."""
        self.monitoring = False
        if hasattr(self, 'task'):
            self.task.cancel()
            
    async def _monitor_loop(self, callback):
        """Monitor loop - checks for new events every second."""
        while self.monitoring:
            try:
                # Get current session
                session = await self.session_service.get_session(
                    app_name=self.app_name,
                    user_id=self.user_id,
                    session_id=self.session_id
                )
                
                if session and len(session.events) > self.last_event_count:
                    new_events = session.events[self.last_event_count:]
                    self.last_event_count = len(session.events)
                    
                    # Call your callback with new events
                    await callback(new_events, session)
                    
                await asyncio.sleep(1.0)  # Check every second
                
            except Exception as e:
                print(f"Monitor error: {e}")
                await asyncio.sleep(1.0)


# Usage:
async def my_callback(new_events, session):
    """Called when new events are detected."""
    for event in new_events:
        if event.content:
            for part in event.content.parts:
                if part.text:
                    print(f"Monitor saw: {part.text[:100]}")
                    
                    # Detect something worth injecting
                    if "dangerous" in part.text.lower():
                        print("⚠️ Monitor detected dangerous content!")
                        return True  # Signal to inject warning
    return False

monitor = SimpleMonitor(session_service, app_name, user_id, session_id)
await monitor.start(my_callback)
```

## Pattern 2: Inject Messages Based on Monitoring

Here's the complete flow for injecting messages:

```python
async def run_with_monitoring_and_injection():
    # Setup
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="app", user_id="user1", session_id="session1"
    )
    
    runner = Runner(agent=my_agent, app_name="app", 
                   session_service=session_service)
    
    # Queue for messages to inject
    injection_queue = asyncio.Queue()
    
    # Monitor callback
    async def monitor_callback(new_events, session):
        for event in new_events:
            if event.content and event.content.role == "model":
                for part in event.content.parts:
                    if part.text and "password" in part.text.lower():
                        # Queue a security warning
                        await injection_queue.put(
                            "⚠️ Security: Don't share real passwords!"
                        )
    
    # Start monitor
    monitor = SimpleMonitor(session_service, "app", "user1", "session1")
    await monitor.start(monitor_callback)
    
    # Send user message
    print("User: How do I reset my password?")
    async for event in runner.run_async(
        user_id="user1",
        session_id="session1",
        new_message=types.UserContent("How do I reset my password?")
    ):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    print(f"Agent: {part.text}")
    
    # Check if monitor queued anything
    if not injection_queue.empty():
        warning = await injection_queue.get()
        print(f"\nSystem: {warning}")
        
        # INJECT the warning into the chat
        print("\nAgent responds to warning:")
        async for event in runner.run_async(
            user_id="user1",
            session_id="session1",
            new_message=types.UserContent(warning)
        ):
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        print(f"Agent: {part.text}")
    
    await monitor.stop()
```

## Pattern 3: Monitoring Agent (Agent Monitors Agent)

Create a separate monitoring agent that analyzes another agent:

```python
async def monitoring_agent_pattern():
    session_service = InMemorySessionService()
    
    # Main agent
    main_agent = LlmAgent(
        name="assistant",
        model="gemini-2.0-flash-exp",
        instruction="You are a helpful assistant."
    )
    
    # Monitoring agent
    monitor_agent = LlmAgent(
        name="safety_monitor",
        model="gemini-2.0-flash-exp",
        instruction="""Analyze conversations for:
        - Safety issues
        - Policy violations
        - Quality concerns
        Respond with 'OK' or describe the issue."""
    )
    
    # Create sessions for both
    main_session = await session_service.create_session(
        app_name="app", user_id="user1", session_id="main"
    )
    monitor_session = await session_service.create_session(
        app_name="app", user_id="monitor", session_id="monitor_session"
    )
    
    main_runner = Runner(agent=main_agent, app_name="app",
                        session_service=session_service)
    monitor_runner = Runner(agent=monitor_agent, app_name="app",
                           session_service=session_service)
    
    async def analyze_with_monitor_agent(new_events, session):
        # Extract conversation
        context = []
        for event in new_events:
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        context.append(f"{event.content.role}: {part.text}")
        
        if not context:
            return
        
        # Ask monitor agent to analyze
        prompt = "Analyze this:\n" + "\n".join(context)
        analysis = []
        
        async for event in monitor_runner.run_async(
            user_id="monitor",
            session_id="monitor_session",
            new_message=types.UserContent(prompt)
        ):
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        analysis.append(part.text)
        
        result = "".join(analysis)
        
        # If monitor found issues, signal for injection
        if result.lower() != "ok":
            print(f"🔍 Monitor Analysis: {result}")
            # Queue intervention message
    
    monitor = SimpleMonitor(session_service, "app", "user1", "main")
    await monitor.start(analyze_with_monitor_agent)
    
    # Run main agent
    async for event in main_runner.run_async(
        user_id="user1",
        session_id="main",
        new_message=types.UserContent("User message here")
    ):
        pass
    
    await monitor.stop()
```

## Key Points

1. **Message Injection**: Call `runner.run_async()` with a new `types.UserContent()` message
2. **Session Persistence**: All messages go into the same session via `session_id`
3. **Event Monitoring**: Access `session.events` to see all conversation events
4. **Session State**: Access `session.state` to read agent state
5. **Background Tasks**: Use `asyncio.create_task()` for background monitoring
6. **Coordination**: Use `asyncio.Queue()` to coordinate between monitor and main loop

## Complete Example

See [monitoring_example.py](./monitoring_example.py) for runnable examples including:
- Passive monitoring (observe only)
- Active injection (add messages based on conditions)
- Monitoring agent (AI monitors AI)
- Multi-turn with dynamic interventions
