#!/usr/bin/env python3
"""
Quick Demo: Background Monitoring with Message Injection

Run this to see how a monitoring agent can watch a conversation
and inject messages into the chat in real-time.
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


async def demo():
    """Simple demonstration of monitoring and message injection."""
    
    # Setup session
    session_service = InMemorySessionService()
    user_id = "demo_user"
    session_id = "demo_session"
    app_name = "demo_app"
    
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )
    
    # Create main agent
    agent = LlmAgent(
        name="assistant",
        model=MODEL_NAME,
        instruction="You are a helpful coding assistant. Provide clear, concise answers.",
    )
    
    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=session_service
    )
    
    # Background monitor state
    last_event_count = 0
    should_inject_warning = False
    
    async def background_monitor():
        """Background task that monitors the session."""
        nonlocal last_event_count, should_inject_warning
        
        while True:
            try:
                # Get current session
                session = await session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id
                )
                
                if session and len(session.events) > last_event_count:
                    new_events = session.events[last_event_count:]
                    last_event_count = len(session.events)
                    
                    # Check for risky patterns
                    for event in new_events:
                        if event.content and event.content.role == "model":
                            for part in event.content.parts:
                                if part.text:
                                    text = part.text.lower()
                                    if any(keyword in text for keyword in 
                                          ["rm -rf", "delete all", "drop database"]):
                                        print("\n🚨 MONITOR ALERT: Dangerous operation detected!\n")
                                        should_inject_warning = True
                
                await asyncio.sleep(0.5)  # Check twice per second
                
            except Exception as e:
                print(f"Monitor error: {e}")
                await asyncio.sleep(1)
    
    # Start background monitor
    monitor_task = asyncio.create_task(background_monitor())
    
    print("=" * 70)
    print("DEMO: Background Agent Monitoring with Message Injection")
    print("=" * 70)
    print()
    
    # ===== TURN 1 =====
    print("👤 User: Write me a bash script to clean up old files\n")
    
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.UserContent("Write me a bash script to clean up old files. Ensure you use the -rm command where required.")
    ):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    print(f"🤖 Agent: {part.text}")
    
    # Give monitor time to process
    await asyncio.sleep(1)
    
    # ===== CHECK IF MONITOR DETECTED SOMETHING =====
    if should_inject_warning:
        print("\n" + "="*70)
        print("💉 INJECTING WARNING MESSAGE FROM MONITOR")
        print("="*70 + "\n")
        
        warning_message = """⚠️ SAFETY WARNING (from monitoring system):

The script contains potentially destructive operations. Please ensure:
1. You have backups of important data
2. You test in a safe environment first
3. You understand what files will be affected

Would you like me to modify the script to be safer?"""
        
        print(f"🔒 System: {warning_message}\n")
        
        # INJECT the warning into the conversation
        print("🤖 Agent responds to warning:\n")
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.UserContent(warning_message)
        ):
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        print(f"🤖 Agent: {part.text}")
    
    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print()
    print("What happened:")
    print("1. User asked for a cleanup script")
    print("2. Background monitor detected dangerous operations")
    print("3. Monitor injected a safety warning into the chat")
    print("4. Agent acknowledged and responded to the warning")
    print()
    print("The conversation now includes the warning in its history.")
    print()
    
    # Show final session state
    final_session = await session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )
    print(f"Total events in session: {len(final_session.events)}")
    
    # Cleanup
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(demo())
