# How to Update Agent Chat with New Messages from a Monitor

## The Core Answer

To update an agent's chat with a new message from your monitoring system:

**Call `runner.run_async()` again with the new message content.**

```python
# This ADDS a new message to the conversation
async for event in runner.run_async(
    user_id=user_id,
    session_id=session_id,  # Same session!
    new_message=types.UserContent("Your injected message here")
):
    # Process the agent's response
    pass
```

That's it! Each call to `run_async()` with the same `session_id` adds to the conversation history.

## Simple Example

```python
import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

async def main():
    # Setup
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="app", user_id="user1", session_id="sess1"
    )
    
    runner = Runner(
        agent=your_agent,
        app_name="app",
        session_service=session_service
    )
    
    # Message 1: Original user question
    async for event in runner.run_async(
        user_id="user1",
        session_id="sess1",
        new_message=types.UserContent("What's the weather?")
    ):
        pass  # Process response
    
    # Message 2: Injected from monitor
    async for event in runner.run_async(
        user_id="user1", 
        session_id="sess1",  # Same session!
        new_message=types.UserContent("🤖 Reminder: Get an umbrella!")
    ):
        pass  # Process agent's response to reminder
```

## Background Monitor Template

```python
async def monitor_loop(session_service, app_name, user_id, session_id):
    """Background task that monitors for new events."""
    last_count = 0
    
    while True:
        session = await session_service.get_session(
            app_name=app_name,
            user_id=user_id, 
            session_id=session_id
        )
        
        if session and len(session.events) > last_count:
            new_events = session.events[last_count:]
            last_count = len(session.events)
            
            # Analyze new events
            for event in new_events:
                if event.content:
                    for part in event.content.parts:
                        if part.text:
                            # Check for conditions
                            if "dangerous" in part.text.lower():
                                return True  # Signal to inject warning
        
        await asyncio.sleep(1)  # Check every second

# Start monitor
monitor_task = asyncio.create_task(
    monitor_loop(session_service, app_name, user_id, session_id)
)
```

## Key Session Methods

From `session_service`:

- **`create_session(app_name, user_id, session_id)`** - Create new session
- **`get_session(app_name, user_id, session_id)`** - Get current session with all events
- **`session.events`** - List of all conversation events
- **`session.state`** - Current session state dictionary

## Files Created

1. **[MONITORING_GUIDE.md](./MONITORING_GUIDE.md)** - Comprehensive patterns and examples
2. **[monitoring_example.py](./app/monitoring_example.py)** - Full working examples (4 patterns)
3. **[quick_demo.py](./app/quick_demo.py)** - Simple runnable demo

Run the quick demo:
```bash
python llm_red_team_agent/quick_demo.py
```
