<script lang="ts">
  import { onMount } from 'svelte';
  import type { KnowledgeGraphData } from '$lib/types';

  export let compact: boolean = true;
  export let sessionContext: string[] = [];

  let kgData: KnowledgeGraphData | null = null;
  let loading = false;

  async function loadGraphData() {
    loading = true;
    try {
      const response = await fetch('/api/knowledge-graph', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sessionContext })
      });
      if (response.ok) {
        kgData = await response.json();
      }
    } catch (error) {
      console.error('Failed to load knowledge graph data:', error);
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (sessionContext.length > 0) {
      loadGraphData();
    }
  });

  // Reactive statement to reload when session context changes
  $: if (sessionContext.length > 0) {
    loadGraphData();
  }
</script>

{#if compact}
  <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-sm font-medium text-blue-900">Knowledge Graph</h3>
        <p class="text-xs text-blue-700 mt-1">
          {#if sessionContext.length === 0}
            Click to explore general knowledge graph
          {:else if loading}
            Loading graph data...
          {:else if kgData}
            {kgData.summary.total_entities} entities, {kgData.summary.total_relationships} relationships
          {:else}
            Explore connections between research concepts
          {/if}
        </p>
      </div>
      <a 
        href="/knowledge-graph{sessionContext.length > 0 ? '?context=' + encodeURIComponent(sessionContext.join(',')) : ''}" 
        class="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 transition-colors"
      >
        View Graph
      </a>
    </div>
  </div>
{:else}
  <div class="bg-white border rounded-lg p-6">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-gray-900">Knowledge Graph Overview</h2>
      <a 
        href="/knowledge-graph{sessionContext.length > 0 ? '?context=' + encodeURIComponent(sessionContext.join(',')) : ''}" 
        class="text-sm bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition-colors"
      >
        Explore Full Graph
      </a>
    </div>
    
    {#if loading}
      <div class="text-center py-8">
        <div class="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-2"></div>
        <p class="text-gray-600">Loading knowledge graph...</p>
      </div>
    {:else if kgData}
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="text-center p-3 bg-blue-50 rounded">
          <div class="text-2xl font-bold text-blue-600">{kgData.summary.total_entities}</div>
          <div class="text-sm text-gray-600">Entities</div>
        </div>
        <div class="text-center p-3 bg-green-50 rounded">
          <div class="text-2xl font-bold text-green-600">{kgData.summary.total_relationships}</div>
          <div class="text-sm text-gray-600">Relationships</div>
        </div>
        <div class="text-center p-3 bg-purple-50 rounded">
          <div class="text-2xl font-bold text-purple-600">{Object.keys(kgData.summary.entity_types).length}</div>
          <div class="text-sm text-gray-600">Entity Types</div>
        </div>
        <div class="text-center p-3 bg-orange-50 rounded">
          <div class="text-2xl font-bold text-orange-600">{Object.keys(kgData.summary.relationship_types).length}</div>
          <div class="text-sm text-gray-600">Relation Types</div>
        </div>
      </div>

      <div class="mb-4">
        <h3 class="text-sm font-medium text-gray-700 mb-2">Top Entities</h3>
        <div class="flex flex-wrap gap-2">
          {#each kgData.summary.top_entities.slice(0, 8) as entity}
            <span class="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600">
              {entity.name} ({entity.frequency})
            </span>
          {/each}
        </div>
      </div>

      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-2">Entity Types</h3>
        <div class="flex flex-wrap gap-2">
          {#each Object.entries(kgData.summary.entity_types) as [type, count]}
            <div class="flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-xs">
              <div class="w-2 h-2 rounded-full" style="background-color: {
                type === 'organism' ? '#e74c3c' :
                type === 'protein' ? '#3498db' :
                type === 'gene' ? '#9b59b6' :
                type === 'condition' ? '#f39c12' :
                type === 'method' ? '#2ecc71' :
                type === 'location' ? '#1abc9c' :
                '#34495e'
              }"></div>
              <span>{type} ({count})</span>
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <div class="text-center py-8 text-gray-500">
        <p>Unable to load knowledge graph data</p>
        <button 
          on:click={loadGraphData}
          class="mt-2 text-sm text-blue-600 hover:text-blue-700"
        >
          Try again
        </button>
      </div>
    {/if}
  </div>
{/if}
