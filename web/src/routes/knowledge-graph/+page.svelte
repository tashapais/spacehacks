<script lang="ts">
  import { onMount } from 'svelte';
  import '../../app.css';
  import KnowledgeGraph from '$lib/components/KnowledgeGraph.svelte';
  import type { KnowledgeGraphData } from '$lib/types';
  import nasaicon from '$lib/assets/nasa-logo.svg';

  let knowledgeGraphData: KnowledgeGraphData | null = null;
  let loading = true;
  let error: string | null = null;
  let sessionContext: string[] = [];

  // Get session context from URL params or default to empty
  onMount(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const context = urlParams.get('context');
    if (context) {
      sessionContext = context.split(',').map(s => s.trim()).filter(s => s.length > 0);
    }
    loadGraphData();
  });

  async function loadGraphData() {
    loading = true;
    error = null;
    try {
      const response = await fetch('/api/knowledge-graph', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sessionContext })
      });
      if (!response.ok) {
        throw new Error(`Failed to load knowledge graph: ${response.status}`);
      }
      
      knowledgeGraphData = await response.json();
      loading = false;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unknown error occurred';
      loading = false;
    }
  }

  function refreshGraph() {
    loadGraphData();
  }
</script>

<svelte:head>
  <title>Knowledge Graph - NASA Bio Studies AI</title>
</svelte:head>

<main class="flex h-screen flex-col">
  <!-- Top navigation / branding -->
  <header class="flex items-center justify-between border-b bg-white px-6 py-3 shadow-sm">
    <div class="flex items-center gap-2">
      <img src={nasaicon} alt="NASA" class="text-md fond-bold h-6 text-black" />
      <span class="text-sm font-semibold text-gray-700">Bio Studies AI - Knowledge Graph</span>
    </div>
    <nav class="flex items-center gap-4 text-sm text-gray-500">
      <a href="/" class="hover:text-blue-600">Chat</a>
      <button 
        on:click={refreshGraph}
        class="hover:text-blue-600 flex items-center gap-1"
        disabled={loading}
      >
        {#if loading}
          <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
          </svg>
        {/if}
        Refresh
      </button>
    </nav>
  </header>

  <div class="flex-1 flex flex-col">
    {#if loading}
      <div class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <svg class="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
          </svg>
          <p class="text-gray-600">Building knowledge graph from research articles...</p>
        </div>
      </div>
    {:else if error}
      <div class="flex-1 flex items-center justify-center">
        <div class="text-center text-red-600">
          <svg class="h-12 w-12 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <p class="text-lg font-medium mb-2">Error loading knowledge graph</p>
          <p class="text-sm">{error}</p>
          <button 
            on:click={refreshGraph}
            class="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Try Again
          </button>
        </div>
      </div>
    {:else if knowledgeGraphData}
      <!-- Summary Stats -->
      <div class="bg-white border-b px-6 py-4">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="text-center">
            <div class="text-2xl font-bold text-blue-600">{knowledgeGraphData.summary.total_entities}</div>
            <div class="text-sm text-gray-600">Entities</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-green-600">{knowledgeGraphData.summary.total_relationships}</div>
            <div class="text-sm text-gray-600">Relationships</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-purple-600">{Object.keys(knowledgeGraphData.summary.entity_types).length}</div>
            <div class="text-sm text-gray-600">Entity Types</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-orange-600">{Object.keys(knowledgeGraphData.summary.relationship_types).length}</div>
            <div class="text-sm text-gray-600">Relation Types</div>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="bg-gray-50 px-6 py-3 border-b">
        <div class="flex flex-wrap gap-4 text-sm">
          <div class="flex items-center gap-2">
            <span class="font-medium text-gray-700">Entity Types:</span>
          </div>
          {#each Object.entries(knowledgeGraphData.summary.entity_types) as [type, count]}
            <div class="flex items-center gap-1">
              <div class="w-3 h-3 rounded-full" style="background-color: {
                type === 'organism' ? '#e74c3c' :
                type === 'protein' ? '#3498db' :
                type === 'gene' ? '#9b59b6' :
                type === 'condition' ? '#f39c12' :
                type === 'method' ? '#2ecc71' :
                type === 'location' ? '#1abc9c' :
                '#34495e'
              }"></div>
              <span class="text-gray-600">{type} ({count})</span>
            </div>
          {/each}
        </div>
      </div>

      <!-- Graph Visualization -->
      <div class="flex-1 p-6">
        <div class="h-full bg-white rounded-lg shadow-sm border">
          <KnowledgeGraph 
            entities={knowledgeGraphData.entities}
            relationships={knowledgeGraphData.relationships}
            width={800}
            height={600}
            {sessionContext}
          />
        </div>
      </div>

      <!-- Top Entities -->
      <div class="bg-gray-50 px-6 py-4 border-t">
        <h3 class="text-sm font-medium text-gray-700 mb-3">Most Frequent Entities</h3>
        <div class="flex flex-wrap gap-2">
          {#each knowledgeGraphData.summary.top_entities.slice(0, 10) as entity}
            <span class="px-2 py-1 bg-white rounded text-xs text-gray-600 border">
              {entity.name} ({entity.frequency})
            </span>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</main>
