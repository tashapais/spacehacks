<script lang="ts">
	import ChatContainer from '$lib/components/ChatContainer.svelte';
</script>

<main class="flex h-screen flex-col">
	<!-- Top navigation / branding -->
	<header class="flex items-center justify-between border-b bg-white px-6 py-3 shadow-sm">
		<div class="flex items-center gap-2">
			<img src="/nasa-logo.svg" alt="NASA" class="h-6" />
			<span class="text-sm font-semibold text-gray-700">Bio Studies AI Dashboard</span>
		</div>
		<nav class="text-sm text-gray-500">
			<a href="#" class="hover:text-blue-600">Explore</a>
		</nav>
	</header>

	<!-- Main Chat Content -->
	<ChatContainer />
</main>
