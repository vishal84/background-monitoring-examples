# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Example: Background Agent Monitoring with Chat Updates

This demonstrates how to create a background monitoring agent that:
1. Watches an ongoing agent session
2. Detects new messages or events
3. Injects new messages into the chat based on monitoring results
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class AgentMonitor:
    """
    Monitors an agent session and can inject messages based on conditions.
    
    This pattern is useful for:
    - Safety monitoring (injecting warnings when risky behavior is detected)
    - Progress tracking (updating user on long-running tasks)
    - Multi-agent coordination (one agent monitoring another)
    - Real-time analysis and intervention
    """

    def __init__(
        self,
        session_service,
        app_name: str,
        user_id: str,
        session_id: str,
        monitor_interval: float = 1.0,
    ):
        self.session_service = session_service
        self.app_name = app_name
        self.user_id = user_id
        self.session_id = session_id
        self.monitor_interval = monitor_interval
        self.last_event_count = 0
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None

    async def start_monitoring(self, on_new_events_callback):
        """
        Start background monitoring.
        
        Args:
            on_new_events_callback: Async function called with new events.
                                   Should return a message to inject (str) or None.
        """
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(
            self._monitor_loop(on_new_events_callback)
        )

    async def stop_monitoring(self):
        """Stop the background monitoring task."""
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self, callback):
        """Internal monitoring loop."""
        while self.is_monitoring:
            try:
                # Get the current session state
                session = await self.session_service.get_session(
                    app_name=self.app_name,
                    user_id=self.user_id,
                    session_id=self.session_id,
                )

                if not session:
                    break

                current_count = len(session.events)

                # Check for new events
                if current_count > self.last_event_count:
                    new_events = session.events[self.last_event_count :]
                    self.last_event_count = current_count

                    # Call the callback to analyze new events
                    message_to_inject = await callback(new_events, session)

                    # If callback returns a message, it will be injected
                    # by the main agent loop (see example below)
                    if message_to_inject:
                        print(f"Monitor wants to inject: {message_to_inject}")

                await asyncio.sleep(self.monitor_interval)

            except Exception as e:
                print(f"Monitor error: {e}")
                await asyncio.sleep(self.monitor_interval)


async def example_1_passive_monitoring():
    """
    Example 1: Passive monitoring - just observe and log
    """
    print("\n=== Example 1: Passive Monitoring ===\n")

    # Setup
    session_service = InMemorySessionService()
    app_name = "monitoring_demo"
    user_id = "user123"
    session_id = "session_001"

    await session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )

    # Create a simple agent
    agent = LlmAgent(
        name="demo_agent",
        model=MODEL_NAME,
        instruction="You are a helpful assistant. Answer questions briefly.",
    )

    runner = Runner(
        app_name=app_name, agent=agent, session_service=session_service
    )

    # Define monitoring callback
    async def monitor_callback(new_events, session):
        """Analyze new events and log interesting patterns."""
        for event in new_events:
            # Check for tool calls
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        print(f"📝 Monitor detected text: {part.text[:100]}...")

                    # Check for function calls
                    if hasattr(part, "function_call") and part.function_call:
                        print(
                            f"🔧 Monitor detected tool call: {part.function_call.name}"
                        )

            # Access session state
            if session.state:
                print(f"📊 Current session state: {session.state}")

        return None  # Don't inject anything, just observe

    # Start monitor
    monitor = AgentMonitor(session_service, app_name, user_id, session_id)
    await monitor.start_monitoring(monitor_callback)

    # Run the agent
    print("User: What is 2+2?")
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.UserContent("What is 2+2?"),
    ):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    print(f"Agent: {part.text}")

    # Cleanup
    await monitor.stop_monitoring()


