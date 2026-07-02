# Revenue Guardian: Architecture Diagrams

This document contains a set of Mermaid diagrams visualizing the architecture, agent interaction flows, data flows, and security boundaries of the **Revenue Guardian** platform.

---

## 1. System Topology Diagram
Visualizes the overall system structure, separating the Presentation Layer, the Application Backend, the MCP Integration Server, and the data sources.

```mermaid
graph TD
    %% Presentation Layer
    subgraph Presentation_Layer [Presentation Layer - React / Streamlit]
        UI[Executive Dashboard]
        HITL[Human-in-the-Loop Approval Panel]
    end

    %% Application Backend
    subgraph Application_Backend [Application Backend - FastAPI]
        API[FastAPI Router]
        Auth[JWT Auth & RBAC Services]
        Orch[RevOps Orchestrator - ADK Core]
        Scheduler[Workflow Scheduler - Cron]
    end

    %% Model Context Protocol Layer
    subgraph MCP_Layer [Integration Layer - Model Context Protocol]
        MCP_Server[FastMCP Server]
    end

    %% External Systems & Databases
    subgraph Data_Layer [Data & External Systems]
        CRM_DB[(CRM SQLite DB - crm.db)]
        Audit_DB[(Audit Log DB - crm.db)]
        Gmail_API[Google Gmail API]
        Cal_API[Google Calendar API]
        Slack_Webhook[Slack Webhooks]
        Gemini[Google Gemini 2.0]
    end

    %% Connections
    UI <-->|REST API / HTTP| API
    HITL -->|POST /api/approvals| API
    Scheduler -->|Trigger Workflow| Orch
    API <-->|Run Agents| Orch
    API -->|Authenticate| Auth

    Orch <-->|Google ADK SDK| Gemini
    Orch <-->|Local stdio transport| MCP_Server

    MCP_Server <-->|SQL Queries| CRM_DB
    MCP_Server <-->|SQL Insert| Audit_DB
    MCP_Server <-->|OAuth2 HTTP| Gmail_API
    MCP_Server <-->|OAuth2 HTTP| Cal_API
    MCP_Server -->|HTTP POST| Slack_Webhook
```

---

## 2. Multi-Agent Execution Pipeline
Illustrates the lifecycle of a single RevOps audit run, highlighting the parallel execution of the data-gathering agents followed by the sequential synthesis agents.

```mermaid
sequenceDiagram
    autonumber
    actor User as RevOps Manager
    participant Orch as Manager Agent (Orchestrator)
    participant CRM as CRM Agent
    participant Email as Email Agent
    participant Cal as Calendar Agent
    participant Predict as Prediction Agent
    participant Recovery as Recovery Agent
    participant Summary as Summary Agent

    User->>Orch: Trigger Audit Workflow
    Note over Orch: Phase 1: Parallel Data Extraction
    
    par CRM Audit
        Orch->>CRM: Task: Reconcile contract vs. pipeline
        CRM-->>Orch: Return: CRMAnalysisResult (JSON)
    and Email Audit
        Orch->>Email: Task: Scan sentiment & urgency
        Email-->>Orch: Return: EmailIntelligenceResult (JSON)
    and Calendar Audit
        Orch->>Cal: Task: Check meetings & availability
        Cal-->>Orch: Return: CalendarAnalysisResult (JSON)
    end

    Note over Orch: Phase 2: Predictive Forecasting
    Orch->>Predict: Task: Run forecasting models (Pass CRM + Email + Cal data)
    Predict-->>Orch: Return: PredictionAnalysisResult (JSON)

    Note over Orch: Phase 3: Recovery Strategy
    Orch->>Recovery: Task: Draft action plans (Pass all previous results)
    Recovery-->>Orch: Return: RecoveryStrategyResult (JSON)

    Note over Orch: Phase 4: Executive Synthesis
    Orch->>Summary: Task: Generate briefings & KPIs (Pass all results)
    Summary-->>Orch: Return: ExecutiveSummaryResult (JSON)

    Orch->>User: Display Morning Briefing & Recommendations
```

---

## 3. Data Flow & Shared Context Map
Shows how Pydantic data models are passed as JSON string messages to maintain a shared context across the decentralized agent core.

```mermaid
graph TD
    %% Phase 1 Outputs
    CRM_Out[CRMAnalysisResult]
    Email_Out[EmailIntelligenceResult]
    Cal_Out[CalendarAnalysisResult]

    %% Phase 2
    subgraph Phase_2 [Phase 2: Revenue Prediction]
        CRM_Out -->|JSON String| Prompt_2[Prediction Prompt Context]
        Email_Out -->|JSON String| Prompt_2
        Cal_Out -->|JSON String| Prompt_2
        Prompt_2 --> Predict_Agent[Revenue Prediction Agent]
        Predict_Agent --> Predict_Out[PredictionAnalysisResult]
    end

    %% Phase 3
    subgraph Phase_3 [Phase 3: Recovery Strategy]
        CRM_Out -->|JSON String| Prompt_3[Recovery Prompt Context]
        Email_Out -->|JSON String| Prompt_3
        Cal_Out -->|JSON String| Prompt_3
        Predict_Out -->|JSON String| Prompt_3
        Prompt_3 --> Recovery_Agent[Recovery Strategy Agent]
        Recovery_Agent --> Recovery_Out[RecoveryStrategyResult]
    end

    %% Phase 4
    subgraph Phase_4 [Phase 4: Executive Summary]
        CRM_Out -->|JSON String| Prompt_4[Summary Prompt Context]
        Email_Out -->|JSON String| Prompt_4
        Cal_Out -->|JSON String| Prompt_4
        Predict_Out -->|JSON String| Prompt_4
        Recovery_Out -->|JSON String| Prompt_4
        Prompt_4 --> Summary_Agent[Executive Summary Agent]
        Summary_Agent --> Final_Output[ExecutiveSummaryResult]
    end
```

---

## 4. Security & RBAC Boundary
Illustrates the authentication and authorization (RBAC) boundaries protecting the system's endpoints and tools.

```mermaid
graph TD
    User([User Request]) --> JWT_Check{JWT Valid?}
    
    JWT_Check -->|No| Reject_Unauthenticated[401 Unauthorized]
    
    JWT_Check -->|Yes| Extract_Role[Extract User Role]
    
    Extract_Role --> Endpoint_Check{Endpoint: /api/approvals/billing?}
    
    Endpoint_Check -->|Yes| CFO_Check{Role == 'CFO' or 'RevOps_Manager'?}
    CFO_Check -->|No| Reject_Forbidden[403 Forbidden]
    CFO_Check -->|Yes| Execute_Billing[Apply Stripe Adjustment]
    
    Endpoint_Check -->|No| Other_Endpoint{Endpoint: /api/approvals/email?}
    Other_Endpoint -->|Yes| Sales_Check{Role == 'Sales_Rep' or 'RevOps_Manager'?}
    Sales_Check -->|No| Reject_Forbidden
    Sales_Check -->|Yes| Execute_Email[Send Gmail Follow-up]
```
