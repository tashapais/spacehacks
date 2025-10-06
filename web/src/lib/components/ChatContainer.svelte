<script lang="ts">
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';
	import { EXPERTISE_CONFIGS, DEFAULT_EXPERTISE, type ExpertiseLevel } from '$lib/expertise';
	import { highlightedSourceUrls } from '$lib/stores/highlightedSources';

	type Citation = {
		id: string;
		title: string;
		url?: string;
		snippet?: string;
	};

	type Message = {
		id: string;
		role: 'user' | 'assistant';
		text: string;
		isLoading?: boolean;
		citations?: Citation[];
	};

	let messageCounter = 0;
	let selectedExpertise: ExpertiseLevel = DEFAULT_EXPERTISE;

	const makeId = (prefix: string) => `${prefix}-${messageCounter++}`;

	let messages: Message[] = [
		{
			id: makeId('assistant'),
			role: 'assistant',
			text: 'Welcome to SPOK the NASA Bio Studies AI assistant! Use the drop down to select your expertise level, then ask me about space biology discoveries. See the top 5 most relevant sources highlighted as gold nodes in the knowledge web above.'
		}
	];

	const handleSend = async (text: string) => {
		if (!text.trim()) return;

		const userMessage: Message = { id: makeId('user'), role: 'user', text };
		const history = [...messages, userMessage];
		const placeholder: Message = {
			id: makeId('assistant'),
			role: 'assistant',
			text: 'Analyzing your question…',
			isLoading: true
		};

		messages = [...history, placeholder];

		try {
			const response = await fetch('/api/chat', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					messages: history.map(({ role, text }) => ({ role, text })),
					expertise: selectedExpertise
				})
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.error ?? 'Chat request failed');
			}

			const reader = response.body?.getReader();
			const decoder = new TextDecoder();
		let accumulatedText = '';
		let citations: Citation[] | undefined;

		while (true) {
			const { done, value } = await reader!.read();
			if (done) break;

			const chunk = decoder.decode(value);
			const lines = chunk.split('\n');

			for (const line of lines) {
				if (line.startsWith('data: ')) {
					const data = line.slice(6);
					if (!data.trim()) continue;

					try {
						const parsed = JSON.parse(data);

						if (parsed.type === 'citations') {
							citations = parsed.citations;
							// Update message with citations
							messages = messages.map((msg) =>
								msg.id === placeholder.id ? { ...msg, citations } : msg
							);
							// Update highlighted sources on the graph
							if (citations && citations.length > 0) {
								const urls = citations.map((c: Citation) => c.url).filter(Boolean) as string[];
								highlightedSourceUrls.set(urls);
							}
						} else if (parsed.type === 'chunk') {
							accumulatedText += parsed.content;
							// Update message with accumulated text
							messages = messages.map((msg) =>
								msg.id === placeholder.id
									? { ...msg, text: accumulatedText, isLoading: false }
									: msg
							);
						} else if (parsed.type === 'done') {
							// Stream completed successfully
							break;
						} else if (parsed.type === 'error') {
							throw new Error(parsed.error);
						}
					} catch (e) {
						console.warn('Failed to parse SSE data:', data);
						continue;
					}
				}
			}
		}
	} catch (error) {
		console.error('Chat error', error);
		messages = [
			...history,
			{
				id: placeholder.id,
				role: 'assistant',
				text: 'I ran into an issue retrieving that answer. Please try again later.'
			}
		];
	}
};
</script>

<div class="flex h-screen flex-col bg-gray-50">
	<div class="border-b border-gray-200 bg-white px-6 py-3">
		<div class="flex items-center gap-3">
			<label for="expertise" class="text-sm font-semibold text-gray-600">Expertise Level:</label>
			<select
				id="expertise"
				bind:value={selectedExpertise}
				class="select-bordered select w-auto max-w-xs border-gray-300 bg-white select-sm text-gray-800 focus:border-blue-500 focus:outline-none"
			>
				{#each Object.values(EXPERTISE_CONFIGS) as config}
					<option value={config.id} title={config.description}>
						{config.name}
					</option>
				{/each}
			</select>
			<span class="hidden text-xs text-gray-500 italic sm:inline">
				{EXPERTISE_CONFIGS[selectedExpertise].description}
			</span>
		</div>
	</div>

	<div class="flex-1 space-y-2 overflow-y-auto px-6 py-4" style="scroll-behavior: smooth;">
		{#each messages as message (message.id)}
			<ChatMessage {message} />
		{/each}
	</div>

	<ChatInput onSend={handleSend} />
</div>
