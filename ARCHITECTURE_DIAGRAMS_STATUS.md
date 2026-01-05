# Architecture Diagrams Status

## Current Status: **UP TO DATE** ✅

The PlantUML architecture diagram (`architecture.puml`) has been **updated** to reflect the current system implementation (January 2025).

### What the Diagram Shows

The updated `architecture.puml` accurately represents:

1. ✅ **All 7 Official Agents**
   - Sourcing Signal (DTP-01)
   - Supplier Scoring (DTP-02)
   - RFx Draft (DTP-03)
   - Negotiation Support (DTP-04)
   - Contract Support (DTP-05)
   - Implementation (DTP-06)

2. ✅ **Hybrid Intent Classification**
   - Rule-based classification (fast, 80-90% of cases)
   - LLM fallback for ambiguous cases
   - Two-level classification (UserGoal + WorkType)
   - Context-aware routing

3. ✅ **Task Execution Hierarchy**
   - Rules → Retrieval → Analytics → LLM
   - All agents follow same execution order
   - Shows deterministic-first approach

4. ✅ **Artifact System**
   - ArtifactPack creation and structure
   - Execution metadata tracking
   - Verification status and grounding references
   - Full audit trail

5. ✅ **Correct Workflow**
   - Chat Service → Router → Agents (direct flow)
   - Supervisor (State Manager) as only state writer
   - Human-in-the-loop checkpoints

6. ✅ **Data Layer**
   - SQLite: Cases, ArtifactPacks, Execution Metadata, Structured Data
   - ChromaDB: Document embeddings
   - File storage: Uploaded documents

### How to Use

**Render the Diagram**:
- VS Code/Cursor: Install PlantUML extension, press `Alt+D` to preview
- Online: Copy to http://www.plantuml.com/plantuml
- Command line: `plantuml architecture.puml`

**Diagram Highlights**:
- Color-coded components by type
- Detailed flow arrows showing data movement
- Governance notes explaining key rules
- Legend for component types

### Current Accurate Architecture Documentation

For accurate, up-to-date architecture information, see:
- **[SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md)** - Complete technical documentation with architecture overview
- **[README.md](README.md)** - Quick start and high-level overview

