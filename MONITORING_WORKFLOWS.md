# Monitoring Example Workflows

This document contains mermaid diagrams illustrating the workflow of each example in the monitoring_example.py file.

## Example 1: Passive Monitoring

This example demonstrates basic monitoring without message injection - the monitor just observes and logs.

```mermaid
sequenceDiagram
    participant User
    participant MainAgent
    participant Runner
    participant Session
    participant Monitor
    
    Note over Monitor: Background Task Started
    
    User->>Runner: "What is 2+2?"
    Runner->>MainAgent: Process message
    MainAgent->>Session: Add user message event
    
    par Main Thread
        MainAgent->>MainAgent: Generate response
        MainAgent->>Session: Add model response event
        MainAgent->>Runner: Stream response
        Runner->>User: "4"
    and Background Monitor Loop
        loop Every 1 second
            Monitor->>Session: get_session()
            Session->>Monitor: Return session with events
            Monitor->>Monitor: Compare event count
            alt New events detected
                Monitor->>Monitor: Extract new events
                Monitor->>Monitor: Analyze events
                Note over Monitor: 📝 Log: "Monitor detected text"
                Note over Monitor: 🔧 Log: "Tool calls detected"
                Note over Monitor: 📊 Log: "Session state"
            end
        end
    end
    
    Note over Monitor: Monitor stopped (no injection)
```

## Example 2: Message Injection via Runner

This example shows how to detect risky patterns and inject warning messages into the chat.

```mermaid
sequenceDiagram
    participant User
    participant MainAgent
    participant Runner
    participant Session
    participant Monitor
    participant Queue as Injection Queue
    
    Note over Monitor: Background Task Started
    
    User->>Runner: "Write bash script to clean up files"
    Runner->>MainAgent: Process message
    MainAgent->>Session: Add user message event
    
    par Main Thread
        MainAgent->>MainAgent: Generate script
        Note over MainAgent: Script contains "rm -rf"
        MainAgent->>Session: Add response event
        MainAgent->>Runner: Stream response
        Runner->>User: Display bash script
    and Background Monitor
        loop Monitor Loop (0.5s interval)
            Monitor->>Session: get_session()
            Session->>Monitor: Return events
            Monitor->>Monitor: Check for new events
            alt Risky pattern detected
                Monitor->>Monitor: Detect "rm -rf" or "delete"
                Note over Monitor: ⚠️ Risk detected!
                Monitor->>Queue: Put warning message
            end
        end
    end
    
    Note over User: Check injection queue
    
    alt Queue not empty
        Queue->>User: Get warning message
        User->>Runner: Inject warning as new message
        Runner->>MainAgent: Process warning
        MainAgent->>Session: Add warning event
        MainAgent->>MainAgent: Generate acknowledgment
        MainAgent->>Session: Add response event
        MainAgent->>Runner: Stream response
        Runner->>User: "Agent acknowledges warning"
    end
    
    Note over Monitor: Monitor stopped
```

## Example 3: Monitoring Agent Pattern (AI Monitors AI)

This example uses a separate AI agent to analyze the main agent's conversation and provide insights.

```mermaid
sequenceDiagram
    participant Customer as Customer (User)
    participant MainAgent as Customer Service Agent
    participant MainRunner as Main Runner
    participant MainSession as Main Session
    participant Monitor as Monitor (Background)
    participant MonitorAgent as Quality Monitor Agent
    participant MonitorRunner as Monitor Runner
    participant MonitorSession as Monitor Session
    
    Note over Monitor: Background monitoring started
    
    Customer->>MainRunner: "I'm frustrated! Product doesn't work!"
    MainRunner->>MainAgent: Process complaint
    MainAgent->>MainSession: Add user message event
    
    par Main Conversation
        MainAgent->>MainAgent: Generate response
        MainAgent->>MainSession: Add model response
        MainAgent->>MainRunner: Stream response
        MainRunner->>Customer: Display response
    and Background Analysis
        loop Every 1 second
            Monitor->>MainSession: get_session()
            MainSession->>Monitor: Return events
            
            alt New events found
                Monitor->>Monitor: Extract conversation context
                Note over Monitor: Build context:<br/>"user: I'm frustrated..."<br/>"model: I apologize..."
                
                Monitor->>MonitorRunner: Send analysis request
                MonitorRunner->>MonitorAgent: Analyze conversation
                MonitorAgent->>MonitorSession: Store analysis request
                MonitorAgent->>MonitorAgent: Evaluate quality
                Note over MonitorAgent: Check for:<br/>- Customer satisfaction<br/>- Professionalism<br/>- Resolution effectiveness
                MonitorAgent->>MonitorSession: Store analysis
                MonitorAgent->>MonitorRunner: Return insights
                MonitorRunner->>Monitor: Get analysis result
                
                alt Issues detected
                    Note over Monitor: "intervene" or "issue" in analysis
                    Monitor->>Monitor: Prepare intervention message
                    Note over Monitor: Could inject into main session<br/>(Example shows pattern only)
                end
            end
        end
    end
    
    Note over Monitor: Monitor stopped after delay
```

## Example 4: Real-World Multi-Turn Scenario

