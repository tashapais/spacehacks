<script lang="ts">
	import '../app.css';
	import ChatContainer from '$lib/components/ChatContainer.svelte';
	import KnowledgeGraph from '$lib/components/KnowledgeGraph.svelte';
	import nasaicon from '$lib/assets/nasa-logo.svg';
</script>

<main class="flex h-screen flex-col">
	<!-- Top navigation / branding -->
	<header class="flex items-center justify-between border-b bg-white px-6 py-3 shadow-sm">
		<div class="flex items-center gap-3">
			<img src={nasaicon} alt="NASA" class="h-6" />
			<span class="text-xl font-extrabold text-gray-900">SPOK</span>
			<span class="text-sm text-gray-600">Bio Studies AI Dashboard</span>
		</div>
		<nav class="flex gap-4 text-sm text-gray-500">
			<a href="/" class="hover:text-blue-600">Explore</a>
		</nav>
	</header>

	<!-- Knowledge Graph -->
	<div class="h-[600px] border-b">
		<KnowledgeGraph />
	</div>

	<!-- Main Chat Content -->
	<ChatContainer />
</main>
