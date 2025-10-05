# Knowledge Graph for Space Biology Research

This implementation provides a comprehensive knowledge graph system that extracts entities, relationships, and concepts from space biology research articles and visualizes them in an interactive graph.

## Features

### 🧠 Knowledge Graph Extraction
- **Entity Recognition**: Automatically identifies organisms, proteins, genes, conditions, methods, and locations
- **Relationship Detection**: Extracts semantic relationships like "affects", "inhibits", "promotes", "regulates"
- **Frequency Analysis**: Tracks how often entities appear across documents
- **Strength Calculation**: Measures relationship strength based on co-occurrence

### 📊 Interactive Visualization
- **D3.js Force-Directed Graph**: Interactive network visualization with zoom and pan
- **Entity Types**: Color-coded nodes for different entity types
- **Relationship Types**: Different colored edges for relationship types
- **Tooltips**: Hover information showing entity details
- **Drag & Drop**: Interactive node positioning

### 🌐 Web Interface
- **Dedicated Graph Page**: Full-screen knowledge graph visualization
- **Chat Integration**: Knowledge graph preview in chat interface
- **Real-time Updates**: Refresh button to rebuild graph from latest data
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Elasticsearch │    │   Knowledge      │    │   Frontend      │
│   (Articles)    │───▶│   Graph API      │───▶│   (SvelteKit)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   D3.js          │
                       │   Visualization  │
                       └──────────────────┘
```

## File Structure

```
rag/
├── knowledge_graph.py          # Core knowledge graph extraction logic
├── test_knowledge_graph.py    # Test script for knowledge graph
└── ...

web/
├── src/
│   ├── routes/
│   │   ├── api/
│   │   │   └── knowledge-graph/
│   │   │       └── +server.ts     # API endpoint for graph data
│   │   └── knowledge-graph/
│   │       └── +page.svelte       # Full graph visualization page
│   └── lib/
│       ├── components/
│       │   ├── KnowledgeGraph.svelte        # D3.js graph component
│       │   └── KnowledgeGraphPreview.svelte # Compact preview
│       └── types.ts                        # TypeScript interfaces
└── ...
```

## Usage

### 1. Backend Knowledge Graph Extraction

```python
# Test the knowledge graph extraction
python rag/test_knowledge_graph.py
```

### 2. Frontend Visualization

1. **Start the development server**:
   ```bash
   cd web
   pnpm dev
   ```

2. **Access the knowledge graph**:
   - Navigate to `/knowledge-graph` for the full visualization
   - Or use the preview in the chat interface at `/`

### 3. API Endpoints

- `GET /api/knowledge-graph` - Returns complete knowledge graph data
- `POST /api/chat` - Existing chat endpoint (unchanged)

## Entity Types

| Type | Color | Examples |
|------|-------|----------|
| Organism | Red | mice, humans, zebrafish |
| Protein | Blue | actin, myosin, collagen |
| Gene | Purple | CDKN1a, p21, RUNX2 |
| Condition | Orange | microgravity, bone loss |
| Method | Green | RT-PCR, Western blot |
| Location | Teal | ISS, bone, muscle |

## Relationship Types

| Type | Color | Examples |
|------|-------|----------|
| Affects | Red | "microgravity affects bone density" |
| Inhibits | Dark Red | "radiation inhibits cell growth" |
| Promotes | Green | "exercise promotes muscle growth" |
| Regulates | Purple | "gene regulates protein expression" |
| Expressed In | Orange | "protein expressed in muscle tissue" |

## Configuration

### Environment Variables

```bash
# Elasticsearch connection
ELASTIC_URL=https://your-elasticsearch-url
ELASTIC_API_KEY=your-api-key
ELASTIC_INDEX=spacehacks
ELASTIC_MODEL_ID=.multilingual-e5-small-elasticsearch
```

### Customization

You can customize the knowledge graph by modifying:

1. **Entity Patterns** (`knowledge_graph.py`):
   ```python
   self.entity_patterns = {
       'organism': [r'\b(mice?|rats?|humans?)\b'],
       # Add your own patterns
   }
   ```

2. **Relationship Patterns** (`knowledge_graph.py`):
   ```python
   self.relationship_patterns = {
       'affects': [r'(\w+)\s+(affects?|influences?)\s+(\w+)'],
       # Add your own patterns
   }
   ```

3. **Visualization Colors** (`KnowledgeGraph.svelte`):
   ```typescript
   const entityColors = {
       organism: '#e74c3c',
       // Customize colors
   };
   ```

## Performance Considerations

- **Document Limit**: Default max 200 documents for graph building
- **Entity Filtering**: Only entities mentioned 2+ times are included
- **Relationship Filtering**: Only relationships with strength ≥ 0.5 are shown
- **Caching**: Consider implementing caching for large datasets

## Future Enhancements

- [ ] **LLM-based Extraction**: Use language models for better entity/relationship extraction
- [ ] **Temporal Analysis**: Track how relationships change over time
- [ ] **Graph Analytics**: Add centrality measures, clustering, path finding
- [ ] **Export Options**: Export graph as PNG, SVG, or GraphML
- [ ] **Search Integration**: Search within the knowledge graph
- [ ] **Real-time Updates**: Live updates as new articles are added

## Troubleshooting

### Common Issues

1. **No entities found**: Check if documents exist in Elasticsearch index
2. **Empty graph**: Verify entity patterns match your document content
3. **Performance issues**: Reduce max_docs parameter or implement pagination
4. **Visualization not loading**: Check browser console for D3.js errors

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Dependencies

### Backend
- `elasticsearch` - Elasticsearch client
- `python-dotenv` - Environment variable management
- `pandas` - Data processing (optional)

### Frontend
- `d3` - Data visualization library
- `@types/d3` - TypeScript definitions
- `svelte` - Frontend framework
- `tailwindcss` - CSS framework
