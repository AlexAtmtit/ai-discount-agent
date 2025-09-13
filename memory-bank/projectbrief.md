# AI Discount Agent - Home Assignment Implementation

## Project Overview
This project implements an AI-powered discount code distribution system for influencer marketing campaigns across Instagram, TikTok, and WhatsApp. The system automatically processes incoming DMs, identifies which creator referred the user, and issues the appropriate discount code.

## Core Mission
Build a production-ready backend that handles natural language processing of user messages, creator detection with fallback strategies, and secure discount code issuance with proper business rule enforcement.

## Assignment Requirements (Step-by-Step)
1. **System Design & Architecture**: Create high-level diagrams and tooling justification for multi-platform DM processing
2. **AI Agent Function**: Implement `run_agent_on_message()` that takes a string message and returns reply + database row JSON
3. **Database Schema**: Design PostgreSQL-compatible table schema for interaction logging
4. **Bonus Features**: Multi-platform support documentation, CRM enrichment simulation, analytics analytics endpoint

## Success Criteria
- Clean, well-commented production-oriented Python code
- Complete coverage of core functionality with all bonus features
- Demonstration of AI engineering best practices and architectural decisions
- Bias for action: working implementation that shows clear understanding of the problem

## Project Scope
- Single-user demo implementation (no real production deployment required)
- In-memory storage for demo purposes (production would use PostgreSQL)
- Mocked LLM calls for reliability without API dependencies
- Complete end-to-end message processing pipeline

## Deliverables
- Working Python implementation with test coverage
- Comprehensive documentation and architecture diagrams
- Clean codebase following Python best practices
- Functional demo showing all required features working
