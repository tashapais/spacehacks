<script lang="ts">
	import '../app.css';
	import ChatContainer from '$lib/components/ChatContainer.svelte';
	import nasaicon from '$lib/assets/nasa-logo.svg';
</script>

<main class="flex h-screen flex-col">
	<!-- Top navigation / branding -->
	<header class="flex items-center justify-between border-b bg-white px-6 py-3 shadow-sm">
		<div class="flex items-center gap-2">
			<img src={nasaicon} alt="NASA" class="text-md fond-bold h-6 text-black" />
			<span class="text-sm font-semibold text-gray-700">Bio Studies AI Dashboard</span>
		</div>
		<nav class="text-sm text-gray-500">
			<a href="/" class="hover:text-blue-600">Chat</a>
			<a href="/knowledge-graph" class="hover:text-blue-600 ml-4">Knowledge Graph</a>
		</nav>
	</header>

	<!-- Main Chat Content -->
	<ChatContainer />
</main>
