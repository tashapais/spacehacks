<script lang="ts">
	export let query = '';
	export let onSend: (text: string) => void;

	let input = query;

	const submit = (e: Event) => {
		e.preventDefault();
		if (!input.trim()) return;
		onSend(input);
		input = '';
	};
</script>

<form
	on:submit={submit}
	class="sticky bottom-0 flex items-center gap-2 border-t border-gray-200 bg-white p-3"
>
	<input
		type="text"
		bind:value={input}
		placeholder="Ask about space biology..."
		class="flex-1 rounded-full border border-gray-300 px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
	/>
	<button
		type="submit"
		class="rounded-full bg-blue-600 px-4 py-2 font-medium text-white transition duration-150 hover:bg-blue-700"
	>
		Ask
	</button>
</form>
