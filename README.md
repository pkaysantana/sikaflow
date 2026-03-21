# Sikaflow

Sikaflow is a decentralized agent orchestration and routing system. It enables intelligent task allocation, policy-driven verification (via Civic), and automated wallet execution on Solana.

## Project Structure

```text
sikaflow/
  README.md
  .env.example
  docs/
    architecture.md          # System design and workflows
    demo-script.md           # Script for demonstration
    checkpoint-notes.md      # Development progress and milestones
  apps/
    web/                     # Frontend interface
  services/
    agent/                   # Planner and orchestration logic
    policy/                  # Civic integration and fallback checks
    wallet/                  # Transaction signing and testnet execution
    routing/                 # Fee comparison and allocation logic
  packages/
    shared/                  # Common types, schemas, and constants
```

## Getting Started

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in the required keys.
3. Explore the `docs/` folder for architectural details.
