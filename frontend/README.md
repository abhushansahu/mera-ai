# Mera AI Frontend

Modern UI for Mera AI with visualizations for the Research → Plan → Implement workflow.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Set up environment variables:
```bash
cp .env.local.example .env.local
# Edit .env.local and set NEXT_PUBLIC_API_URL to your backend URL
```

3. Run development server:
```bash
npm run dev
```

## Features

- **Chat Interface**: Clean chat UI with support for Research, Plan, and Answer messages
- **RPI Workflow Visualization**: Real-time visualization of the Research → Plan → Implement stages
- **Agent Flow**: Visual representation of agent interactions
- **Spaces Management**: Dashboard for managing multiple project spaces
- **Memory Graph**: Interactive knowledge graph visualization
- **Context Panel**: Sidebar showing current space, workflow state, and metadata
- **Real-time Updates**: Server-Sent Events (SSE) for live workflow updates

## Tech Stack

- Next.js 14+
- TypeScript
- Tailwind CSS
- Zustand (state management)
- React Flow (workflow diagrams)
- Cytoscape.js (graph visualization)
- Recharts (charts)
