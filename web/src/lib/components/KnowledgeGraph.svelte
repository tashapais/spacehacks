<script lang="ts">
	import { onMount } from 'svelte';
	import {
		forceSimulation,
		forceLink,
		forceCollide,
		forceManyBody,
		forceCenter,
		type SimulationNodeDatum,
		type SimulationLinkDatum,
		type Simulation
	} from 'd3-force';
	import { interpolateRainbow } from 'd3-scale-chromatic';
	import { zoom, zoomIdentity, type D3ZoomEvent } from 'd3-zoom';
	import { select } from 'd3-selection';
	import { highlightedSourceUrls } from '$lib/stores/highlightedSources';

	interface GraphNode extends SimulationNodeDatum {
		id: string;
		title: string;
		url?: string;
		authors?: string;
		cluster?: number;
	}

	interface GraphLink extends SimulationLinkDatum<GraphNode> {
		similarity: number;
	}

	interface ClusterInfo {
		id: number;
		label: string;
		count: number;
	}

	let loading = $state(true);
	let error = $state<string | null>(null);
	let nodes = $state<GraphNode[]>([]);
	let links = $state<GraphLink[]>([]);
	let clusterInfo = $state<ClusterInfo[]>([]);

	let width = $state(1200);
	let height = $state(800);
	let hoveredNode = $state<GraphNode | null>(null);

	let svgElement = $state<SVGSVGElement | undefined>(undefined);
	let transform = $state({ x: 0, y: 0, k: 1 });
	let simulation: Simulation<GraphNode, GraphLink> | null = null;
	let highlightedUrls = $state<string[]>([]);

	// Subscribe to highlighted sources
	$effect(() => {
		const unsubscribe = highlightedSourceUrls.subscribe(urls => {
			highlightedUrls = urls;
		});
		return unsubscribe;
	});

	async function fetchGraphData() {
		try {
			loading = true;
			const response = await fetch('/api/graph');
			if (!response.ok) {
				throw new Error('Failed to fetch graph data');
			}
			const data = await response.json();
			nodes = data.nodes;
			links = data.links;
			clusterInfo = data.clusterInfo || [];
			runSimulation();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	}

	function runSimulation() {
		// Stop existing simulation
		if (simulation) {
			simulation.stop();
		}

		simulation = forceSimulation<GraphNode>(nodes)
			.force(
				'link',
				forceLink<GraphNode, GraphLink>(links)
					.id((d) => d.id)
					.distance(100)
					.strength((d) => d.similarity * 0.5)
			)
			.force('charge', forceManyBody().strength(-500))
			.force('collide', forceCollide().radius(12))
			.force('center', forceCenter(width / 2, height / 2));

		// Run simulation synchronously to get final positions
		for (let i = 0; i < 500; ++i) simulation.tick();

		// Update nodes with positions
		nodes = simulation.nodes();
	}

	function setupZoom() {
		if (!svgElement) return;

		const zoomBehavior = zoom<SVGSVGElement, unknown>()
			.scaleExtent([0.1, 4])
			.on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
				transform = event.transform;
			});

		select(svgElement).call(zoomBehavior);

		// Fit graph to view on initial load
		const bounds = getBounds();
		if (bounds) {
			const scale = Math.min(
				width / (bounds.maxX - bounds.minX),
				height / (bounds.maxY - bounds.minY)
			) * 0.9;

			const translateX = width / 2 - (bounds.minX + bounds.maxX) / 2 * scale;
			const translateY = height / 2 - (bounds.minY + bounds.maxY) / 2 * scale;

			select(svgElement).call(
				zoomBehavior.transform,
				zoomIdentity.translate(translateX, translateY).scale(scale)
			);
		}
	}

	function getBounds() {
		if (nodes.length === 0) return null;

		let minX = Infinity, maxX = -Infinity;
		let minY = Infinity, maxY = -Infinity;

		for (const node of nodes) {
			if (node.x !== undefined) {
				minX = Math.min(minX, node.x);
				maxX = Math.max(maxX, node.x);
			}
			if (node.y !== undefined) {
				minY = Math.min(minY, node.y);
				maxY = Math.max(maxY, node.y);
			}
		}

		return { minX, maxX, minY, maxY };
	}

	function getNodeColor(cluster: number | undefined): string {
		if (cluster === undefined) return '#999999';
		// Use d3-scale-chromatic for colors matching the screenshot
		const numClusters = Math.max(...nodes.map((n) => n.cluster ?? 0)) + 1;
		return interpolateRainbow(cluster / numClusters);
	}

	function handleNodeHover(node: GraphNode | null) {
		hoveredNode = node;
	}

	function handleNodeClick(node: GraphNode) {
		if (node.url) {
			window.open(node.url, '_blank');
		}
	}

	function isNodeHighlighted(node: GraphNode): boolean {
		return highlightedUrls.includes(node.url || '');
	}

	onMount(() => {
		fetchGraphData();

		// Handle window resize
		const handleResize = () => {
			const container = document.querySelector('.knowledge-graph-container');
			if (container) {
				width = container.clientWidth - 20;
				height = container.clientHeight - 40;
			}
			if (nodes.length > 0) {
				runSimulation();
				setupZoom();
			}
		};

		handleResize();
		window.addEventListener('resize', handleResize);
		return () => window.removeEventListener('resize', handleResize);
	});

	$effect(() => {
		if (nodes.length > 0 && svgElement) {
			setupZoom();
		}
	});
</script>