This example demonstrates coordinated monitoring across multiple conversation turns with dynamic intervention limits.

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Runner
    participant Session
    participant Monitor
    
    Note over Monitor: Background monitoring started<br/>Max interventions: 2
    
    rect rgb(200, 220, 240)
        Note over User,Monitor: Turn 1: Setup Authentication
        User->>Runner: "How do I set up authentication?"
        Runner->>Agent: Process query
        Agent->>Session: Add user event
        
        par Main Thread
            Agent->>Agent: Generate response
            Agent->>Session: Add model response
            Agent->>Runner: Stream response
            Runner->>User: Display response
        and Background Monitor
            loop Monitor Loop
                Monitor->>Session: get_session()
                Session->>Monitor: Return events
                Monitor->>Monitor: Check for sensitive patterns
                Note over Monitor: No "password", "api key", "secret"<br/>in response → OK
            end
        end
    end
    
    rect rgb(250, 220, 220)
        Note over User,Monitor: Turn 2: API Key Example
        User->>Runner: "Show me example with API keys?"
        Runner->>Agent: Process query
        Agent->>Session: Add user event
        
        par Main Thread
            Agent->>Agent: Generate response
            Note over Agent: Response mentions "API key"
            Agent->>Session: Add model response
            Agent->>Runner: Stream response
            Runner->>User: Display response
        and Background Monitor
            loop Monitor Loop
                Monitor->>Session: get_session()
                Session->>Monitor: Return events
                Monitor->>Monitor: Analyze new events
                
                alt Sensitive data detected
                    Note over Monitor: 🔒 "api key" detected!
                    Monitor->>Monitor: intervention_count++
                    Monitor->>Monitor: Return security reminder
                    Note over Monitor: "Never share actual API keys"
                    Note over Monitor: Could inject via runner here
                end
            end
        end
    end
    
    Note over User: Delay for monitor processing (0.5s)
    
    Note over Monitor: Monitor stopped<br/>Total interventions: 1
```

## Architecture Overview: AgentMonitor Class

```mermaid
graph TB
    subgraph "AgentMonitor Class"
        Init[Initialize Monitor]
        Start[start_monitoring]
        Loop[_monitor_loop]
        Stop[stop_monitoring]
        Callback[on_new_events_callback]
    end
    
    subgraph "Session Service"
        Session[Session Storage]
        Events[Event History]
        State[Session State]
    end
    
    subgraph "Main Application"
        Runner[Runner]
        Agent[LLM Agent]
        User[User Interaction]
    end
    
    Init -->|configure| Start
    Start -->|create_task| Loop
    
    Loop -->|every interval| Session
    Session -->|get_session| Events
    Events -->|new events?| Callback
    Callback -->|analyze| Loop
    Callback -.->|return message| User
    
    User -->|inject via runner| Runner
    Runner -->|process| Agent
    Agent -->|store| Session
    
    Stop -->|cancel task| Loop
    
    style Init fill:#e1f5ff
    style Loop fill:#fff4e1
    style Callback fill:#ffe1e1
    style Session fill:#e1ffe1
```

## Key Patterns Comparison

```mermaid
graph LR
    subgraph "Pattern 1: Passive"
        P1A[Monitor] -->|observe only| P1B[Log Events]
        P1B -->|no action| P1C[Continue]
    end
    
    subgraph "Pattern 2: Active Injection"
        P2A[Monitor] -->|detect pattern| P2B[Queue Warning]
        P2B -->|main checks queue| P2C[Inject Message]
        P2C -->|runner.run_async| P2D[Agent Responds]
    end
    
    subgraph "Pattern 3: AI Monitor"
        P3A[Monitor] -->|extract context| P3B[Monitor Agent]
        P3B -->|analyze| P3C[Return Insights]
        P3C -->|if issue| P3D[Prepare Intervention]
    end
    
    subgraph "Pattern 4: Multi-Turn"
        P4A[Monitor] -->|track across turns| P4B[Count Interventions]
        P4B -->|enforce limit| P4C[Selective Inject]
    end
    
    style P1B fill:#90EE90
    style P2C fill:#FFB6C1
    style P3B fill:#87CEEB
    style P4C fill:#FFD700
```

## Message Flow: How Injection Works

```mermaid
flowchart TD
    Start([User sends message]) --> Runner1[Runner.run_async]
    Runner1 --> Agent1[Agent processes]
    Agent1 --> Session1[Add to session events]
    Session1 --> Response1[Stream response to user]
    
    Response1 --> Monitor{Monitor detects<br/>issue?}
    
    Monitor -->|No| End1([Continue])
    Monitor -->|Yes| Queue[Add to injection queue]
    
    Queue --> Check{Queue<br/>empty?}
    Check -->|Yes| End2([Done])
    Check -->|No| GetMsg[Get message from queue]
    
    GetMsg --> Runner2[Runner.run_async<br/>SAME session_id]
    Runner2 --> Agent2[Agent processes<br/>injected message]
    Agent2 --> Session2[Add to session events]
    Session2 --> Response2[Stream response]
    Response2 --> End3([Session updated])
    
    style Monitor fill:#FFE4B5
    style Queue fill:#FFB6C1
    style Runner2 fill:#98FB98
    style Session2 fill:#87CEEB
```