async def example_2_inject_messages_via_runner():
    """
    Example 2: How to inject messages into the chat from monitor
    
    This shows the CORRECT way to add messages - by calling runner.run_async()
    with a new message from the monitoring agent.
    """
    print("\n=== Example 2: Injecting Messages via Runner ===\n")

    session_service = InMemorySessionService()
    app_name = "monitoring_demo"
    user_id = "user123"
    session_id = "session_002"

    await session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )

    # Main agent
    agent = LlmAgent(
        name="main_agent",
        model=MODEL_NAME,
        instruction="You are a coding assistant. Help users write code.",
    )

    runner = Runner(
        app_name=app_name, agent=agent, session_service=session_service
    )

    # Queue for messages to inject
    injection_queue = asyncio.Queue()

    # Monitor callback that detects risky code patterns
    async def safety_monitor_callback(new_events, session):
        """Monitor for unsafe code patterns and inject warnings."""
        for event in new_events:
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        text = part.text.lower()
                        # Detect risky patterns
                        if "rm -rf" in text or "delete" in text:
                            warning = (
                                "⚠️ SAFETY WARNING: Potentially destructive "
                                "operation detected. Please review carefully."
                            )
                            # Queue the warning to be injected
                            await injection_queue.put(warning)
                            return warning
        return None

    # Start monitor
    monitor = AgentMonitor(
        session_service, app_name, user_id, session_id, monitor_interval=0.5
    )
    await monitor.start_monitoring(safety_monitor_callback)

    # Simulate a conversation with monitoring
    print("User: Write a bash script to clean up temporary files")

    # First user message
    response_parts = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.UserContent(
            "Write a bash script to clean up temporary files"
        ),
    ):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    response_parts.append(part.text)
                    print(f"Agent: {part.text}")

    # Check if monitor queued any warnings
    if not injection_queue.empty():
        warning = await injection_queue.get()
        print(f"\n🤖 Monitor: {warning}\n")

        # INJECT the warning as a system/user message
        print(
            "Injecting warning into chat as a user message (from monitoring system)..."
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.UserContent(warning),
        ):
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        print(f"Agent acknowledges: {part.text}")

    await monitor.stop_monitoring()


async def example_3_monitoring_agent_pattern():
    """
    Example 3: Full monitoring agent pattern
    
    This creates a SEPARATE monitoring agent that analyzes the main agent's
    session and can inject analytical commentary or suggestions.
    """
    print("\n=== Example 3: Monitoring Agent Pattern ===\n")

    session_service = InMemorySessionService()
    app_name = "monitoring_demo"

    # Main agent and session
    main_user_id = "user123"
    main_session_id = "main_session"
    await session_service.create_session(
        app_name=app_name, user_id=main_user_id, session_id=main_session_id
    )

    main_agent = LlmAgent(
        name="customer_service",
        model=MODEL_NAME,
        instruction="You are a customer service agent. Help users with their issues.",
    )

    main_runner = Runner(
        app_name=app_name, agent=main_agent, session_service=session_service
    )

    # Monitoring agent (separate agent that analyzes the conversation)
    monitor_agent = LlmAgent(
        name="quality_monitor",
        model=MODEL_NAME,
        instruction="""You are a quality assurance agent monitoring customer service conversations.
        Analyze the conversation for:
        - Customer satisfaction indicators
        - Agent professionalism
        - Resolution effectiveness
        
        Provide brief insights when you detect issues or excellent service.""",
    )

    monitor_user_id = "monitor_bot"
    monitor_session_id = "monitor_session"
    await session_service.create_session(
        app_name=app_name,
        user_id=monitor_user_id,
        session_id=monitor_session_id,
    )

    monitor_runner = Runner(
        app_name=app_name,
        agent=monitor_agent,
        session_service=session_service,
    )

    async def intelligent_monitor_callback(new_events, session):
        """Use monitoring agent to analyze new events."""
        # Build context from new events
        context = []
        for event in new_events:
            if event.content:
                role = event.content.role
                for part in event.content.parts:
                    if part.text:
                        context.append(f"{role}: {part.text}")

        if not context:
            return None

        # Ask monitoring agent to analyze
        analysis_prompt = (
            f"Analyze this conversation excerpt:\n\n"
            + "\n".join(context)
            + "\n\nShould I intervene or provide feedback?"
        )

        analysis_parts = []
        async for event in monitor_runner.run_async(
            user_id=monitor_user_id,
            session_id=monitor_session_id,
            new_message=types.UserContent(analysis_prompt),
        ):
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        analysis_parts.append(part.text)

        analysis = "".join(analysis_parts)

        # If monitor detects issues, return intervention message
        if "intervene" in analysis.lower() or "issue" in analysis.lower():
            return f"[Monitor Insight] {analysis[:200]}"

        return None

    # Start intelligent monitoring
    monitor = AgentMonitor(
        session_service, app_name, main_user_id, main_session_id
    )
    await monitor.start_monitoring(intelligent_monitor_callback)

    # Simulate customer conversation
    print("Customer: I'm very frustrated! This product doesn't work!")

    async for event in main_runner.run_async(
        user_id=main_user_id,
        session_id=main_session_id,
        new_message=types.UserContent(
            "I'm very frustrated! This product doesn't work!"
        ),
    ):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    print(f"CS Agent: {part.text}")

    # Small delay for monitor to process
    await asyncio.sleep(2)

    await monitor.stop_monitoring()