<div class="knowledge-graph-container">
	{#if loading}
		<div class="loading">Loading knowledge graph...</div>
	{:else if error}
		<div class="error">Error: {error}</div>
	{:else}
		<div class="graph-wrapper">
			<svg {width} {height} bind:this={svgElement}>
				<g transform="translate({transform.x},{transform.y}) scale({transform.k})">
					<!-- Links -->
					<g class="links">
						{#each links as link}
							<line
								x1={typeof link.source === 'object' ? link.source.x : 0}
								y1={typeof link.source === 'object' ? link.source.y : 0}
								x2={typeof link.target === 'object' ? link.target.x : 0}
								y2={typeof link.target === 'object' ? link.target.y : 0}
								stroke="#cccccc"
								stroke-width={link.similarity * 2}
								stroke-opacity="0.3"
							/>
						{/each}
					</g>

					<!-- Nodes -->
					<g class="nodes">
						{#each nodes as node}
							{#if isNodeHighlighted(node)}
								<!-- Highlighted node with glow effect -->
								<circle
									cx={node.x}
									cy={node.y}
									r={18}
									fill="none"
									stroke="#FFD700"
									stroke-width="6"
									opacity="0.5"
									class="node-glow"
								/>
								<circle
									cx={node.x}
									cy={node.y}
									r={10}
									fill={getNodeColor(node.cluster)}
									stroke="#FFD700"
									stroke-width="4"
									opacity="1"
									onmouseenter={() => handleNodeHover(node)}
									onmouseleave={() => handleNodeHover(null)}
									onclick={() => handleNodeClick(node)}
									class="node-circle highlighted"
								/>
							{:else}
								<circle
									cx={node.x}
									cy={node.y}
									r={hoveredNode?.id === node.id ? 8 : 6}
									fill={getNodeColor(node.cluster)}
									stroke="#ffffff"
									stroke-width="1.5"
									opacity={hoveredNode && hoveredNode.id !== node.id ? 0.3 : 1}
									onmouseenter={() => handleNodeHover(node)}
									onmouseleave={() => handleNodeHover(null)}
									onclick={() => handleNodeClick(node)}
									class="node-circle"
								/>
							{/if}
						{/each}
					</g>
				</g>
			</svg>

			<!-- Tooltip -->
			{#if hoveredNode && hoveredNode.x !== undefined && hoveredNode.y !== undefined}
				<div
					class="tooltip"
					style="left: {(hoveredNode.x * transform.k + transform.x)}px; top: {(hoveredNode.y * transform.k + transform.y)}px;"
				>
					<div class="tooltip-title">{hoveredNode.title}</div>
					{#if hoveredNode.authors}
						<div class="tooltip-authors">{hoveredNode.authors}</div>
					{/if}
					{#if hoveredNode.url}
						<div class="tooltip-url">{hoveredNode.url}</div>
					{/if}
				</div>
			{/if}

			<!-- Legend -->
			<div class="legend">
				<div class="legend-title">Clusters</div>
				{#each clusterInfo as cluster}
					<div class="legend-item">
						<div class="legend-color" style="background-color: {getNodeColor(cluster.id)}"></div>
						<div class="legend-label">{cluster.label}</div>
						<div class="legend-count">({cluster.count})</div>
					</div>
				{/each}
			</div>
		</div>

		<div class="graph-info">
			<p>{nodes.length} articles • {links.length} connections</p>
		</div>
	{/if}
</div>

<style>
	.knowledge-graph-container {
		width: 100%;
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		background: #ffffff;
		padding: 8px;
	}

	.loading,
	.error {
		font-size: 1.2rem;
		color: #666;
	}

	.error {
		color: #ff4444;
	}

	.graph-wrapper {
		position: relative;
		overflow: hidden;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		background: url('/background.png') no-repeat center center;
		background-size: cover;
	}

	svg {
		display: block;
	}

	.node-circle {
		cursor: pointer;
		transition:
			r 0.2s ease,
			opacity 0.2s ease;
	}

	.node-circle:hover {
		filter: brightness(1.2);
	}

	.node-circle.highlighted {
		filter: brightness(1.3);
	}

	.node-glow {
		animation: pulse 2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% {
			opacity: 0.3;
			stroke-width: 6;
		}
		50% {
			opacity: 0.7;
			stroke-width: 8;
		}
	}

	.tooltip {
		position: absolute;
		background: rgba(0, 0, 0, 0.85);
		color: white;
		padding: 8px 12px;
		border-radius: 4px;
		pointer-events: none;
		transform: translate(10px, -50%);
		max-width: 300px;
		font-size: 0.85rem;
		z-index: 100;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
	}

	.tooltip-title {
		font-weight: 600;
		margin-bottom: 4px;
	}

	.tooltip-authors {
		font-size: 0.8rem;
		color: #ddd;
		margin-bottom: 4px;
		font-style: italic;
	}

	.tooltip-url {
		font-size: 0.75rem;
		opacity: 0.8;
		word-break: break-all;
	}

	.graph-info {
		margin-top: 4px;
		font-size: 0.75rem;
		color: #666;
		text-align: center;
	}

	.legend {
		position: absolute;
		top: 16px;
		right: 16px;
		background: rgba(255, 255, 255, 0.95);
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		font-size: 0.85rem;
		max-width: 200px;
		z-index: 10;
	}

	.legend-title {
		font-weight: 600;
		margin-bottom: 8px;
		color: #333;
		font-size: 0.9rem;
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 6px;
	}

	.legend-item:last-child {
		margin-bottom: 0;
	}

	.legend-color {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		flex-shrink: 0;
		border: 1px solid rgba(0, 0, 0, 0.1);
	}

	.legend-label {
		flex: 1;
		font-size: 0.75rem;
		color: #555;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.legend-count {
		font-size: 0.7rem;
		color: #999;
		font-weight: 500;
	}
</style>
