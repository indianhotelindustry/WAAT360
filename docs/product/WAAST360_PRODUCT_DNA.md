# WAAST360 Product DNA

## Overview
WAAST360 (Wise Accounting Automation System for Tally) provides an intelligent automation layer over traditional accounting via Tally. 

## DNA Traits
1. **Verifiable Truth:** Every step from document ingestion to Tally posting must be verifiable.
2. **Abstracted AI:** The system must not be permanently tied to one AI provider. AI is treated as an interchangeable engine.
3. **Abstracted Transport:** Tally integrations (JSON, XML, etc.) must be abstracted via a `TallyAdapter`.
4. **Prime-grade Foundation:** Even the Lite version must share the robust, multi-tenant capable architecture envisioned for Prime. Throwaway logic is forbidden.
