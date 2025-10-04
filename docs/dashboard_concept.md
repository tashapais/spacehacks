# Dashboard Concept

## Experience Goals
- Rapidly surface studies relevant to a user's mission profile, organism, or scientific theme.
- Reveal relationships via an explorable knowledge graph with explainable AI summaries.
- Provide persona toggles that tune narrative tone, metrics, and recommended actions.
- Maintain provenance through inline citation markers and hover-to-preview evidence.

## Key Views
1. **Landing Overview**
   - Mission timeline bands showing publication density by year and mission class.
   - Highlight cards summarizing latest insights, knowledge gaps, and newly ingested data.
2. **Graph Explorer**
   - Force-directed or radial graph anchored on selected node (publication, organism, mission).
   - Side pane shows AI summary, citations list, imagery carousel, and quick actions (open OSDR, Task Book).
   - Filters for persona, confidence threshold, temporal range, environment, organism taxonomy.
3. **Insight Workspace**
   - Query builder enabling natural-language or faceted search (e.g., "microgravity plant stress 2015-2020").
   - Result grid with card previews, excerpt highlights, and aggregated metrics (consensus score, funding lineage).
   - Export options (PDF brief, CSV of references, mission planning packet).
4. **Curation Deck**
   - Manual annotation queue for scientists to validate entities, relationships, and AI summaries.
   - Feedback loop to retrain extraction models.

## Component Architecture
- **Frontend**: React + Vite with TypeScript. Visualization via D3/Visx for graph, ECharts/Observable Plot for timelines.
- **State Management**: Zustand or Redux Toolkit for global persona + filter state.
- **Design System**: Themed components with NASA branding cues (dark background, accent blue/orange).

## API Contract (FastAPI / GraphQL hybrid)
- `GET /api/v1/nodes/{id}`: Returns node metadata, neighbors, embeddings, summary cache.
- `POST /api/v1/summaries`: Accepts persona + node ids, returns SummaryResponse payload.
- `POST /api/v1/search`: Semantic + keyword search across publications and nodes.
- `GET /api/v1/insights/gaps`: Aggregated knowledge gap analytics (e.g., low coverage organisms).

GraphQL layer provides flexible queries:
```graphql
query NodeContext($id: ID!, $persona: Persona!) {
  node(id: $id) {
    id
    label
    properties
    neighbors(filter: {type: "Organism"}) {
      id
      label
    }
    summary(persona: $persona) {
      summaryText
      citations {
        publicationId
        sentence
      }
      imageSuggestions
    }
  }
}
```

## Persona Toggle Behavior
- Switching persona updates summary prompt, key metrics, recommended actions, and color-coded badges.
- Summaries persist per persona to avoid recomputation where cached.

## Imagery Integration
- Call NASA Image and Video Library API with query derived from node context (mission, organism).
- Cache thumbnails and captions; show credit metadata and download links.

## Roadmap for Frontend Build
1. Scaffold Vite React project under `web/` with TypeScript and NASA-styled theming.
2. Implement Graph Explorer view with mock API responses from `scripts/bootstrap_demo.py` output.
3. Integrate persona toggle; render summary text with citation markers linking to references modal.
4. Add search bar with semantic suggestions backed by API endpoints.
5. Iterate on performance, accessibility, and responsive layouts.
