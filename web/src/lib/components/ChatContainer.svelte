<script lang="ts">
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';

	interface Message {
		role: 'user' | 'assistant';
		text: string;
	}

	let messages: Message[] = [
		{
			role: 'assistant',
			text: 'Welcome to the NASA Bio Studies AI assistant! Ask me about space biology discoveries.'
		}
	];

	const handleSend = (text: string) => {
		messages = [...messages, { role: 'user', text }];

		// Placeholder assistant response (mock for now)
		setTimeout(() => {
			messages = [
				...messages,
				{ role: 'assistant', text: `You asked about "${text}" — let's explore that soon.` }
			];
		}, 600);
	};
</script>

<div class="flex h-screen flex-col bg-gray-50">
	<div class="flex-1 space-y-2 overflow-y-auto px-6 py-4" style="scroll-behavior: smooth;">
		{#each messages as message (message.text)}
			<ChatMessage {message} />
		{/each}
	</div>

	<ChatInput onSend={handleSend} />
</div>
