<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as d3 from 'd3';
  import type { Entity, Relationship } from './types';

  export let entities: Entity[] = [];
  export let relationships: Relationship[] = [];
  export let width: number = 800;
  export let height: number = 600;
  export let sessionContext: string[] = [];

  let svgElement: SVGSVGElement;
  let tooltipElement: HTMLDivElement;
  let simulation: d3.Simulation<Entity, Relationship> | null = null;

  // Color scheme for different entity types
  const entityColors: Record<string, string> = {
    organism: '#e74c3c',
    protein: '#3498db',
    gene: '#9b59b6',
    condition: '#f39c12',
    method: '#2ecc71',
    location: '#1abc9c',
    concept: '#34495e'
  };

  // Relationship type colors
  const relationshipColors: Record<string, string> = {
    affects: '#e74c3c',
    inhibits: '#c0392b',
    promotes: '#27ae60',
    regulates: '#8e44ad',
    expressed_in: '#f39c12'
  };

  onMount(() => {
    if (entities.length > 0) {
      initializeGraph();
    }
  });

  onDestroy(() => {
    if (simulation) {
      simulation.stop();
    }
  });

  function initializeGraph() {
    if (!svgElement) return;

    // Clear previous content
    d3.select(svgElement).selectAll('*').remove();

    // Create SVG
    const svg = d3.select(svgElement)
      .attr('width', width)
      .attr('height', height)
      .style('background-color', '#f8f9fa');

    // Create tooltip
    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'kg-tooltip')
      .style('position', 'absolute')
      .style('background', 'rgba(0, 0, 0, 0.8)')
      .style('color', 'white')
      .style('padding', '8px 12px')
      .style('border-radius', '4px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('opacity', 0)
      .style('z-index', 1000);

    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        container.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Create container for zoomable content
    const container = svg.append('g');

    // Create arrow markers for directed relationships
    const defs = svg.append('defs');
    
    Object.entries(relationshipColors).forEach(([type, color]) => {
      defs.append('marker')
        .attr('id', `arrow-${type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 25)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', color);
    });

    // Create force simulation
    simulation = d3.forceSimulation(entities)
      .force('link', d3.forceLink(relationships)
        .id((d: Entity) => d.id)
        .distance(100)
        .strength(0.1)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(20));

    // Create links
    const links = container.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(relationships)
      .enter().append('line')
      .attr('stroke', (d: Relationship) => relationshipColors[d.relation_type] || '#999')
      .attr('stroke-width', (d: Relationship) => Math.max(1, d.strength * 3))
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', (d: Relationship) => `url(#arrow-${d.relation_type})`);

    // Create nodes
    const nodes = container.append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(entities)
      .enter().append('circle')
      .attr('r', (d: Entity) => Math.max(8, Math.min(25, Math.sqrt(d.frequency) * 3)))
      .attr('fill', (d: Entity) => entityColors[d.type] || '#95a5a6')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .call(d3.drag<SVGCircleElement, Entity>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
      )
      .on('mouseover', function(event, d: Entity) {
        tooltip.transition()
          .duration(200)
          .style('opacity', 0.9);
        
        tooltip.html(`
          <div><strong>${d.name}</strong></div>
          <div>Type: ${d.type}</div>
          <div>Frequency: ${d.frequency}</div>
        `)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseout', function() {
        tooltip.transition()
          .duration(500)
          .style('opacity', 0);
      });

    // Add labels
    const labels = container.append('g')
      .attr('class', 'labels')
      .selectAll('text')
      .data(entities)
      .enter().append('text')
      .text((d: Entity) => d.name)
      .attr('font-size', '10px')
      .attr('font-family', 'Arial, sans-serif')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .style('pointer-events', 'none')
      .style('user-select', 'none');

    // Update positions on simulation tick
    simulation.on('tick', () => {
      links
        .attr('x1', (d: Relationship) => {
          const source = d.source as Entity;
          return source.x || 0;
        })
        .attr('y1', (d: Relationship) => {
          const source = d.source as Entity;
          return source.y || 0;
        })
        .attr('x2', (d: Relationship) => {
          const target = d.target as Entity;
          return target.x || 0;
        })
        .attr('y2', (d: Relationship) => {
          const target = d.target as Entity;
          return target.y || 0;
        });

      nodes
        .attr('cx', (d: Entity) => d.x || 0)
        .attr('cy', (d: Entity) => d.y || 0);

      labels
        .attr('x', (d: Entity) => d.x || 0)
        .attr('y', (d: Entity) => d.y || 0);
    });

    // Drag functions
    function dragstarted(event: any, d: Entity) {
      if (!event.active && simulation) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event: any, d: Entity) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event: any, d: Entity) {
      if (!event.active && simulation) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }
  }

  // Reactive statement to reinitialize when data changes
  $: if (entities.length > 0) {
    initializeGraph();
  }
</script>

<div class="knowledge-graph-container">
  <svg bind:this={svgElement} class="knowledge-graph-svg"></svg>
</div>

<style>
  .knowledge-graph-container {
    width: 100%;
    height: 100%;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
  }

  .knowledge-graph-svg {
    width: 100%;
    height: 100%;
    display: block;
  }

  :global(.kg-tooltip) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
</style>