async def example_4_real_world_scenario():
    """
    Example 4: Real-world scenario - Multi-turn with dynamic injection
    
    Shows how to coordinate main agent, monitoring, and message injection
    in a realistic multi-turn conversation.
    """
    print("\n=== Example 4: Real-World Multi-Turn Scenario ===\n")

    session_service = InMemorySessionService()
    app_name = "security_demo"
    user_id = "user456"
    session_id = "secure_session"

    await session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )

    agent = LlmAgent(
        name="assistant",
        model=MODEL_NAME,
        instruction="You are a helpful assistant. Be concise.",
    )

    runner = Runner(
        app_name=app_name, agent=agent, session_service=session_service
    )

    intervention_count = 0
    max_interventions = 2

    async def security_monitor(new_events, session):
        """Monitor for security concerns."""
        nonlocal intervention_count

        if intervention_count >= max_interventions:
            return None

        for event in new_events:
            if event.content and event.content.role == "model":
                for part in event.content.parts:
                    if part.text:
                        text = part.text.lower()
                        # Check for sensitive data patterns
                        if (
                            "password" in text
                            or "api key" in text
                            or "secret" in text
                        ):
                            intervention_count += 1
                            return (
                                "🔒 Security reminder: Never share actual "
                                "passwords or API keys. Use placeholders."
                            )
        return None

    monitor = AgentMonitor(session_service, app_name, user_id, session_id)
    await monitor.start_monitoring(security_monitor)

    # Message queue for injections
    pending_injections = asyncio.Queue()

    # Helper to send message and check for injections
    async def send_and_monitor(message_text: str):
        print(f"\nUser: {message_text}")

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.UserContent(message_text),
        ):
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        print(f"Agent: {part.text}")

        # Small delay for monitor to react
        await asyncio.sleep(0.5)

        # Check for monitoring injections
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        # Look for monitor-generated warnings in recent events
        # (In practice, the callback would signal via queue/event)

    # Multi-turn conversation
    await send_and_monitor("How do I set up authentication?")
    await send_and_monitor("Can you show me an example with API keys?")
    # Monitor would detect "API key" mention and inject warning

    await monitor.stop_monitoring()
    print(f"\n✅ Monitor made {intervention_count} interventions")


async def main():
    """Run all examples."""
    # await example_1_passive_monitoring()
    # print("\n" + "=" * 60 + "\n")

    # await example_2_inject_messages_via_runner()
    # print("\n" + "=" * 60 + "\n")

    # Uncomment to run more advanced examples
    await example_3_monitoring_agent_pattern()
    print("\n" + "=" * 60 + "\n")

    await example_4_real_world_scenario()


if __name__ == "__main__":
    asyncio.run(main())
